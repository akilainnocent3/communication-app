package com.kilimanjaro.communicationmanager.sms.sync

import android.content.Context
import android.util.Log
import com.kilimanjaro.communicationmanager.sms.BuildConfig
import com.kilimanjaro.communicationmanager.sms.bridge.ProviderMessage
import com.kilimanjaro.communicationmanager.sms.bridge.SendRequest
import com.kilimanjaro.communicationmanager.sms.bridge.SendResult
import com.kilimanjaro.communicationmanager.sms.data.SyncStore
import com.kilimanjaro.communicationmanager.sms.security.DeviceKey
import com.kilimanjaro.communicationmanager.sms.security.SecureHttp
import com.kilimanjaro.communicationmanager.sms.telephony.Provider
import org.json.JSONArray
import org.json.JSONObject
import java.io.InputStream
import java.security.MessageDigest
import java.time.Instant
import java.util.concurrent.TimeUnit
import java.util.concurrent.locks.ReentrantLock
import kotlin.math.min
import kotlin.random.Random

/** What the engine needs from the phone. Production: [AndroidPhone]; tests: a fake. */
interface Phone {
    fun heartbeatState(): JSONObject
    fun messagesSince(since: Long, limit: Int, offset: Int): List<ProviderMessage>
    fun openPart(uri: String): InputStream?
    fun contactNames(addresses: List<String>): Map<String, String>
    fun blockedNumbers(): List<String>
    fun send(request: SendRequest): SendResult
    fun markThreadRead(threadId: Long)
    fun block(address: String)
    fun unblock(address: String)
}

/** Exponential backoff with full jitter (Dart's Backoff). Never a tight loop: the shortest wait is [base]. */
class Backoff(private val base: Long = 2_000, private val cap: Long = 5 * 60_000, private val random: Random = Random.Default) {
    var failures = 0
        private set
    fun reset() { failures = 0 }
    fun next(): Long {
        val ceiling = min(cap, base * (1L shl min(failures, 20)))
        failures = min(failures + 1, 20)
        return maxOf(base, random.nextLong(ceiling + 1))
    }
}

/**
 * One sync cycle: heartbeat (when due) → push token → backfill (once) → upload events → upload media → phone-scheduled
 * sends → outbox (admin replies and commands) → status reports. Ported from lib/core/sync/sync_engine.dart, which it
 * replaces: the same protocol, idempotency and at-most-once guard, without a second Flutter engine in the service.
 *
 * Safe to call from the foreground service, WorkManager, an FCM wake-up or a receiver: cycles are serialised by a
 * lock, every step is idempotent, and a sync requested during a cycle runs once more right after it.
 */
