package com.kilimanjaro.communicationmanager.sms.sync

import android.content.Context
import androidx.core.app.NotificationManagerCompat
import androidx.work.WorkManager
import com.kilimanjaro.communicationmanager.sms.bridge.EventBus
import com.kilimanjaro.communicationmanager.sms.data.SyncStore
import com.kilimanjaro.communicationmanager.sms.safely
import com.kilimanjaro.communicationmanager.sms.security.DatabaseKey
import com.kilimanjaro.communicationmanager.sms.security.DeviceKey
import java.io.File

/**
 * The administrator removed this phone (401 device_revoked): delete the Keystore identity, the sync database (outbox,
 * caches, settings) and its key. The phone's own SMS in the Telephony provider are untouched; the server keeps its
 * copy. The app shows "This phone was removed" on its next start (or at once if it is open).
 */
object Revocation {
    private const val PREFS = "cm_state"

    fun handle(context: Context) {
        wipe(context)
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean("removed", true).commit()
        EventBus.emit("sync_state", state = "revoked")
    }

    fun wipe(context: Context) {
        NativeSyncEngine.forget()
        safely("stop work") { WorkManager.getInstance(context).cancelAllWork() }
        safely("stop service") { SyncService.stop(context) }
        safely("notifications") { NotificationManagerCompat.from(context).cancelAll() }
        SyncStore.close()
        DeviceKey.delete()
        val path = DatabaseKey.path(context)
        listOf(path, "$path-wal", "$path-shm", "$path-journal").forEach { File(it).delete() }
        DatabaseKey.delete(context)
    }

    /** Read once by the UI at startup. */
    fun consumeRemoved(context: Context): Boolean {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val removed = prefs.getBoolean("removed", false)
        if (removed) prefs.edit().remove("removed").apply()
        return removed
    }
}
