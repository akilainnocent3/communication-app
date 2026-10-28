package com.kilimanjaro.communicationmanager.sms.telephony

import android.Manifest
import android.annotation.SuppressLint
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.app.RemoteInput
import androidx.core.content.ContextCompat
import com.kilimanjaro.communicationmanager.sms.MainActivity
import com.kilimanjaro.communicationmanager.sms.R
import com.kilimanjaro.communicationmanager.sms.bridge.ProviderMessage
import com.kilimanjaro.communicationmanager.sms.bridge.SendRequest
import com.kilimanjaro.communicationmanager.sms.data.SyncStore
import com.kilimanjaro.communicationmanager.sms.safely
import java.util.UUID

/**
 * Message notifications: one channel per conversation (so staff can tune each in system settings), inline reply
 * (RemoteInput), "Mark as read", "Copy code" for one-time codes, and text hidden on the lock screen by default.
 * Admin replies post a silent "Admin replied" notification.
 */
object Notifications {
    const val SERVICE_CHANNEL = "sync_service"
    private const val ADMIN_CHANNEL = "admin_replies"
    private const val KEY_REPLY = "reply"
    private val otp = Regex("""(?i)(code|otp|pin|verification|msimbo)""")
    private val digits = Regex("""(?<![\d-])(\d{3}[- ]\d{3}|\d{4,8})(?![\d-])""")

    private fun allowed(context: Context) =
        android.os.Build.VERSION.SDK_INT < 33 || ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED

