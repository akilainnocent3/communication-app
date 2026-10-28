package com.kilimanjaro.communicationmanager.sms.telephony

import android.content.Context
import android.database.ContentObserver
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import com.kilimanjaro.communicationmanager.sms.bridge.EventBus

/**
 * Changes to the message store made by someone else (another app, the system, a restore). Active only while the UI
 * listens for events. Coalesced: one `message_changed` 500 ms after the last change, and none for 1.5 s after this
 * app's own writes, which already announce themselves with precise events (message_received, send_state).
 */
object ProviderWatcher {
    private const val DEBOUNCE_MS = 500L
    private const val OWN_WRITE_MS = 1_500L
    private val main = Handler(Looper.getMainLooper())
    @Volatile private var lastOwnWrite = 0L
    private var observer: ContentObserver? = null
    private val fire = Runnable {
        if (SystemClock.elapsedRealtime() - lastOwnWrite < OWN_WRITE_MS) return@Runnable
        Provider.invalidateAddresses()
        EventBus.emit("message_changed")
    }

    fun ownWrite() {
        lastOwnWrite = SystemClock.elapsedRealtime()
    }

    fun start(context: Context) = main.post {
        if (observer != null) return@post
        observer = object : ContentObserver(main) {
            override fun onChange(selfChange: Boolean, uri: Uri?) {
                if (SystemClock.elapsedRealtime() - lastOwnWrite < OWN_WRITE_MS) return
                main.removeCallbacks(fire)
                main.postDelayed(fire, DEBOUNCE_MS)
            }
        }.also { context.contentResolver.registerContentObserver(Uri.parse("content://mms-sms/"), true, it) }
    }

    fun stop(context: Context) = main.post {
        observer?.let { context.contentResolver.unregisterContentObserver(it) }
        observer = null
        main.removeCallbacks(fire)
    }
}
