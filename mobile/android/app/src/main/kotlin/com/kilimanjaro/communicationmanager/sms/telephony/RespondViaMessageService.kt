package com.kilimanjaro.communicationmanager.sms.telephony

import android.app.Service
import android.content.Intent
import android.os.IBinder
import android.telephony.TelephonyManager
import com.kilimanjaro.communicationmanager.sms.bridge.SendRequest
import com.kilimanjaro.communicationmanager.sms.safely
import java.util.UUID

/** "Reply with message" on an incoming call (RESPOND_VIA_MESSAGE, protected by SEND_RESPOND_VIA_MESSAGE). Headless. */
class RespondViaMessageService : Service() {
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == TelephonyManager.ACTION_RESPOND_VIA_MESSAGE) {
            val address = intent.data?.schemeSpecificPart?.substringBefore('?')
            val text = intent.getStringExtra(Intent.EXTRA_TEXT)?.trim()
            if (!address.isNullOrBlank() && !text.isNullOrEmpty()) {
                Thread {
                    try {
                        safely("respond via message") {
                            SmsSender.send(this, SendRequest(clientUuid = UUID.randomUUID().toString(), addresses = listOf(address), body = text,
                                subscriptionId = null, deliveryReport = false, attachmentUris = emptyList(), origin = "phone"))
                        }
                    } finally {
                        stopSelf(startId)
                    }
                }.start()
                return START_NOT_STICKY
            }
        }
        stopSelf(startId)
        return START_NOT_STICKY
    }
}
