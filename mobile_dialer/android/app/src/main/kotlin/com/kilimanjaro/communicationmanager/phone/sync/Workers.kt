package com.kilimanjaro.communicationmanager.phone.sync

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.work.CoroutineWorker
import androidx.work.ForegroundInfo
import androidx.work.WorkerParameters
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import com.kilimanjaro.communicationmanager.phone.R
import com.kilimanjaro.communicationmanager.phone.data.SyncStore
import com.kilimanjaro.communicationmanager.phone.safely
import com.kilimanjaro.communicationmanager.phone.dialer.CallNotifications
import com.kilimanjaro.communicationmanager.phone.telephony.SyncTrigger
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * WorkManager runs the native sync engine (periodic 15 min backstop, expedited "sync now" after a call, and the
 * call-log content trigger, which re-arms itself after each run). OCM Phone keeps no foreground service.
 */
class SyncWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        if (tags.contains(SyncTrigger.TAG_CALL_LOG)) safely("call log trigger") { SyncTrigger.watchCallLog(applicationContext) }
        val engine = runCatching { NativeSyncEngine.get(applicationContext) }.getOrNull() ?: return@withContext Result.success()
        val outcome = engine.runOnce(forceHeartbeat = tags.contains(SyncTrigger.TAG_PERIODIC))
        if (outcome == NativeSyncEngine.Result.REVOKED) {
            Revocation.handle(applicationContext)
            return@withContext Result.success()
        }
        if (outcome == NativeSyncEngine.Result.OFFLINE && !tags.contains(SyncTrigger.TAG_PERIODIC) && runAttemptCount < 5) Result.retry() else Result.success()
    }

    /**
     * Android 11 and older run expedited work as a foreground service and ask for this notification: it discloses the
     * company copy while it runs.
     */
    override suspend fun getForegroundInfo(): ForegroundInfo {
        CallNotifications.ensureSyncChannel(applicationContext)
        val notification = NotificationCompat.Builder(applicationContext, CallNotifications.SYNC_CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_ocm).setContentTitle(applicationContext.getString(R.string.service_title)).setSilent(true)
            .setPriority(NotificationCompat.PRIORITY_MIN).setCategory(NotificationCompat.CATEGORY_SERVICE).build()
        return ForegroundInfo(NOTIFICATION_ID, notification)
    }

    private companion object {
        const val NOTIFICATION_ID = 42
    }
}

/** After a reboot or an update: re-arm the periodic job and the call-log trigger, then sync. */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED && intent.action != Intent.ACTION_MY_PACKAGE_REPLACED) return
        safely("boot") {
            if (SyncStore.get(context) == null) return
            SyncTrigger.schedulePeriodic(context)
            SyncTrigger.watchCallLog(context)
            SyncTrigger.expedite(context)
        }
    }
}

/**
 * Firebase wake-ups. Data-only, high priority, no content: {"type": "sync" | "callbacks" | "config"}. The engine runs
 * here directly (onMessageReceived has ~20 s), so a new call-back task reaches the phone in seconds.
 */
class PushService : FirebaseMessagingService() {
    override fun onMessageReceived(message: RemoteMessage) {
        safely("push") {
            if (SyncStore.get(this) == null) return
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
