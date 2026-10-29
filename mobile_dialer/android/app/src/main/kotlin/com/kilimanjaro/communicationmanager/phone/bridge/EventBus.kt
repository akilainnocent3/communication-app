package com.kilimanjaro.communicationmanager.phone.bridge

import android.content.Context
import android.os.Handler
import android.os.Looper
import com.kilimanjaro.communicationmanager.phone.telephony.Contacts
import io.flutter.plugin.common.BinaryMessenger

/**
 * Native events for the UI engine: calls_changed, sync_state, launch. They carry states only, never numbers. With no UI
 * listening the event is dropped: the durable outbox already has everything the server needs. While the UI listens,
 * address-book changes are watched too.
 */
object EventBus {
    private val sinks = mutableListOf<PigeonEventSink<TelephonyEvent>>()
    private val main = Handler(Looper.getMainLooper())

    fun register(messenger: BinaryMessenger, context: Context) {
        val app = context.applicationContext
        EventsStreamHandler.register(messenger, object : EventsStreamHandler() {
            private var sink: PigeonEventSink<TelephonyEvent>? = null
            override fun onListen(p0: Any?, sink: PigeonEventSink<TelephonyEvent>) {
                this.sink = sink
                synchronized(sinks) { sinks += sink }
                Contacts.watch(app)
            }
            override fun onCancel(p0: Any?) {
                synchronized(sinks) { sink?.let { sinks -= it } }
                sink = null
            }
        })
    }

    fun emit(type: String, state: String? = null) {
        val event = TelephonyEvent(type = type, state = state)
        main.post { synchronized(sinks) { sinks.toList() }.forEach { runCatching { it.success(event) } } }
    }
}
