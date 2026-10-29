package com.kilimanjaro.communicationmanager.phone.data

import android.content.ContentValues
import android.content.Context
import com.kilimanjaro.communicationmanager.phone.security.DatabaseKey
import org.json.JSONObject
import java.io.File

/**
 * Native side of the encrypted sync database that Dart (drift) creates. Receivers append outbox events here in the same
 * code path that writes the Telephony provider, so an event exists before anything else can fail, and the native sync
 * engine (NativeSyncEngine) uploads them. Before enrollment there is nothing to sync and [get] returns null (the
 * backfill after enrollment copies the history anyway).
 */
class SyncStore(private val db: Sql) {

    data class Event(val seq: Long, val type: String, val payload: String)
    data class Outbound(val clientUuid: String, val state: String, val updatedAt: Long, val errorCode: Long?, val parts: Long?)
    data class Media(val providerId: Long, val date: Long, val seq: Int, val uri: String, val size: Long, val offset: Long)
    data class Scheduled(val clientUuid: String, val addresses: List<String>, val body: String, val subscriptionId: Long?)

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

    // --- Outbound (at most once) -------------------------------------------------------------------------------

    /** false when this client_uuid was already started (never send it twice). */
    @Synchronized
    fun startOutbound(clientUuid: String, sentBy: String?): Boolean = db.insert("outbound_states", ContentValues().apply {
        put("client_uuid", clientUuid)
        put("state", "sending")
        put("updated_at", System.currentTimeMillis())
        if (sentBy != null) put("sent_by", sentBy)
    }, Sql.Conflict.IGNORE) != -1L

    fun outboundExists(clientUuid: String): Boolean = db.query("SELECT 1 FROM outbound_states WHERE client_uuid = ?", arrayOf(clientUuid)) { it.moveToFirst() }

    /** An admin message offered after it expired: recorded failed (1003) without sending. */
    @Synchronized
    fun recordExpired(clientUuid: String, now: Long) {
        db.insert("outbound_states", ContentValues().apply {
            put("client_uuid", clientUuid); put("state", "failed"); put("error_code", 1003); put("updated_at", now)
        }, Sql.Conflict.REPLACE)
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

    /** A send the phone started but never got a result for (the process died mid-send). */
    @Synchronized
    fun markStaleSendsUnknown(olderThan: Long, now: Long): Int = db.update("outbound_states", ContentValues().apply { put("state", "unknown"); put("updated_at", now) },
        "state = 'sending' AND updated_at < ?", arrayOf(olderThan.toString()))

    fun unreportedOutbound(): List<Outbound> = db.query(
        "SELECT client_uuid, state, updated_at, error_code, parts FROM outbound_states WHERE reported_state IS NULL OR reported_state != state",
    ) { c ->
        buildList {
            while (c.moveToNext()) add(Outbound(c.getString(0), c.getString(1), c.getLong(2), if (c.isNull(3)) null else c.getLong(3), if (c.isNull(4)) null else c.getLong(4)))
        }
    }

    @Synchronized
    fun markReported(clientUuid: String, state: String) {
        db.update("outbound_states", ContentValues().apply { put("reported_state", state) }, "client_uuid = ?", arrayOf(clientUuid))
    }

    fun sentBy(providerId: Long): String? =
        db.query("SELECT sent_by FROM outbound_states WHERE provider_id = ?", arrayOf(providerId.toString())) { if (it.moveToFirst()) it.getString(0) else null }

    // --- MMS media still to upload -----------------------------------------------------------------------------

    @Synchronized
    fun addPendingMedia(providerId: Long, date: Long, seq: Int, uri: String, size: Long) {
        db.insert("pending_media", ContentValues().apply {
            put("provider_id", providerId); put("date", date); put("seq", seq); put("uri", uri); put("size", size); put("offset", 0)
        }, Sql.Conflict.REPLACE)
    }

    fun pendingMedia(): List<Media> = db.query("SELECT provider_id, date, seq, uri, size, \"offset\" FROM pending_media") { c ->
        buildList { while (c.moveToNext()) add(Media(c.getLong(0), c.getLong(1), c.getInt(2), c.getString(3), c.getLong(4), c.getLong(5))) }
    }

    private fun mediaKey(m: Media) = arrayOf(m.providerId.toString(), m.date.toString(), m.seq.toString())

    @Synchronized
    fun setMediaOffset(media: Media, offset: Long) {
        db.update("pending_media", ContentValues().apply { put("offset", offset) }, "provider_id = ? AND date = ? AND seq = ?", mediaKey(media))
    }

    @Synchronized
    fun deleteMedia(media: Media) {
        db.delete("pending_media", "provider_id = ? AND date = ? AND seq = ?", mediaKey(media))
    }

    // --- Phone-side scheduled sends ----------------------------------------------------------------------------

    fun dueScheduled(now: Long): List<Scheduled> = db.query("SELECT client_uuid, addresses, body, subscription_id FROM scheduled_sends WHERE send_at <= ?", arrayOf(now.toString())) { c ->
        buildList {
            while (c.moveToNext()) {
                val addresses = org.json.JSONArray(c.getString(1)).let { a -> List(a.length()) { a.getString(it) } }
                add(Scheduled(c.getString(0), addresses, c.getString(2), if (c.isNull(3)) null else c.getLong(3)))
            }
        }
    }

    @Synchronized
    fun deleteScheduled(clientUuid: String) {
        db.delete("scheduled_sends", "client_uuid = ?", arrayOf(clientUuid))
    }

    // --- Key/value and preferences -----------------------------------------------------------------------------

    fun value(key: String): String? = db.query("SELECT value FROM kv WHERE key = ?", arrayOf(key)) { if (it.moveToFirst()) it.getString(0) else null }

    @Synchronized
    fun setValue(key: String, value: String?) {
        if (value == null) db.delete("kv", "key = ?", arrayOf(key))
        else db.insert("kv", ContentValues().apply { put("key", key); put("value", value) }, Sql.Conflict.REPLACE)
    }

    fun setting(key: String, default: String = ""): String = value("setting.$key") ?: default

    fun isMuted(threadId: Long): Boolean =
        db.query("SELECT muted FROM conversation_prefs WHERE thread_id = ?", arrayOf(threadId.toString())) { it.moveToFirst() && it.getInt(0) == 1 }
}
