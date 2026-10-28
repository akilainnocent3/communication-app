package com.kilimanjaro.communicationmanager.sms.telephony

import android.content.Context
import android.os.SystemClock
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.OutOfQuotaPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import com.kilimanjaro.communicationmanager.sms.bridge.DeviceState
import com.kilimanjaro.communicationmanager.sms.safely
import com.kilimanjaro.communicationmanager.sms.sync.NativeSyncEngine
import com.kilimanjaro.communicationmanager.sms.sync.SyncService
import com.kilimanjaro.communicationmanager.sms.sync.SyncWorker
import java.util.concurrent.TimeUnit

/**
 * Something changed: make sure a sync runs soon. The running foreground service syncs at once; otherwise expedited
 * WorkManager work runs the native engine. A periodic job (15 min, the platform minimum) is the backstop.
 */
object SyncTrigger {
    const val TAG_PERIODIC = "sync-periodic"
    /** Total time a receiver may spend uploading inside its goAsync() window (the system allows about 10 s). */
    private const val RECEIVER_BUDGET_MS = 8_000L

    fun now(context: Context) {
        NativeSyncEngine.requestAgain()
        if (SyncService.running) SyncService.request() else expedite(context)
    }

    fun expedite(context: Context) {
        val request = OneTimeWorkRequestBuilder<SyncWorker>()
            .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork("sync-now", ExistingWorkPolicy.KEEP, request)
    }

    /**
     * Called by the SMS/MMS receivers after the provider row and the outbox event are written: with the service down,
     * upload the event right here (≤ 8 s from [startedAt], network permitting) so the admin sees the message in
     * seconds, then hand the rest (outbox, media) to expedited work.
     */
    fun afterIncoming(context: Context, startedAt: Long) {
        if (SyncService.running) {
            SyncService.request()
            return
        }
        safely("direct upload") {
            if (DeviceState.networkValidated(context)) {
                val deadline = startedAt + RECEIVER_BUDGET_MS
                val left = deadline - SystemClock.elapsedRealtime()
                if (left > 1_000) NativeSyncEngine.get(context, callTimeoutMs = left - 500)?.uploadNow(System.currentTimeMillis() + left - 500)
            }
        }
        now(context)
    }

    fun schedulePeriodic(context: Context) {
        val request = PeriodicWorkRequestBuilder<SyncWorker>(15, TimeUnit.MINUTES)
            .addTag(TAG_PERIODIC)
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(TAG_PERIODIC, ExistingPeriodicWorkPolicy.UPDATE, request)
    }
}
