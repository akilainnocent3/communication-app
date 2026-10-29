package com.kilimanjaro.communicationmanager.phone.sync

import android.content.Context
import androidx.core.app.NotificationManagerCompat
import androidx.work.WorkManager
import com.kilimanjaro.communicationmanager.phone.bridge.EventBus
import com.kilimanjaro.communicationmanager.phone.data.SyncStore
import com.kilimanjaro.communicationmanager.phone.safely
import com.kilimanjaro.communicationmanager.phone.security.DatabaseKey
import com.kilimanjaro.communicationmanager.phone.security.DeviceKey
import java.io.File

/**
 * The administrator removed this phone (401 device_revoked): delete the Keystore identity, the sync database (outbox,
 * caller-ID cache, call-backs, settings) and its key. The phone's call log is untouched and the server keeps its copy.
 * OCM Phone stays a working Phone app (calls are no longer copied); it shows "This phone was removed" once.
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
        safely("notifications") { NotificationManagerCompat.from(context).cancelAll() }
        safely("caller id") { com.kilimanjaro.communicationmanager.phone.dialer.CallerId.forget() }
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
