package com.kilimanjaro.communicationmanager.phone.sync

import android.content.Context
import android.util.Log
import com.kilimanjaro.communicationmanager.phone.BuildConfig
import com.kilimanjaro.communicationmanager.phone.data.SyncStore
import com.kilimanjaro.communicationmanager.phone.security.DeviceKey
import com.kilimanjaro.communicationmanager.phone.security.SecureHttp
import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import java.util.concurrent.TimeUnit
import java.util.concurrent.locks.ReentrantLock
import kotlin.math.min
import kotlin.random.Random

/** What the engine needs from the phone. Production: [AndroidPhone]; tests: a fake. */
interface Phone {
    fun heartbeatState(): JSONObject
}

/**
 * The Calls part of a cycle (CallsSync in the app; a fake in tests). Called after the heartbeat with the server's
 * capabilities, and once per cycle while Calls is on for this phone.
 */
interface CallsHooks {
    fun onCapabilities(capabilities: JSONObject)
    fun cycle(api: DeviceApiClient, force: Boolean)
}

/** Exponential backoff with full jitter. Never a tight loop: the shortest wait is [base]. */
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
 * One sync cycle of OCM Phone: heartbeat (when due) → push token → Calls (call log, config, caller-ID directory,
 * call-back tasks) → upload events. The same protocol, idempotency and outbox as OCM Messages' engine, without SMS.
 *
 * Safe to call from WorkManager, an FCM wake-up or the in-call service: cycles are serialised by a lock, every step is
 * idempotent, and a sync requested during a cycle runs once more right after it.
 */
class NativeSyncEngine(
    private val store: SyncStore,
    private val api: DeviceApiClient,
    private val phone: Phone,
    private val appVersion: String,
    private val calls: CallsHooks? = null,
    private val clock: () -> Long = System::currentTimeMillis,
) {
    enum class Result { OK, OFFLINE, SUSPENDED, REVOKED, UPGRADE_REQUIRED, NOT_ENROLLED }

    companion object {
        const val MAX_BATCH_EVENTS = 200
        const val MAX_BATCH_BYTES = 900 * 1024 // under the server's 1 MB limit
        const val HEARTBEAT_EVERY = 5 * 60_000L
        private const val TAG = "OcmSync" // ids, counts and codes only: never numbers or names

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
                AndroidPhone(context.applicationContext), BuildConfig.VERSION_NAME, calls = com.kilimanjaro.communicationmanager.phone.dialer.CallsSync(context.applicationContext))
            if (callTimeoutMs == null) synchronized(this) { shared = engine; sharedFor = key }
            return engine
        }

        fun forget() = synchronized(this) { shared = null; sharedFor = null }

        /** One lock for every engine in the process. */
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

    /** Only the event upload, within [deadline] (right after a call ends, while the in-call service still runs). */
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
        calls?.let { hooks -> runCatching { hooks.cycle(api, forceHeartbeat) }.onFailure { if (it is ApiException && it !is CallsDisabled) throw it } }
        uploadEvents()
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
        Log.w(TAG, "sync step failed: ${e.javaClass.name}")
        Result.OFFLINE
    }

    // --- Heartbeat ---------------------------------------------------------------------------------------------

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
        response.optJSONObject("capabilities")?.let { caps -> calls?.onCapabilities(caps) }
        return response
    }

    /** FCM tokens arrive natively (PushService.onNewToken) and wait in the database until registered here. */
    private fun registerPushToken() {
        val token = store.value("push_token_pending")?.takeIf { it.isNotEmpty() } ?: return
        api.registerPushToken(token)
        store.setValue("push_token_pending", null)
        store.setValue("push_registered", "1")
    }

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
}

/** 403 calls_not_enabled / platform_disabled on a Calls endpoint: skip Calls this cycle, keep uploading what is queued. */
class CallsDisabled(code: String) : ApiException(403, code)
