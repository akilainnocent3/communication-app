package com.kilimanjaro.communicationmanager.sms

import android.content.Intent
import android.provider.Telephony
import androidx.test.core.app.ApplicationProvider
import com.kilimanjaro.communicationmanager.sms.mms.MmsReceiver
import com.kilimanjaro.communicationmanager.sms.mms.MmsSentReceiver
import com.kilimanjaro.communicationmanager.sms.telephony.SmsDeliveredReceiver
import com.kilimanjaro.communicationmanager.sms.telephony.SmsSender
import com.kilimanjaro.communicationmanager.sms.telephony.SmsSentReceiver
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Malformed broadcasts from a modem or OEM build must never crash the process (every crash repeats per message). */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class ReceiverResilienceTest {
    private val context = ApplicationProvider.getApplicationContext<android.content.Context>()

    @Test
    fun safelySwallowsFailures() {
        var ran = false
        safely("test") {
            ran = true
            throw IllegalStateException("boom")
        }
        assertTrue(ran)
    }

    @Test
    fun garbageDeliveryReportDoesNotThrow() {
        val intent = Intent(SmsSender.ACTION_DELIVERED).putExtra(SmsSender.EXTRA_URI, "content://sms/1")
            .putExtra("pdu", byteArrayOf(0x7f, 0x00, 0x13)).putExtra("format", "3gpp")
        SmsDeliveredReceiver().onReceive(context, intent)
    }

    @Test
    fun sentResultForUnknownMessageDoesNotThrow() {
        val intent = Intent(SmsSender.ACTION_SENT).putExtra(SmsSender.EXTRA_URI, "content://sms/999999")
            .putExtra(SmsSender.EXTRA_PART, 0).putExtra(SmsSender.EXTRA_PARTS, 1)
        SmsSentReceiver().onReceive(context, intent)
        MmsSentReceiver().onReceive(context, Intent().putExtra("id", 999999L))
    }

    @Test
    fun garbageWapPushDoesNotThrow() {
        MmsReceiver().onReceive(context, Intent(Telephony.Sms.Intents.WAP_PUSH_DELIVER_ACTION).putExtra("data", byteArrayOf(1, 2, 3)))
    }
}
