package com.kilimanjaro.communicationmanager.phone.sync

import android.util.Base64
import com.kilimanjaro.communicationmanager.phone.security.SecureHttp
import org.json.JSONArray
import org.json.JSONObject
import java.security.SecureRandom

/** Every HTTPS request of the sync engine. Production: [SecureHttp] (pinned OkHttp); tests: MockWebServer. */
fun interface HttpTransport {
    /** Status 0 = no response (offline, TLS or pin failure, refused host). */
    fun send(method: String, url: String, headers: Map<String, String>, body: ByteArray?): SecureHttp.Response
}

/** Signs with the non-exportable Keystore key (ECDSA P-256 / SHA-256, DER). */
fun interface DeviceSigner {
    fun sign(message: ByteArray): ByteArray
}

open class ApiException(val status: Int, val code: String) : Exception("ApiException($status, $code)") {
    val retryable get() = status == 0 || status == 408 || status == 429 || status >= 500
}
class DeviceRevoked : ApiException(401, "device_revoked")
class DeviceSuspended : ApiException(403, "device_suspended")
class UpgradeRequired : ApiException(426, "upgrade_required")

const val TOKEN_PATH = "/api/v1/device/auth/token/"

/** `CMSMS-<PURPOSE>-1\n<field>\n…`: a signature for one purpose can never be replayed as another. */
fun canonical(purpose: String, fields: List<String>): ByteArray = (listOf("CMSMS-$purpose-1") + fields).joinToString("\n").toByteArray()

/**
 * The phone-facing API (/api/v1/device/…), ported from lib/core/api/device_api.dart (the Dart client now only enrolls).
 * Short-lived access tokens are minted on demand from a signed request; no long-lived bearer secret is stored.
 * The token lives in memory only, so every process (service, worker, receiver) mints its own.
 */
class DeviceApiClient(
    private val transport: HttpTransport,
    private val server: String,
    private val deviceId: String,
    private val signer: DeviceSigner,
    private val appVersion: String,
    private val clock: () -> Long = System::currentTimeMillis,
) {
    private var token: String? = null
    private var expires = 0L
    private val random = SecureRandom()

    private fun url(path: String) = server.trimEnd('/') + "/api/v1/device/" + path

    private fun nonce(): String = ByteArray(18).also { random.nextBytes(it) }.let { Base64.encodeToString(it, Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING) }

    private fun decode(response: SecureHttp.Response): JSONObject {
        val data = try {
            val text = String(response.body).trim()
            when {
                text.isEmpty() -> JSONObject()
                text.startsWith("[") -> JSONObject().put("__array", JSONArray(text))
                else -> JSONObject(text)
            }
        } catch (e: org.json.JSONException) {
            JSONObject()
        }
        if (response.status in 200..299) return data
        val code = data.optString("code").ifEmpty { "http_${response.status}" }
        if (code == "device_revoked") throw DeviceRevoked()
        if (code == "device_suspended") throw DeviceSuspended()
        if (response.status == 426) throw UpgradeRequired()
        throw ApiException(response.status, code)
    }

    @Synchronized
    private fun accessToken(force: Boolean): String {
        val current = token
        if (!force && current != null && clock() < expires) return current
        val timestamp = clock() / 1000
        val nonce = nonce()
        val signature = Base64.encodeToString(signer.sign(canonical("AUTH", listOf("POST", TOKEN_PATH, deviceId, "$timestamp", nonce))), Base64.NO_WRAP)
        val body = JSONObject().put("device_id", deviceId).put("timestamp", timestamp).put("nonce", nonce).put("signature", signature)
        val data = decode(transport.send("POST", server.trimEnd('/') + TOKEN_PATH, mapOf("Content-Type" to "application/json", "Accept" to "application/json"), body.toString().toByteArray()))
        token = data.getString("access_token")
        expires = clock() + (data.getLong("expires_in") - 30) * 1000
        return token!!
    }

    fun forgetToken() = synchronized(this) { token = null; expires = 0 }

    private fun authorized(method: String, path: String, json: JSONObject? = null, raw: ByteArray? = null, contentType: String? = null): JSONObject {
        for (attempt in 0..1) {
            val headers = mutableMapOf("Authorization" to "Bearer ${accessToken(force = attempt > 0)}", "X-CM-App-Version" to appVersion, "Accept" to "application/json")
            val body = when {
                json != null -> json.toString().toByteArray().also { headers["Content-Type"] = "application/json" }
                else -> raw.also { contentType?.let { headers["Content-Type"] = it } }
            }
            val response = transport.send(method, url(path), headers, body)
            if (response.status == 401 && attempt == 0) {
                try {
                    decode(response)
                } catch (e: DeviceRevoked) {
                    throw e
                } catch (e: ApiException) {
                    if (e.code == "token_expired" || e.code == "invalid_token") {
                        forgetToken()
                        continue
                    }
                    throw e
                }
            }
            return decode(response)
        }
        throw ApiException(401, "invalid_token")
    }

    fun heartbeat(state: JSONObject) = authorized("POST", "heartbeat/", state)
    fun registerPushToken(token: String) = authorized("POST", "push-token/", JSONObject().put("token", token))
    fun syncEvents(events: JSONArray) = authorized("POST", "sync/events/", JSONObject().put("events", events))
    // Calls (only on phones the server enabled for Calls; 403 calls_not_enabled otherwise).
    fun callsConfig() = authorized("GET", "calls/config/")
    fun callbacks(): JSONArray = authorizedArray("GET", "calls/callbacks/")
    fun directory(cursor: String?) = authorized("GET", "calls/directory/" + (cursor?.let { "?cursor=" + java.net.URLEncoder.encode(it, "UTF-8") } ?: ""))

    /** A JSON array response (decode() expects objects). */
    private fun authorizedArray(method: String, path: String): JSONArray {
        val wrapped = authorized(method, path)
        return wrapped.optJSONArray("__array") ?: JSONArray()
    }
}
