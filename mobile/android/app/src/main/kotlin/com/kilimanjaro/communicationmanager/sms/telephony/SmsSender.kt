package com.kilimanjaro.communicationmanager.sms.telephony

import android.app.Activity
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Telephony
import android.telephony.SmsManager
import android.telephony.SubscriptionManager
import com.kilimanjaro.communicationmanager.sms.bridge.EventBus
import com.kilimanjaro.communicationmanager.sms.bridge.SendRequest
import com.kilimanjaro.communicationmanager.sms.bridge.SendResult
import com.kilimanjaro.communicationmanager.sms.data.SyncStore
import com.kilimanjaro.communicationmanager.sms.mms.MmsSender
import java.util.concurrent.atomic.AtomicInteger

/**
 * Sends SMS on the chosen SIM. State machine per message: outbox row → (admin messages: durable "sending" mark) →
 * SmsManager → per-part sent results → sent/failed → delivery report → delivered.
 *
 * At most once: for admin messages the durable mark is written *before* SmsManager is called and a client_uuid that
 * was already started is refused, so a crash or a re-offered lease can never send twice.
 */
object SmsSender {
    const val ACTION_SENT = "com.kilimanjaro.communicationmanager.sms.SMS_SENT"
    const val ACTION_DELIVERED = "com.kilimanjaro.communicationmanager.sms.SMS_DELIVERED"
    const val EXTRA_URI = "uri"
    const val EXTRA_UUID = "client_uuid"
    const val EXTRA_PARTS = "parts"
    const val EXTRA_PART = "part"
    private val requestCodes = AtomicInteger((System.currentTimeMillis() % 100000).toInt())

    // App-defined error codes the server explains (see modules/sms/services/outbound.py ERROR_REASONS).
    const val ERROR_NOT_DEFAULT = 1001
    const val ERROR_NO_SIM = 1004

    fun manager(context: Context, subId: Int?): SmsManager {
        val base = context.getSystemService(SmsManager::class.java)
        val id = subId ?: SubscriptionManager.getDefaultSmsSubscriptionId()
        return if (id != SubscriptionManager.INVALID_SUBSCRIPTION_ID) base.createForSubscriptionId(id) else base
    }

    fun send(context: Context, request: SendRequest): SendResult {
        val admin = request.origin == "admin"
        val store = SyncStore.get(context)
        if (admin && store != null && !store.startOutbound(request.clientUuid, request.sentBy)) {
            return SendResult(clientUuid = request.clientUuid, state = "duplicate")
        }
        if (Telephony.Sms.getDefaultSmsPackage(context) != context.packageName) {
            if (admin) store?.updateOutbound(request.clientUuid, "failed", errorCode = ERROR_NOT_DEFAULT)
            return SendResult(clientUuid = request.clientUuid, state = "failed", errorCode = ERROR_NOT_DEFAULT.toLong())
        }
        if (request.addresses.size > 1 || request.attachmentUris.isNotEmpty()) {
            return MmsSender.send(context, request)
        }
        val address = request.addresses.first()
        val subId = request.subscriptionId?.toInt()
        val uri = Provider.insertOutbox(context, address, request.body, subId)
            ?: return SendResult(clientUuid = request.clientUuid, state = "failed", errorCode = 1)
        val providerId = uri.lastPathSegment?.toLongOrNull()
        val sms = try { manager(context, subId) } catch (e: Exception) { null }
        if (sms == null) {
            Provider.setSmsType(context, uri, Telephony.Sms.MESSAGE_TYPE_FAILED, ERROR_NO_SIM)
            if (admin) store?.updateOutbound(request.clientUuid, "failed", providerId, ERROR_NO_SIM)
            return SendResult(clientUuid = request.clientUuid, state = "failed", providerId = providerId, errorCode = ERROR_NO_SIM.toLong())
        }
        val parts = sms.divideMessage(request.body)
        if (admin) store?.updateOutbound(request.clientUuid, "sending", providerId, parts = parts.size)
        // The provider row exists now: report it (linked to the admin message by client_uuid).
        Provider.sms(context, uri)?.let { store?.appendEvent("message.upsert", Provider.payload(it, if (admin) request.clientUuid else null)) }
        val sent = ArrayList<PendingIntent>()
        val delivered = ArrayList<PendingIntent>()
        parts.indices.forEach { index ->
            sent += pending(context, ACTION_SENT, uri, request.clientUuid.takeIf { admin }, parts.size, index)
            delivered += pending(context, ACTION_DELIVERED, uri, request.clientUuid.takeIf { admin }, parts.size, index)
        }
        if (parts.size > 1) sms.sendMultipartTextMessage(address, null, parts, sent, if (request.deliveryReport) delivered else null)
        else sms.sendTextMessage(address, null, request.body, sent.first(), if (request.deliveryReport) delivered.first() else null)
        EventBus.emit("send_state", clientUuid = request.clientUuid, state = "sending", providerId = providerId)
        return SendResult(clientUuid = request.clientUuid, state = "sending", providerId = providerId, parts = parts.size.toLong())
    }

