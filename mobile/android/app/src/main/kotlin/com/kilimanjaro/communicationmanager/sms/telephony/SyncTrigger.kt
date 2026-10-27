package com.kilimanjaro.communicationmanager.sms.telephony

import android.content.Context
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.OutOfQuotaPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import com.kilimanjaro.communicationmanager.sms.bridge.EventBus
import com.kilimanjaro.communicationmanager.sms.sync.SyncService
import com.kilimanjaro.communicationmanager.sms.sync.SyncWorker
import java.util.concurrent.TimeUnit

/**
 * Something changed: make sure a sync runs soon. If the foreground service is alive its Dart loop reacts to the event;
 * otherwise an expedited WorkManager job (re)starts it. A periodic job (15 min, the platform minimum) is the backstop.
 */
object SyncTrigger {
    fun now(context: Context) {
        EventBus.emit("outbox_changed")
        if (SyncService.running) return
        val request = OneTimeWorkRequestBuilder<SyncWorker>()
            .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork("sync-now", ExistingWorkPolicy.KEEP, request)
    }

    fun schedulePeriodic(context: Context) {
        val request = PeriodicWorkRequestBuilder<SyncWorker>(15, TimeUnit.MINUTES)
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork("sync-periodic", ExistingPeriodicWorkPolicy.KEEP, request)
    }
}
