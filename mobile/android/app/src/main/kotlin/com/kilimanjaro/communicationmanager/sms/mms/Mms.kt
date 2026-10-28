package com.kilimanjaro.communicationmanager.sms.mms

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import android.provider.Telephony
import androidx.core.content.FileProvider
import com.kilimanjaro.communicationmanager.sms.bridge.EventBus
import com.kilimanjaro.communicationmanager.sms.bridge.SendRequest
import com.kilimanjaro.communicationmanager.sms.bridge.SendResult
import com.kilimanjaro.communicationmanager.sms.data.SyncStore
import com.kilimanjaro.communicationmanager.sms.safely
import com.kilimanjaro.communicationmanager.sms.telephony.Blocking
import com.kilimanjaro.communicationmanager.sms.telephony.Notifications
import com.kilimanjaro.communicationmanager.sms.telephony.Provider
import com.kilimanjaro.communicationmanager.sms.telephony.SmsSender
import com.kilimanjaro.communicationmanager.sms.telephony.SyncTrigger
import java.io.File
import java.util.UUID
import java.util.concurrent.atomic.AtomicInteger

private val codes = AtomicInteger((System.currentTimeMillis() % 100000).toInt() + 50000)
private const val AUTHORITY_SUFFIX = ".mmsfiles"

private fun mmsDir(context: Context) = File(context.cacheDir, "mms").apply { mkdirs() }
private fun fileUri(context: Context, file: File): Uri = FileProvider.getUriForFile(context, context.packageName + AUTHORITY_SUFFIX, file)

/** WAP_PUSH_DELIVER (application/vnd.wap.mms-message), protected by BROADCAST_WAP_PUSH. Downloads per the setting. */
class MmsReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Telephony.Sms.Intents.WAP_PUSH_DELIVER_ACTION) return
        safely("mms notification") {
            val notification = Pdu.parseNotification(intent.getByteArrayExtra("data") ?: return) ?: return
            if (notification.from != null && Blocking.isBlocked(context, notification.from)) return
            var mode = "wifi"
            safely("mms setting") { mode = SyncStore.get(context)?.setting("mms_download", "wifi") ?: "wifi" }
            val cm = context.getSystemService(ConnectivityManager::class.java)
            val wifi = cm.getNetworkCapabilities(cm.activeNetwork)?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true
            if (mode == "never" || (mode == "wifi" && !wifi)) {
                Notifications.mmsWaiting(context, notification.from)
                return
            }
            download(context, notification.contentLocation, intent.getIntExtra("subscription", -1).takeIf { it >= 0 })
        }
    }

    companion object {
        fun download(context: Context, location: String, subId: Int?) {
            val file = File(mmsDir(context), "in-${UUID.randomUUID()}.pdu")
            val done = Intent(context, MmsDownloadedReceiver::class.java).setPackage(context.packageName).putExtra("file", file.absolutePath).putExtra("sub", subId ?: -1)
            val pending = PendingIntent.getBroadcast(context, codes.incrementAndGet(), done, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE)
            SmsSender.manager(context, subId).downloadMultimediaMessage(context, location, fileUri(context, file), null, pending)
        }
    }
}

/** The downloaded M-Retrieve.conf: store it as an inbox MMS (message, addresses, parts) and queue the upload. */
class MmsDownloadedReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val file = File(intent.getStringExtra("file") ?: return)
        val pending = goAsync()
        Thread {
            val ok = resultCode == android.app.Activity.RESULT_OK
            try {
                safely("mms downloaded") {
                    if (!ok || !file.exists()) return@safely
                    val retrieved = Pdu.parseRetrieve(file.readBytes()) ?: return@safely
                    val from = retrieved.from ?: return@safely
                    val subId = intent.getIntExtra("sub", -1).takeIf { it >= 0 }
                    val id = MmsStore.insert(context, Telephony.Mms.MESSAGE_BOX_INBOX, from, retrieved.to, retrieved.subject, retrieved.parts, subId) ?: return@safely
                    val message = Provider.mms(context, id) ?: return@safely
                    safely("mms outbox") {
                        val store = SyncStore.get(context)
                        store?.appendEvent("message.upsert", MmsStore.payloadWithHashes(context, message))
                        message.parts.forEach { part -> part.uri?.let { store?.addPendingMedia(message.providerId, message.date, part.seq.toInt(), it, part.size) } }
                    }
                    safely("mms notify") { Notifications.incoming(context, message) }
                    EventBus.emit("message_received", threadId = message.threadId, providerId = message.providerId)
                    safely("mms trigger") { SyncTrigger.now(context) }
                }
            } finally {
                file.delete()
                pending.finish()
            }
        }.start()
    }
}

