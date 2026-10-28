package com.kilimanjaro.communicationmanager.sms.calls

import android.app.Activity
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.telecom.Call
import com.kilimanjaro.communicationmanager.sms.safely

/** Notification buttons (private receiver, explicit immutable intents): answer, decline, hang up, call-back snooze/done. */
class CallActionReceiver : BroadcastReceiver() {
    companion object {
        const val ANSWER = "ocm.call.ANSWER"
        const val DECLINE = "ocm.call.DECLINE"
        const val HANG_UP = "ocm.call.HANG_UP"
        const val SNOOZE = "ocm.callback.SNOOZE"
        const val DONE = "ocm.callback.DONE"
    }

    override fun onReceive(context: Context, intent: Intent) = safely("call action") {
        when (intent.action) {
            ANSWER -> CallManager.ringing()?.let { OcmInCallService.answer(it) }
            DECLINE -> CallManager.ringing()?.let { OcmInCallService.decline(it) }
            HANG_UP -> CallManager.primary()?.disconnect()
            SNOOZE, DONE -> {
                val task = intent.getStringExtra("task") ?: return@safely
                CallbackTasks.report(context, task, if (intent.action == DONE) "done" else "snoozed")
                CallNotifications.cancelCallback(context, intent.getIntExtra("notification", 0))
            }
        }
    }
}

/**
 * Places a call after a person tapped something (a missed-call or call-back notification). An Activity, so the call is
 * placed from the foreground. Never started without a tap: the server can only ask; the staff member dials.
 */
class PlaceCallActivity : Activity() {
    companion object {
        fun intent(context: Context, number: String, origin: String, task: String?) =
            Intent(context, PlaceCallActivity::class.java).putExtra("number", number).putExtra("origin", origin).putExtra("task", task)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_NO_HISTORY)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        safely("place call") {
            val number = intent.getStringExtra("number").orEmpty()
            val task = intent.getStringExtra("task")
            if (Dialer.place(this, number, origin = intent.getStringExtra("origin") ?: "manual", callbackTask = task) == "placed" && task != null) {
                CallbackTasks.report(this, task, "dialed")
            }
        }
        finish()
    }
}

/** Unused-call guard for code that only needs a Call's number. */
internal fun Call.number(): String? = details.handle?.schemeSpecificPart
