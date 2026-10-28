package com.kilimanjaro.communicationmanager.sms

import com.kilimanjaro.communicationmanager.sms.bridge.ProviderMessage
import com.kilimanjaro.communicationmanager.sms.bridge.SendRequest
import com.kilimanjaro.communicationmanager.sms.bridge.SendResult
import com.kilimanjaro.communicationmanager.sms.data.SyncStore
import com.kilimanjaro.communicationmanager.sms.security.SecureHttp
import com.kilimanjaro.communicationmanager.sms.sync.Backoff
import com.kilimanjaro.communicationmanager.sms.sync.DeviceApiClient
import com.kilimanjaro.communicationmanager.sms.sync.HttpTransport
import com.kilimanjaro.communicationmanager.sms.sync.NativeSyncEngine
import com.kilimanjaro.communicationmanager.sms.sync.Phone
import com.kilimanjaro.communicationmanager.sms.sync.TOKEN_PATH
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
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.ByteArrayInputStream
import java.io.InputStream
import java.time.Instant
import java.util.concurrent.TimeUnit
import kotlin.random.Random

/**
 * The Dart sync engine's tests (test/sync_engine_test.dart, removed with it), ported to the native engine: same fake
 * server, same expectations. The engine runs against MockWebServer over real HTTP and against the real store SQL.
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
    private lateinit var engine: NativeSyncEngine
    private val signed = mutableListOf<String>()

    /** A tiny in-memory device API (the Dart FakeServer). */
    class FakeServer : Dispatcher() {
        var ackedSeq = 0L
        val events = mutableListOf<JSONObject>()
        var claimable = JSONArray()
        var commands = JSONArray()
        val reports = mutableListOf<JSONObject>()
        val acks = mutableListOf<JSONObject>()
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
            return when (path.removePrefix("/api/v1/device/")) {
                "heartbeat/" -> { heartbeats++; json(200, JSONObject().put("status", "active").put("attention", JSONArray()).put("server_time", 0).put("poll_seconds", 20)) }
                "config/" -> json(200, JSONObject().put("quick_replies", JSONArray().put(JSONObject().put("id", 1).put("title", "Asante").put("body", "Asante sana!"))))
                "sync/events/" -> {
                    val batch = data.getJSONArray("events")
                    for (i in 0 until batch.length()) {
                        val event = batch.getJSONObject(i)
                        if (event.getLong("seq") > ackedSeq) events += event
                        ackedSeq = maxOf(ackedSeq, event.getLong("seq"))
                    }
                    json(200, JSONObject().put("acked_seq", ackedSeq).put("processed", batch.length()).put("skipped", 0).put("rejected", JSONArray()))
                }
                "outbox/claim/" -> {
                    val result = JSONObject().put("messages", claimable).put("commands", commands).put("lease_seconds", 120)
                    commands = JSONArray()
                    json(200, result)
                }
                "outbox/status/" -> {
                    val incoming = data.getJSONArray("reports")
                    val results = JSONArray()
                    for (i in 0 until incoming.length()) {
                        reports += incoming.getJSONObject(i)
                        results.put(JSONObject().put("client_uuid", incoming.getJSONObject(i).getString("client_uuid")).put("result", "ok"))
                    }
                    val commandAcks = data.getJSONArray("command_acks")
                    for (i in 0 until commandAcks.length()) acks += commandAcks.getJSONObject(i)
                    json(200, JSONObject().put("results", results))
                }
                "push-token/" -> json(200, JSONObject())
                else -> json(404, JSONObject().put("code", "not_found"))
            }
        }
    }

    class FakePhone(private val store: () -> SyncStore) : Phone {
        var history = listOf<ProviderMessage>()
        var names = mapOf<String, String>()
        val sent = mutableListOf<SendRequest>()
        val calls = mutableListOf<String>()
        override fun heartbeatState() = JSONObject().put("is_default_sms_app", true).put("battery", 80).put("background_restricted", false).put("standby_bucket", 10)
        override fun messagesSince(since: Long, limit: Int, offset: Int) = history.filter { it.date >= since }.drop(offset).take(limit)
        override fun openPart(uri: String): InputStream = ByteArrayInputStream(ByteArray(0))
        override fun contactNames(addresses: List<String>) = names.filterKeys { it in addresses }
        override fun blockedNumbers() = emptyList<String>()
        /** Mirrors the native at-most-once guard (SyncStore.startOutbound before SmsManager). */
        override fun send(request: SendRequest): SendResult {
            if (request.origin == "admin" && !store().startOutbound(request.clientUuid, request.sentBy)) return SendResult(clientUuid = request.clientUuid, state = "duplicate")
            sent += request
            return SendResult(clientUuid = request.clientUuid, state = "sending", providerId = 900L + sent.size)
        }
        override fun markThreadRead(threadId: Long) { calls += "read:$threadId" }
        override fun block(address: String) { calls += "block:$address" }
        override fun unblock(address: String) { calls += "unblock:$address" }
    }

    private fun message(id: Long, date: Long) = ProviderMessage(
        providerId = id, kind = "sms", threadId = 7, addresses = listOf("+255754210331"), body = "Habari", date = date, outbound = false, read = true,
        status = "received", subscriptionId = 1, errorCode = null, parts = emptyList(), subject = null,
    )

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
        phone = FakePhone { store }
        engine = NativeSyncEngine(store, api(), phone, "1.0.2") { now }
    }

    @After
    fun tearDown() {
        http.shutdown()
        sql.close()
    }

    @Test
    fun backfillTurnsHistoryIntoUpsertContactAndProgressEventsOnce() {
        phone.history = listOf(message(1, now - 2 * 86_400_000L), message(2, now - 400 * 86_400_000L))
        phone.names = mapOf("+255754210331" to "Neema Mushi")
        assertEquals(NativeSyncEngine.Result.OK, engine.runOnce())
        val types = server.events.map { it.getString("type") }
        assertEquals(1, types.count { it == "message.upsert" }) // outside the 90-day window is skipped
        assertTrue("contact.upsert" in types)
        assertEquals("backfill.progress", types.last())
        assertEquals(0, store.pendingCount()) // acknowledged events are deleted
        server.events.clear()
        engine.runOnce()
        assertTrue(server.events.isEmpty())
        assertEquals(1, server.heartbeats) // heartbeats only every 5 minutes
        assertEquals("[{\"id\":1,\"title\":\"Asante\",\"body\":\"Asante sana!\"}]", store.value("cache.quick_replies")) // cached for the UI
    }

    @Test
    fun theDurableOutboxSurvivesBeingOfflineAndUploadsInOrderLater() {
        store.setValue("backfill_done", "1")
        store.appendEvent("message.upsert", JSONObject().put("provider_id", 1))
        store.appendEvent("message.read", JSONObject().put("provider_id", 1))
        server.offline = true
        assertEquals(NativeSyncEngine.Result.OFFLINE, engine.runOnce())
        assertEquals(2, store.pendingCount())
        server.offline = false
        assertEquals(NativeSyncEngine.Result.OK, engine.runOnce())
        assertEquals(listOf(1L, 2L), server.events.map { it.getLong("seq") })
        assertEquals(0, store.pendingCount())
    }

    @Test
    fun adminMessagesAreSentAtMostOnceAndTheirStatesReported() {
        store.setValue("backfill_done", "1")
        server.claimable = JSONArray().put(JSONObject().put("client_uuid", "u-1").put("kind", "sms").put("addresses", JSONArray().put("+255754210331"))
            .put("body", "Karibu").put("subscription_id", 1).put("sent_by", "Amina").put("expires_at", Instant.ofEpochMilli(now + 3_600_000).toString()))
        engine.runOnce()
        assertEquals("u-1", phone.sent.single().clientUuid)
        assertEquals("admin", phone.sent.single().origin)
        assertEquals("Amina", phone.sent.single().sentBy)
        // The lease expired and the server offers it again: the phone never sends a started message twice.
        engine.runOnce()
        assertEquals(1, phone.sent.size)
        assertEquals("sending", server.reports.single().getString("status"))
        // The native receiver records "sent": reported once.
        store.updateOutbound("u-1", "sent", parts = 1)
        engine.runOnce()
        engine.runOnce()
        assertEquals(listOf("sending", "sent"), server.reports.map { it.getString("status") })
    }

    @Test
    fun aSendThatNeverGotAResultBecomesUnknownAndExpiredMessagesAreNotSent() {
        store.setValue("backfill_done", "1")
        store.startOutbound("old", null)
        sql.exec("UPDATE outbound_states SET updated_at = ${now - 3_600_000} WHERE client_uuid = 'old'")
        server.claimable = JSONArray().put(JSONObject().put("client_uuid", "late").put("kind", "sms").put("addresses", JSONArray().put("+255754210331"))
            .put("body", "x").put("expires_at", Instant.ofEpochMilli(now - 60_000).toString()))
        engine.runOnce()
        assertTrue(phone.sent.isEmpty())
        val byUuid = server.reports.associateBy { it.getString("client_uuid") }
        assertEquals("unknown", byUuid["old"]!!.getString("status"))
        assertEquals("failed", byUuid["late"]!!.getString("status"))
        assertEquals(1003, byUuid["late"]!!.getInt("error_code"))
    }

    @Test
    fun commandsFromTheAdminRunAndAreAcknowledged() {
        store.setValue("backfill_done", "1")
        server.commands = JSONArray()
            .put(JSONObject().put("id", 5).put("kind", "mark_read").put("payload", JSONObject().put("thread_id", 7)))
            .put(JSONObject().put("id", 6).put("kind", "block").put("payload", JSONObject().put("address", "+255700111222")))
            .put(JSONObject().put("id", 7).put("kind", "nonsense").put("payload", JSONObject()))
        engine.runOnce()
        assertEquals(listOf("read:7", "block:+255700111222"), phone.calls)
        assertEquals(listOf(true, true, false), server.acks.map { it.getBoolean("ok") })
    }

    @Test
    fun aRevokedPhoneStopsSyncing() {
        server.revoked = true
        assertEquals(NativeSyncEngine.Result.REVOKED, engine.runOnce(forceHeartbeat = true))
    }

    @Test
    fun accessTokensAreMintedWithAProofOfPossessionSignatureReusedAndRefreshedOnceWhenExpired() {
        store.setValue("backfill_done", "1")
        engine.runOnce()
        engine.runOnce()
        assertEquals(1, server.tokens)
        assertEquals(listOf("CMSMS-AUTH-1", "POST", TOKEN_PATH, "dev"), signed.first().split("\n").subList(0, 4))
        server.expireNextToken = true
        assertEquals(NativeSyncEngine.Result.OK, engine.runOnce())
        assertEquals(2, server.tokens)
        val heartbeat = generateSequence { http.takeRequest(0, TimeUnit.SECONDS) }.first { it.path == "/api/v1/device/heartbeat/" }
        assertEquals("Bearer t1", heartbeat.getHeader("Authorization"))
        assertEquals("1.0.2", heartbeat.getHeader("X-CM-App-Version"))
        assertEquals(false, JSONObject(heartbeat.body.readUtf8()).getBoolean("background_restricted"))
    }

    @Test
    fun aRequestDuringACycleRunsOnceMoreAfterIt() {
        store.setValue("backfill_done", "1")
        // A message arrives while the cycle is uploading: it is uploaded in the same runOnce, not left for the next poll.
        val slow = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                if (request.path == "/api/v1/device/sync/events/" && store.pendingCount() == 1 && server.events.isEmpty()) {
                    store.appendEvent("message.upsert", JSONObject().put("provider_id", 2))
                    NativeSyncEngine.requestAgain()
                }
                return server.dispatch(request)
            }
        }
        http.dispatcher = slow
        store.appendEvent("message.upsert", JSONObject().put("provider_id", 1))
        engine.runOnce()
        assertEquals(0, store.pendingCount())
        assertEquals(2, server.events.size)
    }

    @Test
    fun theReceiverUploadStopsAtItsDeadline() {
        store.setValue("backfill_done", "1")
        store.appendEvent("message.upsert", JSONObject().put("provider_id", 1))
        var clock = now
        val receiver = NativeSyncEngine(store, api({ clock }), phone, "1.0.2") { clock }
        clock = now + 9_000
        assertEquals(NativeSyncEngine.Result.OFFLINE, receiver.uploadNow(deadline = now + 8_000)) // window already over: nothing sent
        assertEquals(1, store.pendingCount())
        clock = now
        assertEquals(NativeSyncEngine.Result.OK, receiver.uploadNow(deadline = now + 8_000))
        assertEquals(0, store.pendingCount())
    }

    @Test
    fun aTransportFailureNeverEscapesTheLoop() {
        store.setValue("backfill_done", "1")
        val broken = NativeSyncEngine(store, DeviceApiClient({ _, _, _, _ -> throw IllegalArgumentException("Server not allowed") }, "https://x", "dev", { it }, "1"), phone, "1") { now }
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
