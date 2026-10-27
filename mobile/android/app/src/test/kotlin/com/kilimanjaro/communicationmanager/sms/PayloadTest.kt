package com.kilimanjaro.communicationmanager.sms

import android.provider.Telephony
import com.kilimanjaro.communicationmanager.sms.bridge.MmsPartData
import com.kilimanjaro.communicationmanager.sms.bridge.ProviderMessage
import com.kilimanjaro.communicationmanager.sms.telephony.Provider
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class PayloadTest {
    private fun message(kind: String = "sms", outbound: Boolean = false) = ProviderMessage(
        providerId = 42, kind = kind, threadId = 7, addresses = listOf("+255754210331"), body = "Habari", date = 1_700_000_000_000,
        outbound = outbound, read = false, status = if (outbound) "sent" else "received", subscriptionId = 1, errorCode = null,
        parts = if (kind == "mms") listOf(MmsPartData(seq = 0, contentType = "image/jpeg", filename = "p.jpg", size = 10, uri = "content://mms/part/9")) else emptyList(),
        subject = null,
    )

    @Test
    fun smsPayloadMatchesTheServerEvent() {
        val payload = Provider.payload(message())
        assertEquals("sms", payload.getString("kind"))
        assertEquals(42, payload.getLong("provider_id"))
        assertEquals("in", payload.getString("direction"))
        assertEquals("+255754210331", payload.getJSONArray("addresses").getString(0))
        assertEquals(1, payload.getInt("sub_id"))
        assertFalse(payload.has("client_uuid"))
        assertFalse(payload.has("parts"))
    }

    @Test
    fun adminMessagesCarryTheirClientUuid() {
        val payload = Provider.payload(message(outbound = true), clientUuid = "u-1")
        assertEquals("out", payload.getString("direction"))
        assertEquals("u-1", payload.getString("client_uuid"))
    }

    @Test
    fun mmsPayloadListsParts() {
        val parts = Provider.payload(message(kind = "mms")).getJSONArray("parts")
        assertEquals("image/jpeg", parts.getJSONObject(0).getString("content_type"))
        assertEquals(10, parts.getJSONObject(0).getLong("size"))
    }

    @Test
    fun providerTypesMapToStatuses() {
        assertEquals("received", Provider.smsStatus(Telephony.Sms.MESSAGE_TYPE_INBOX, -1))
        assertEquals("sending", Provider.smsStatus(Telephony.Sms.MESSAGE_TYPE_OUTBOX, -1))
        assertEquals("failed", Provider.smsStatus(Telephony.Sms.MESSAGE_TYPE_FAILED, -1))
        assertEquals("sent", Provider.smsStatus(Telephony.Sms.MESSAGE_TYPE_SENT, Telephony.Sms.STATUS_PENDING))
        assertEquals("delivered", Provider.smsStatus(Telephony.Sms.MESSAGE_TYPE_SENT, Telephony.Sms.STATUS_COMPLETE))
    }
}
