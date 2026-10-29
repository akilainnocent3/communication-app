package com.kilimanjaro.communicationmanager.phone.dialer

import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.telecom.Call
import android.telecom.CallAudioState
import android.telecom.InCallService
import android.telecom.VideoProfile
import androidx.core.app.NotificationManagerCompat
import androidx.core.app.ServiceCompat
import com.kilimanjaro.communicationmanager.phone.safely
import com.kilimanjaro.communicationmanager.phone.telephony.SyncTrigger

/**
 * Telecom binds this while the app is the default dialer and a call exists. It never depends on Flutter: the call
 * screen is native (InCallActivity), the ringer is native, and every state change is written to the encrypted outbox
 * by CallTracker before anything else. Emergency and USSD calls are handled (shown, answered, ended) like any call but
 * never written down.
 */
class OcmInCallService : InCallService() {
    private val callbacks = HashMap<Call, Call.Callback>()

    override fun onCreate() {
        super.onCreate()
        CallManager.service = this
    }

    override fun onDestroy() {
        CallManager.service = null
        Ringer.stop()
        super.onDestroy()
    }

    override fun onCallAdded(call: Call) {
        super.onCallAdded(call)
        CallManager.calls += call
        val key = CallManager.key(call)
        val details = call.details
        val incoming = details.callDirection == Call.Details.DIRECTION_INCOMING || call.details.state == Call.STATE_RINGING
        val number = details.handle?.schemeSpecificPart
        val presentation = when (details.handlePresentation) { 2 -> "restricted"; 3 -> "unknown"; 4 -> "payphone"; else -> "allowed" }
        val identity = CallerId.identify(this, number)
        val intent = if (incoming) null else Dialer.takeIntent(number)
        safely("track call") {
            CallsFeature.tracker(this).added(key, incoming, number, presentation, Dialer.subscriptionFor(this, details.accountHandle?.id),
                identity.name.takeIf { identity.source == "contact" }, intent?.origin, intent?.callbackTask)
        }
        val callback = object : Call.Callback() {
            override fun onStateChanged(call: Call, state: Int) = onState(call, state)
            override fun onDetailsChanged(call: Call, details: Call.Details) {
                if (details.hasProperty(Call.Details.PROPERTY_CONFERENCE)) safely("conference") { CallsFeature.tracker(this@OcmInCallService).conference(key, call.children.size + 1) }
                CallManager.changed()
            }
            override fun onChildrenChanged(call: Call, children: MutableList<Call>) {
                safely("conference") { CallsFeature.tracker(this@OcmInCallService).conference(key, children.size + 1) }
                CallManager.changed()
            }
        }
        callbacks[call] = callback
        call.registerCallback(callback)
        if (call.details.state == Call.STATE_RINGING) ring(call, identity, number) else show(call, identity, number)
        SyncTrigger.now(this)
        CallManager.changed()
    }

    private fun label(identity: CallerId.Identity, number: String?) = identity.name ?: number?.takeIf { it.isNotBlank() } ?: getString(com.kilimanjaro.communicationmanager.phone.R.string.private_number)

    private fun ring(call: Call, identity: CallerId.Identity, number: String?) {
        // A second call while on a call is "call waiting": a tone from Telecom, no ringtone over the conversation.
        if (CallManager.calls.none { it != call && it.details.state == Call.STATE_ACTIVE }) Ringer.start(this, number)
        val detail = if (identity.source == "directory") getString(com.kilimanjaro.communicationmanager.phone.R.string.company_directory) else number.orEmpty()
        foreground(CallNotifications.incoming(this, label(identity, number), detail))
        safely("call screen") { startActivity(Intent(this, InCallActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
    }

    private fun show(call: Call, identity: CallerId.Identity, number: String?) {
        foreground(CallNotifications.ongoing(this, label(identity, number), System.currentTimeMillis()))
        safely("call screen") { startActivity(Intent(this, InCallActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
    }

    private fun foreground(notification: android.app.Notification) = safely("call notification") {
        ServiceCompat.startForeground(this, CallNotifications.CALL_ID, notification, if (Build.VERSION.SDK_INT >= 30) ServiceInfo.FOREGROUND_SERVICE_TYPE_PHONE_CALL else 0)
    }

    private fun onState(call: Call, state: Int) {
        val key = CallManager.key(call)
        val tracker = CallsFeature.tracker(this)
        when (state) {
            Call.STATE_ACTIVE -> {
                Ringer.stop()
                safely("state") { tracker.stateChanged(key, CallTracker.State.ACTIVE) }
                val number = call.details.handle?.schemeSpecificPart
                foreground(CallNotifications.ongoing(this, label(CallerId.identify(this, number), number), System.currentTimeMillis()))
            }
            Call.STATE_HOLDING -> safely("state") { tracker.stateChanged(key, CallTracker.State.HOLDING) }
            Call.STATE_DISCONNECTED, Call.STATE_DISCONNECTING -> Ringer.stop()
        }
        CallManager.changed()
    }

    override fun onCallRemoved(call: Call) {
        super.onCallRemoved(call)
        Ringer.stop()
        callbacks.remove(call)?.let { call.unregisterCallback(it) }
        CallManager.calls -= call
        val key = CallManager.key(call)
        val cause = call.details.disconnectCause
        val wasMissed = call.details.callDirection == Call.Details.DIRECTION_INCOMING && cause?.code == Disconnect.MISSED
        val tracked = CallsFeature.tracker(this).isTracked(key)
        safely("removed") { CallsFeature.tracker(this).removed(key, cause?.code ?: Disconnect.UNKNOWN, cause?.label?.toString()) }
        if (wasMissed && tracked) {
            val number = call.details.handle?.schemeSpecificPart.orEmpty()
            safely("missed notification") { CallNotifications.missed(this, number, CallerId.identify(this, number).name) }
        }
        if (CallManager.calls.isEmpty()) {
            ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
            NotificationManagerCompat.from(this).cancel(CallNotifications.CALL_ID)
        }
        SyncTrigger.now(this)
        CallManager.changed()
        com.kilimanjaro.communicationmanager.phone.bridge.EventBus.emit("calls_changed")
    }

    override fun onCallAudioStateChanged(audioState: CallAudioState) {
        CallManager.audio = audioState
        CallManager.changed()
    }

    /** Volume key during ringing: silence (the call keeps ringing silently and can still be answered). */
    override fun onSilenceRinger() {
        Ringer.stop()
    }

    companion object {
        fun answer(call: Call) {
            Ringer.stop()
            call.answer(VideoProfile.STATE_AUDIO_ONLY)
        }

        fun decline(call: Call) {
            Ringer.stop()
            call.reject(false, null)
        }
    }
}
