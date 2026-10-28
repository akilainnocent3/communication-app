package com.kilimanjaro.communicationmanager.sms.sync

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.work.CoroutineWorker
import androidx.work.ForegroundInfo
import androidx.work.WorkerParameters
import com.kilimanjaro.communicationmanager.sms.R
import com.kilimanjaro.communicationmanager.sms.data.SyncStore
import com.kilimanjaro.communicationmanager.sms.safely
import com.kilimanjaro.communicationmanager.sms.telephony.Notifications
import com.kilimanjaro.communicationmanager.sms.telephony.Provider
import com.kilimanjaro.communicationmanager.sms.telephony.SyncTrigger
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage

/** WorkManager backstop (periodic, 15 min floor) and expedited "sync now": (re)starts the foreground service. */
class SyncWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val enrolled = runCatching { SyncStore.get(applicationContext) != null }.getOrDefault(false)
        if (!enrolled) return Result.success()
        return runCatching { SyncService.start(applicationContext) }.fold({ Result.success() }, { Result.retry() })
    }

    /**
     * Android 11 and older run expedited work as a foreground service and ask for this notification. Without it every
     * "sync now" failed there with IllegalStateException("Not implemented").
     */
    override suspend fun getForegroundInfo(): ForegroundInfo {
        Notifications.ensureServiceChannel(applicationContext)
        val notification = NotificationCompat.Builder(applicationContext, Notifications.SERVICE_CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_message).setContentTitle(applicationContext.getString(R.string.service_title))
            .setPriority(NotificationCompat.PRIORITY_MIN).setCategory(NotificationCompat.CATEGORY_SERVICE).build()
        return ForegroundInfo(NOTIFICATION_ID, notification)
    }

    private companion object {
        const val NOTIFICATION_ID = 42
    }
}

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED && intent.action != Intent.ACTION_MY_PACKAGE_REPLACED) return
        // No send survives a reboot; after an update a radio result may still arrive, so only old rows are failed.
        val staleAfter = if (intent.action == Intent.ACTION_BOOT_COMPLETED) 0L else 10 * 60 * 1000L
        safely("stale outbox") { Provider.failStaleOutbox(context, staleAfter) }
        safely("boot") {
            if (SyncStore.get(context) == null) return
            SyncTrigger.schedulePeriodic(context)
            runCatching { SyncService.start(context) }.onFailure { SyncTrigger.now(context) }
        }
    }
}

/**
 * Firebase wake-ups (optional). Data-only, high priority, no message content: {"type": "sync" | "outbox" | "command"}.
 * The token is stored for the Dart loop to register with the server.
 */
class PushService : FirebaseMessagingService() {
    override fun onMessageReceived(message: RemoteMessage) {
        safely("push") {
            if (SyncStore.get(this) == null) return
            runCatching { startForegroundService(Intent(this, SyncService::class.java).setAction("push")) }.onFailure { SyncTrigger.now(this) }
        }
    }

    override fun onNewToken(token: String) {
        safely("push token") { SyncStore.get(this)?.setValue("push_token_pending", token) }
    }
}
