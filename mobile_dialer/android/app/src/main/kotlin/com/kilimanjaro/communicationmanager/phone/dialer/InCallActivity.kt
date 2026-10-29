package com.kilimanjaro.communicationmanager.phone.dialer

import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.telecom.Call
import android.telecom.CallAudioState
import android.text.InputType
import android.util.TypedValue
import android.view.Gravity
import android.view.KeyEvent
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.Button
import android.widget.EditText
import android.widget.GridLayout
import android.widget.HorizontalScrollView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import com.kilimanjaro.communicationmanager.phone.MainActivity
import com.kilimanjaro.communicationmanager.phone.R
import com.kilimanjaro.communicationmanager.phone.data.SyncStore
import com.kilimanjaro.communicationmanager.phone.safely
import com.kilimanjaro.communicationmanager.phone.telephony.SyncTrigger
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

/**
 * The call screen, native and independent of Flutter (decision 74): it must draw within a few hundred milliseconds from
 * a cold process on a low-end phone, over the lock screen. Plain Views, no Compose (APK size) and no XML inflation.
 * Incoming: answer, decline, reply with an SMS (the SMS app's quick replies). In a call: mute, keypad (DTMF digits
 * are shown on screen only and never stored), audio route, hold, add call, merge, swap, end; call waiting; proximity
 * screen-off at the ear. After a call: the optional post-call card (outcome and note, synced as an annotation).
 */
class InCallActivity : Activity() {
    private val main = Handler(Looper.getMainLooper())
    private var unlisten: (() -> Unit)? = null
    private var proximity: PowerManager.WakeLock? = null
    private lateinit var root: LinearLayout
    private lateinit var name: TextView
    private lateinit var detail: TextView
    private lateinit var status: TextView
    private lateinit var controls: LinearLayout
    private var keypadDigits: TextView? = null
    private var lastCall: Ended? = null
    private var showingCard = false
    private val tick = object : Runnable {
        override fun run() { updateStatus(); main.postDelayed(this, 1000) }
    }

