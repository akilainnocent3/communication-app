package com.kilimanjaro.communicationmanager.sms

import com.kilimanjaro.communicationmanager.sms.mms.Pdu
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.io.ByteArrayOutputStream

class PduTest {
    private fun text(out: ByteArrayOutputStream, value: String) { out.write(value.toByteArray()); out.write(0) }

    @Test
    fun parsesNotificationInd() {
        val out = ByteArrayOutputStream()
        out.write(Pdu.MESSAGE_TYPE); out.write(Pdu.TYPE_NOTIFICATION_IND)
        out.write(Pdu.TRANSACTION_ID); text(out, "T123")
        out.write(Pdu.MMS_VERSION); out.write(0x92)
        val from = "+255754210331/TYPE=PLMN".toByteArray()
        out.write(Pdu.FROM); out.write(from.size + 2); out.write(0x80); out.write(from); out.write(0)
        out.write(Pdu.MESSAGE_SIZE); out.write(2); out.write(0x10); out.write(0x00)
        out.write(0x88); out.write(5); out.write(0x81); out.write(3); out.write(0x01); out.write(0x51); out.write(0x80) // expiry: skipped generically
        out.write(Pdu.CONTENT_LOCATION); text(out, "http://mmsc.example/abc")
        val parsed = Pdu.parseNotification(out.toByteArray())!!
        assertEquals("http://mmsc.example/abc", parsed.contentLocation)
        assertEquals("T123", parsed.transactionId)
        assertEquals("+255754210331", parsed.from)
        assertEquals(4096L, parsed.size)
    }

    @Test
    fun sendReqRoundTripsThroughTheRetrieveParser() {
        val image = ByteArray(300) { (it % 251).toByte() }
        val parts = listOf(Pdu.Part("text/plain", "text.txt", "Habari 😊".toByteArray()), Pdu.Part("image/jpeg", "photo.jpg", image))
        val encoded = Pdu.encodeSendReq("T1", listOf("+255754210331", "+255713402118"), "Hi", parts)
        // A retrieve.conf has the same body layout; flip the message type and parse it back.
        encoded[1] = Pdu.TYPE_RETRIEVE_CONF.toByte()
        val parsed = Pdu.parseRetrieve(encoded)!!
        assertEquals(listOf("+255754210331", "+255713402118"), parsed.to)
        assertEquals("Hi", parsed.subject)
        assertNull(parsed.from) // insert-address-token: the carrier fills it in
        assertEquals(listOf("text/plain", "image/jpeg"), parsed.parts.map { it.contentType })
        assertEquals("Habari 😊", String(parsed.parts[0].data))
        assertArrayEquals(image, parsed.parts[1].data)
        assertEquals("photo.jpg", parsed.parts[1].name)
    }

    @Test
    fun rejectsOtherMessageTypes() {
        val encoded = Pdu.encodeSendReq("T1", listOf("+255754210331"), null, listOf(Pdu.Part("text/plain", null, "x".toByteArray())))
        assertNull(Pdu.parseRetrieve(encoded))
        assertNull(Pdu.parseNotification(encoded))
    }

    @Test
    fun largePartsUseMultiByteLengths() {
        val big = ByteArray(200_000) { 7 }
        val encoded = Pdu.encodeSendReq("T2", listOf("+255754210331"), null, listOf(Pdu.Part("application/pdf", "doc.pdf", big)))
        encoded[1] = Pdu.TYPE_RETRIEVE_CONF.toByte()
        val parsed = Pdu.parseRetrieve(encoded)!!
        assertEquals("application/pdf", parsed.parts.single().contentType)
        assertEquals(200_000, parsed.parts.single().data.size)
    }

    @Test
    fun truncatedOrGarbageInputNeverThrows() {
        val full = Pdu.encodeSendReq("T3", listOf("+255754210331"), "s", listOf(Pdu.Part("image/png", "a.png", ByteArray(500) { 1 })))
        full[1] = Pdu.TYPE_RETRIEVE_CONF.toByte()
        for (n in 0..full.size) {
            Pdu.parseRetrieve(full.copyOf(n))
            Pdu.parseNotification(full.copyOf(n))
        }
        val random = java.util.Random(7)
        repeat(500) {
            val junk = ByteArray(random.nextInt(64)).also { random.nextBytes(it) }
            Pdu.parseRetrieve(junk)
            Pdu.parseNotification(junk)
        }
    }
}
