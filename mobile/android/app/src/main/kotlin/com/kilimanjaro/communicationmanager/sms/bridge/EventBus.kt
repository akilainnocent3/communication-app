package com.kilimanjaro.communicationmanager.sms.bridge

import android.os.Handler
import android.os.Looper
import io.flutter.plugin.common.BinaryMessenger

/**
 * Fans native events out to every live Flutter engine (the UI and the background sync loop). Events carry ids and
 * states only, never message text. When no engine is alive the event is dropped: the durable outbox already has it.
 */
object EventBus {
    private val sinks = mutableListOf<PigeonEventSink<TelephonyEvent>>()
    private val main = Handler(Looper.getMainLooper())

    fun register(messenger: BinaryMessenger) {
        EventsStreamHandler.register(messenger, object : EventsStreamHandler() {
            private var sink: PigeonEventSink<TelephonyEvent>? = null
            override fun onListen(p0: Any?, sink: PigeonEventSink<TelephonyEvent>) {
                this.sink = sink
                synchronized(sinks) { sinks += sink }
            }
            override fun onCancel(p0: Any?) {
                synchronized(sinks) { sink?.let { sinks -= it } }
                sink = null
            }
        })
    }

    fun emit(type: String, threadId: Long? = null, providerId: Long? = null, clientUuid: String? = null, state: String? = null) {
        val event = TelephonyEvent(type = type, threadId = threadId, providerId = providerId, clientUuid = clientUuid, state = state)
        main.post { synchronized(sinks) { sinks.toList() }.forEach { runCatching { it.success(event) } } }
    }
}
