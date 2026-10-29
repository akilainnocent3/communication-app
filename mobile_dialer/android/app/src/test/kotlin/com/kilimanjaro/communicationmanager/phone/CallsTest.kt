package com.kilimanjaro.communicationmanager.phone

import android.app.NotificationManager
import android.media.AudioManager
import android.telecom.TelecomManager
import androidx.test.core.app.ApplicationProvider
import com.kilimanjaro.communicationmanager.phone.dialer.CallLogMapper
import com.kilimanjaro.communicationmanager.phone.dialer.CallLogRow
import com.kilimanjaro.communicationmanager.phone.dialer.CallPrivacy
import com.kilimanjaro.communicationmanager.phone.dialer.CallTracker
import com.kilimanjaro.communicationmanager.phone.dialer.CallbackTasks
import com.kilimanjaro.communicationmanager.phone.dialer.Dialer
import com.kilimanjaro.communicationmanager.phone.dialer.Disconnect
import com.kilimanjaro.communicationmanager.phone.dialer.EventSink
import com.kilimanjaro.communicationmanager.phone.dialer.OcmCallScreeningService
import com.kilimanjaro.communicationmanager.phone.dialer.Ringer
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

/** The dialer's call logic: state machine, call-log mapping, privacy (USSD, emergency), ringing rules, screening. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class CallsTest {
    private val events = mutableListOf<Pair<String, JSONObject>>()
    private val sink = EventSink { type, payload -> events += type to payload }
    private var now = 1_700_000_000_000L
    private val emergency = setOf("112", "911", "999")
    private fun tracker() = CallTracker(sink, clock = { now }, isEmergency = { it.filter(Char::isDigit) in emergency })
    private fun upserts() = events.filter { it.first == "call.upsert" }.map { it.second }
    private fun kinds() = events.filter { it.first == "call.event" }.map { it.second.getString("kind") }

    @Test
    fun incomingAnsweredHeldAndEnded() {
        val tracker = tracker()
        assertTrue(tracker.added("k1", incoming = true, number = "+255754210331", subId = 1, contactName = "Neema"))
        assertEquals("ringing", tracker.summary())
        now += 6_000; tracker.stateChanged("k1", CallTracker.State.ACTIVE)
        now += 20_000; tracker.stateChanged("k1", CallTracker.State.HOLDING)
        assertEquals("held", tracker.summary())
        now += 10_000; tracker.stateChanged("k1", CallTracker.State.ACTIVE)
        now += 30_000; tracker.removed("k1", Disconnect.REMOTE, "Remote hung up")
        assertEquals(listOf("ringing", "active", "hold", "unhold", "ended"), kinds())
        val first = upserts().first()
        assertEquals("missed", first.getString("result")) // provisional until the end
        assertFalse(first.has("ended_at"))
        val last = upserts().last()
        assertEquals("answered", last.getString("result"))
        assertEquals(1_700_000_006_000L, last.getLong("answered_at"))
        assertEquals(1_700_000_066_000L, last.getLong("ended_at"))
        assertEquals(10, last.getLong("hold_seconds"))
        assertEquals("remote", last.getString("ended_by"))
        assertEquals("Neema", last.getString("contact_name"))
        assertEquals(1, last.getLong("sub_id"))
        assertEquals("idle", tracker.summary())
    }

    @Test
    fun resultsFromDisconnectCauses() {
        assertEquals("missed", CallTracker.result("in", false, Disconnect.MISSED))
        assertEquals("rejected", CallTracker.result("in", false, Disconnect.REJECTED))
        assertEquals("answered_elsewhere", CallTracker.result("in", false, Disconnect.ANSWERED_ELSEWHERE))
        assertEquals("busy", CallTracker.result("out", false, Disconnect.BUSY))
        assertEquals("failed", CallTracker.result("out", false, Disconnect.ERROR))
        assertEquals("cancelled", CallTracker.result("out", false, Disconnect.LOCAL))
        assertEquals("no_answer", CallTracker.result("out", false, Disconnect.REMOTE))
        assertEquals("answered", CallTracker.result("out", true, Disconnect.LOCAL))
    }

    @Test
    fun outgoingCarriesItsOriginAndCallbackTask() {
        val tracker = tracker()
        tracker.added("k2", incoming = false, number = "0754210331", origin = "callback_task", callbackTask = "task-1")
        tracker.conference("k2", 3)
        tracker.removed("k2", Disconnect.LOCAL)
        val last = upserts().last()
        assertEquals("out", last.getString("direction"))
        assertEquals("callback_task", last.getString("origin"))
        assertEquals("task-1", last.getString("callback_task"))
        assertEquals(3, last.getInt("conference_size"))
        assertEquals("cancelled", last.getString("result"))
    }

    @Test
    fun ussdAndEmergencyCallsLeaveNoTrace() {
        val tracker = tracker()
        for ((key, number) in listOf("u1" to "*150*00#", "u2" to "*#06#", "e1" to "112", "e2" to "911")) {
            assertFalse(tracker.added(key, incoming = false, number = number))
            tracker.stateChanged(key, CallTracker.State.ACTIVE)
            tracker.removed(key, Disconnect.LOCAL)
        }
        assertTrue(events.isEmpty())
        assertEquals("idle", tracker.summary())
        // A broken emergency check counts as emergency: never record by mistake.
        assertTrue(CallPrivacy.isPrivate("0754210331") { throw IllegalStateException() })
        assertFalse(CallPrivacy.isPrivate("") { false }) // a withheld number is still a call
    }

    @Test
    fun callLogRowsMap() {
        val emergencyCheck = { n: String -> n in emergency }
        fun row(type: Int, number: String = "+255754210331", duration: Long = 42, presentation: Int = 1) =
            CallLogRow(id = 9, number = number, type = type, date = now, durationSeconds = duration, presentation = presentation, subId = 2, cachedName = "Neema")
        assertEquals("answered", CallLogMapper.payload(row(CallLogMapper.INCOMING), emergencyCheck)!!.getString("result"))
        assertEquals(42, CallLogMapper.payload(row(CallLogMapper.INCOMING), emergencyCheck)!!.getLong("duration"))
        assertEquals("no_answer", CallLogMapper.payload(row(CallLogMapper.OUTGOING, duration = 0), emergencyCheck)!!.getString("result"))
        assertEquals("voicemail", CallLogMapper.payload(row(CallLogMapper.VOICEMAIL), emergencyCheck)!!.getString("result"))
        assertEquals(0, CallLogMapper.payload(row(CallLogMapper.MISSED), emergencyCheck)!!.getLong("duration"))
        assertEquals("blocked", CallLogMapper.payload(row(CallLogMapper.BLOCKED), emergencyCheck)!!.getString("result"))
        val hidden = CallLogMapper.payload(row(CallLogMapper.INCOMING, presentation = 2), emergencyCheck)!!
        assertEquals("restricted", hidden.getString("presentation"))
        assertEquals("", hidden.getString("number"))
        assertNull(CallLogMapper.payload(row(CallLogMapper.OUTGOING, number = "*150*00#"), emergencyCheck))
        assertNull(CallLogMapper.payload(row(CallLogMapper.OUTGOING, number = "112"), emergencyCheck))
        assertEquals(9, CallLogMapper.payload(row(CallLogMapper.MISSED), emergencyCheck)!!.getLong("call_log_id"))
    }

    @Test
    fun ringerFollowsRingerModeAndDoNotDisturb() {
        assertEquals(Ringer.Plan(sound = true, vibrate = true), Ringer.plan(AudioManager.RINGER_MODE_NORMAL, dndAllows = true, vibrateWhenRinging = true))
        assertEquals(Ringer.Plan(sound = true, vibrate = false), Ringer.plan(AudioManager.RINGER_MODE_NORMAL, dndAllows = true, vibrateWhenRinging = false))
        assertEquals(Ringer.Plan(sound = false, vibrate = true), Ringer.plan(AudioManager.RINGER_MODE_VIBRATE, dndAllows = true, vibrateWhenRinging = false))
        assertEquals(Ringer.Plan(sound = false, vibrate = false), Ringer.plan(AudioManager.RINGER_MODE_SILENT, dndAllows = true, vibrateWhenRinging = true))
        assertEquals(Ringer.Plan(sound = false, vibrate = false), Ringer.plan(AudioManager.RINGER_MODE_NORMAL, dndAllows = false, vibrateWhenRinging = true))
    }

    @Test
    fun doNotDisturbLetsThroughOnlyTheCallersThePersonChose() {
        val all = NotificationManager.INTERRUPTION_FILTER_ALL
        val priority = NotificationManager.INTERRUPTION_FILTER_PRIORITY
        val none = NotificationManager.INTERRUPTION_FILTER_NONE
        val starred = NotificationManager.Policy.PRIORITY_SENDERS_STARRED
        val contacts = NotificationManager.Policy.PRIORITY_SENDERS_CONTACTS
        val anyone = NotificationManager.Policy.PRIORITY_SENDERS_ANY
        assertTrue(Ringer.dndAllows(all, null, callsAllowed = false, senders = -1, isContact = false, isStarred = false))
        // Android 13+: the system decides
        assertTrue(Ringer.dndAllows(priority, true, callsAllowed = false, senders = -1, isContact = false, isStarred = false))
        assertFalse(Ringer.dndAllows(priority, false, callsAllowed = true, senders = anyone, isContact = true, isStarred = true))
        // Android 10–12: the public policy
        assertTrue(Ringer.dndAllows(priority, null, callsAllowed = true, senders = starred, isContact = true, isStarred = true))
        assertFalse(Ringer.dndAllows(priority, null, callsAllowed = true, senders = starred, isContact = true, isStarred = false))
        assertTrue(Ringer.dndAllows(priority, null, callsAllowed = true, senders = contacts, isContact = true, isStarred = false))
        assertFalse(Ringer.dndAllows(priority, null, callsAllowed = true, senders = contacts, isContact = false, isStarred = false))
        assertTrue(Ringer.dndAllows(priority, null, callsAllowed = true, senders = anyone, isContact = false, isStarred = false))
        assertFalse(Ringer.dndAllows(priority, null, callsAllowed = false, senders = anyone, isContact = true, isStarred = true))
        assertFalse(Ringer.dndAllows(none, null, callsAllowed = true, senders = anyone, isContact = true, isStarred = true))
    }

    @Test
    fun onlyTheProtectedAliasPlacesCallsFromOtherApps() {
        val pkg = "com.kilimanjaro.communicationmanager.phone"
        assertTrue(Dialer.placesAtOnce("android.intent.action.CALL", "tel", "$pkg.CallIntentHandler", pkg))
        // explicit intents straight to the exported activity or the Phone alias carry no CALL_PHONE check
        assertFalse(Dialer.placesAtOnce("android.intent.action.CALL", "tel", "$pkg.MainActivity", pkg))
        assertFalse(Dialer.placesAtOnce("android.intent.action.CALL", "tel", "$pkg.PhoneLauncher", pkg))
        assertFalse(Dialer.placesAtOnce("android.intent.action.CALL", "tel", null, pkg))
        assertFalse(Dialer.placesAtOnce("android.intent.action.DIAL", "tel", "$pkg.CallIntentHandler", pkg))
        assertFalse(Dialer.placesAtOnce("android.intent.action.CALL", "sms", "$pkg.CallIntentHandler", pkg))
    }

    @Test
    fun screeningNeverBlocksEmergencyOrOutgoingCalls() {
        val blocked = { _: String -> true }
        assertTrue(OcmCallScreeningService.shouldBlock(true, "+255754210331", { false }, blocked))
        assertFalse(OcmCallScreeningService.shouldBlock(true, "112", { it == "112" }, blocked))
        assertFalse(OcmCallScreeningService.shouldBlock(false, "+255754210331", { false }, blocked))
        assertFalse(OcmCallScreeningService.shouldBlock(true, "+255754210331", { throw IllegalStateException() }, blocked))
        assertFalse(OcmCallScreeningService.shouldBlock(true, "+255754210331", { false }, { false }))
    }

    @Test
    fun emergencyCallsArePlacedWithoutEnrollmentPermissionOrRole() {
        // Not enrolled (no sync database), not the default dialer, CALL_PHONE not granted: an emergency number still goes
        // to Telecom (or, failing that, to the system dialer). Nothing about it is remembered.
        val context = ApplicationProvider.getApplicationContext<android.app.Application>()
        val telecom = shadowOf(context.getSystemService(TelecomManager::class.java))
        val result = Dialer.place(context, "112")
        assertTrue(result == "placed" || result == "permission")
        assertTrue(telecom.allOutgoingCalls.isNotEmpty() || shadowOf(context).nextStartedActivity != null)
        assertNull(Dialer.takeIntent("112"))
    }

    @Test
    fun ussdIsPlacedThroughTelecomAndNeverRemembered() {
        val context = ApplicationProvider.getApplicationContext<android.app.Application>()
        shadowOf(context).grantPermissions(android.Manifest.permission.CALL_PHONE)
        assertEquals("placed", Dialer.place(context, "*150*00#"))
        assertNull(Dialer.takeIntent("*150*00#"))
        assertEquals("placed", Dialer.place(context, "0754210331", origin = "callback_task", callbackTask = "t-9"))
        val intent = Dialer.takeIntent("+255754210331")!!
        assertEquals("t-9", intent.callbackTask)
        assertNull(Dialer.takeIntent("+255754210331")) // used once
    }

    @Test
    fun callbackTasksParse() {
        val tasks = CallbackTasks.parse(JSONArray("""[{"id":"a","number":"+255754210331","name":"Neema","reason":"Quote","requested_by":"Halima","priority":"high","due_at":5,"state":"open"}]"""))
        assertEquals("Neema", tasks.single().name)
        assertEquals("high", tasks.single().priority)
    }
}