    /** What the post-call card needs about the call that just ended. */
    private data class Ended(val key: String, val talkSeconds: Long, val number: String?)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setShowWhenLocked(true)
        setTurnScreenOn(true)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.parseColor("#0B1220"))
            setPadding(dp(24), dp(56), dp(24), dp(32))
            gravity = Gravity.CENTER_HORIZONTAL
        }
        val avatar = TextView(this).apply {
            textSize = 34f; setTextColor(Color.WHITE); gravity = Gravity.CENTER; typeface = Typeface.DEFAULT_BOLD
            background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(Color.parseColor("#1D4ED8")) }
            tag = "avatar"
        }
        root.addView(avatar, LinearLayout.LayoutParams(dp(96), dp(96)))
        name = text(28f, Color.WHITE, bold = true).also { root.addView(it, wrap(top = 20)) }
        detail = text(16f, Color.parseColor("#94A3B8")).also { root.addView(it, wrap(top = 4)) }
        status = text(16f, Color.parseColor("#CBD5E1")).also { root.addView(it, wrap(top = 12)) }
        root.addView(View(this), LinearLayout.LayoutParams(1, 0, 1f))
        controls = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL }
        root.addView(controls, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        setContentView(root)
        proximity = runCatching {
            getSystemService(PowerManager::class.java).newWakeLock(PowerManager.PROXIMITY_SCREEN_OFF_WAKE_LOCK, "ocm:proximity")
        }.getOrNull()
        render()
    }

    override fun onStart() {
        super.onStart()
        unlisten = CallManager.listen { render() }
        main.post(tick)
    }

    override fun onStop() {
        unlisten?.invoke()
        main.removeCallbacks(tick)
        super.onStop()
    }

    override fun onDestroy() {
        releaseProximity()
        super.onDestroy()
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if ((keyCode == KeyEvent.KEYCODE_VOLUME_DOWN || keyCode == KeyEvent.KEYCODE_VOLUME_UP) && Ringer.ringing) {
            Ringer.stop() // silence, keep ringing visually
            return true
        }
        return super.onKeyDown(keyCode, event)
    }

    // --- Rendering -----------------------------------------------------------------------------------------------

    private fun render() {
        if (showingCard) return
        val ringing = CallManager.ringing()
        val call = CallManager.primary()
        if (call == null) {
            releaseProximity()
            if (!maybeShowCard()) finish()
            return
        }
        rememberForCard(call)
        val number = call.number()
        val identity = CallerId.identify(this, number)
        val label = identity.name ?: number?.takeIf { it.isNotBlank() } ?: getString(R.string.private_number)
        name.text = label
        (root.findViewWithTag<TextView>("avatar")).text = label.firstOrNull { it.isLetterOrDigit() }?.uppercase() ?: "?"
        detail.text = listOfNotNull(
            if (identity.name != null) number else null,
            if (identity.source == "directory") getString(R.string.company_directory) else null,
        ).joinToString(" · ")
        updateStatus()
        controls.removeAllViews()
        if (ringing != null && (call == ringing || CallManager.calls.size == 1)) incomingControls(ringing)
        else {
            ongoingControls(call)
            if (ringing != null) waitingBanner(ringing)
        }
        val earpiece = CallManager.audio?.route?.let { it == CallAudioState.ROUTE_EARPIECE } ?: true
        if (call.details.state == Call.STATE_ACTIVE && earpiece) acquireProximity() else releaseProximity()
    }

    private fun updateStatus() {
        val call = CallManager.primary() ?: return
        status.text = when (call.details.state) {
            Call.STATE_RINGING -> getString(R.string.incoming_call)
            Call.STATE_DIALING, Call.STATE_CONNECTING -> getString(R.string.calling)
            Call.STATE_HOLDING -> getString(R.string.on_hold)
            Call.STATE_ACTIVE -> {
                val since = call.details.connectTimeMillis.takeIf { it > 0 } ?: System.currentTimeMillis()
                val seconds = (System.currentTimeMillis() - since) / 1000
                "%d:%02d".format(seconds / 60, seconds % 60)
            }
            else -> getString(R.string.call_ended)
        }
    }

    private fun incomingControls(call: Call) {
        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER }
        row.addView(round(getString(R.string.decline), "#DC2626") { OcmInCallService.decline(call) }, weight())
        row.addView(round(getString(R.string.reply_sms), "#334155") { replyWithSms(call) }, weight())
        row.addView(round(getString(R.string.answer), "#16A34A") { OcmInCallService.answer(call) }, weight())
        controls.addView(row, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
    }

    private fun waitingBanner(ringing: Call) {
        val waiting = text(14f, Color.WHITE).apply { text = getString(R.string.call_waiting, ringing.number() ?: getString(R.string.private_number)) }
        controls.addView(waiting, wrap(top = 16))
        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER }
        row.addView(pill(getString(R.string.decline), "#DC2626") { OcmInCallService.decline(ringing) })
        row.addView(pill(getString(R.string.hold_and_answer), "#16A34A") { CallManager.primary()?.hold(); OcmInCallService.answer(ringing) })
        controls.addView(row, wrap(top = 8))
    }

    private fun ongoingControls(call: Call) {
        keypadDigits = null
        val audio = CallManager.audio
        val grid = GridLayout(this).apply { columnCount = 3 }
        grid.addView(toggle(getString(R.string.mute), audio?.isMuted == true) { CallManager.setMuted(!(CallManager.audio?.isMuted ?: false)) })
        grid.addView(toggle(getString(R.string.keypad), false) { showKeypad(call) })
        grid.addView(toggle(routeLabel(audio), audio?.route == CallAudioState.ROUTE_SPEAKER || audio?.route == CallAudioState.ROUTE_BLUETOOTH) { chooseRoute() })
        val held = call.details.state == Call.STATE_HOLDING
        grid.addView(toggle(getString(if (held) R.string.resume else R.string.hold), held) { if (held) call.unhold() else call.hold() })
        grid.addView(toggle(getString(R.string.add_call), false) {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("ocmphone://phone/keypad")).setClass(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        })
        val other = CallManager.held()
        when {
            call.conferenceableCalls.isNotEmpty() || call.details.can(Call.Details.CAPABILITY_MERGE_CONFERENCE) ->
                grid.addView(toggle(getString(R.string.merge), false) { call.conferenceableCalls.firstOrNull()?.let(call::conference) ?: call.mergeConference() })
            other != null -> grid.addView(toggle(getString(R.string.swap), false) { call.hold(); other.unhold() })
            else -> grid.addView(View(this), GridLayout.LayoutParams().apply { width = dp(96); height = dp(72) })
        }
        controls.addView(grid, wrap())
        controls.addView(round(getString(R.string.end_call), "#DC2626") { call.disconnect() }, wrap(top = 24))
    }

    private fun routeLabel(audio: CallAudioState?): String = when (audio?.route) {
        CallAudioState.ROUTE_SPEAKER -> getString(R.string.speaker)
        CallAudioState.ROUTE_BLUETOOTH -> getString(R.string.bluetooth)
        CallAudioState.ROUTE_WIRED_HEADSET -> getString(R.string.headset)
        else -> getString(R.string.speaker)
    }

    /** Speaker toggles when there are only two routes; with Bluetooth or a headset, a chooser. */
    private fun chooseRoute() {
        val audio = CallManager.audio
        if (audio == null) {
            CallManager.setRoute(CallAudioState.ROUTE_SPEAKER)
            return
        }
        val routes = listOf(CallAudioState.ROUTE_EARPIECE to R.string.earpiece, CallAudioState.ROUTE_SPEAKER to R.string.speaker,
            CallAudioState.ROUTE_BLUETOOTH to R.string.bluetooth, CallAudioState.ROUTE_WIRED_HEADSET to R.string.headset)
            .filter { (route, _) -> audio.supportedRouteMask and route != 0 }
        if (routes.size <= 2) {
            CallManager.setRoute(if (audio.route == CallAudioState.ROUTE_SPEAKER) routes.first().first else CallAudioState.ROUTE_SPEAKER)
            return
        }
        AlertDialog.Builder(this).setTitle(R.string.audio_output).setItems(routes.map { getString(it.second) }.toTypedArray()) { _, which ->
            CallManager.setRoute(routes[which].first)
        }.show()
    }

    private fun showKeypad(call: Call) {
        controls.removeAllViews()
        val digits = text(26f, Color.WHITE).apply { letterSpacing = 0.1f }
        keypadDigits = digits
        controls.addView(digits, wrap())
        val grid = GridLayout(this).apply { columnCount = 3 }
        for (key in listOf('1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '0', '#')) {
            grid.addView(Button(this).apply {
                text = key.toString(); textSize = 24f; setTextColor(Color.WHITE); isAllCaps = false
                background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(Color.parseColor("#1E293B")) }
                setOnTouchListener { view, event ->
                    when (event.actionMasked) {
                        android.view.MotionEvent.ACTION_DOWN -> { call.playDtmfTone(key); digits.append(key.toString()); view.isPressed = true }
                        android.view.MotionEvent.ACTION_UP, android.view.MotionEvent.ACTION_CANCEL -> { call.stopDtmfTone(); view.isPressed = false }
                    }
                    true
                }
            }, GridLayout.LayoutParams().apply { width = dp(76); height = dp(76); setMargins(dp(8), dp(6), dp(8), dp(6)) })
        }
        controls.addView(grid, wrap(top = 8))
        controls.addView(pill(getString(R.string.hide_keypad), "#334155") { render() }, wrap(top = 8))
    }

    private fun replyWithSms(call: Call) {
        val replies = runCatching {
            val array = JSONArray(SyncStore.get(this)?.value("cache.quick_replies") ?: "[]")
            (0 until array.length()).map { array.getJSONObject(it).getString("body") }
        }.getOrDefault(emptyList()).ifEmpty { listOf(getString(R.string.reply_default_1), getString(R.string.reply_default_2)) }
        AlertDialog.Builder(this).setTitle(R.string.reply_sms).setItems(replies.toTypedArray()) { _, which ->
            Ringer.stop()
            call.reject(true, replies[which]) // sent by our RespondViaMessageService, through the SMS path
        }.show()
    }

    // --- Post-call card ------------------------------------------------------------------------------------------

    private fun rememberForCard(call: Call) {
        val key = CallManager.key(call)
        val connected = call.details.connectTimeMillis
        if (call.details.state == Call.STATE_ACTIVE && connected > 0) {
            lastCall = Ended(key, (System.currentTimeMillis() - connected) / 1000, call.number())
        }
    }

    private fun maybeShowCard(): Boolean {
        val ended = lastCall ?: return false
        if (!CallsFeature.enabled(this) || CallPrivacy.isPrivate(ended.number) { CallsFeature.isEmergency(this, it) }) return false
        val config = runCatching { JSONObject(SyncStore.get(this)?.value("cache.calls_config") ?: "{}") }.getOrDefault(JSONObject())
        if (!config.optBoolean("post_call_card", true)) return false
        val outcomes = config.optJSONArray("outcomes") ?: JSONArray()
        if (outcomes.length() == 0) return false
        val threshold = config.optLong("outcome_required_after_seconds", 0)
        val required = threshold > 0 && ended.talkSeconds >= threshold
        showingCard = true
        releaseProximity()
        showCard(ended, outcomes, required)
        return true
    }

    private fun showCard(ended: Ended, outcomes: JSONArray, required: Boolean) {
        root.removeAllViews()
        root.gravity = Gravity.TOP
        val content = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        content.addView(text(22f, Color.WHITE, bold = true).apply { text = getString(R.string.post_call_title) }, wrap())
        content.addView(text(14f, Color.parseColor("#94A3B8")).apply { text = getString(if (required) R.string.post_call_required else R.string.post_call_optional) }, wrap(top = 4))
        var chosen: Long? = null
        val chips = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        val buttons = mutableListOf<Button>()
        for (i in 0 until outcomes.length()) {
            val o = outcomes.getJSONObject(i)
            val colour = runCatching { Color.parseColor(o.optString("colour", "#3758F9")) }.getOrDefault(Color.parseColor("#3758F9"))
            val button = Button(this).apply {
                text = o.getString("name"); isAllCaps = false; setTextColor(colour)
                background = GradientDrawable().apply { cornerRadius = dp(18).toFloat(); setStroke(dp(1), colour); setColor(Color.TRANSPARENT) }
            }
            button.setOnClickListener {
                chosen = o.getLong("id")
                buttons.forEach { b -> (b.background as GradientDrawable).setColor(Color.TRANSPARENT); b.setTextColor((b.tag as Int)) }
                (button.background as GradientDrawable).setColor(colour); button.setTextColor(Color.WHITE)
            }
            button.tag = colour
            buttons += button
            chips.addView(button, LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, dp(40)).apply { marginEnd = dp(8) })
        }
        content.addView(HorizontalScrollView(this).apply { addView(chips) }, wrap(top = 16))
        val note = EditText(this).apply {
            hint = getString(R.string.post_call_note); setTextColor(Color.WHITE); setHintTextColor(Color.parseColor("#64748B"))
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE or InputType.TYPE_TEXT_FLAG_CAP_SENTENCES; minLines = 2
        }
        content.addView(note, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { topMargin = dp(12) })
        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.END }
        if (!required) row.addView(pill(getString(R.string.skip), "#334155") { finish() })
        row.addView(pill(getString(R.string.save), "#1D4ED8") {
            if (chosen == null && note.text.isBlank()) return@pill
            if (required && chosen == null) return@pill
            safely("annotation") {
                SyncStore.get(this)?.appendEvent("call.annotation", JSONObject().put("client_uuid", UUID.randomUUID().toString()).put("call_key", ended.key)
                    .put("outcome_id", chosen ?: JSONObject.NULL).put("note", note.text.toString().take(2000)))
                SyncTrigger.now(this)
            }
            finish()
        })
        content.addView(row, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { topMargin = dp(16) })
        root.addView(ScrollView(this).apply { addView(content) }, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
    }

    // --- Small view helpers ----------------------------------------------------------------------------------------

    private fun dp(value: Int) = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, value.toFloat(), resources.displayMetrics).toInt()
    private fun wrap(top: Int = 0) = LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { topMargin = dp(top); gravity = Gravity.CENTER_HORIZONTAL }
    private fun weight() = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)

    private fun text(size: Float, colour: Int, bold: Boolean = false) = TextView(this).apply {
        textSize = size; setTextColor(colour); gravity = Gravity.CENTER; if (bold) typeface = Typeface.DEFAULT_BOLD
    }

    private fun round(label: String, colour: String, onClick: () -> Unit) = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL
        addView(Button(context).apply {
            contentDescription = label; text = ""
            background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(Color.parseColor(colour)) }
            setOnClickListener { safely("call button") { onClick() } }
        }, LinearLayout.LayoutParams(dp(68), dp(68)))
        addView(TextView(context).apply { text = label; setTextColor(Color.WHITE); textSize = 13f; gravity = Gravity.CENTER }, LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { topMargin = dp(6) })
    }

    private fun toggle(label: String, on: Boolean, onClick: () -> Unit) = Button(this).apply {
        text = label; isAllCaps = false; textSize = 13f; setTextColor(if (on) Color.parseColor("#0B1220") else Color.WHITE)
        background = GradientDrawable().apply { cornerRadius = dp(16).toFloat(); setColor(Color.parseColor(if (on) "#E2E8F0" else "#1E293B")) }
        setOnClickListener { safely("call control") { onClick() } }
        layoutParams = GridLayout.LayoutParams().apply { width = dp(96); height = dp(72); setMargins(dp(6), dp(6), dp(6), dp(6)) }
    }

    private fun pill(label: String, colour: String, onClick: () -> Unit) = Button(this).apply {
        text = label; isAllCaps = false; setTextColor(Color.WHITE)
        background = GradientDrawable().apply { cornerRadius = dp(20).toFloat(); setColor(Color.parseColor(colour)) }
        setOnClickListener { safely("pill") { onClick() } }
        layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, dp(44)).apply { marginStart = dp(6); marginEnd = dp(6) }
    }

    private fun acquireProximity() {
        val lock = proximity ?: return
        if (!lock.isHeld) runCatching { lock.acquire(4 * 60 * 60 * 1000L) }
    }

    private fun releaseProximity() {
        proximity?.takeIf { it.isHeld }?.let { runCatching { it.release(PowerManager.RELEASE_FLAG_WAIT_FOR_NO_PROXIMITY) } }
    }

    companion object {
        fun start(context: Context) = context.startActivity(Intent(context, InCallActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }
}
