package com.kilimanjaro.communicationmanager.sms.calls

import android.app.NotificationManager
import android.app.role.RoleManager
import android.content.ComponentName
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.telephony.TelephonyManager
import com.kilimanjaro.communicationmanager.sms.bridge.DeviceState
import com.kilimanjaro.communicationmanager.sms.data.SyncStore
import com.kilimanjaro.communicationmanager.sms.safely

/**
 * Whether this phone is a Calls phone (the server says so in every heartbeat), and the dialer's place in the system:
 * the "OCM Phone" launcher entry is an activity-alias that exists only on Calls phones, so staff see a Phone app and
 * a Messages app, and phones that are not enabled never show a dialer they cannot use.
 */
object CallsFeature {
    const val PHONE_ALIAS = "com.kilimanjaro.communicationmanager.sms.PhoneLauncher"
    const val CALL_ALIAS = "com.kilimanjaro.communicationmanager.sms.CallIntentHandler"
    val permissionNames = listOf("READ_CALL_LOG", "WRITE_CALL_LOG", "CALL_PHONE", "ANSWER_PHONE_CALLS", "READ_PHONE_STATE", "READ_PHONE_NUMBERS", "READ_CONTACTS", "WRITE_CONTACTS") +
        (if (Build.VERSION.SDK_INT >= 31) listOf("BLUETOOTH_CONNECT") else emptyList()) + (if (Build.VERSION.SDK_INT >= 33) listOf("POST_NOTIFICATIONS") else emptyList())

    /** The one tracker of live calls in this process (InCallService feeds it; the heartbeat reads its summary). */
    @Volatile var tracker: CallTracker? = null

    fun tracker(context: Context): CallTracker = tracker ?: synchronized(this) {
        tracker ?: CallTracker(sink = { type, payload -> SyncStore.get(context)?.appendEvent(type, payload) }, isEmergency = { isEmergency(context, it) }).also { tracker = it }
    }

    fun enabled(context: Context): Boolean = runCatching { SyncStore.get(context)?.value("calls_enabled") == "1" }.getOrDefault(false)

    /** From the heartbeat's `capabilities`. Turning Calls on shows the Phone launcher entry and starts the call-log copy. */
    fun setEnabled(context: Context, enabled: Boolean) {
        val store = SyncStore.get(context) ?: return
        val was = store.value("calls_enabled") == "1"
        store.setValue("calls_enabled", if (enabled) "1" else null)
        setAlias(context, PHONE_ALIAS, enabled)
        setAlias(context, CALL_ALIAS, enabled)
        if (enabled && !was) {
            store.setValue("calls_backfill_done", null)
            safely("call log watch") { CallLogSync.watch(context) }
        }
    }

    private fun setAlias(context: Context, name: String, enabled: Boolean) = safely("alias $name") {
        val state = if (enabled) PackageManager.COMPONENT_ENABLED_STATE_ENABLED else PackageManager.COMPONENT_ENABLED_STATE_DISABLED
        val component = ComponentName(context.packageName, name)
        if (context.packageManager.getComponentEnabledSetting(component) != state) {
            context.packageManager.setComponentEnabledSetting(component, state, PackageManager.DONT_KILL_APP)
        }
    }

    fun isDefaultDialer(context: Context): Boolean = runCatching { context.getSystemService(RoleManager::class.java).isRoleHeld(RoleManager.ROLE_DIALER) }.getOrDefault(false)

    /** Android 14+: the incoming-call screen over the lock screen needs this special permission (granted by default to dialers on most builds). */
    fun canUseFullScreenIntent(context: Context): Boolean =
        Build.VERSION.SDK_INT < 34 || context.getSystemService(NotificationManager::class.java).canUseFullScreenIntent()

    fun missingPermissions(context: Context): List<String> = permissionNames.filterNot { DeviceState.granted(context, it) }

    /** TelephonyManager decides for the SIM's region (112, 911, 999, 114 …). Errors count as emergency: never record by mistake. */
    fun isEmergency(context: Context, number: String): Boolean = try {
        context.getSystemService(TelephonyManager::class.java).isEmergencyNumber(number)
    } catch (e: Exception) {
        number.filter { it.isDigit() } in setOf("112", "911", "999", "110", "114", "115", "000", "08", "118", "119")
    }
}