/** Group messages and attachments go out as MMS (M-Send.req through SmsManager.sendMultimediaMessage). */
object MmsSender {
    fun send(context: Context, request: SendRequest): SendResult {
        val admin = request.origin == "admin"
        val store = SyncStore.get(context)
        val parts = mutableListOf<Pdu.Part>()
        if (request.body.isNotEmpty()) parts += Pdu.Part("text/plain", "text.txt", request.body.toByteArray(Charsets.UTF_8))
        request.attachmentUris.forEachIndexed { index, value ->
            val uri = Uri.parse(value)
            val type = context.contentResolver.getType(uri) ?: "application/octet-stream"
            val data = context.contentResolver.openInputStream(uri)?.use { it.readBytes() } ?: return@forEachIndexed
            parts += Pdu.Part(type, "attachment$index", data)
        }
        val subId = request.subscriptionId?.toInt()
        val id = MmsStore.insert(context, Telephony.Mms.MESSAGE_BOX_OUTBOX, null, request.addresses, null, parts, subId)
            ?: return SendResult(clientUuid = request.clientUuid, state = "failed", errorCode = 1)
        val file = File(mmsDir(context), "out-${UUID.randomUUID()}.pdu").apply { writeBytes(Pdu.encodeSendReq(UUID.randomUUID().toString().take(12), request.addresses, null, parts)) }
        if (admin) store?.updateOutbound(request.clientUuid, "sending", id)
        Provider.mms(context, id)?.let { store?.appendEvent("message.upsert", MmsStore.payloadWithHashes(context, it).put("client_uuid", if (admin) request.clientUuid else null)) }
        val sent = Intent(context, MmsSentReceiver::class.java).setPackage(context.packageName)
            .putExtra("id", id).putExtra("file", file.absolutePath).apply { if (admin) putExtra(SmsSender.EXTRA_UUID, request.clientUuid) }
        val pending = PendingIntent.getBroadcast(context, codes.incrementAndGet(), sent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE)
        SmsSender.manager(context, subId).sendMultimediaMessage(context, fileUri(context, file), null, null, pending)
        return SendResult(clientUuid = request.clientUuid, state = "sending", providerId = id)
    }
}

class MmsSentReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val id = intent.getLongExtra("id", -1).takeIf { it >= 0 } ?: return
        File(intent.getStringExtra("file") ?: "").delete()
        val ok = resultCode == android.app.Activity.RESULT_OK
        val clientUuid = intent.getStringExtra(SmsSender.EXTRA_UUID)
        safely("mms sent") {
            context.contentResolver.update(Uri.withAppendedPath(Telephony.Mms.CONTENT_URI, id.toString()), ContentValues().apply {
                put(Telephony.Mms.MESSAGE_BOX, if (ok) Telephony.Mms.MESSAGE_BOX_SENT else Telephony.Mms.MESSAGE_BOX_FAILED)
            }, null, null)
            val store = SyncStore.get(context)
            clientUuid?.let { store?.updateOutbound(it, if (ok) "sent" else "failed", id, errorCode = if (ok) null else resultCode) }
            Provider.mms(context, id)?.let { store?.appendEvent("message.upsert", MmsStore.payloadWithHashes(context, it).put("client_uuid", clientUuid)) }
        }
        EventBus.emit("send_state", clientUuid = clientUuid, state = if (ok) "sent" else "failed", providerId = id)
        safely("mms trigger") { SyncTrigger.now(context) }
    }
}

