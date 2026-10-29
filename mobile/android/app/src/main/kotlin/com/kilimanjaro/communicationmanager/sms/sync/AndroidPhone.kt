package com.kilimanjaro.communicationmanager.sms.sync

import android.content.Context
import android.net.Uri
import com.kilimanjaro.communicationmanager.sms.bridge.DeviceState
import com.kilimanjaro.communicationmanager.sms.bridge.ProviderMessage
import com.kilimanjaro.communicationmanager.sms.bridge.SendRequest
import com.kilimanjaro.communicationmanager.sms.bridge.SendResult
import com.kilimanjaro.communicationmanager.sms.data.SyncStore
import com.kilimanjaro.communicationmanager.sms.telephony.Blocking
import com.kilimanjaro.communicationmanager.sms.telephony.Contacts
import com.kilimanjaro.communicationmanager.sms.telephony.Provider
import com.kilimanjaro.communicationmanager.sms.telephony.SmsSender
import org.json.JSONArray
import org.json.JSONObject
import java.io.InputStream

/** The real phone for [NativeSyncEngine]: the Telephony provider, contacts, the block list and SmsManager. */
class AndroidPhone(private val context: Context) : Phone {
    override fun heartbeatState(): JSONObject {
        val status = DeviceState.serviceStatus(context)
        val facts = DeviceState.facts(context)
        return JSONObject().apply {
            put("battery", status.battery ?: JSONObject.NULL)
            put("charging", status.charging)
            put("network_type", status.networkType)
            put("signal", status.signal ?: JSONObject.NULL)
            put("is_default_sms_app", SmsSender.isDefaultSmsApp(context))
            put("permissions", JSONObject().apply { DeviceState.permissions(context).forEach { put(it.name, it.granted) } })
            put("battery_optimised", status.batteryOptimised)
            // Why a phone stops syncing in the background, shown on the admin's phone page.
            put("background_restricted", status.backgroundRestricted)
            put("standby_bucket", status.standbyBucket ?: JSONObject.NULL)
            put("manufacturer", facts.manufacturer)
            put("android_version", facts.androidVersion)
            put("risk_signals", JSONObject().put("rooted", facts.isRooted).put("emulator", facts.isEmulator).put("debugger", facts.debuggerAttached))
            put("sims", JSONArray().apply {
                DeviceState.sims(context).forEach { sim ->
                    put(JSONObject().put("subscription_id", sim.subscriptionId).put("slot", sim.slot).put("carrier", sim.carrier)
                        .put("country_iso", sim.countryIso).put("number", sim.number ?: "").put("is_default", sim.isDefault))
                }
            })
        }
    }

    override fun messagesSince(since: Long, limit: Int, offset: Int) = Provider.messagesSince(context, since, limit, offset)

    override fun openPart(uri: String): InputStream? {
        require(uri.startsWith("content://mms/part/")) { "Only MMS parts can be read" }
        return context.contentResolver.openInputStream(Uri.parse(uri))
    }

    override fun contactNames(addresses: List<String>): Map<String, String> =
        Contacts.lookup(context, addresses).mapNotNull { c -> c.displayName?.let { c.address to it } }.toMap()

    override fun blockedNumbers() = Blocking.list(context)
    override fun send(request: SendRequest): SendResult = SmsSender.send(context, request)

    override fun markThreadRead(threadId: Long) {
        Provider.markThreadRead(context, threadId)
        SyncStore.get(context)?.appendEvent("thread.read", JSONObject().put("thread_id", threadId))
    }

    override fun block(address: String) = Blocking.block(context, address)
    override fun unblock(address: String) = Blocking.unblock(context, address)
}
