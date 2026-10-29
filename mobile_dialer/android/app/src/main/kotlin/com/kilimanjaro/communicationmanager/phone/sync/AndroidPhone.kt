package com.kilimanjaro.communicationmanager.phone.sync

import android.content.Context
import com.kilimanjaro.communicationmanager.phone.bridge.DeviceState
import com.kilimanjaro.communicationmanager.phone.dialer.CallsFeature
import org.json.JSONArray
import org.json.JSONObject

/** The real phone for [NativeSyncEngine]: what the heartbeat reports about the dialer and the phone. */
class AndroidPhone(private val context: Context) : Phone {
    override fun heartbeatState(): JSONObject {
        val status = DeviceState.serviceStatus(context)
        val facts = DeviceState.facts(context)
        return JSONObject().apply {
            put("battery", status.battery ?: JSONObject.NULL)
            put("charging", status.charging)
            put("network_type", status.networkType)
            put("signal", status.signal ?: JSONObject.NULL)
            put("permissions", JSONObject().apply { DeviceState.permissions(context).forEach { put(it.name, it.granted) } })
            put("is_default_dialer", CallsFeature.isDefaultDialer(context))
            put("full_screen_intent_allowed", CallsFeature.canUseFullScreenIntent(context))
            put("call_state", CallsFeature.tracker?.summary() ?: "idle")
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
}
