package com.kilimanjaro.communicationmanager.phone.telephony

import android.content.Context
import android.provider.CallLog
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.OutOfQuotaPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import com.kilimanjaro.communicationmanager.phone.sync.NativeSyncEngine
import com.kilimanjaro.communicationmanager.phone.sync.SyncWorker
import java.util.concurrent.TimeUnit

/**
 * Something changed: make sure a sync runs soon. OCM Phone has no persistent service (decision 81): expedited
 * WorkManager work runs the native engine, a call-log trigger catches rows Telecom writes while the app is not running,
 * and a periodic job (15 min, the platform minimum) is the backstop.
 */
object SyncTrigger {
    const val TAG_PERIODIC = "sync-periodic"
    const val TAG_CALL_LOG = "sync-call-log"

    fun now(context: Context) {
        NativeSyncEngine.requestAgain()
        expedite(context)
    }

    fun expedite(context: Context) {
        val request = OneTimeWorkRequestBuilder<SyncWorker>()
            .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork("sync-now", ExistingWorkPolicy.KEEP, request)
    }

    /** Runs a sync when the system call log changes, even with the app's process gone (JobScheduler content trigger). */
    fun watchCallLog(context: Context) {
        val request = OneTimeWorkRequestBuilder<SyncWorker>()
            .addTag(TAG_CALL_LOG)
            .setConstraints(Constraints.Builder().addContentUriTrigger(CallLog.Calls.CONTENT_URI, true)
                .setTriggerContentUpdateDelay(2, TimeUnit.SECONDS).setTriggerContentMaxDelay(30, TimeUnit.SECONDS).build())
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork(TAG_CALL_LOG, ExistingWorkPolicy.KEEP, request)
    }

    /** After enrollment and on every app-requested sync: the backstops exist (idempotent: KEEP leaves them as they are). */
    fun ensureScheduled(context: Context) {
        watchCallLog(context)
        val request = PeriodicWorkRequestBuilder<SyncWorker>(15, TimeUnit.MINUTES)
            .addTag(TAG_PERIODIC)
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(TAG_PERIODIC, ExistingPeriodicWorkPolicy.KEEP, request)
    }

    fun schedulePeriodic(context: Context) {
        val request = PeriodicWorkRequestBuilder<SyncWorker>(15, TimeUnit.MINUTES)
            .addTag(TAG_PERIODIC)
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(TAG_PERIODIC, ExistingPeriodicWorkPolicy.UPDATE, request)
    }
}
