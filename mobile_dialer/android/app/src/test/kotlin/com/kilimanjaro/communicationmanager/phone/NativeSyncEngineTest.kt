package com.kilimanjaro.communicationmanager.phone

import com.kilimanjaro.communicationmanager.phone.data.SyncStore
import com.kilimanjaro.communicationmanager.phone.security.SecureHttp
import com.kilimanjaro.communicationmanager.phone.sync.Backoff
import com.kilimanjaro.communicationmanager.phone.sync.CallsHooks
import com.kilimanjaro.communicationmanager.phone.sync.DeviceApiClient
import com.kilimanjaro.communicationmanager.phone.sync.HttpTransport
import com.kilimanjaro.communicationmanager.phone.sync.NativeSyncEngine
import com.kilimanjaro.communicationmanager.phone.sync.Phone
import com.kilimanjaro.communicationmanager.phone.sync.TOKEN_PATH
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.time.Instant
import java.util.concurrent.TimeUnit
import kotlin.random.Random

/**
 * OCM Phone's sync engine against MockWebServer over real HTTP and the real store SQL: the same protocol as OCM
 * Messages (outbox, proof-of-possession tokens, revocation), the Calls hooks, and no SMS endpoint ever.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class NativeSyncEngineTest {
    private val now = Instant.parse("2026-10-27T09:00:00Z").toEpochMilli()
    private lateinit var http: MockWebServer
    private lateinit var server: FakeServer
    private lateinit var sql: FrameworkSql
    private lateinit var store: SyncStore
    private lateinit var phone: FakePhone
    private lateinit var calls: FakeCalls
    private lateinit var engine: NativeSyncEngine
    private val signed = mutableListOf<String>()

    /** A tiny in-memory device API (the Dart FakeServer). */
    class FakeServer : Dispatcher() {
        var ackedSeq = 0L
        val events = mutableListOf<JSONObject>()
        val paths = mutableListOf<String>()
        var heartbeats = 0
        var tokens = 0
        @Volatile var offline = false
        var revoked = false
        var expireNextToken = false

        private fun json(status: Int, body: Any) = MockResponse().setResponseCode(status).setHeader("Content-Type", "application/json").setBody(body.toString())

        override fun dispatch(request: RecordedRequest): MockResponse {
            if (offline) return MockResponse().setResponseCode(503)
            val path = request.requestUrl!!.encodedPath
            if (path == TOKEN_PATH) {
                if (revoked) return json(401, JSONObject().put("code", "device_revoked"))
                tokens++
                return json(200, JSONObject().put("access_token", "t$tokens").put("expires_in", 900))
            }
            if (expireNextToken) {
                expireNextToken = false
                return json(401, JSONObject().put("code", "token_expired"))
            }
            val data = request.body.readUtf8().let { if (it.isEmpty()) JSONObject() else JSONObject(it) }
            paths += path.removePrefix("/api/v1/device/")
            return when (path.removePrefix("/api/v1/device/")) {
                "heartbeat/" -> {
                    heartbeats++
                    json(200, JSONObject().put("status", "active").put("attention", JSONArray()).put("server_time", 0)
                        .put("capabilities", JSONObject().put("sms", false).put("calls", true)))
                }
                "sync/events/" -> {
                    val batch = data.getJSONArray("events")
                    for (i in 0 until batch.length()) {
                        val event = batch.getJSONObject(i)
                        if (event.getLong("seq") > ackedSeq) events += event
                        ackedSeq = maxOf(ackedSeq, event.getLong("seq"))
                    }
                    json(200, JSONObject().put("acked_seq", ackedSeq).put("processed", batch.length()).put("skipped", 0).put("rejected", JSONArray()))
                }
                "push-token/" -> json(200, JSONObject())
                else -> json(404, JSONObject().put("code", "not_found"))
            }
        }
    }

    class FakePhone : Phone {
        override fun heartbeatState() = JSONObject().put("is_default_dialer", true).put("battery", 80).put("background_restricted", false).put("standby_bucket", 10)
    }

    /** Records what the engine asks of the Calls part (CallsSync in the app). */
    class FakeCalls : CallsHooks {
        val capabilities = mutableListOf<JSONObject>()
        var cycles = 0
        override fun onCapabilities(capabilities: JSONObject) { this.capabilities += capabilities }
        override fun cycle(api: DeviceApiClient, force: Boolean) { cycles++ }
    }

    /** Plain HTTP to MockWebServer (production goes through SecureHttp: HTTPS, pins, allow-list). */
    private fun transport(client: OkHttpClient = OkHttpClient()) = HttpTransport { method, url, headers, body ->
        try {
            val type = headers["Content-Type"]?.toMediaTypeOrNull()
            val request = Request.Builder().url(url).method(method, body?.toRequestBody(type) ?: if (method == "POST") ByteArray(0).toRequestBody(type) else null)
                .apply { headers.forEach { (k, v) -> header(k, v) } }.build()
            client.newCall(request).execute().use { SecureHttp.Response(it.code, it.body.bytes()) }
        } catch (e: java.io.IOException) {
            SecureHttp.Response(0, ByteArray(0))
        }
    }

    private fun api(clock: () -> Long = { now }, client: OkHttpClient = OkHttpClient()) =
        DeviceApiClient(transport(client), http.url("/").toString(), "dev", { signed += String(it); byteArrayOf(1, 2, 3) }, "1.0.2", clock)

    @Before
    fun setUp() {
        server = FakeServer()
        http = MockWebServer().apply { dispatcher = server; start() }
        sql = FrameworkSql.withDriftSchema()
        store = SyncStore(sql)
        store.setValue("device_id", "dev")
        phone = FakePhone()
        calls = FakeCalls()
        engine = NativeSyncEngine(store, api(), phone, "1.0.2", calls) { now }
    }

    @After
    fun tearDown() {
        http.shutdown()
        sql.close()
    }

    @Test
    fun theDurableOutboxSurvivesBeingOfflineAndUploadsInOrderLater() {
        store.appendEvent("call.upsert", JSONObject().put("call_log_id", 1))
        store.appendEvent("call.event", JSONObject().put("call_key", "k1"))
        server.offline = true
        assertEquals(NativeSyncEngine.Result.OFFLINE, engine.runOnce())
        assertEquals(2, store.pendingCount())
        server.offline = false
        assertEquals(NativeSyncEngine.Result.OK, engine.runOnce())
        assertEquals(listOf(1L, 2L), server.events.map { it.getLong("seq") })
        assertEquals(0, store.pendingCount())
    }

    @Test
    fun aCycleFollowsTheCapabilitiesRunsCallsAndNeverTouchesSmsEndpoints() {
        store.appendEvent("call.upsert", JSONObject().put("call_log_id", 1))
        assertEquals(NativeSyncEngine.Result.OK, engine.runOnce(forceHeartbeat = true))
        assertEquals(true, calls.capabilities.single().getBoolean("calls"))
        assertEquals(1, calls.cycles)
        assertEquals(1, server.events.size)
        assertFalse(server.paths.any { it.startsWith("outbox/") || it == "config/" || it.startsWith("sync/media") })
    }

    @Test
    fun aRevokedPhoneStopsSyncing() {
        server.revoked = true
        assertEquals(NativeSyncEngine.Result.REVOKED, engine.runOnce(forceHeartbeat = true))
    }

    @Test
    fun accessTokensAreMintedWithAProofOfPossessionSignatureReusedAndRefreshedOnceWhenExpired() {
        engine.runOnce()
        engine.runOnce()
        assertEquals(1, server.tokens)
        assertEquals(listOf("CMSMS-AUTH-1", "POST", TOKEN_PATH, "dev"), signed.first().split("\n").subList(0, 4))
        server.expireNextToken = true
        store.appendEvent("call.upsert", JSONObject().put("call_log_id", 1)) // the engine only calls the server with something to do
        assertEquals(NativeSyncEngine.Result.OK, engine.runOnce())
        assertEquals(2, server.tokens)
        val heartbeat = generateSequence { http.takeRequest(0, TimeUnit.SECONDS) }.first { it.path == "/api/v1/device/heartbeat/" }
        assertEquals("Bearer t1", heartbeat.getHeader("Authorization"))
        assertEquals("1.0.2", heartbeat.getHeader("X-CM-App-Version"))
        assertEquals(false, JSONObject(heartbeat.body.readUtf8()).getBoolean("background_restricted"))
    }

    @Test
    fun aRequestDuringACycleRunsOnceMoreAfterIt() {
        // A call ends while the cycle is uploading: it is uploaded in the same runOnce, not left for the next poll.
        val slow = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                if (request.path == "/api/v1/device/sync/events/" && store.pendingCount() == 1 && server.events.isEmpty()) {
                    store.appendEvent("call.upsert", JSONObject().put("call_log_id", 2))
                    NativeSyncEngine.requestAgain()
                }
                return server.dispatch(request)
            }
        }
        http.dispatcher = slow
        store.appendEvent("call.upsert", JSONObject().put("call_log_id", 1))
        engine.runOnce()
        assertEquals(0, store.pendingCount())
        assertEquals(2, server.events.size)
    }

    @Test
    fun theAfterCallUploadStopsAtItsDeadline() {
        store.appendEvent("call.upsert", JSONObject().put("call_log_id", 1))
        var clock = now
        val receiver = NativeSyncEngine(store, api({ clock }), phone, "1.0.2", calls) { clock }
        clock = now + 9_000
        assertEquals(NativeSyncEngine.Result.OFFLINE, receiver.uploadNow(deadline = now + 8_000)) // window already over: nothing sent
        assertEquals(1, store.pendingCount())
        clock = now
        assertEquals(NativeSyncEngine.Result.OK, receiver.uploadNow(deadline = now + 8_000))
        assertEquals(0, store.pendingCount())
    }

    @Test
    fun aTransportFailureNeverEscapesTheLoop() {
        val broken = NativeSyncEngine(store, DeviceApiClient({ _, _, _, _ -> throw IllegalArgumentException("Server not allowed") }, "https://x", "dev", { it }, "1"), phone, "1", calls) { now }
        assertEquals(NativeSyncEngine.Result.OFFLINE, broken.runOnce())
    }

    @Test
    fun backoffGrowsWithJitterAndNeverSpins() {
        val backoff = Backoff(random = Random(1))
        val waits = List(12) { backoff.next() }
        assertTrue(waits.all { it in 2_000..300_000 })
        backoff.reset()
        assertEquals(0, backoff.failures)
    }
}
