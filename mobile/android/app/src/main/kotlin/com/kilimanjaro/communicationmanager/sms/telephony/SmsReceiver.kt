package com.kilimanjaro.communicationmanager.sms.telephony

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import android.telephony.SmsMessage
import com.kilimanjaro.communicationmanager.sms.ClassZeroActivity
import com.kilimanjaro.communicationmanager.sms.bridge.EventBus
import com.kilimanjaro.communicationmanager.sms.data.SyncStore

/**
 * SMS_DELIVER (only the default SMS app receives it; protected by BROADCAST_SMS). Works without the Flutter engine:
 * write the provider, append the outbox event, notify, then wake the sync service.
 */
class SmsReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Telephony.Sms.Intents.SMS_DELIVER_ACTION) return
        val parts = Telephony.Sms.Intents.getMessagesFromIntent(intent) ?: return
        if (parts.isEmpty()) return
        val first = parts.first()
        val address = first.displayOriginatingAddress ?: first.originatingAddress ?: return
        val body = parts.joinToString("") { it.displayMessageBody ?: "" }
        val subId = intent.getIntExtra("subscription", -1).takeIf { it >= 0 }
        if (first.messageClass == SmsMessage.MessageClass.CLASS_0) {
            // Flash SMS: shown, not stored (3GPP TS 23.038).
            context.startActivity(Intent(context, ClassZeroActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                .putExtra("address", address).putExtra("body", body))
            return
        }
        if (Blocking.isBlocked(context, address)) return
        val pending = goAsync()
        Thread {
            try {
                val uri = Provider.insertInbox(context, address, body, System.currentTimeMillis(), first.timestampMillis, subId) ?: return@Thread
                val message = Provider.sms(context, uri) ?: return@Thread
                SyncStore.get(context)?.appendEvent("message.upsert", Provider.payload(message))
                Notifications.incoming(context, message)
                EventBus.emit("message_received", threadId = message.threadId, providerId = message.providerId)
                SyncTrigger.now(context)
            } finally {
                pending.finish()
            }
        }.start()
    }
}
