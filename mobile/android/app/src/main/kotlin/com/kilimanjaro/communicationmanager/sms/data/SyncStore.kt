package com.kilimanjaro.communicationmanager.sms.data

import android.content.ContentValues
import android.content.Context
import com.kilimanjaro.communicationmanager.sms.security.DatabaseKey
import net.zetetic.database.sqlcipher.SQLiteDatabase
import org.json.JSONObject
import java.io.File

/**
 * Native writer for the encrypted sync database that Dart (drift) owns. Receivers append outbox events here in the
 * same code path that writes the Telephony provider, so an event exists before anything else can fail. The schema is
 * created by drift when the phone enrolls; before that there is nothing to sync and writes are skipped (the
 * backfill after enrollment copies the history anyway).
 */
class SyncStore private constructor(private val db: SQLiteDatabase) {

    companion object {
        @Volatile private var instance: SyncStore? = null
        private var loaded = false

        /** null until the app has enrolled (no schema yet). */
        fun get(context: Context): SyncStore? {
            instance?.let { return it }
            synchronized(this) {
                instance?.let { return it }
                val path = DatabaseKey.path(context)
                if (!File(path).exists()) return null
                if (!loaded) { System.loadLibrary("sqlcipher"); loaded = true }
                val db = SQLiteDatabase.openDatabase(path, DatabaseKey.get(context), null, SQLiteDatabase.OPEN_READWRITE, null, null)
                db.rawQuery("PRAGMA busy_timeout = 5000", null).close()
                val store = SyncStore(db)
                if (!store.enrolled()) { db.close(); return null }
                instance = store
                return store
            }
        }

        fun close() = synchronized(this) { instance?.db?.close(); instance = null }
    }

    private fun enrolled(): Boolean = try {
        db.rawQuery("SELECT value FROM kv WHERE key = 'device_id'", null).use { it.moveToFirst() }
    } catch (e: Exception) {
        false
    }

    @Synchronized
    fun appendEvent(type: String, payload: JSONObject): Long =
        db.insert("sync_events", null, ContentValues().apply {
            put("type", type)
            put("payload", payload.toString())
            put("created_at", System.currentTimeMillis())
        })

    /** At-most-once guard: false when this client_uuid was already started (never send it twice). */
    @Synchronized
    fun startOutbound(clientUuid: String, sentBy: String?): Boolean {
        val values = ContentValues().apply {
            put("client_uuid", clientUuid)
            put("state", "sending")
            put("updated_at", System.currentTimeMillis())
            if (sentBy != null) put("sent_by", sentBy)
        }
        return db.insertWithOnConflict("outbound_states", null, values, SQLiteDatabase.CONFLICT_IGNORE) != -1L
    }

    @Synchronized
    fun updateOutbound(clientUuid: String, state: String, providerId: Long? = null, errorCode: Int? = null, parts: Int? = null) {
        val values = ContentValues().apply {
            put("state", state)
            put("updated_at", System.currentTimeMillis())
            providerId?.let { put("provider_id", it) }
            errorCode?.let { put("error_code", it) }
            parts?.let { put("parts", it) }
        }
        // Delivery never goes back to "sent", and nothing overrides a final failure with a late "sending".
        db.update("outbound_states", values, "client_uuid = ? AND NOT (state = 'delivered' AND ? = 'sent')", arrayOf(clientUuid, state))
    }

    @Synchronized
    fun addPendingMedia(providerId: Long, date: Long, seq: Int, uri: String, size: Long) {
        db.insertWithOnConflict("pending_media", null, ContentValues().apply {
            put("provider_id", providerId); put("date", date); put("seq", seq); put("uri", uri); put("size", size); put("offset", 0)
        }, SQLiteDatabase.CONFLICT_REPLACE)
    }

    fun setting(key: String, default: String = ""): String =
        db.rawQuery("SELECT value FROM kv WHERE key = ?", arrayOf("setting.$key")).use { if (it.moveToFirst()) it.getString(0) else default }

    fun setValue(key: String, value: String) {
        db.insertWithOnConflict("kv", null, ContentValues().apply { put("key", key); put("value", value) }, SQLiteDatabase.CONFLICT_REPLACE)
    }

    fun isMuted(threadId: Long): Boolean =
        db.rawQuery("SELECT muted FROM conversation_prefs WHERE thread_id = ?", arrayOf(threadId.toString())).use { it.moveToFirst() && it.getInt(0) == 1 }

    fun sentBy(providerId: Long): String? =
        db.rawQuery("SELECT sent_by FROM outbound_states WHERE provider_id = ?", arrayOf(providerId.toString())).use { if (it.moveToFirst()) it.getString(0) else null }
}