object MmsStore {
    /** Insert an MMS with its addresses and parts into the Telephony provider. Returns the provider id. */
    fun insert(context: Context, box: Int, from: String?, to: List<String>, subject: String?, parts: List<Pdu.Part>, subId: Int?): Long? {
        val resolver = context.contentResolver
        val recipients = (listOfNotNull(from) + to).toSet()
        val threadId = Telephony.Threads.getOrCreateThreadId(context, recipients)
        val uri = resolver.insert(Telephony.Mms.CONTENT_URI, ContentValues().apply {
            put(Telephony.Mms.THREAD_ID, threadId); put(Telephony.Mms.DATE, System.currentTimeMillis() / 1000); put(Telephony.Mms.MESSAGE_BOX, box)
            put(Telephony.Mms.READ, if (box == Telephony.Mms.MESSAGE_BOX_INBOX) 0 else 1); put(Telephony.Mms.SEEN, if (box == Telephony.Mms.MESSAGE_BOX_INBOX) 0 else 1)
            put(Telephony.Mms.MESSAGE_TYPE, if (box == Telephony.Mms.MESSAGE_BOX_INBOX) Pdu.TYPE_RETRIEVE_CONF else Pdu.TYPE_SEND_REQ)
            put(Telephony.Mms.CONTENT_TYPE, "application/vnd.wap.multipart.mixed"); put(Telephony.Mms.MMS_VERSION, 0x12)
            subject?.let { put(Telephony.Mms.SUBJECT, it) }
            subId?.let { put(Telephony.Mms.SUBSCRIPTION_ID, it) }
        }) ?: return null
        val id = uri.lastPathSegment?.toLongOrNull() ?: return null
        from?.let { insertAddress(context, id, it, 137) }
        to.forEach { insertAddress(context, id, it, 151) }
        parts.forEachIndexed { index, part ->
            val partUri = resolver.insert(Uri.parse("content://mms/$id/part"), ContentValues().apply {
                put(Telephony.Mms.Part.MSG_ID, id); put(Telephony.Mms.Part.SEQ, index); put(Telephony.Mms.Part.CONTENT_TYPE, part.contentType)
                put(Telephony.Mms.Part.NAME, part.name); put(Telephony.Mms.Part.CONTENT_LOCATION, part.name)
                if (part.contentType == "text/plain") { put(Telephony.Mms.Part.CHARSET, 106); put(Telephony.Mms.Part.TEXT, String(part.data, Charsets.UTF_8)) }
            }) ?: return@forEachIndexed
            if (part.contentType != "text/plain") resolver.openOutputStream(partUri)?.use { it.write(part.data) }
        }
        return id
    }

    private fun insertAddress(context: Context, id: Long, address: String, type: Int) {
        context.contentResolver.insert(Uri.parse("content://mms/$id/addr"), ContentValues().apply {
            put(Telephony.Mms.Addr.ADDRESS, address); put(Telephony.Mms.Addr.TYPE, type); put(Telephony.Mms.Addr.CHARSET, 106)
        })
    }

    /** The upsert payload with each part's SHA-256 (the server verifies uploads against it). */
    fun payloadWithHashes(context: Context, message: com.kilimanjaro.communicationmanager.sms.bridge.ProviderMessage) = Provider.payload(message).apply {
        val parts = optJSONArray("parts") ?: return@apply
        for (i in 0 until parts.length()) {
            val uri = message.parts[i].uri ?: continue
            val digest = java.security.MessageDigest.getInstance("SHA-256")
            context.contentResolver.openInputStream(Uri.parse(uri))?.use { input ->
                val buffer = ByteArray(16 * 1024)
                while (true) { val n = input.read(buffer); if (n < 0) break; digest.update(buffer, 0, n) }
            }
            parts.getJSONObject(i).put("sha256", digest.digest().joinToString("") { "%02x".format(it) })
        }
    }
}