    /**
     * FLAG_MUTABLE is required (the system fills in errorCode, pdu and format extras). It is safe here because the
     * intent is explicit (component set) and each part has its own request code.
     */
    private fun pending(context: Context, action: String, uri: Uri, clientUuid: String?, parts: Int, part: Int): PendingIntent {
        val target = if (action == ACTION_SENT) SmsSentReceiver::class.java else SmsDeliveredReceiver::class.java
        val intent = Intent(context, target).setAction(action).setPackage(context.packageName)
            .putExtra(EXTRA_URI, uri.toString()).putExtra(EXTRA_PARTS, parts).putExtra(EXTRA_PART, part)
            .apply { clientUuid?.let { putExtra(EXTRA_UUID, it) } }
        return PendingIntent.getBroadcast(context, requestCodes.incrementAndGet(), intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE)
    }
}

/** Per-part send result. The message is sent when the last part succeeds; any failed part fails the message. */
class SmsSentReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != SmsSender.ACTION_SENT) return
        val uri = Uri.parse(intent.getStringExtra(SmsSender.EXTRA_URI) ?: return)
        val clientUuid = intent.getStringExtra(SmsSender.EXTRA_UUID)
        val last = intent.getIntExtra(SmsSender.EXTRA_PART, 0) == intent.getIntExtra(SmsSender.EXTRA_PARTS, 1) - 1
        val store = SyncStore.get(context)
        val providerId = uri.lastPathSegment?.toLongOrNull()
        if (resultCode == Activity.RESULT_OK) {
            if (!last) return
            Provider.setSmsType(context, uri, Telephony.Sms.MESSAGE_TYPE_SENT)
            clientUuid?.let { store?.updateOutbound(it, "sent", providerId, parts = intent.getIntExtra(SmsSender.EXTRA_PARTS, 1)) }
        } else {
            val code = intent.getIntExtra("errorCode", resultCode)
            Provider.setSmsType(context, uri, Telephony.Sms.MESSAGE_TYPE_FAILED, code)
            clientUuid?.let { store?.updateOutbound(it, "failed", providerId, errorCode = resultCode) }
            Notifications.sendFailed(context, uri)
        }
        Provider.sms(context, uri)?.let { store?.appendEvent("message.upsert", Provider.payload(it, clientUuid)) }
        EventBus.emit("send_state", clientUuid = clientUuid, state = if (resultCode == Activity.RESULT_OK) "sent" else "failed", providerId = providerId)
        SyncTrigger.now(context)
    }
}

class SmsDeliveredReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != SmsSender.ACTION_DELIVERED) return
        val uri = Uri.parse(intent.getStringExtra(SmsSender.EXTRA_URI) ?: return)
        val pdu = intent.getByteArrayExtra("pdu") ?: return
        val report = android.telephony.SmsMessage.createFromPdu(pdu, intent.getStringExtra("format"))
        val status = report?.status ?: return
        val delivered = status == Telephony.Sms.STATUS_COMPLETE
        Provider.setSmsStatus(context, uri, if (delivered) Telephony.Sms.STATUS_COMPLETE else Telephony.Sms.STATUS_FAILED)
        val clientUuid = intent.getStringExtra(SmsSender.EXTRA_UUID)
        val store = SyncStore.get(context)
        if (delivered) clientUuid?.let { store?.updateOutbound(it, "delivered", uri.lastPathSegment?.toLongOrNull()) }
        Provider.sms(context, uri)?.let { store?.appendEvent("message.upsert", Provider.payload(it, clientUuid)) }
        EventBus.emit("send_state", clientUuid = clientUuid, state = if (delivered) "delivered" else "failed")
        SyncTrigger.now(context)
    }
}
