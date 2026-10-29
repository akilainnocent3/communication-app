package com.kilimanjaro.communicationmanager.phone.security

import com.kilimanjaro.communicationmanager.phone.BuildConfig
import com.kilimanjaro.communicationmanager.phone.sync.HttpTransport
import okhttp3.CertificatePinner
import okhttp3.ConnectionSpec
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.TlsVersion
import java.util.concurrent.TimeUnit

/**
 * The only HTTP client in the app. HTTPS with TLS 1.2+ only (cleartext is also refused by the network security
 * config), and SPKI certificate pinning for the allowed server hosts when pins are supplied at build time
 * (--dart-define=PINNED_SPKI=…, at least two: current and backup). Without pins, the system trust store applies.
 */
object SecureHttp {
    data class Response(val status: Int, val body: ByteArray)

    val client: OkHttpClient by lazy {
        val builder = OkHttpClient.Builder()
            .connectionSpecs(listOf(ConnectionSpec.Builder(ConnectionSpec.MODERN_TLS).tlsVersions(TlsVersion.TLS_1_3, TlsVersion.TLS_1_2).build()))
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .writeTimeout(60, TimeUnit.SECONDS)
            .followRedirects(false)
            .followSslRedirects(false)
            .retryOnConnectionFailure(true)
        val pins = BuildConfig.PINNED_SPKI.split(",").map { it.trim() }.filter { it.isNotEmpty() }
        val hosts = BuildConfig.ALLOWED_SERVER_HOSTS.split(",").map { it.trim() }.filter { it.isNotEmpty() }
        if (pins.isNotEmpty() && hosts.isNotEmpty()) {
            val pinner = CertificatePinner.Builder()
            for (host in hosts) for (pin in pins) pinner.add(host, "sha256/$pin")
            builder.certificatePinner(pinner.build())
        }
        builder.build()
    }

    /**
     * The sync engine's transport. Every failure (offline, TLS, pin mismatch, a host outside the allow-list) is status 0,
     * which the engine backs off from: an exception escaping here once stopped the old Dart sync loop for good.
     * [callTimeoutMs] bounds a whole call (receivers upload inside their short goAsync window).
     */
    fun transport(callTimeoutMs: Long? = null): HttpTransport {
        val http = if (callTimeoutMs == null) client else client.newBuilder().callTimeout(callTimeoutMs, TimeUnit.MILLISECONDS).build()
        return HttpTransport { method, url, headers, body ->
            try {
                execute(method, url, headers, body, http)
            } catch (e: java.io.IOException) {
                Response(0, ByteArray(0))
            } catch (e: IllegalArgumentException) {
                Response(0, ByteArray(0))
            }
        }
    }

    fun execute(method: String, url: String, headers: Map<String, String>, body: ByteArray?, http: OkHttpClient = client): Response {
        require(url.startsWith("https://")) { "Only HTTPS is allowed" }
        val host = url.toHttpUrl().host
        val allowed = BuildConfig.ALLOWED_SERVER_HOSTS.split(",").map { it.trim().lowercase() }.filter { it.isNotEmpty() }
        require(allowed.isEmpty() || host.lowercase() in allowed) { "Server not allowed" }
        val type = headers.entries.firstOrNull { it.key.equals("Content-Type", true) }?.value?.toMediaTypeOrNull()
        val requestBody = when {
            body != null -> body.toRequestBody(type)
            method == "POST" || method == "PUT" || method == "PATCH" -> ByteArray(0).toRequestBody(type)
            else -> null
        }
        val request = Request.Builder().url(url).method(method, requestBody).apply { headers.forEach { (k, v) -> header(k, v) } }.build()
        http.newCall(request).execute().use { response ->
            return Response(response.code, response.body.bytes())
        }
    }
}
