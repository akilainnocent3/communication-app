package com.kilimanjaro.communicationmanager.sms.telephony

import android.content.ContentValues
import android.content.Context
import android.database.Cursor
import android.net.Uri
import android.provider.Telephony
import com.kilimanjaro.communicationmanager.sms.bridge.MmsPartData
import com.kilimanjaro.communicationmanager.sms.bridge.ProviderMessage
import com.kilimanjaro.communicationmanager.sms.bridge.ThreadSummary
import org.json.JSONArray
import org.json.JSONObject

/**
 * Reads and writes the Telephony provider. As the default SMS app we own the message store: the system does not
 * write incoming messages or our sent messages for us.
 */
object Provider {
    private fun Cursor.long(column: String): Long = getLong(getColumnIndexOrThrow(column))
    private fun Cursor.int(column: String): Int = getInt(getColumnIndexOrThrow(column))
    private fun Cursor.str(column: String): String? = getString(getColumnIndexOrThrow(column))
    private fun Cursor.intOrNull(column: String): Int? = getColumnIndex(column).takeIf { it >= 0 && !isNull(it) }?.let { getInt(it) }

    fun smsStatus(type: Int, status: Int): String = when (type) {
        Telephony.Sms.MESSAGE_TYPE_INBOX -> "received"
        Telephony.Sms.MESSAGE_TYPE_OUTBOX, Telephony.Sms.MESSAGE_TYPE_QUEUED -> "sending"
        Telephony.Sms.MESSAGE_TYPE_FAILED -> "failed"
        Telephony.Sms.MESSAGE_TYPE_SENT -> if (status == Telephony.Sms.STATUS_COMPLETE) "delivered" else "sent"
        else -> "sent"
    }

    // --- Writes ---------------------------------------------------------------------------------------------

    fun insertInbox(context: Context, address: String, body: String, date: Long, dateSent: Long, subId: Int?): Uri? =
        context.contentResolver.insert(Telephony.Sms.Inbox.CONTENT_URI, ContentValues().apply {
            put(Telephony.Sms.ADDRESS, address)
            put(Telephony.Sms.BODY, body)
            put(Telephony.Sms.DATE, date)
            put(Telephony.Sms.DATE_SENT, dateSent)
            put(Telephony.Sms.READ, 0)
            put(Telephony.Sms.SEEN, 0)
            put(Telephony.Sms.TYPE, Telephony.Sms.MESSAGE_TYPE_INBOX)
            subId?.let { put(Telephony.Sms.SUBSCRIPTION_ID, it) }
        })

    fun insertOutbox(context: Context, address: String, body: String, subId: Int?): Uri? =
        context.contentResolver.insert(Telephony.Sms.Outbox.CONTENT_URI, ContentValues().apply {
            put(Telephony.Sms.ADDRESS, address)
            put(Telephony.Sms.BODY, body)
            put(Telephony.Sms.DATE, System.currentTimeMillis())
            put(Telephony.Sms.READ, 1)
            put(Telephony.Sms.SEEN, 1)
            put(Telephony.Sms.TYPE, Telephony.Sms.MESSAGE_TYPE_OUTBOX)
            put(Telephony.Sms.STATUS, Telephony.Sms.STATUS_PENDING)
            subId?.let { put(Telephony.Sms.SUBSCRIPTION_ID, it) }
        })

    fun setSmsType(context: Context, uri: Uri, type: Int, errorCode: Int? = null) {
        context.contentResolver.update(uri, ContentValues().apply {
            put(Telephony.Sms.TYPE, type)
            errorCode?.let { put(Telephony.Sms.ERROR_CODE, it) }
        }, null, null)
    }

    fun setSmsStatus(context: Context, uri: Uri, status: Int) {
        context.contentResolver.update(uri, ContentValues().apply { put(Telephony.Sms.STATUS, status) }, null, null)
    }

    fun markThreadRead(context: Context, threadId: Long) {
        val values = ContentValues().apply { put("read", 1); put("seen", 1) }
        context.contentResolver.update(Telephony.Sms.CONTENT_URI, values, "thread_id = ? AND read = 0", arrayOf(threadId.toString()))
        context.contentResolver.update(Telephony.Mms.CONTENT_URI, values, "thread_id = ? AND read = 0", arrayOf(threadId.toString()))
    }

    fun deleteMessage(context: Context, kind: String, id: Long) {
        val base = if (kind == "mms") Telephony.Mms.CONTENT_URI else Telephony.Sms.CONTENT_URI
        context.contentResolver.delete(Uri.withAppendedPath(base, id.toString()), null, null)
    }

