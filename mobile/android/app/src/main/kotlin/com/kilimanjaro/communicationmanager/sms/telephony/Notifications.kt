package com.kilimanjaro.communicationmanager.sms.telephony

import android.Manifest
import android.annotation.SuppressLint
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.ClipData
import android.content.ClipDescription
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.app.Person
import androidx.core.app.RemoteInput
import androidx.core.content.ContextCompat
import androidx.core.content.LocusIdCompat
import androidx.core.content.pm.ShortcutInfoCompat
import androidx.core.content.pm.ShortcutManagerCompat
import androidx.core.graphics.drawable.IconCompat
import com.kilimanjaro.communicationmanager.sms.MainActivity
import com.kilimanjaro.communicationmanager.sms.R
import com.kilimanjaro.communicationmanager.sms.bridge.EventBus
import com.kilimanjaro.communicationmanager.sms.bridge.ProviderMessage
import com.kilimanjaro.communicationmanager.sms.bridge.SendRequest
import com.kilimanjaro.communicationmanager.sms.data.SyncStore
import com.kilimanjaro.communicationmanager.sms.safely
import java.util.UUID

/**
 * Message notifications the way the phone's own Messages app posts them, so they land in Android's "Conversations"
 * section: MessagingStyle with the sender as a Person (name and photo), a long-lived conversation shortcut, a
 * conversation channel (Android 11+; one channel per conversation before that), grouped under a summary, with inline
 * reply, "Mark as read" and "Copy code" for one-time codes. Text is hidden on the lock screen by default (public
 * version: "New message"). Admin replies post a silent "Admin replied" notification.
 */
object Notifications {
    // "monitoring" replaces "sync_service" (IMPORTANCE_MIN hid the notice; a channel's importance cannot be raised later).
    const val SERVICE_CHANNEL = "monitoring"
    private const val MESSAGES_CHANNEL = "messages"
    private const val ADMIN_CHANNEL = "admin_replies"
    private const val GROUP = "cm_messages"
    private const val SUMMARY_ID = 1
    private const val KEY_REPLY = "reply"
    private val otp = Regex("""(?i)(code|otp|pin|verification|msimbo)""")
    private val digits = Regex("""(?<![\d-])(\d{3}[- ]\d{3}|\d{4,8})(?![\d-])""")

    private fun allowed(context: Context) =
        Build.VERSION.SDK_INT < 33 || ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED

