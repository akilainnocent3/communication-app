package com.kilimanjaro.communicationmanager.phone.dialer

import android.annotation.SuppressLint
import android.content.Context
import android.net.Uri
import android.os.Bundle
import android.telecom.PhoneAccountHandle
import android.telecom.TelecomManager
import android.telephony.SubscriptionManager
import com.kilimanjaro.communicationmanager.phone.bridge.DeviceState

/**
 * Placing calls. Always through TelecomManager.placeCall, which also routes USSD/MMI codes (*150*00#) to the network
 * and shows the operator's response dialog, and which places emergency calls whatever state this app is in (enrolled
 * or not, locked, revoked, offline). Nothing here may stand between the keypad and an emergency number.
 */
object Dialer {
    /** What the next outgoing call came from (callback task, an SMS, redial), matched by number when Telecom adds it. */
    data class Intent(val number: String, val origin: String, val callbackTask: String?, val at: Long)

    @Volatile private var pending: Intent? = null

    fun takeIntent(number: String?, now: Long = System.currentTimeMillis()): Intent? {
        val intent = pending ?: return null
        pending = null
        val digits = { s: String -> s.filter { it.isDigit() }.takeLast(9) }
        return intent.takeIf { now - it.at < 60_000 && number != null && digits(number) == digits(it.number) }
    }

    /**
     * Whether a launch intent may place a call without a tap: only ACTION_CALL tel: that arrived through the
     * CallIntentHandler alias, whose CALL_PHONE permission Android enforces on the sender. The alias name survives in
     * the intent's component; anything addressed to MainActivity or another alias did not pass that check.
     */
    fun placesAtOnce(action: String?, scheme: String?, componentClass: String?, packageName: String): Boolean =
        action == android.content.Intent.ACTION_CALL && scheme == "tel" && componentClass == "$packageName.CallIntentHandler"

    /** Result codes for the UI: placed, or why not (the role and permission prompts are the UI's job). */
    @SuppressLint("MissingPermission")
    fun place(context: Context, number: String, subscriptionId: Long? = null, origin: String = "manual", callbackTask: String? = null): String {
        val clean = number.trim()
        if (clean.isEmpty()) return "empty"
        val telecom = context.getSystemService(TelecomManager::class.java)
        if (clean == "voicemail") return try {
            telecom.placeCall(Uri.fromParts("voicemail", "", null), Bundle())
            "placed"
        } catch (e: SecurityException) {
            "permission"
        }
        val emergency = CallsFeature.isEmergency(context, clean)
        if (!emergency && !CallPrivacy.isMmi(clean)) pending = Intent(clean, origin, callbackTask, System.currentTimeMillis())
        val extras = Bundle()
        accountFor(context, subscriptionId)?.let { if (!emergency) extras.putParcelable(TelecomManager.EXTRA_PHONE_ACCOUNT_HANDLE, it) }
        return try {
            if (!DeviceState.granted(context, "CALL_PHONE") && !emergency) return "permission"
            telecom.placeCall(Uri.fromParts("tel", clean, null), extras)
            "placed"
        } catch (e: SecurityException) {
            // Without CALL_PHONE the system dialer still handles an emergency number; hand it over rather than fail.
            if (emergency) runCatching {
                context.startActivity(android.content.Intent(android.content.Intent.ACTION_DIAL, Uri.fromParts("tel", clean, null)).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK))
            }
            "permission"
        }
    }

    @SuppressLint("MissingPermission")
    private fun accountFor(context: Context, subscriptionId: Long?): PhoneAccountHandle? {
        if (subscriptionId == null || !DeviceState.granted(context, "READ_PHONE_STATE")) return null
        val telecom = context.getSystemService(TelecomManager::class.java)
        val subscriptions = context.getSystemService(SubscriptionManager::class.java)
        val info = runCatching { subscriptions.getActiveSubscriptionInfo(subscriptionId.toInt()) }.getOrNull() ?: return null
        return runCatching { telecom.callCapablePhoneAccounts }.getOrNull()?.firstOrNull { handle ->
            handle.id == info.subscriptionId.toString() || (info.iccId?.isNotEmpty() == true && handle.id.startsWith(info.iccId))
        }
    }

    /** The subscription id of a phone account (call log PHONE_ACCOUNT_ID, a live call's handle). Best effort. */
    @SuppressLint("MissingPermission")
    fun subscriptionFor(context: Context, accountId: String?): Long? {
        if (accountId.isNullOrEmpty()) return null
        accountId.toLongOrNull()?.let { if (it < 100) return it }
        if (!DeviceState.granted(context, "READ_PHONE_STATE")) return null
        val list = runCatching { context.getSystemService(SubscriptionManager::class.java).activeSubscriptionInfoList }.getOrNull() ?: return null
        return list.firstOrNull { (it.iccId?.isNotEmpty() == true && accountId.startsWith(it.iccId)) || accountId == it.subscriptionId.toString() }?.subscriptionId?.toLong()
    }
}