    fun deleteThread(context: Context, threadId: Long) {
        context.contentResolver.delete(Uri.withAppendedPath(Telephony.Threads.CONTENT_URI, threadId.toString()), null, null)
    }

    // --- Reads ----------------------------------------------------------------------------------------------

    fun sms(context: Context, uri: Uri): ProviderMessage? =
        context.contentResolver.query(uri, null, null, null, null)?.use { if (it.moveToFirst()) smsFrom(it) else null }

    private fun smsFrom(c: Cursor): ProviderMessage {
        val type = c.int(Telephony.Sms.TYPE)
        return ProviderMessage(
            providerId = c.long(Telephony.Sms._ID), kind = "sms", threadId = c.long(Telephony.Sms.THREAD_ID),
            addresses = listOf(c.str(Telephony.Sms.ADDRESS) ?: ""), body = c.str(Telephony.Sms.BODY) ?: "", date = c.long(Telephony.Sms.DATE),
            outbound = type != Telephony.Sms.MESSAGE_TYPE_INBOX, read = c.int(Telephony.Sms.READ) == 1, status = smsStatus(type, c.int(Telephony.Sms.STATUS)),
            subscriptionId = c.intOrNull(Telephony.Sms.SUBSCRIPTION_ID)?.toLong(), errorCode = c.intOrNull(Telephony.Sms.ERROR_CODE)?.toLong(),
            parts = emptyList(), subject = null,
        )
    }

    fun threads(context: Context, limit: Int, offset: Int): List<ThreadSummary> {
        val uri = Uri.parse("content://mms-sms/conversations?simple=true")
        val result = mutableListOf<ThreadSummary>()
        context.contentResolver.query(uri, arrayOf("_id", "date", "message_count", "recipient_ids", "snippet", "read"), null, null, "date DESC")?.use { c ->
            if (!c.moveToPosition(offset)) return result
            do {
                val threadId = c.getLong(0)
                val addresses = recipients(context, c.getString(3) ?: "")
                result += ThreadSummary(
                    threadId = threadId, addresses = addresses.ifEmpty { listOf("") }, snippet = c.getString(4) ?: "", date = c.getLong(1),
                    unreadCount = unread(context, threadId), messageCount = c.getLong(2), hasMms = false,
                )
            } while (result.size < limit && c.moveToNext())
        }
        return result
    }

    private fun unread(context: Context, threadId: Long): Long =
        context.contentResolver.query(Telephony.Sms.Inbox.CONTENT_URI, arrayOf("count(*)"), "thread_id = ? AND read = 0", arrayOf(threadId.toString()), null)
            ?.use { if (it.moveToFirst()) it.getLong(0) else 0L } ?: 0L

    private fun recipients(context: Context, ids: String): List<String> = ids.split(" ").filter { it.isNotBlank() }.mapNotNull { id ->
        context.contentResolver.query(Uri.parse("content://mms-sms/canonical-address/$id"), null, null, null, null)?.use { if (it.moveToFirst()) it.getString(0) else null }
    }

    fun messages(context: Context, threadId: Long, limit: Int, beforeDate: Long?): List<ProviderMessage> {
        val selection = "thread_id = ?" + if (beforeDate != null) " AND date < ?" else ""
        val args = listOfNotNull(threadId.toString(), beforeDate?.toString()).toTypedArray()
        val sms = context.contentResolver.query(Telephony.Sms.CONTENT_URI, null, selection, args, "date DESC LIMIT $limit")?.use { c ->
            buildList { while (c.moveToNext()) add(smsFrom(c)) }
        } ?: emptyList()
        val mmsArgs = listOfNotNull(threadId.toString(), beforeDate?.let { (it / 1000).toString() }).toTypedArray()
        val mms = context.contentResolver.query(Telephony.Mms.CONTENT_URI, null, selection, mmsArgs, "date DESC LIMIT $limit")?.use { c ->
            buildList { while (c.moveToNext()) add(mmsFrom(context, c)) }
        } ?: emptyList()
        return (sms + mms).sortedByDescending { it.date }.take(limit)
    }

    fun messagesSince(context: Context, since: Long, limit: Int, offset: Int): List<ProviderMessage> {
        val sms = context.contentResolver.query(Telephony.Sms.CONTENT_URI, null, "date >= ?", arrayOf(since.toString()), "date DESC LIMIT $limit OFFSET $offset")?.use { c ->
            buildList { while (c.moveToNext()) add(smsFrom(c)) }
        } ?: emptyList()
        // MMS dates are in seconds. Their pages follow the SMS pages (offset past the SMS count).
        val smsCount = context.contentResolver.query(Telephony.Sms.CONTENT_URI, arrayOf("count(*)"), "date >= ?", arrayOf(since.toString()), null)?.use { if (it.moveToFirst()) it.getInt(0) else 0 } ?: 0
        if (sms.size >= limit) return sms
        val mmsOffset = (offset - smsCount).coerceAtLeast(0)
        val mms = context.contentResolver.query(Telephony.Mms.CONTENT_URI, null, "date >= ?", arrayOf((since / 1000).toString()), "date DESC LIMIT ${limit - sms.size} OFFSET $mmsOffset")?.use { c ->
            buildList { while (c.moveToNext()) add(mmsFrom(context, c)) }
        } ?: emptyList()
        return sms + mms
    }