class NativeSyncEngine(
    private val store: SyncStore,
    private val api: DeviceApiClient,
    private val phone: Phone,
    private val appVersion: String,
    private val clock: () -> Long = System::currentTimeMillis,
) {
    enum class Result { OK, OFFLINE, SUSPENDED, REVOKED, UPGRADE_REQUIRED, NOT_ENROLLED }

    companion object {
        const val MAX_BATCH_EVENTS = 200
        const val MAX_BATCH_BYTES = 900 * 1024 // under the server's 1 MB limit
        const val CHUNK_SIZE = 256 * 1024
        const val HEARTBEAT_EVERY = 5 * 60_000L
        const val CONFIG_EVERY = 60 * 60_000L
        const val STALE_SEND_AFTER = 10 * 60_000L
        const val ERROR_EXPIRED = 1003
        private const val TAG = "CmSync" // ids, counts and codes only: never text, names or numbers

        @Volatile private var shared: NativeSyncEngine? = null
        @Volatile private var sharedFor: String? = null

        /** The process-wide engine for the enrolled phone; null before enrollment. */
        fun get(context: Context, callTimeoutMs: Long? = null): NativeSyncEngine? {
            val store = SyncStore.get(context) ?: return null
            val server = store.value("server") ?: return null
            val deviceId = store.value("device_id") ?: return null
            val key = "$server|$deviceId"
            if (callTimeoutMs == null) shared?.takeIf { sharedFor == key }?.let { return it }
            val transport = SecureHttp.transport(callTimeoutMs)
            val engine = NativeSyncEngine(store, DeviceApiClient(transport, server, deviceId, { DeviceKey.sign(it) }, BuildConfig.VERSION_NAME),
                AndroidPhone(context.applicationContext), BuildConfig.VERSION_NAME)
            if (callTimeoutMs == null) synchronized(this) { shared = engine; sharedFor = key }
            return engine
        }

        fun forget() = synchronized(this) { shared = null; sharedFor = null }

        /** One lock for every engine in the process (the receivers' short-timeout engines included). */
        private val cycle = ReentrantLock()

        /** Something changed: a cycle that is running now runs once more when it finishes. */
        @Volatile private var again = false
        fun requestAgain() { again = true }
    }

    @Volatile var lastResult: Result? = null
        private set

    /** A full cycle. If one is already running, it runs once more when that one finishes. */
    fun runOnce(forceHeartbeat: Boolean = false): Result {
        if (!cycle.tryLock()) {
            again = true
            return Result.OK
        }
        try {
            var result: Result
            do {
                again = false
                result = cycleOnce(forceHeartbeat)
            } while (again && result == Result.OK)
            lastResult = result
            return result
        } finally {
            cycle.unlock()
        }
    }

    /** Only the event upload, within [deadline] (a receiver's goAsync window). The rest is handed to WorkManager. */
    fun uploadNow(deadline: Long): Result {
        val wait = deadline - clock()
        if (wait <= 0 || !cycle.tryLock(wait, TimeUnit.MILLISECONDS)) return Result.OFFLINE
        try {
            return guarded { uploadEvents(deadline) }
        } finally {
            cycle.unlock()
        }
    }

    private fun cycleOnce(forceHeartbeat: Boolean): Result = guarded {
        heartbeatIfDue(forceHeartbeat)
        registerPushToken()
        refreshConfigIfDue()
        backfillIfNeeded()
        uploadEvents()
        uploadMedia()
        sendScheduled()
        processOutbox()
        reportStatuses()
        store.setValue("last_sync_at", "${clock()}")
    }

    private inline fun guarded(block: () -> Unit): Result = try {
        block()
        Result.OK
    } catch (e: DeviceRevoked) {
        Result.REVOKED
    } catch (e: DeviceSuspended) {
        Result.SUSPENDED
    } catch (e: UpgradeRequired) {
        Result.UPGRADE_REQUIRED
    } catch (e: ApiException) {
        Log.i(TAG, "sync failed: ${e.status} ${e.code}")
        Result.OFFLINE
    } catch (e: Exception) {
        // Never let one bad step stop the loop (the Dart loop died on an uncaught platform exception).
        Log.w(TAG, "sync step failed: ${e.javaClass.name}")
        Result.OFFLINE
    }

    // --- Heartbeat and configuration ---------------------------------------------------------------------------

    private fun heartbeatIfDue(force: Boolean) {
        val last = store.value("last_heartbeat_at")?.toLongOrNull() ?: 0
        if (!force && clock() - last < HEARTBEAT_EVERY) return
        heartbeat()
    }

    fun heartbeat(): JSONObject {
        val state = phone.heartbeatState()
            .put("pending_outbox", store.pendingCount())
            .put("app_version", appVersion)
        store.value("last_sync_at")?.toLongOrNull()?.let { state.put("last_sync_at", Instant.ofEpochMilli(it).toString()) }
        val response = api.heartbeat(state)
        store.setValue("last_heartbeat_at", "${clock()}")
        response.optInt("poll_seconds").takeIf { it > 0 }?.let { store.setValue("poll_seconds", "$it") }
        return response
    }

    /** Quick replies and options from the admin, cached for the UI (which never calls the server for them). */
    private fun refreshConfigIfDue() {
        val last = store.value("config_at")?.toLongOrNull() ?: 0
        if (clock() - last < CONFIG_EVERY && store.value("cache.quick_replies") != null) return
        val config = api.config()
        store.setValue("cache.quick_replies", (config.optJSONArray("quick_replies") ?: JSONArray()).toString())
        store.setValue("config_at", "${clock()}")
    }

    /** FCM tokens arrive natively (PushService.onNewToken) and wait in the database until registered here. */
    private fun registerPushToken() {
        val token = store.value("push_token_pending")?.takeIf { it.isNotEmpty() } ?: return
        api.registerPushToken(token)
        store.setValue("push_token_pending", null)
        store.setValue("push_registered", "1")
    }

    // --- Backfill ----------------------------------------------------------------------------------------------

    /** Copies the history inside the backfill window once (newest first), as ordinary upsert events. */
    fun backfillIfNeeded() {
        if (store.value("backfill_done") == "1") return
        val days = store.value("backfill_days")?.toIntOrNull() ?: 90
        val since = clock() - days * 24L * 60 * 60 * 1000
        var offset = store.value("backfill_offset")?.toIntOrNull() ?: 0
        val addresses = linkedSetOf<String>()
        while (true) {
            val page = phone.messagesSince(since, 200, offset)
            if (page.isEmpty()) break
            for (message in page) {
                addresses += message.addresses
                store.appendEvent("message.upsert", payloadWithHashes(message))
                queueParts(message)
            }
            offset += page.size
            store.setValue("backfill_offset", "$offset")
            store.appendEvent("backfill.progress", JSONObject().put("phase", "running").put("done", offset).put("total", offset + if (page.size == 200) 200 else 0))
            if (page.size < 200) break
        }
        // Names only for numbers that appear in conversations (data minimisation), never the whole address book.
        for ((address, name) in phone.contactNames(addresses.toList())) {
            if (name.isNotEmpty()) store.appendEvent("contact.upsert", JSONObject().put("address", address).put("display_name", name).put("photo_hash", ""))
        }
        for (number in phone.blockedNumbers()) store.appendEvent("block.add", JSONObject().put("address", number))
        store.appendEvent("backfill.progress", JSONObject().put("phase", "done").put("done", offset).put("total", offset))
        store.setValue("backfill_done", "1")
        store.setValue("backfill_offset", null)
        Log.i(TAG, "backfill queued $offset messages")
    }

    /** The upsert payload; MMS parts carry their SHA-256 and size (streamed, never the whole file in memory). */
    fun payloadWithHashes(message: ProviderMessage): JSONObject {
        val payload = Provider.payload(message)
        val parts = payload.optJSONArray("parts") ?: return payload
        val kept = JSONArray()
        for (i in 0 until parts.length()) {
            val uri = message.parts[i].uri ?: continue
            val (hash, size) = digest(uri) ?: continue
            kept.put(parts.getJSONObject(i).put("sha256", hash).put("size", size))
        }
        return payload.put("parts", kept)
    }

    private fun digest(uri: String): Pair<String, Long>? = phone.openPart(uri)?.use { input ->
        val digest = MessageDigest.getInstance("SHA-256")
        val buffer = ByteArray(16 * 1024)
        var size = 0L
        while (true) {
            val n = input.read(buffer)
            if (n < 0) break
            digest.update(buffer, 0, n)
            size += n
        }
        digest.digest().joinToString("") { "%02x".format(it) } to size
    }

    private fun queueParts(message: ProviderMessage) {
        if (message.kind != "mms") return
        for (part in message.parts) part.uri?.let { store.addPendingMedia(message.providerId, message.date, part.seq.toInt(), it, part.size) }
    }

    // --- Upload ------------------------------------------------------------------------------------------------

    /** Uploads the durable outbox in batches (≤ 200 events, < 1 MB) and deletes what the server acknowledged. */
    fun uploadEvents(deadline: Long = Long.MAX_VALUE): Int {
        var uploaded = 0
        while (clock() < deadline) {
            val rows = store.pendingEvents(MAX_BATCH_EVENTS)
            if (rows.isEmpty()) return uploaded
            val batch = JSONArray()
            var bytes = 0
            var lastSeq = 0L
            for (row in rows) {
                bytes += row.payload.length + 64
                if (batch.length() > 0 && bytes > MAX_BATCH_BYTES) break
                batch.put(JSONObject().put("seq", row.seq).put("type", row.type).put("payload", JSONObject(row.payload)))
                lastSeq = row.seq
            }
            val result = api.syncEvents(batch)
            val acked = result.getLong("acked_seq")
            val rejected = result.optJSONArray("rejected")?.length() ?: 0
            if (rejected > 0) Log.i(TAG, "server rejected $rejected events")
            store.acknowledge(acked)
            uploaded += batch.length()
            if (acked < lastSeq) return uploaded // the server is behind; try again next cycle
        }
        return uploaded
    }

    fun uploadMedia() {
        for (part in store.pendingMedia()) {
            var offset = part.offset
            var restarts = 0
            while (true) {
                val chunk = readChunk(part.uri, offset)
                if (chunk == null || chunk.isEmpty()) {
                    store.deleteMedia(part) // uploaded to the end, or the part no longer exists on the phone
                    break
                }
                try {
                    val result = api.uploadChunk(part.providerId, part.date, part.seq, offset, chunk)
                    offset = result.getLong("received_bytes")
                    if (result.optBoolean("complete")) {
                        store.deleteMedia(part)
                        break
                    }
                } catch (e: ApiException) {
                    if (e.code == "checksum_mismatch") {
                        store.setMediaOffset(part, 0) // start again from scratch next cycle
                        break
                    }
                    if (e.code == "offset_mismatch" && restarts++ < 2) {
                        offset = 0
                        continue
                    }
                    if (e.status == 404) break // not declared yet: the event upload comes first next time
                    throw e
                }
                store.setMediaOffset(part, offset)
            }
        }
    }

    private fun readChunk(uri: String, offset: Long): ByteArray? = phone.openPart(uri)?.use { input ->
        var skipped = 0L
        while (skipped < offset) {
            val n = input.skip(offset - skipped)
            if (n <= 0) break
            skipped += n
        }
        val buffer = ByteArray(CHUNK_SIZE)
        var filled = 0
        while (filled < CHUNK_SIZE) {
            val n = input.read(buffer, filled, CHUNK_SIZE - filled)
            if (n < 0) break
            filled += n
        }
        buffer.copyOf(filled)
    }

    // --- Outbox: admin replies and commands --------------------------------------------------------------------

    /**
     * Claims due admin messages and sends each exactly once. The sender records `sending` durably before it calls
     * SmsManager and refuses a client_uuid it has already started, so a crash can never cause a duplicate.
     */
    fun processOutbox(): Int {
        store.markStaleSendsUnknown(clock() - STALE_SEND_AFTER, clock())
        val claim = api.claimOutbox()
        val acks = JSONArray()
        val commands = claim.optJSONArray("commands") ?: JSONArray()
        for (i in 0 until commands.length()) {
            val command = commands.getJSONObject(i)
            acks.put(JSONObject().put("id", command.get("id")).put("ok", runCommand(command.getString("kind"), command.optJSONObject("payload") ?: JSONObject())))
        }
        var sent = 0
        val messages = claim.optJSONArray("messages") ?: JSONArray()
        for (i in 0 until messages.length()) {
            val item = messages.getJSONObject(i)
            val clientUuid = item.getString("client_uuid")
            if (store.outboundExists(clientUuid)) continue // already started: its state is reported below
            val expires = item.optString("expires_at").takeIf { it.isNotEmpty() }?.let { runCatching { Instant.parse(it).toEpochMilli() }.getOrNull() }
            if (expires != null && clock() > expires) {
                store.recordExpired(clientUuid, clock())
                continue
            }
            val addresses = item.getJSONArray("addresses").let { a -> List(a.length()) { a.getString(it) } }
            val result = phone.send(SendRequest(
                clientUuid = clientUuid, addresses = addresses, body = item.getString("body"),
                subscriptionId = if (item.isNull("subscription_id")) null else item.optLong("subscription_id"), deliveryReport = true,
                attachmentUris = emptyList(), origin = "admin", sentBy = item.optString("sent_by").takeIf { !item.isNull("sent_by") && it.isNotEmpty() },
            ))
            if (result.state == "sending") sent++
        }
        if (acks.length() > 0) api.reportStatus(commandAcks = acks)
        return sent
    }

    private fun runCommand(kind: String, payload: JSONObject): Boolean = try {
        when (kind) {
            "mark_read" -> { phone.markThreadRead(payload.getLong("thread_id")); true }
            "block" -> { phone.block(payload.getString("address")); true }
            "unblock" -> { phone.unblock(payload.getString("address")); true }
            "resync" -> {
                store.setValue("backfill_done", null)
                if (payload.has("days") && !payload.isNull("days")) store.setValue("backfill_days", "${payload.getInt("days")}")
                true
            }
            else -> false
        }
    } catch (e: Exception) {
        false
    }

    /** Sends every state change the server has not seen yet (sending → sent → delivered, failed, unknown). */
    fun reportStatuses() {
        val rows = store.unreportedOutbound()
        if (rows.isEmpty()) return
        val reports = JSONArray()
        for (row in rows) reports.put(JSONObject().put("client_uuid", row.clientUuid).put("status", row.state).put("at", row.updatedAt).apply {
            row.errorCode?.let { put("error_code", it) }
            row.parts?.let { put("parts", it) }
        })
        val result = api.reportStatus(reports = reports)
        val byUuid = rows.associateBy { it.clientUuid }
        val results = result.optJSONArray("results") ?: JSONArray()
        // ok, ignored (the server already knows better) or unknown_message: none of them is worth sending again.
        for (i in 0 until results.length()) byUuid[results.getJSONObject(i).optString("client_uuid")]?.let { store.markReported(it.clientUuid, it.state) }
    }

    // --- Phone-side scheduled sends ----------------------------------------------------------------------------

    fun sendScheduled() {
        for (item in store.dueScheduled(clock())) {
            phone.send(SendRequest(clientUuid = item.clientUuid, addresses = item.addresses, body = item.body, subscriptionId = item.subscriptionId,
                deliveryReport = true, attachmentUris = emptyList(), origin = "phone"))
            store.deleteScheduled(item.clientUuid)
        }
    }
}
