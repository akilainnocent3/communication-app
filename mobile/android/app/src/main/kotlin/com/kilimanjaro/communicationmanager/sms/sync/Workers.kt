package com.kilimanjaro.communicationmanager.sms.sync

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.work.CoroutineWorker
import androidx.work.ForegroundInfo
import androidx.work.WorkerParameters
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import com.kilimanjaro.communicationmanager.sms.R
import com.kilimanjaro.communicationmanager.sms.data.SyncStore
import com.kilimanjaro.communicationmanager.sms.safely
import com.kilimanjaro.communicationmanager.sms.telephony.Notifications
import com.kilimanjaro.communicationmanager.sms.telephony.Provider
import com.kilimanjaro.communicationmanager.sms.telephony.SyncTrigger
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * WorkManager runs the native sync engine itself (periodic 15 min backstop, and expedited "sync now" after a message
 * arrives or a send changes state), then tries to (re)start the foreground service. That start may be refused in the
 * background on Android 12+; the work is done either way.
 */
class SyncWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val engine = runCatching { NativeSyncEngine.get(applicationContext) }.getOrNull() ?: return@withContext Result.success()
        val outcome = engine.runOnce(forceHeartbeat = tags.contains(SyncTrigger.TAG_PERIODIC))
        if (outcome == NativeSyncEngine.Result.REVOKED) {
            Revocation.handle(applicationContext)
            return@withContext Result.success()
        }
        safely("service start") { SyncService.start(applicationContext) }
        if (outcome == NativeSyncEngine.Result.OFFLINE && !tags.contains(SyncTrigger.TAG_PERIODIC) && runAttemptCount < 5) Result.retry() else Result.success()
    }

    /**
     * Android 11 and older run expedited work as a foreground service and ask for this notification. Without it every
     * "sync now" failed there with IllegalStateException("Not implemented").
     */
    override suspend fun getForegroundInfo(): ForegroundInfo {
        Notifications.ensureServiceChannel(applicationContext)
        val notification = NotificationCompat.Builder(applicationContext, Notifications.SERVICE_CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_message).setContentTitle(applicationContext.getString(R.string.service_title)).setSilent(true)
            .setPriority(NotificationCompat.PRIORITY_MIN).setCategory(NotificationCompat.CATEGORY_SERVICE).build()
        return ForegroundInfo(NOTIFICATION_ID, notification)
    }

    private companion object {
        const val NOTIFICATION_ID = 42
    }
}

/** BOOT_COMPLETED and MY_PACKAGE_REPLACED are foreground-start exemptions: start the service and sync. */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED && intent.action != Intent.ACTION_MY_PACKAGE_REPLACED) return
        // No send survives a reboot; after an update a radio result may still arrive, so only old rows are failed.
        val staleAfter = if (intent.action == Intent.ACTION_BOOT_COMPLETED) 0L else 10 * 60 * 1000L
        safely("stale outbox") { Provider.failStaleOutbox(context, staleAfter) }
        safely("boot") {
            if (SyncStore.get(context) == null) return
            SyncTrigger.schedulePeriodic(context)
            if (!SyncService.start(context)) SyncTrigger.expedite(context)
        }
    }
}

/**
 * Firebase wake-ups. Data-only, high priority, no message content: {"type": "sync" | "outbox" | "command"}. A
 * high-priority message lets the app start its foreground service from the background; the engine also runs here
 * directly (onMessageReceived has ~20 s), so an admin reply is claimed and sent with no Flutter and no UI involved.
 */
class PushService : FirebaseMessagingService() {
    override fun onMessageReceived(message: RemoteMessage) {
        safely("push") {
            if (SyncStore.get(this) == null) return
            if (SyncService.running) {
                SyncService.request()
                return
            }
            SyncService.start(this)
            val outcome = NativeSyncEngine.get(this)?.runOnce() ?: return
            if (outcome == NativeSyncEngine.Result.REVOKED) Revocation.handle(this)
            else if (outcome != NativeSyncEngine.Result.OK) SyncTrigger.expedite(this)
        }
    }

    override fun onNewToken(token: String) {
        safely("push token") {
            SyncStore.get(this)?.setValue("push_token_pending", token)
            SyncTrigger.now(this)
        }
    }
}