    fun mms(context: Context, id: Long): ProviderMessage? =
        context.contentResolver.query(Uri.withAppendedPath(Telephony.Mms.CONTENT_URI, id.toString()), null, null, null, null)?.use { if (it.moveToFirst()) mmsFrom(context, it) else null }

    private fun mmsFrom(context: Context, c: Cursor): ProviderMessage {
        val id = c.long(Telephony.Mms._ID)
        val box = c.int(Telephony.Mms.MESSAGE_BOX)
        val parts = mutableListOf<MmsPartData>()
        var text = ""
        context.contentResolver.query(Uri.parse("content://mms/part"), null, "mid = ?", arrayOf(id.toString()), "seq")?.use { p ->
            var seq = 0L
            while (p.moveToNext()) {
                val type = p.getString(p.getColumnIndexOrThrow(Telephony.Mms.Part.CONTENT_TYPE)) ?: continue
                val partId = p.getLong(p.getColumnIndexOrThrow(Telephony.Mms.Part._ID))
                when {
                    type == "text/plain" -> text += p.getString(p.getColumnIndexOrThrow(Telephony.Mms.Part.TEXT)) ?: ""
                    type == "application/smil" -> Unit
                    else -> {
                        val uri = "content://mms/part/$partId"
                        val size = context.contentResolver.openAssetFileDescriptor(Uri.parse(uri), "r")?.use { it.length } ?: 0L
                        parts += MmsPartData(seq = seq++, contentType = type, filename = p.getString(p.getColumnIndexOrThrow(Telephony.Mms.Part.NAME)), size = size, uri = uri)
                    }
                }
            }
        }
        val outbound = box != Telephony.Mms.MESSAGE_BOX_INBOX
        return ProviderMessage(
            providerId = id, kind = "mms", threadId = c.long(Telephony.Mms.THREAD_ID), addresses = mmsAddresses(context, id, outbound), body = text,
            date = c.long(Telephony.Mms.DATE) * 1000, outbound = outbound, read = c.int(Telephony.Mms.READ) == 1,
            status = when (box) { Telephony.Mms.MESSAGE_BOX_INBOX -> "received"; Telephony.Mms.MESSAGE_BOX_OUTBOX -> "sending"; Telephony.Mms.MESSAGE_BOX_FAILED -> "failed"; else -> "sent" },
            subscriptionId = c.intOrNull(Telephony.Mms.SUBSCRIPTION_ID)?.toLong(), errorCode = null, parts = parts, subject = c.str(Telephony.Mms.SUBJECT),
        )
    }

    private fun mmsAddresses(context: Context, id: Long, outbound: Boolean): List<String> {
        // PduHeaders: FROM = 137, TO = 151, CC = 130.
        val wanted = if (outbound) setOf(151, 130) else setOf(137)
        return context.contentResolver.query(Uri.parse("content://mms/$id/addr"), arrayOf("address", "type"), null, null, null)?.use { c ->
            buildList { while (c.moveToNext()) if (c.getInt(1) in wanted && c.getString(0) != "insert-address-token") add(c.getString(0)) }
        } ?: emptyList()
    }

    /** The server event payload (same shape as Dart's messagePayload). */
    fun payload(m: ProviderMessage, clientUuid: String? = null): JSONObject = JSONObject().apply {
        put("kind", m.kind); put("provider_id", m.providerId); put("date", m.date); put("thread_id", m.threadId)
        put("addresses", JSONArray(m.addresses)); put("direction", if (m.outbound) "out" else "in"); put("body", m.body)
        put("subject", m.subject ?: ""); put("is_read", m.read); put("status", m.status)
        m.subscriptionId?.let { put("sub_id", it) }
        m.errorCode?.let { put("error_code", it) }
        clientUuid?.let { put("client_uuid", it) }
        if (m.kind == "mms") put("parts", JSONArray(m.parts.map { JSONObject().apply { put("seq", it.seq); put("content_type", it.contentType); put("filename", it.filename ?: ""); put("size", it.size) } }))
    }
}
