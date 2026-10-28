package com.kilimanjaro.communicationmanager.sms.telephony

import android.app.Activity
import android.app.PendingIntent
import android.app.role.RoleManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Telephony
import android.telephony.SmsManager
import android.telephony.SubscriptionManager
import com.kilimanjaro.communicationmanager.sms.bridge.EventBus
import com.kilimanjaro.communicationmanager.sms.bridge.SendRequest
import com.kilimanjaro.communicationmanager.sms.bridge.SendResult
import com.kilimanjaro.communicationmanager.sms.data.SyncStore
import com.kilimanjaro.communicationmanager.sms.mms.MmsSender
import com.kilimanjaro.communicationmanager.sms.safely
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
    const val ERROR_REFUSED = 1005

    /**
     * SmsManager for one SIM. createForSubscriptionId and SmsManager as a system service exist only on Android 12+;
     * on Android 10 and 11 calling them threw NoSuchMethodError, so every send failed (and crashed the process when
     * it ran in a receiver: notification reply, reply-with-message, admin messages sent in the background).
     */
    @Suppress("DEPRECATION")
    fun manager(context: Context, subId: Int?): SmsManager {
        val id = subId ?: SubscriptionManager.getDefaultSmsSubscriptionId()
        val valid = id != SubscriptionManager.INVALID_SUBSCRIPTION_ID
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val base = context.getSystemService(SmsManager::class.java)
            return if (valid) base.createForSubscriptionId(id) else base
        }
        return if (valid) SmsManager.getSmsManagerForSubscriptionId(id) else SmsManager.getDefault()
    }

    /**
     * RoleManager is the source of truth for the SMS role. Telephony.Sms.getDefaultSmsPackage returned null on Android
     * 16 while the role was held (the platform reported a lost app-op it could not repair from this process), which
     * refused every send with "not the default SMS app".
     */
    fun isDefaultSmsApp(context: Context): Boolean =
        context.getSystemService(RoleManager::class.java)?.isRoleHeld(RoleManager.ROLE_SMS) == true

    fun send(context: Context, request: SendRequest): SendResult {
        val admin = request.origin == "admin"
        val store = SyncStore.get(context)
        if (admin && store != null && !store.startOutbound(request.clientUuid, request.sentBy)) {
            return SendResult(clientUuid = request.clientUuid, state = "duplicate")
        }
        if (!isDefaultSmsApp(context)) {
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
        val written = Provider.sms(context, uri)
        written?.let { store?.appendEvent("message.upsert", Provider.payload(it, if (admin) request.clientUuid else null)) }
        val threadId = written?.threadId
        val sent = ArrayList<PendingIntent>()
        val delivered = ArrayList<PendingIntent>()
        parts.indices.forEach { index ->
            sent += pending(context, ACTION_SENT, uri, request.clientUuid.takeIf { admin }, parts.size, index)
            delivered += pending(context, ACTION_DELIVERED, uri, request.clientUuid.takeIf { admin }, parts.size, index)
        }
        try {
            if (parts.size > 1) sms.sendMultipartTextMessage(address, null, parts, sent, if (request.deliveryReport) delivered else null)
            else sms.sendTextMessage(address, null, request.body, sent.first(), if (request.deliveryReport) delivered.first() else null)
        } catch (e: Exception) {
            // Refused before it reached the radio (bad address, SIM gone, OEM restriction): nothing was sent.
            Provider.setSmsType(context, uri, Telephony.Sms.MESSAGE_TYPE_FAILED, ERROR_REFUSED)
            if (admin) store?.updateOutbound(request.clientUuid, "failed", providerId, ERROR_REFUSED)
            Provider.sms(context, uri)?.let { store?.appendEvent("message.upsert", Provider.payload(it, if (admin) request.clientUuid else null)) }
            EventBus.emit("send_state", clientUuid = request.clientUuid, state = "failed", providerId = providerId, threadId = threadId)
            return SendResult(clientUuid = request.clientUuid, state = "failed", providerId = providerId, errorCode = ERROR_REFUSED.toLong())
        }
        EventBus.emit("send_state", clientUuid = request.clientUuid, state = "sending", providerId = providerId, threadId = threadId)
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
        val providerId = uri.lastPathSegment?.toLongOrNull()
        val ok = resultCode == Activity.RESULT_OK
        if (ok && !last) return
        var threadId: Long? = null
        safely("sms sent") {
            val store = SyncStore.get(context)
            if (ok) {
                Provider.setSmsType(context, uri, Telephony.Sms.MESSAGE_TYPE_SENT)
                clientUuid?.let { store?.updateOutbound(it, "sent", providerId, parts = intent.getIntExtra(SmsSender.EXTRA_PARTS, 1)) }
            } else {
                val code = intent.getIntExtra("errorCode", resultCode)
                Provider.setSmsType(context, uri, Telephony.Sms.MESSAGE_TYPE_FAILED, code)
                clientUuid?.let { store?.updateOutbound(it, "failed", providerId, errorCode = resultCode) }
                safely("sms failed notify") { Notifications.sendFailed(context, uri) }
            }
            Provider.sms(context, uri)?.let {
                threadId = it.threadId
                store?.appendEvent("message.upsert", Provider.payload(it, clientUuid))
            }
        }
        EventBus.emit("send_state", clientUuid = clientUuid, state = if (ok) "sent" else "failed", providerId = providerId, threadId = threadId)
        safely("sms trigger") { SyncTrigger.now(context) }
    }
}

class SmsDeliveredReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != SmsSender.ACTION_DELIVERED) return
        val uri = Uri.parse(intent.getStringExtra(SmsSender.EXTRA_URI) ?: return)
        val pdu = intent.getByteArrayExtra("pdu") ?: return
        val clientUuid = intent.getStringExtra(SmsSender.EXTRA_UUID)
        var delivered = false
        var threadId: Long? = null
        safely("sms delivered") {
            // Some modems send malformed status reports; createFromPdu can throw on them.
            val report = android.telephony.SmsMessage.createFromPdu(pdu, intent.getStringExtra("format"))
            val status = report?.status ?: return
            delivered = status == Telephony.Sms.STATUS_COMPLETE
            Provider.setSmsStatus(context, uri, if (delivered) Telephony.Sms.STATUS_COMPLETE else Telephony.Sms.STATUS_FAILED)
            val store = SyncStore.get(context)
            if (delivered) clientUuid?.let { store?.updateOutbound(it, "delivered", uri.lastPathSegment?.toLongOrNull()) }
            Provider.sms(context, uri)?.let {
                threadId = it.threadId
                store?.appendEvent("message.upsert", Provider.payload(it, clientUuid))
            }
        }
        EventBus.emit("send_state", clientUuid = clientUuid, state = if (delivered) "delivered" else "failed", providerId = uri.lastPathSegment?.toLongOrNull(), threadId = threadId)
        safely("sms trigger") { SyncTrigger.now(context) }
    }
}
