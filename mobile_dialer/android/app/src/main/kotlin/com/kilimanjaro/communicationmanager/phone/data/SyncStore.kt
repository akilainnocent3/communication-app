package com.kilimanjaro.communicationmanager.phone.data

import android.content.ContentValues
import android.content.Context
import com.kilimanjaro.communicationmanager.phone.security.DatabaseKey
import org.json.JSONObject
import java.io.File

/**
 * Native side of the encrypted sync database that Dart (drift) creates. The call code appends outbox events here in the same
 * code path that records the call, so an event exists before anything else can fail, and the native sync
 * engine (NativeSyncEngine) uploads them. Before enrollment there is nothing to sync and [get] returns null (the
 * backfill after enrollment copies the history anyway).
 */
class SyncStore(private val db: Sql) {

    data class Event(val seq: Long, val type: String, val payload: String)

    companion object {
        @Volatile private var instance: SyncStore? = null
        private var loaded = false

        /** null until the app has enrolled. */
        fun get(context: Context): SyncStore? {
            instance?.let { return it }
            synchronized(this) {
                instance?.let { return it }
                val path = DatabaseKey.path(context)
                if (!File(path).exists()) return null
                if (!loaded) { System.loadLibrary("sqlcipher"); loaded = true }
                val store = SyncStore(DatabaseKey.open(context))
                if (!store.enrolled()) { store.db.close(); return null }
                instance = store
                return store
            }
        }

        fun close() = synchronized(this) { instance?.db?.close(); instance = null }
    }

    fun enrolled(): Boolean = try {
        value("device_id") != null
    } catch (e: Exception) {
        false // no schema yet
    }

    // --- Outbox ------------------------------------------------------------------------------------------------

    @Synchronized
    fun appendEvent(type: String, payload: JSONObject): Long = db.insert("sync_events", ContentValues().apply {
        put("type", type)
        put("payload", payload.toString())
        put("created_at", System.currentTimeMillis())
    })

    fun pendingEvents(limit: Int): List<Event> = db.query("SELECT seq, type, payload FROM sync_events ORDER BY seq LIMIT ?", arrayOf(limit.toString())) { c ->
        buildList { while (c.moveToNext()) add(Event(c.getLong(0), c.getString(1), c.getString(2))) }
    }

    fun pendingCount(): Int = db.query("SELECT count(*) FROM sync_events") { if (it.moveToFirst()) it.getInt(0) else 0 }

    @Synchronized
    fun acknowledge(upTo: Long) {
        db.delete("sync_events", "seq <= ?", arrayOf(upTo.toString()))
    }

    // --- Key/value and settings -----------------------------------------------------------------------------------

    fun value(key: String): String? = db.query("SELECT value FROM kv WHERE key = ?", arrayOf(key)) { if (it.moveToFirst()) it.getString(0) else null }

    @Synchronized
    fun setValue(key: String, value: String?) {
        if (value == null) db.delete("kv", "key = ?", arrayOf(key))
        else db.insert("kv", ContentValues().apply { put("key", key); put("value", value) }, Sql.Conflict.REPLACE)
    }

    fun setting(key: String, default: String = ""): String = value("setting.$key") ?: default
}