    fun ensureServiceChannel(context: Context) {
        // LOW: always listed with its icon in the status bar, never makes a sound. The monitoring disclosure must be visible.
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(SERVICE_CHANNEL, context.getString(R.string.channel_service), NotificationManager.IMPORTANCE_LOW).apply { setShowBadge(false) },
        )
        manager.deleteNotificationChannel("sync_service")
    }

    private fun messagesChannel(context: Context) {
        context.getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(MESSAGES_CHANNEL, context.getString(R.string.channel_messages), NotificationManager.IMPORTANCE_HIGH).apply {
                lockscreenVisibility = NotificationCompat.VISIBILITY_PRIVATE
            },
        )
    }

    /** Android 11+: a conversation channel under "Messages" (per-conversation settings, Conversations section). */
    private fun conversationChannel(context: Context, threadId: Long, title: String, shortcutId: String): String {
        val manager = context.getSystemService(NotificationManager::class.java)
        messagesChannel(context)
        if (Build.VERSION.SDK_INT < 30) {
            val id = "thread_$threadId"
            if (manager.getNotificationChannel(id) == null) {
                manager.createNotificationChannel(NotificationChannel(id, title, NotificationManager.IMPORTANCE_HIGH).apply { lockscreenVisibility = NotificationCompat.VISIBILITY_PRIVATE })
            }
            return id
        }
        val id = "conv_$threadId"
        if (manager.getNotificationChannel(MESSAGES_CHANNEL, shortcutId) == null && manager.getNotificationChannel(id) == null) {
            manager.createNotificationChannel(NotificationChannel(id, title, NotificationManager.IMPORTANCE_HIGH).apply {
                lockscreenVisibility = NotificationCompat.VISIBILITY_PRIVATE
                setConversationId(MESSAGES_CHANNEL, shortcutId)
            })
        }
        return id
    }

    private fun openChat(context: Context, threadId: Long): Intent =
        Intent(Intent.ACTION_VIEW, Uri.parse("cmsms://chat/$threadId")).setClass(context, MainActivity::class.java)

    /** The sender as a Person: contact photo when there is one, otherwise coloured initials (like the list). */
    private fun person(context: Context, address: String, name: String?): Person {
        val photo = Contacts.photo(context, address)?.let { runCatching { Thumbnails.get(context, it, 192) }.getOrNull() }
        val bitmap = photo?.let { BitmapFactory.decodeByteArray(it, 0, it.size) } ?: Avatars.initials(address, name)
        return Person.Builder().setName(name ?: address).setKey(address).setImportant(name != null).setIcon(IconCompat.createWithBitmap(bitmap)).build()
    }

    /** Long-lived shortcut: what makes Android treat the notification as a conversation (and offer it in share). */
    private fun pushShortcut(context: Context, id: String, threadId: Long, title: String, person: Person) = safely("shortcut") {
        ShortcutManagerCompat.pushDynamicShortcut(context, ShortcutInfoCompat.Builder(context, id)
            .setShortLabel(title).setLongLived(true).setPerson(person).setIcon(person.icon ?: IconCompat.createWithResource(context, R.mipmap.ic_launcher_messages))
            .setLocusId(LocusIdCompat(id)).setIntent(openChat(context, threadId)).build())
    }

    fun removeShortcut(context: Context, threadId: Long) = safely("shortcut remove") {
        ShortcutManagerCompat.removeLongLivedShortcuts(context, listOf("thread_$threadId"))
    }

    @SuppressLint("MissingPermission") // POST_NOTIFICATIONS is checked by allowed()
    fun incoming(context: Context, message: ProviderMessage) {
        if (!allowed(context)) return
        val store = SyncStore.get(context)
        if (store?.isMuted(message.threadId) == true) return
        val hide = (store?.setting("hide_on_lock_screen", "1") ?: "1") != "0"
        val address = message.addresses.firstOrNull() ?: return
        val name = Contacts.name(context, address)
        val title = name ?: address
        val sender = person(context, address, name)
        val shortcutId = "thread_${message.threadId}"
        pushShortcut(context, shortcutId, message.threadId, title, sender)
        val channel = conversationChannel(context, message.threadId, title, shortcutId)
        // The unread messages of this conversation, oldest first (the new one is among them).
        val style = NotificationCompat.MessagingStyle(Person.Builder().setName(context.getString(R.string.you)).build())
        val unread = Provider.recentUnread(context, message.threadId, 6).ifEmpty { listOf(message) }
        for (m in unread) style.addMessage(m.body.ifEmpty { context.getString(R.string.picture_message) }, m.date, sender)
        val open = PendingIntent.getActivity(context, message.threadId.toInt(), openChat(context, message.threadId), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val builder = NotificationCompat.Builder(context, channel)
            .setSmallIcon(R.drawable.ic_stat_ocm).setStyle(style).setContentTitle(title).setContentText(message.body)
            .setShortcutId(shortcutId).setLocusId(LocusIdCompat(shortcutId)).setContentIntent(open).setAutoCancel(true)
            .setCategory(NotificationCompat.CATEGORY_MESSAGE).setGroup(GROUP).setNumber(unread.size).setWhen(message.date)
            .setVisibility(if (hide) NotificationCompat.VISIBILITY_PRIVATE else NotificationCompat.VISIBILITY_PUBLIC)
            .setPublicVersion(NotificationCompat.Builder(context, channel).setSmallIcon(R.drawable.ic_stat_ocm).setContentTitle(context.getString(R.string.new_message)).build())
        // Explicit, immutable intents to our own non-exported receiver (the reply one must be mutable for RemoteInput).
        val reply = Intent(context, NotificationActionReceiver::class.java).setAction("reply").setPackage(context.packageName)
            .putExtra("thread", message.threadId).putExtra("address", address).putExtra("sub", message.subscriptionId ?: -1L)
        builder.addAction(NotificationCompat.Action.Builder(0, context.getString(R.string.reply),
            PendingIntent.getBroadcast(context, (message.threadId * 10 + 1).toInt(), reply, PendingIntent.FLAG_MUTABLE or PendingIntent.FLAG_UPDATE_CURRENT))
            .addRemoteInput(RemoteInput.Builder(KEY_REPLY).setLabel(context.getString(R.string.reply)).build()).setAllowGeneratedReplies(false)
            .setSemanticAction(NotificationCompat.Action.SEMANTIC_ACTION_REPLY).setShowsUserInterface(false).build())
        val read = Intent(context, NotificationActionReceiver::class.java).setAction("read").setPackage(context.packageName).putExtra("thread", message.threadId)
        builder.addAction(NotificationCompat.Action.Builder(0, context.getString(R.string.mark_read),
            PendingIntent.getBroadcast(context, (message.threadId * 10 + 2).toInt(), read, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT))
            .setSemanticAction(NotificationCompat.Action.SEMANTIC_ACTION_MARK_AS_READ).setShowsUserInterface(false).build())
        if (otp.containsMatchIn(message.body)) digits.find(message.body)?.value?.replace(Regex("[- ]"), "")?.let { code ->
            val copy = Intent(context, NotificationActionReceiver::class.java).setAction("copy").setPackage(context.packageName).putExtra("code", code).putExtra("thread", message.threadId)
            builder.addAction(0, context.getString(R.string.copy_code), PendingIntent.getBroadcast(context, (message.threadId * 10 + 3).toInt(), copy, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT))
        }
        val manager = NotificationManagerCompat.from(context)
        manager.notify(message.threadId.toInt(), builder.build())
        summary(context, manager)
    }

    /** The group header ("3 new messages"); counts only, so nothing leaks on the lock screen. */
    @SuppressLint("MissingPermission")
    private fun summary(context: Context, manager: NotificationManagerCompat) {
        val count = manager.activeNotifications.count { it.notification.group == GROUP && it.id != SUMMARY_ID }
        if (count < 1) return
        manager.notify(SUMMARY_ID, NotificationCompat.Builder(context, MESSAGES_CHANNEL).setSmallIcon(R.drawable.ic_stat_ocm)
            .setContentTitle(context.resources.getQuantityString(R.plurals.new_messages, count, count)).setGroup(GROUP).setGroupSummary(true)
            .setGroupAlertBehavior(NotificationCompat.GROUP_ALERT_CHILDREN).setAutoCancel(true).setSilent(true)
            .setContentIntent(PendingIntent.getActivity(context, 0, Intent(context, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)).build())
    }

    fun cancel(context: Context, threadId: Long) {
        val manager = NotificationManagerCompat.from(context)
        manager.cancel(threadId.toInt())
        if (manager.activeNotifications.none { it.notification.group == GROUP && it.id != SUMMARY_ID }) manager.cancel(SUMMARY_ID)
    }

    @SuppressLint("MissingPermission") // POST_NOTIFICATIONS is checked by allowed()
    fun adminReplied(context: Context, threadId: Long, address: String) {
        if (!allowed(context)) return
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(ADMIN_CHANNEL, context.getString(R.string.channel_admin), NotificationManager.IMPORTANCE_LOW))
        val title = context.getString(R.string.admin_replied, Contacts.name(context, address) ?: address)
        NotificationManagerCompat.from(context).notify((threadId + 100000).toInt(), NotificationCompat.Builder(context, ADMIN_CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_ocm).setContentTitle(title).setSilent(true).setAutoCancel(true).build())
    }

    @SuppressLint("MissingPermission") // POST_NOTIFICATIONS is checked by allowed()
    fun sendFailed(context: Context, uri: Uri) {
        if (!allowed(context)) return
        val message = Provider.sms(context, uri) ?: return
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel("failed", context.getString(R.string.channel_failed), NotificationManager.IMPORTANCE_DEFAULT))
        NotificationManagerCompat.from(context).notify((message.threadId + 200000).toInt(), NotificationCompat.Builder(context, "failed")
            .setSmallIcon(R.drawable.ic_stat_ocm).setContentTitle(context.getString(R.string.send_failed)).setAutoCancel(true).build())
    }

    @SuppressLint("MissingPermission") // POST_NOTIFICATIONS is checked by allowed()
    fun mmsWaiting(context: Context, from: String?) {
        if (!allowed(context)) return
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel("mms", context.getString(R.string.channel_mms), NotificationManager.IMPORTANCE_DEFAULT))
        NotificationManagerCompat.from(context).notify(300000, NotificationCompat.Builder(context, "mms").setSmallIcon(R.drawable.ic_stat_ocm)
            .setContentTitle(context.getString(R.string.mms_waiting)).setContentText(from ?: "").setAutoCancel(true).build())
    }

    fun handle(context: Context, intent: Intent) {
        val threadId = intent.getLongExtra("thread", -1)
        when (intent.action) {
            "reply" -> {
                val text = RemoteInput.getResultsFromIntent(intent)?.getCharSequence(KEY_REPLY)?.toString()?.trim().orEmpty()
                val address = intent.getStringExtra("address") ?: return
                if (text.isEmpty()) return
                SmsSender.send(context, SendRequest(clientUuid = UUID.randomUUID().toString(), addresses = listOf(address), body = text,
                    subscriptionId = intent.getLongExtra("sub", -1).takeIf { it >= 0 }, deliveryReport = true, attachmentUris = emptyList(), origin = "phone"))
                if (Provider.markThreadRead(context, threadId) > 0) SyncStore.get(context)?.appendEvent("thread.read", org.json.JSONObject().put("thread_id", threadId))
                cancel(context, threadId)
            }
            "read" -> {
                if (Provider.markThreadRead(context, threadId) > 0) SyncStore.get(context)?.appendEvent("thread.read", org.json.JSONObject().put("thread_id", threadId))
                cancel(context, threadId)
            }
            "copy" -> {
                val code = intent.getStringExtra("code") ?: return
                val clip = ClipData.newPlainText("code", code)
                // Android 13+ hides sensitive clips from the clipboard preview and keyboard suggestions.
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    clip.description.extras = android.os.PersistableBundle().apply { putBoolean(ClipDescription.EXTRA_IS_SENSITIVE, true) }
                }
                context.getSystemService(ClipboardManager::class.java).setPrimaryClip(clip)
            }
        }
        EventBus.emit("message_changed", threadId = threadId)
        SyncTrigger.now(context)
    }
}

class NotificationActionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val pending = goAsync()
        Thread { try { safely("notification action") { Notifications.handle(context, intent) } } finally { pending.finish() } }.start()
    }
}
