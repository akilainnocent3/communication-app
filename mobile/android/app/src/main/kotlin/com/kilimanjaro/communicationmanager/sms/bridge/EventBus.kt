package com.kilimanjaro.communicationmanager.sms.bridge

import android.content.Context
import android.os.Handler
import android.os.Looper
import com.kilimanjaro.communicationmanager.sms.telephony.Contacts
import com.kilimanjaro.communicationmanager.sms.telephony.ProviderWatcher
import io.flutter.plugin.common.BinaryMessenger

/**
 * Native events for the UI engine. Events carry ids and states only, never message text. With no UI listening the
 * event is dropped: the durable outbox already has everything the server needs, and the native engine syncs it.
 * While the UI listens, outside changes to the message store and the address book are watched too.
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
                ProviderWatcher.start(app)
                Contacts.watch(app)
            }
            override fun onCancel(p0: Any?) {
                val empty = synchronized(sinks) { sink?.let { sinks -= it }; sinks.isEmpty() }
                sink = null
                if (empty) ProviderWatcher.stop(app)
            }
        })
    }

    fun emit(type: String, threadId: Long? = null, providerId: Long? = null, clientUuid: String? = null, state: String? = null) {
        val event = TelephonyEvent(type = type, threadId = threadId, providerId = providerId, clientUuid = clientUuid, state = state)
        main.post { synchronized(sinks) { sinks.toList() }.forEach { runCatching { it.success(event) } } }
    }
}
