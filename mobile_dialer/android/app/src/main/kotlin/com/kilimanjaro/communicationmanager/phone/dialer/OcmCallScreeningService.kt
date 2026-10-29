package com.kilimanjaro.communicationmanager.phone.dialer

import android.telecom.Call
import android.telecom.CallScreeningService
import com.kilimanjaro.communicationmanager.phone.telephony.Blocking

/**
 * As the default dialer the app screens incoming calls. A number on the phone's block list (the same list SMS
 * blocking and the admin's "block" use) is rejected and kept out of the ringing UI; the system logs it as blocked.
 * Never applied to emergency numbers, outgoing calls, or anything this screening cannot be sure about.
 */
class OcmCallScreeningService : CallScreeningService() {
    override fun onScreenCall(details: Call.Details) {
        val number = details.handle?.schemeSpecificPart
        val incoming = details.callDirection == Call.Details.DIRECTION_INCOMING
        val block = shouldBlock(incoming, number, { CallsFeature.isEmergency(this, it) }, { runCatching { Blocking.isBlocked(this, it) }.getOrDefault(false) })
        val response = CallResponse.Builder()
        if (block) response.setDisallowCall(true).setRejectCall(true).setSkipNotification(true).setSkipCallLog(false)
        respondToCall(details, response.build())
    }

    companion object {
        /** Emergency numbers are never blocked, whatever the list says; outgoing calls are never screened. */
        fun shouldBlock(incoming: Boolean, number: String?, isEmergency: (String) -> Boolean, isBlocked: (String) -> Boolean): Boolean {
            if (!incoming || number.isNullOrBlank()) return false
            if (runCatching { isEmergency(number) }.getOrDefault(true)) return false
            return isBlocked(number)
        }
    }
}
