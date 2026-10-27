package com.kilimanjaro.communicationmanager.sms.mms

import java.io.ByteArrayOutputStream

/**
 * Minimal MMS encapsulation (OMA-MMS-ENC 1.3 / WAP-230-WSP) for what a default SMS app must do itself:
 * read M-Notification.ind (WAP push), read M-Retrieve.conf (downloaded message) and write M-Send.req.
 * Unknown header fields are skipped with the generic WSP value rules, so new fields never break parsing.
 */
object Pdu {
    const val MESSAGE_TYPE = 0x8C
    const val TRANSACTION_ID = 0x98
    const val MMS_VERSION = 0x8D
    const val FROM = 0x89
    const val TO = 0x97
    const val CC = 0x82
    const val SUBJECT = 0x96
    const val CONTENT_TYPE = 0x84
    const val CONTENT_LOCATION = 0x83
    const val MESSAGE_SIZE = 0x8E
    const val PART_CONTENT_LOCATION = 0x8E
    const val PART_CONTENT_ID = 0xC0

    const val TYPE_SEND_REQ = 0x80
    const val TYPE_NOTIFICATION_IND = 0x82
    const val TYPE_RETRIEVE_CONF = 0x84

    /** Well-known content types (WSP Table 40) we read and write. */
    private val wellKnown = mapOf(
        0x03 to "text/plain", 0x1D to "image/gif", 0x1E to "image/jpeg", 0x20 to "image/png", 0x21 to "image/vnd.wap.wbmp",
        0x22 to "application/vnd.wap.multipart.*", 0x23 to "application/vnd.wap.multipart.mixed", 0x33 to "application/vnd.wap.multipart.related",
        0x12 to "application/vnd.wap.multipart.alternative", 0x10 to "text/x-vcard",
    )
    private val reverse = wellKnown.entries.associate { (k, v) -> v to k }

    class Part(val contentType: String, val name: String?, val data: ByteArray)
    class Notification(val transactionId: String?, val contentLocation: String, val from: String?, val size: Long?)
    class Retrieved(val from: String?, val to: List<String>, val subject: String?, val parts: List<Part>)

    /** Thrown for truncated or malformed input; the parse functions turn it into null (hostile PDUs never crash). */
    class Malformed : Exception()

    class Reader(private val data: ByteArray) {
        var pos = 0
        fun hasMore() = pos < data.size
        fun peek(): Int = if (pos < data.size) data[pos].toInt() and 0xFF else throw Malformed()
        fun byte(): Int = peek().also { pos++ }
        fun bytes(n: Int): ByteArray = if (n < 0 || pos + n > data.size) throw Malformed() else data.copyOfRange(pos, pos + n).also { pos += n }

        fun uintvar(): Long {
            var value = 0L
            while (true) {
                val b = byte()
                value = (value shl 7) or (b and 0x7F).toLong()
                if (b and 0x80 == 0) return value
            }
        }

        fun text(): String {
            if (peek() == 0x7F) pos++ // quote
            val start = pos
            while (pos < data.size && data[pos].toInt() != 0) pos++
            if (pos >= data.size) throw Malformed()
            return String(data, start, pos++ - start, Charsets.UTF_8)
        }

        fun valueLength(): Int {
            val b = byte()
            return if (b < 0x1F) b else uintvar().toInt()
        }

        fun longInteger(): Long {
            val len = byte()
            var v = 0L
            repeat(len) { v = (v shl 8) or byte().toLong() }
            return v
        }

        /** Encoded-string-value: text, or [length][charset][text]. */
        fun encodedString(): String {
            if (peek() <= 0x1F) {
                val len = valueLength()
                val end = pos + len
                if (peek() >= 0x80) byte() else longInteger()
                val s = text()
                pos = end
                return s
            }
            return text()
        }

        /** Skip one WSP value of any shape. */
        fun skipValue() {
            val b = peek()
            when {
                b >= 0x80 -> pos++
                b <= 0x1F -> { val len = valueLength(); pos += len }
                else -> text()
            }
        }

        fun contentType(): Pair<String, Int> {
            val b = peek()
            return when {
                b >= 0x80 -> Pair(wellKnown[byte() and 0x7F] ?: "application/octet-stream", pos)
                b <= 0x1F -> {
                    val len = valueLength()
                    val end = pos + len
                    val type = if (peek() >= 0x80) wellKnown[byte() and 0x7F] ?: "application/octet-stream" else text()
                    pos = end
                    Pair(type, pos)
                }
                else -> Pair(text(), pos)
            }
        }
    }

    private fun stripType(address: String) = address.substringBefore("/TYPE=")

    fun parseNotification(data: ByteArray): Notification? = try { notification(data) } catch (e: Malformed) { null }

    fun parseRetrieve(data: ByteArray): Retrieved? = try { retrieve(data) } catch (e: Malformed) { null }

