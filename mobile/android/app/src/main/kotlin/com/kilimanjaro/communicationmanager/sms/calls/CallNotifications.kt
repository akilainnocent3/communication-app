package com.kilimanjaro.communicationmanager.sms.calls

import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.app.Person
import com.kilimanjaro.communicationmanager.sms.MainActivity
import com.kilimanjaro.communicationmanager.sms.R

/**
 * Call notifications: the incoming call (full-screen intent: the native call screen over the lock screen, instantly,
 * from a cold process), the ongoing call, missed calls (Call back / Message) and call-back tasks.
 */
object CallNotifications {
    const val INCOMING_CHANNEL = "calls_incoming"
    const val ONGOING_CHANNEL = "calls_ongoing"
    const val MISSED_CHANNEL = "calls_missed"
    const val CALLBACK_CHANNEL = "calls_callbacks"
    const val CALL_ID = 61
    private const val MISSED_ID = 62
    private const val FLAGS = PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT

    fun channels(context: Context) {
        val manager = context.getSystemService(NotificationManager::class.java)
        // The app rings itself (IN_CALL_SERVICE_RINGING): the incoming channel is silent but high priority.
        manager.createNotificationChannel(NotificationChannel(INCOMING_CHANNEL, context.getString(R.string.channel_calls_incoming), NotificationManager.IMPORTANCE_HIGH).apply { setSound(null, null); enableVibration(false) })
        manager.createNotificationChannel(NotificationChannel(ONGOING_CHANNEL, context.getString(R.string.channel_calls_ongoing), NotificationManager.IMPORTANCE_LOW))
        manager.createNotificationChannel(NotificationChannel(MISSED_CHANNEL, context.getString(R.string.channel_calls_missed), NotificationManager.IMPORTANCE_DEFAULT))
        manager.createNotificationChannel(NotificationChannel(CALLBACK_CHANNEL, context.getString(R.string.channel_callbacks), NotificationManager.IMPORTANCE_HIGH))
    }

    private fun screen(context: Context) = Intent(context, InCallActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_NO_USER_ACTION)

    private fun action(context: Context, action: String, code: Int, extra: (Intent) -> Unit = {}): PendingIntent =
        PendingIntent.getBroadcast(context, code, Intent(context, CallActionReceiver::class.java).setAction(action).also(extra), FLAGS)

    fun incoming(context: Context, name: String, detail: String): Notification {
        channels(context)
        val full = PendingIntent.getActivity(context, 0, screen(context), FLAGS)
        val caller = Person.Builder().setName(name).setImportant(true).build()
        return NotificationCompat.Builder(context, INCOMING_CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_ocm).setContentTitle(name).setContentText(detail).setCategory(NotificationCompat.CATEGORY_CALL)
            .setPriority(NotificationCompat.PRIORITY_MAX).setOngoing(true).setFullScreenIntent(full, true).setContentIntent(full)
            .setStyle(NotificationCompat.CallStyle.forIncomingCall(caller, action(context, CallActionReceiver.DECLINE, 1), action(context, CallActionReceiver.ANSWER, 2)))
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC).build()
    }

    fun ongoing(context: Context, name: String, startedAt: Long): Notification {
        channels(context)
        val open = PendingIntent.getActivity(context, 0, screen(context), FLAGS)
        val caller = Person.Builder().setName(name).build()
        return NotificationCompat.Builder(context, ONGOING_CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_ocm).setContentTitle(name).setCategory(NotificationCompat.CATEGORY_CALL).setOngoing(true)
            .setUsesChronometer(true).setWhen(startedAt).setContentIntent(open)
            .setStyle(NotificationCompat.CallStyle.forOngoingCall(caller, action(context, CallActionReceiver.HANG_UP, 3))).build()
    }

    @SuppressLint("MissingPermission") // POST_NOTIFICATIONS checked by areNotificationsEnabled
    fun missed(context: Context, number: String, name: String?) {
        val manager = NotificationManagerCompat.from(context)
        if (!manager.areNotificationsEnabled()) return
        channels(context)
        val open = PendingIntent.getActivity(context, 10, Intent(Intent.ACTION_VIEW, Uri.parse("cmsms://phone/recents")).setClass(context, MainActivity::class.java), FLAGS)
        val callBack = PendingIntent.getActivity(context, 11, PlaceCallActivity.intent(context, number, "redial", null), FLAGS)
        val message = PendingIntent.getActivity(context, 12, Intent(Intent.ACTION_SENDTO, Uri.fromParts("smsto", number, null)).setClass(context, MainActivity::class.java), FLAGS)
        manager.notify(MISSED_ID, NotificationCompat.Builder(context, MISSED_CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_ocm).setContentTitle(context.getString(R.string.missed_call)).setContentText(name ?: number)
            .setCategory(NotificationCompat.CATEGORY_MISSED_CALL).setAutoCancel(true).setContentIntent(open)
            .setVisibility(NotificationCompat.VISIBILITY_PRIVATE)
            .addAction(0, context.getString(R.string.call_back), callBack).addAction(0, context.getString(R.string.message), message).build())
    }

    @SuppressLint("MissingPermission")
    fun callback(context: Context, task: CallbackTasks.Task) {
        val manager = NotificationManagerCompat.from(context)
        if (!manager.areNotificationsEnabled()) return
        channels(context)
        val id = 1000 + (task.id.hashCode() and 0xffff)
        val who = task.name.ifBlank { task.number }
        val call = PendingIntent.getActivity(context, id, PlaceCallActivity.intent(context, task.number, "callback_task", task.id), FLAGS)
        val open = PendingIntent.getActivity(context, id + 1, Intent(Intent.ACTION_VIEW, Uri.parse("cmsms://phone/callbacks")).setClass(context, MainActivity::class.java), FLAGS)
        manager.notify(id, NotificationCompat.Builder(context, CALLBACK_CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_ocm)
            .setContentTitle(context.getString(R.string.callback_title, who))
            .setContentText(listOf(task.reason, context.getString(R.string.requested_by, task.requestedBy)).filter { it.isNotBlank() }.joinToString(" · "))
            .setCategory(NotificationCompat.CATEGORY_REMINDER).setContentIntent(open).setAutoCancel(true).setVisibility(NotificationCompat.VISIBILITY_PRIVATE)
            .addAction(0, context.getString(R.string.call), call)
            .addAction(0, context.getString(R.string.snooze), action(context, CallActionReceiver.SNOOZE, id + 2) { it.putExtra("task", task.id).putExtra("notification", id) })
            .addAction(0, context.getString(R.string.done), action(context, CallActionReceiver.DONE, id + 3) { it.putExtra("task", task.id).putExtra("notification", id) })
            .build())
    }

    fun cancelCallback(context: Context, notificationId: Int) = NotificationManagerCompat.from(context).cancel(notificationId)
}