    fun ensureServiceChannel(context: Context) {
        context.getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(SERVICE_CHANNEL, context.getString(R.string.channel_service), NotificationManager.IMPORTANCE_MIN),
        )
    }

    private fun conversationChannel(context: Context, threadId: Long, title: String): String {
        val id = "thread_$threadId"
        val manager = context.getSystemService(NotificationManager::class.java)
        if (manager.getNotificationChannel(id) == null) {
            manager.createNotificationChannel(NotificationChannel(id, title, NotificationManager.IMPORTANCE_HIGH).apply {
                group = null
                lockscreenVisibility = NotificationCompat.VISIBILITY_PRIVATE
            })
        }
        return id
    }

    @SuppressLint("MissingPermission") // POST_NOTIFICATIONS is checked by allowed()
    fun incoming(context: Context, message: ProviderMessage) {
        if (!allowed(context)) return
        val store = SyncStore.get(context)
        if (store?.isMuted(message.threadId) == true) return
        val hide = (store?.setting("hide_on_lock_screen", "1") ?: "1") != "0"
        val address = message.addresses.firstOrNull() ?: return
        val title = Contacts.name(context, address) ?: address
        val open = PendingIntent.getActivity(context, message.threadId.toInt(), Intent(context, MainActivity::class.java).setData(Uri.parse("cmsms://chat/${message.threadId}")), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val builder = NotificationCompat.Builder(context, conversationChannel(context, message.threadId, title))
            .setSmallIcon(R.drawable.ic_stat_message).setContentTitle(title).setContentText(message.body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(message.body)).setContentIntent(open).setAutoCancel(true)
            .setCategory(NotificationCompat.CATEGORY_MESSAGE)
            .setVisibility(if (hide) NotificationCompat.VISIBILITY_PRIVATE else NotificationCompat.VISIBILITY_PUBLIC)
            .setPublicVersion(NotificationCompat.Builder(context, conversationChannel(context, message.threadId, title)).setSmallIcon(R.drawable.ic_stat_message).setContentTitle(context.getString(R.string.new_message)).build())
        // Explicit, immutable intents to our own non-exported receiver (the reply one must be mutable for RemoteInput).
        val reply = Intent(context, NotificationActionReceiver::class.java).setAction("reply").setPackage(context.packageName)
            .putExtra("thread", message.threadId).putExtra("address", address).putExtra("sub", message.subscriptionId ?: -1L)
        val replyAction = NotificationCompat.Action.Builder(0, context.getString(R.string.reply),
            PendingIntent.getBroadcast(context, (message.threadId * 10 + 1).toInt(), reply, PendingIntent.FLAG_MUTABLE or PendingIntent.FLAG_UPDATE_CURRENT))
            .addRemoteInput(RemoteInput.Builder(KEY_REPLY).setLabel(context.getString(R.string.reply)).build()).setAllowGeneratedReplies(false).build()
        val read = Intent(context, NotificationActionReceiver::class.java).setAction("read").setPackage(context.packageName).putExtra("thread", message.threadId)
        builder.addAction(replyAction)
        builder.addAction(0, context.getString(R.string.mark_read), PendingIntent.getBroadcast(context, (message.threadId * 10 + 2).toInt(), read, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT))
        if (otp.containsMatchIn(message.body)) digits.find(message.body)?.value?.replace(Regex("[- ]"), "")?.let { code ->
            val copy = Intent(context, NotificationActionReceiver::class.java).setAction("copy").setPackage(context.packageName).putExtra("code", code).putExtra("thread", message.threadId)
            builder.addAction(0, context.getString(R.string.copy_code), PendingIntent.getBroadcast(context, (message.threadId * 10 + 3).toInt(), copy, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT))
        }
        NotificationManagerCompat.from(context).notify(message.threadId.toInt(), builder.build())
    }

    @SuppressLint("MissingPermission") // POST_NOTIFICATIONS is checked by allowed()
    fun adminReplied(context: Context, threadId: Long, address: String) {
        if (!allowed(context)) return
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(ADMIN_CHANNEL, context.getString(R.string.channel_admin), NotificationManager.IMPORTANCE_LOW))
        val title = context.getString(R.string.admin_replied, Contacts.name(context, address) ?: address)
        NotificationManagerCompat.from(context).notify((threadId + 100000).toInt(), NotificationCompat.Builder(context, ADMIN_CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_message).setContentTitle(title).setSilent(true).setAutoCancel(true).build())
    }

    @SuppressLint("MissingPermission") // POST_NOTIFICATIONS is checked by allowed()
    fun sendFailed(context: Context, uri: Uri) {
        if (!allowed(context)) return
        val message = Provider.sms(context, uri) ?: return
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel("failed", context.getString(R.string.channel_failed), NotificationManager.IMPORTANCE_DEFAULT))
        NotificationManagerCompat.from(context).notify((message.threadId + 200000).toInt(), NotificationCompat.Builder(context, "failed")
            .setSmallIcon(R.drawable.ic_stat_message).setContentTitle(context.getString(R.string.send_failed)).setAutoCancel(true).build())
    }

    @SuppressLint("MissingPermission") // POST_NOTIFICATIONS is checked by allowed()
    fun mmsWaiting(context: Context, from: String?) {
        if (!allowed(context)) return
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel("mms", context.getString(R.string.channel_mms), NotificationManager.IMPORTANCE_DEFAULT))
        NotificationManagerCompat.from(context).notify(300000, NotificationCompat.Builder(context, "mms").setSmallIcon(R.drawable.ic_stat_message)
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
                Provider.markThreadRead(context, threadId)
                NotificationManagerCompat.from(context).cancel(threadId.toInt())
            }
            "read" -> {
                Provider.markThreadRead(context, threadId)
                SyncStore.get(context)?.appendEvent("thread.read", org.json.JSONObject().put("thread_id", threadId))
                NotificationManagerCompat.from(context).cancel(threadId.toInt())
            }
            "copy" -> {
                val code = intent.getStringExtra("code") ?: return
                context.getSystemService(ClipboardManager::class.java).setPrimaryClip(ClipData.newPlainText("code", code))
            }
        }
        SyncTrigger.now(context)
    }
}

class NotificationActionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val pending = goAsync()
        Thread { try { safely("notification action") { Notifications.handle(context, intent) } } finally { pending.finish() } }.start()
    }
}
