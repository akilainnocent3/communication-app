package com.kilimanjaro.communicationmanager.sms.calls

import org.json.JSONObject

/**
 * The dialer's call logic without Android types, so it can be unit-tested: which calls may be recorded at all, the
 * live-call state machine that turns InCallService callbacks into sync events, and the mapping of system call-log rows.
 *
 * Privacy (docs/security.md): USSD/MMI codes (anything with * or #) and emergency calls are never recorded, logged or
 * synced. DTMF digits never reach this layer.
 */
object CallPrivacy {
    private val mmi = Regex("[*#]")

    fun isMmi(number: String?): Boolean = number != null && mmi.containsMatchIn(number)

    /** True when nothing about this call may be written anywhere. [isEmergency] is TelephonyManager.isEmergencyNumber. */
    fun isPrivate(number: String?, isEmergency: (String) -> Boolean): Boolean {
        val raw = number?.trim().orEmpty()
        if (raw.isEmpty()) return false // a private (withheld) number is still a call
        return isMmi(raw) || runCatching { isEmergency(raw) }.getOrDefault(true)
    }
}

/** Where events go: the encrypted outbox (SyncStore.appendEvent) in the app, a list in tests. */
fun interface EventSink {
    fun append(type: String, payload: JSONObject)
}

/** android.telecom.DisconnectCause codes (stable public constants). */
object Disconnect {
    const val UNKNOWN = 0; const val ERROR = 1; const val LOCAL = 2; const val REMOTE = 3; const val CANCELED = 4; const val MISSED = 5
    const val REJECTED = 6; const val BUSY = 7; const val RESTRICTED = 8; const val OTHER = 9; const val ANSWERED_ELSEWHERE = 11
}

/**
 * Live calls, keyed by the dialer's own id. Every transition is written to the outbox at once (a crash or a killed
 * process loses nothing): `call.upsert` when the call appears and when it ends, `call.event` for the timeline.
 */
class CallTracker(private val sink: EventSink, private val clock: () -> Long = System::currentTimeMillis, private val isEmergency: (String) -> Boolean) {
    enum class State { RINGING, DIALING, ACTIVE, HOLDING, DISCONNECTED }

    private class Tracked(
        val key: String, val direction: String, val number: String, val presentation: String, val subId: Long?, val startedAt: Long,
        val contactName: String?, val origin: String?, val callbackTask: String?,
    ) {
        var state = State.RINGING
        var answeredAt: Long? = null
        var holdStartedAt: Long? = null
        var heldMs = 0L
        var conferenceSize = 0
    }

    private val calls = LinkedHashMap<String, Tracked>()
    private val ignored = HashSet<String>()

    /** A call appeared (incoming ringing or outgoing dialing). Returns false when it is private and not tracked. */
    @Synchronized
    fun added(key: String, incoming: Boolean, number: String?, presentation: String = "allowed", subId: Long? = null, contactName: String? = null,
              origin: String? = null, callbackTask: String? = null, at: Long = clock()): Boolean {
        if (CallPrivacy.isPrivate(number, isEmergency)) {
            ignored += key
            return false
        }
        val call = Tracked(key, if (incoming) "in" else "out", number?.trim().orEmpty(), presentation, subId, at, contactName, origin, callbackTask)
        call.state = if (incoming) State.RINGING else State.DIALING
        calls[key] = call
        sink.append("call.upsert", payload(call, result = if (incoming) "missed" else "no_answer", endedAt = null))
        event(call, if (incoming) "ringing" else "dialing", at)
        return true
    }

    @Synchronized
    fun stateChanged(key: String, state: State, at: Long = clock()) {
        val call = calls[key] ?: return
        if (call.state == state) return
        val previous = call.state
        call.state = state
        when (state) {
            State.ACTIVE -> {
                if (call.answeredAt == null) {
                    call.answeredAt = at
                    event(call, "active", at)
                } else if (previous == State.HOLDING) {
                    call.holdStartedAt?.let { call.heldMs += at - it }
                    call.holdStartedAt = null
                    event(call, "unhold", at)
                }
            }
            State.HOLDING -> {
                call.holdStartedAt = at
                event(call, "hold", at)
            }
            else -> Unit
        }
    }

    @Synchronized
    fun conference(key: String, size: Int, at: Long = clock()) {
        val call = calls[key] ?: return
        if (size > call.conferenceSize) {
            call.conferenceSize = size
            sink.append("call.event", JSONObject().put("call_key", key).put("kind", "conference_add").put("at", at).put("size", size))
        }
    }

