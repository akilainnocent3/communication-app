package com.kilimanjaro.communicationmanager.phone.bridge

import android.app.ActivityManager
import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.BatteryManager
import android.os.Build
import android.os.Debug
import android.os.PowerManager
import android.telephony.SubscriptionManager
import android.telephony.TelephonyManager
import androidx.core.content.ContextCompat
import com.kilimanjaro.communicationmanager.phone.BuildConfig
import java.io.File

/** Phone state shared by the Pigeon API (UI) and the native sync engine's heartbeat. */
object DeviceState {
    /** What the dialer needs; reported in the heartbeat (the server shows missing ones as call_permissions_missing). */
    val permissionNames get() = com.kilimanjaro.communicationmanager.phone.dialer.CallsFeature.permissionNames

    fun granted(context: Context, name: String) = ContextCompat.checkSelfPermission(context, "android.permission.$name") == PackageManager.PERMISSION_GRANTED

    /** CAMERA is asked for only by the QR scanner; it is shown to the UI but not reported to the server. */
    val uiPermissionNames get() = (permissionNames + "CAMERA").distinct()

    fun permissions(context: Context, names: List<String> = permissionNames): List<PermissionState> = names.map { PermissionState(name = it, granted = granted(context, it)) }

    fun sims(context: Context): List<SimInfo> {
        if (!granted(context, "READ_PHONE_STATE")) return emptyList()
        val manager = context.getSystemService(SubscriptionManager::class.java)
        val default = SubscriptionManager.getDefaultVoiceSubscriptionId()
        @Suppress("MissingPermission")
        val list = runCatching { manager.activeSubscriptionInfoList }.getOrNull() ?: emptyList()
        return list.map { info ->
            @Suppress("MissingPermission") // READ_PHONE_NUMBERS checked; a SecurityException is caught
            val number = if (granted(context, "READ_PHONE_NUMBERS")) runCatching {
                if (Build.VERSION.SDK_INT >= 33) manager.getPhoneNumber(info.subscriptionId) else @Suppress("DEPRECATION") info.number
            }.getOrNull() else null
            SimInfo(subscriptionId = info.subscriptionId.toLong(), slot = info.simSlotIndex.toLong(), carrier = info.carrierName?.toString() ?: "",
                countryIso = info.countryIso ?: "", number = number?.takeIf { it.isNotBlank() }, isDefault = info.subscriptionId == default)
        }
    }

    fun facts(context: Context): DeviceFacts = DeviceFacts(
        manufacturer = Build.MANUFACTURER, model = Build.MODEL, androidVersion = Build.VERSION.RELEASE, sdkInt = Build.VERSION.SDK_INT.toLong(),
        appVersion = BuildConfig.VERSION_NAME, isEmulator = RiskSignals.emulator(), isRooted = RiskSignals.rooted(), debuggerAttached = Debug.isDebuggerConnected(),
    )

    fun serviceStatus(context: Context): ServiceStatus {
        val cm = context.getSystemService(ConnectivityManager::class.java)
        val caps = cm.getNetworkCapabilities(cm.activeNetwork)
        val type = when {
            caps == null -> "none"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "wifi"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "cellular"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "ethernet"
            else -> "other"
        }
        val battery = context.getSystemService(BatteryManager::class.java)
        val power = context.getSystemService(PowerManager::class.java)
        val signal = runCatching { context.getSystemService(TelephonyManager::class.java).signalStrength?.level?.toLong() }.getOrNull()
        return ServiceStatus(
            running = false, batteryOptimised = !power.isIgnoringBatteryOptimizations(context.packageName),
            networkAvailable = caps?.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED) == true, networkType = type,
            battery = battery.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY).toLong(), charging = battery.isCharging, signal = signal,
            backgroundRestricted = context.getSystemService(ActivityManager::class.java).isBackgroundRestricted,
            standbyBucket = runCatching { context.getSystemService(UsageStatsManager::class.java).appStandbyBucket.toLong() }.getOrNull(),
        )
    }

    fun networkValidated(context: Context): Boolean {
        val cm = context.getSystemService(ConnectivityManager::class.java)
        return cm.getNetworkCapabilities(cm.activeNetwork)?.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED) == true
    }
}

/** Root / emulator signals reported in the heartbeat. Reported, never blocking (they are easy to fake both ways). */
object RiskSignals {
    fun emulator(): Boolean = Build.FINGERPRINT.startsWith("generic") || Build.FINGERPRINT.contains("emulator") || Build.MODEL.contains("sdk_gphone") ||
        Build.HARDWARE.contains("ranchu") || Build.HARDWARE.contains("goldfish")

    fun rooted(): Boolean = listOf("/system/bin/su", "/system/xbin/su", "/sbin/su", "/system/app/Superuser.apk").any { File(it).exists() } ||
        Build.TAGS?.contains("test-keys") == true
}