    private fun notification(data: ByteArray): Notification? {
        val r = Reader(data)
        var type = -1
        var transaction: String? = null
        var location: String? = null
        var from: String? = null
        var size: Long? = null
        while (r.hasMore()) {
            when (r.byte()) {
                MESSAGE_TYPE -> type = r.byte()
                TRANSACTION_ID -> transaction = r.text()
                CONTENT_LOCATION -> location = r.text()
                MESSAGE_SIZE -> size = r.longInteger()
                CONTENT_TYPE -> break // a body follows: this is not a notification
                FROM -> { val len = r.valueLength(); val end = r.pos + len; if (r.byte() == 0x80) from = stripType(r.encodedString()); r.pos = end }
                else -> r.skipValue()
            }
        }
        return if (type == TYPE_NOTIFICATION_IND && location != null) Notification(transaction, location, from, size) else null
    }

    private fun retrieve(data: ByteArray): Retrieved? {
        val r = Reader(data)
        var from: String? = null
        val to = mutableListOf<String>()
        var subject: String? = null
        var type = -1
        while (r.hasMore()) {
            val field = r.byte()
            when (field) {
                MESSAGE_TYPE -> type = r.byte()
                FROM -> { val len = r.valueLength(); val end = r.pos + len; if (r.byte() == 0x80) from = stripType(r.encodedString()); r.pos = end }
                TO, CC -> to += stripType(r.encodedString())
                SUBJECT -> subject = r.encodedString()
                CONTENT_TYPE -> { r.contentType(); break } // the last header: the multipart body follows
                else -> r.skipValue()
            }
        }
        if (type != TYPE_RETRIEVE_CONF) return null
        val parts = mutableListOf<Part>()
        val count = r.uintvar().toInt()
        repeat(count) {
            val headersLength = r.uintvar().toInt()
            val dataLength = r.uintvar().toInt()
            val headersEnd = r.pos + headersLength
            val (contentType, _) = r.contentType()
            var name: String? = null
            while (r.pos < headersEnd) {
                when (r.byte()) {
                    PART_CONTENT_LOCATION -> name = r.text()
                    PART_CONTENT_ID -> r.text()
                    else -> r.skipValue()
                }
            }
            r.pos = headersEnd
            parts += Part(contentType, name, r.bytes(dataLength))
        }
        return Retrieved(from, to, subject, parts)
    }

    // --- Encoding ------------------------------------------------------------------------------------------------

    private fun ByteArrayOutputStream.uintvar(value: Long) {
        val stack = ArrayList<Int>()
        var v = value
        stack += (v and 0x7F).toInt()
        v = v shr 7
        while (v > 0) { stack += ((v and 0x7F) or 0x80).toInt(); v = v shr 7 }
        for (i in stack.indices.reversed()) write(stack[i])
    }

    private fun ByteArrayOutputStream.text(value: String) {
        val bytes = value.toByteArray(Charsets.UTF_8)
        if (bytes.isNotEmpty() && (bytes[0].toInt() and 0xFF) > 0x7F) write(0x7F)
        write(bytes); write(0)
    }

    private fun ByteArrayOutputStream.valueLength(length: Int) {
        if (length < 0x1F) write(length) else { write(0x1F); uintvar(length.toLong()) }
    }

    private fun contentTypeBytes(type: String): ByteArray = ByteArrayOutputStream().apply {
        if (type == "text/plain") {
            // Value-length, text/plain, charset=utf-8 (106).
            write(3); write(0x80 or 0x03); write(0x81); write(0x80 or 106)
        } else {
            val code = reverse[type]
            if (code != null) write(0x80 or code) else text(type)
        }
    }.toByteArray()

    fun encodeSendReq(transactionId: String, recipients: List<String>, subject: String?, parts: List<Part>): ByteArray = ByteArrayOutputStream().apply {
        write(MESSAGE_TYPE); write(TYPE_SEND_REQ)
        write(TRANSACTION_ID); text(transactionId)
        write(MMS_VERSION); write(0x92) // 1.2
        write(FROM); write(1); write(0x81) // insert-address-token: the carrier fills in our number
        for (recipient in recipients) { write(TO); text(if (recipient.contains('@')) recipient else "$recipient/TYPE=PLMN") }
        if (!subject.isNullOrBlank()) { write(SUBJECT); text(subject) }
        write(CONTENT_TYPE); write(0x80 or 0x23) // multipart/mixed
        uintvar(parts.size.toLong())
        for (part in parts) {
            val headers = ByteArrayOutputStream().apply {
                write(contentTypeBytes(part.contentType))
                part.name?.let { write(PART_CONTENT_LOCATION); text(it) }
            }.toByteArray()
            uintvar(headers.size.toLong())
            uintvar(part.data.size.toLong())
            write(headers)
            write(part.data)
        }
    }.toByteArray()
}