    /** The call is over. [cause] is a DisconnectCause code; [endedBy] local/remote/system. */
    @Synchronized
    fun removed(key: String, cause: Int, label: String? = null, at: Long = clock()) {
        ignored.remove(key)
        val call = calls.remove(key) ?: return
        call.holdStartedAt?.let { call.heldMs += at - it }
        val result = result(call.direction, call.answeredAt != null, cause)
        val endedBy = when (cause) {
            Disconnect.LOCAL, Disconnect.REJECTED, Disconnect.CANCELED -> "local"
            Disconnect.REMOTE, Disconnect.BUSY, Disconnect.MISSED -> "remote"
            Disconnect.ERROR, Disconnect.RESTRICTED, Disconnect.OTHER -> "system"
            else -> ""
        }
        sink.append("call.upsert", payload(call, result, at).put("disconnect_code", cause).put("disconnect_label", label?.take(80) ?: "").put("ended_by", endedBy))
        event(call, "ended", at)
    }

    /** What the phone is doing, for the heartbeat and the admin's live board. */
    @Synchronized
    fun summary(): String = when {
        calls.values.any { it.state == State.RINGING } -> "ringing"
        calls.values.any { it.state == State.ACTIVE || it.state == State.DIALING } -> "active"
        calls.isNotEmpty() -> "held"
        else -> "idle"
    }

    @Synchronized
    fun isTracked(key: String) = key in calls

    private fun event(call: Tracked, kind: String, at: Long) {
        sink.append("call.event", JSONObject().put("call_key", call.key).put("kind", kind).put("at", at))
    }

    private fun payload(call: Tracked, result: String, endedAt: Long?): JSONObject = JSONObject().apply {
        put("call_key", call.key)
        put("direction", call.direction)
        put("result", result)
        put("number", call.number)
        put("presentation", call.presentation)
        put("started_at", call.startedAt)
        call.answeredAt?.let { put("answered_at", it) }
        endedAt?.let { put("ended_at", it) }
        call.subId?.let { put("sub_id", it) }
        call.contactName?.let { put("contact_name", it.take(120)) }
        if (call.direction == "out") call.origin?.let { put("origin", it) }
        call.callbackTask?.let { put("callback_task", it) }
        if (call.conferenceSize > 0) put("is_conference", true).put("conference_size", call.conferenceSize)
        if (call.heldMs > 0) put("hold_seconds", call.heldMs / 1000)
    }

    companion object {
        fun result(direction: String, answered: Boolean, cause: Int): String = when {
            answered -> "answered"
            direction == "in" -> when (cause) {
                Disconnect.REJECTED -> "rejected"
                Disconnect.ANSWERED_ELSEWHERE -> "answered_elsewhere"
                else -> "missed"
            }
            else -> when (cause) {
                Disconnect.BUSY -> "busy"
                Disconnect.ERROR, Disconnect.RESTRICTED -> "failed"
                Disconnect.LOCAL, Disconnect.CANCELED -> "cancelled"
                else -> "no_answer"
            }
        }
    }
}

/** One row of CallLog.Calls, already read from the cursor. */
data class CallLogRow(
    val id: Long, val number: String?, val type: Int, val date: Long, val durationSeconds: Long, val presentation: Int, val subId: Long?, val cachedName: String?,
)

object CallLogMapper {
    // CallLog.Calls.TYPE values
    const val INCOMING = 1; const val OUTGOING = 2; const val MISSED = 3; const val VOICEMAIL = 4; const val REJECTED = 5; const val BLOCKED = 6
    const val ANSWERED_EXTERNALLY = 7

    /** The call.upsert payload for a call-log row, or null when it must not be synced (USSD/MMI, emergency). */
    fun payload(row: CallLogRow, isEmergency: (String) -> Boolean): JSONObject? {
        if (CallPrivacy.isPrivate(row.number, isEmergency)) return null
        val (direction, result) = when (row.type) {
            INCOMING -> "in" to "answered"
            OUTGOING -> "out" to if (row.durationSeconds > 0) "answered" else "no_answer"
            MISSED -> "in" to "missed"
            VOICEMAIL -> "in" to "voicemail"
            REJECTED -> "in" to "rejected"
            BLOCKED -> "in" to "blocked"
            ANSWERED_EXTERNALLY -> "in" to "answered_elsewhere"
            else -> return null
        }
        val presentation = when (row.presentation) { 2 -> "restricted"; 3 -> "unknown"; 4 -> "payphone"; else -> "allowed" }
        return JSONObject().apply {
            put("call_log_id", row.id)
            put("direction", direction)
            put("result", result)
            put("number", if (presentation == "allowed") row.number.orEmpty() else "")
            put("presentation", presentation)
            put("started_at", row.date)
            put("duration", if (result == "answered") row.durationSeconds.coerceIn(0, 24 * 3600) else 0)
            row.subId?.let { put("sub_id", it) }
            row.cachedName?.takeIf { it.isNotBlank() }?.let { put("contact_name", it.take(120)) }
        }
    }
}
