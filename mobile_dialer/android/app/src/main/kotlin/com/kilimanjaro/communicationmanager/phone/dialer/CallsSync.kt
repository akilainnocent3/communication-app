package com.kilimanjaro.communicationmanager.phone.dialer

import android.content.Context
import com.kilimanjaro.communicationmanager.phone.data.SyncStore
import com.kilimanjaro.communicationmanager.phone.safely
import com.kilimanjaro.communicationmanager.phone.sync.ApiException
import com.kilimanjaro.communicationmanager.phone.sync.CallsDisabled
import com.kilimanjaro.communicationmanager.phone.sync.CallsHooks
import com.kilimanjaro.communicationmanager.phone.sync.DeviceApiClient
import org.json.JSONObject

/**
 * The Calls part of the native sync engine's cycle: follow the server's capabilities, copy new call-log rows, refresh
 * the Calls config (outcomes, post-call card) and the caller-ID directory hourly, and fetch call-back tasks every cycle
 * (one small request; FCM "callbacks" wakes the engine for new ones).
 */
class CallsSync(private val context: Context, private val clock: () -> Long = System::currentTimeMillis) : CallsHooks {
    companion object {
        const val CONFIG_EVERY = 60 * 60_000L
    }

    override fun onCapabilities(capabilities: JSONObject) {
        CallsFeature.setEnabled(context, capabilities.optBoolean("calls"))
    }

    override fun cycle(api: DeviceApiClient, force: Boolean) {
        if (!CallsFeature.enabled(context)) return
        val store = SyncStore.get(context) ?: return
        safely("call log") { CallLogSync.watch(context); CallLogSync.copyNew(context) }
        guard {
            val last = store.value("calls_config_at")?.toLongOrNull() ?: 0
            if (force || clock() - last > CONFIG_EVERY || store.value("cache.calls_config") == null) {
                store.setValue("cache.calls_config", api.callsConfig().toString())
                refreshDirectory(api, store)
                store.setValue("calls_config_at", "${clock()}")
            }
            CallbackTasks.update(context, api.callbacks(), clock())
        }
    }

    private fun refreshDirectory(api: DeviceApiClient, store: SyncStore) {
        var cursor = store.value("directory_cursor")
        repeat(20) {
            val page = api.directory(cursor)
            val entries = page.optJSONArray("entries") ?: return
            CallerId.apply(context, (0 until entries.length()).map { i ->
                val e = entries.getJSONObject(i)
                Triple(e.getString("number"), e.optString("name"), e.optBoolean("removed"))
            })
            cursor = page.optString("next_cursor").takeIf { it.isNotEmpty() && it != "null" } ?: cursor
            store.setValue("directory_cursor", cursor)
            if (page.optBoolean("complete", true)) return
        }
    }

    /** A Calls endpoint refusing (Calls switched off for this phone or on the server) never fails the SMS cycle. */
    private inline fun guard(block: () -> Unit) {
        try {
            block()
        } catch (e: ApiException) {
            if (e.status == 403 && e.code in setOf("calls_not_enabled", "platform_disabled")) throw CallsDisabled(e.code)
            throw e
        }
    }
}
