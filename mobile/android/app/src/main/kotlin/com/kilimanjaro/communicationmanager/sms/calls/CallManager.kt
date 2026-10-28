package com.kilimanjaro.communicationmanager.sms.calls

import android.os.Handler
import android.os.Looper
import android.telecom.Call
import android.telecom.CallAudioState
import android.telecom.InCallService
import java.util.concurrent.CopyOnWriteArrayList

/** The live calls and audio route, shared by the InCallService and the native in-call screen (same process). */
object CallManager {
    @Volatile var service: InCallService? = null
    val calls = CopyOnWriteArrayList<Call>()
    @Volatile var audio: CallAudioState? = null
    private val listeners = CopyOnWriteArrayList<() -> Unit>()
    private val main = Handler(Looper.getMainLooper())

    fun listen(listener: () -> Unit): () -> Unit {
        listeners += listener
        return { listeners -= listener }
    }

    fun changed() = main.post { listeners.forEach { runCatching { it() } } }

    fun ringing(): Call? = calls.firstOrNull { it.details.state == Call.STATE_RINGING }
    fun primary(): Call? = calls.firstOrNull { it.details.state == Call.STATE_ACTIVE } ?: calls.firstOrNull { it.details.state == Call.STATE_DIALING || it.details.state == Call.STATE_CONNECTING }
        ?: calls.firstOrNull { it.details.state != Call.STATE_DISCONNECTED && it.details.state != Call.STATE_RINGING } ?: ringing()
    fun held(): Call? = calls.firstOrNull { it.details.state == Call.STATE_HOLDING && it != primary() }

    fun key(call: Call): String = keys.getOrPut(call) { java.util.UUID.randomUUID().toString().replace("-", "").take(24) }
    private val keys = java.util.WeakHashMap<Call, String>()

    @Suppress("DEPRECATION")
    fun setMuted(muted: Boolean) = service?.setMuted(muted)
    @Suppress("DEPRECATION")
    fun setRoute(route: Int) = service?.setAudioRoute(route)
}
