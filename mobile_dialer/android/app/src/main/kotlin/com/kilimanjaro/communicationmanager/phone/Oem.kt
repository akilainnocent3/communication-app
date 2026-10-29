package com.kilimanjaro.communicationmanager.phone

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings

/**
 * Manufacturer settings that stop background apps ("Keep messages flowing"). Component names change between OEM
 * releases, so each setting lists every known screen and is offered only when one of them exists on this phone
 * (`<queries>` in the manifest makes those packages visible). If none resolves, the app's own settings page is the
 * fallback: on every Android version it leads to Battery → Unrestricted.
 *
 * Sources: the OEMs' own help pages and dontkillmyapp.com (Samsung, Xiaomi, Transsion, Oppo/Realme/OnePlus, Huawei).
 */
object Oem {
    private fun component(pkg: String, cls: String) = Intent().setComponent(ComponentName(pkg, cls))

    /** id → candidate intents, first that resolves wins. */
    private val screens: Map<String, List<Intent>> = mapOf(
        // Samsung One UI: Battery → Background usage limits → Never sleeping apps.
        "samsung_never_sleeping" to listOf(
            component("com.samsung.android.lool", "com.samsung.android.sm.battery.ui.BatteryActivity"),
            component("com.samsung.android.lool", "com.samsung.android.sm.ui.battery.BatteryActivity"),
            component("com.samsung.android.sm", "com.samsung.android.sm.ui.battery.BatteryActivity"),
        ),
        // Xiaomi / Redmi / POCO (MIUI, HyperOS): Security → Autostart.
        "xiaomi_autostart" to listOf(
            component("com.miui.securitycenter", "com.miui.permcenter.autostart.AutoStartManagementActivity"),
            component("com.miui.securitycenter", "com.miui.powercenter.PowerSettings"),
        ),
        // Tecno / Infinix / itel (HiOS, XOS, itel OS): Phone Master → Auto-start management.
        "transsion_autostart" to listOf(
            component("com.transsion.phonemaster", "com.cyin.himgr.autostart.AutoStartActivity"),
            component("com.transsion.phonemaster", "com.cyin.himgr.widget.activity.MainSettingGpActivity"),
        ),
        // Oppo / Realme (ColorOS, realme UI) and OnePlus (OxygenOS): auto-launch.
        "oppo_autolaunch" to listOf(
            component("com.coloros.safecenter", "com.coloros.safecenter.permission.startup.StartupAppListActivity"),
            component("com.coloros.safecenter", "com.coloros.safecenter.startupapp.StartupAppListActivity"),
            component("com.oppo.safe", "com.oppo.safe.permission.startup.StartupAppListActivity"),
            component("com.oplus.battery", "com.oplus.startupapp.view.StartupAppListActivity"),
        ),
        "oneplus_autolaunch" to listOf(
            component("com.oneplus.security", "com.oneplus.security.chainlaunch.view.ChainLaunchAppListActivity"),
            component("com.oplus.battery", "com.oplus.startupapp.view.StartupAppListActivity"),
        ),
        // Huawei / Honor (EMUI): App launch → Manage manually.
        "huawei_app_launch" to listOf(
            component("com.huawei.systemmanager", "com.huawei.systemmanager.startupmgr.ui.StartupNormalAppListActivity"),
            component("com.huawei.systemmanager", "com.huawei.systemmanager.optimize.process.ProtectActivity"),
            component("com.hihonor.systemmanager", "com.hihonor.systemmanager.startupmgr.ui.StartupNormalAppListActivity"),
        ),
    )

    /** Which manufacturer family this phone belongs to (also used to pick the default look). */
    fun family(): String {
        val names = "${Build.MANUFACTURER} ${Build.BRAND}".lowercase()
        return when {
            "samsung" in names -> "samsung"
            listOf("xiaomi", "redmi", "poco").any { it in names } -> "xiaomi"
            listOf("tecno", "infinix", "itel", "transsion").any { it in names } -> "transsion"
            "oneplus" in names -> "oneplus"
            listOf("oppo", "realme", "oplus").any { it in names } -> "oppo"
            listOf("huawei", "honor").any { it in names } -> "huawei"
            "google" in names -> "google"
            else -> "other"
        }
    }

    private fun resolves(context: Context, intent: Intent) = intent.resolveActivity(context.packageManager) != null

    /** Ids of the screens that exist here, always including the generic battery ones. */
    fun available(context: Context): List<String> =
        listOf("battery_optimisation", "app_battery") + screens.filter { (_, intents) -> intents.any { resolves(context, it) } }.keys

    fun open(context: Context, id: String): Boolean {
        val candidates = when (id) {
            // The direct "allow?" dialog needs REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, which only the private (MDM) flavor
            // declares (Google Play restricts it). The play flavor opens the list, where the holder picks OCM.
            "battery_optimisation" -> listOfNotNull(
                Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:${context.packageName}")).takeIf { BuildConfig.DIRECT_BATTERY_REQUEST },
                Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS),
            )
            "app_battery" -> emptyList()
            else -> screens[id].orEmpty()
        } + appDetails(context)
        for (intent in candidates) {
            if (!resolves(context, intent)) continue
            try {
                context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                return true
            } catch (e: Exception) {
                // SecurityException (not exported on this build) or ActivityNotFoundException: try the next one.
            }
        }
        return false
    }

    fun appDetails(context: Context) = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${context.packageName}"))
}
