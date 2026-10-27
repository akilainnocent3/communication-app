package com.kilimanjaro.communicationmanager.sms.sync

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.kilimanjaro.communicationmanager.sms.data.SyncStore
import com.kilimanjaro.communicationmanager.sms.telephony.SyncTrigger
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage

/** WorkManager backstop (periodic, 15 min floor) and expedited "sync now": (re)starts the foreground service. */
class SyncWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        if (SyncStore.get(applicationContext) == null) return Result.success() // not enrolled
        return runCatching { SyncService.start(applicationContext) }.fold({ Result.success() }, { Result.retry() })
    }
}

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED && intent.action != Intent.ACTION_MY_PACKAGE_REPLACED) return
        if (SyncStore.get(context) == null) return
        SyncTrigger.schedulePeriodic(context)
        runCatching { SyncService.start(context) }.onFailure { SyncTrigger.now(context) }
    }
}

/**
 * Firebase wake-ups (optional). Data-only, high priority, no message content: {"type": "sync" | "outbox" | "command"}.
 * The token is stored for the Dart loop to register with the server.
 */
class PushService : FirebaseMessagingService() {
    override fun onMessageReceived(message: RemoteMessage) {
        if (SyncStore.get(this) == null) return
        runCatching { startForegroundService(Intent(this, SyncService::class.java).setAction("push")) }.onFailure { SyncTrigger.now(this) }
    }

    override fun onNewToken(token: String) {
        SyncStore.get(this)?.setValue("push_token_pending", token)
    }
}
