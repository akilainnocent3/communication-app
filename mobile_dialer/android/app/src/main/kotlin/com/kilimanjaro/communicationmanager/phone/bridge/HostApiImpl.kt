package com.kilimanjaro.communicationmanager.phone.bridge

import android.app.Activity
import android.app.role.RoleManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import android.view.WindowManager
import com.kilimanjaro.communicationmanager.phone.Oem
import com.kilimanjaro.communicationmanager.phone.dialer.CallbackTasks
import com.kilimanjaro.communicationmanager.phone.dialer.CallsFeature
import com.kilimanjaro.communicationmanager.phone.dialer.Dialer
import com.kilimanjaro.communicationmanager.phone.dialer.DialerData
import com.kilimanjaro.communicationmanager.phone.security.DatabaseKey
import com.kilimanjaro.communicationmanager.phone.security.DeviceKey
import com.kilimanjaro.communicationmanager.phone.security.SecureHttp
import com.kilimanjaro.communicationmanager.phone.sync.Revocation
import com.kilimanjaro.communicationmanager.phone.telephony.Blocking
import com.kilimanjaro.communicationmanager.phone.telephony.SyncTrigger
import com.kilimanjaro.communicationmanager.phone.telephony.Thumbnails
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Callbacks only an Activity can serve (role request, runtime permissions, photo picker). */
interface ActivityBridge {
    val activity: Activity?
    fun requestRole(intent: Intent, done: CompletableDeferred<Boolean>)
    fun requestPermissions(names: Array<String>, done: CompletableDeferred<Unit>)
    fun pickImage(done: CompletableDeferred<Uri?>)
}

/**
 * The Pigeon host API of OCM Phone. Every call-log, contacts, Keystore and network call runs on Dispatchers.IO ([io]) so nothing
 * blocks the Android main thread (which also draws Flutter's platform views and handles input); quick binder
 * getters run on Pigeon's background task queue; only Activity calls stay on main.
 */
class HostApiImpl(private val context: Context, private val bridge: ActivityBridge? = null) : TelephonyHostApi {
    private suspend fun <T> io(block: () -> T): T = withContext(Dispatchers.IO) { block() }

    // --- Main thread ---------------------------------------------------------------------------------------------

    /** The role dialog can be dismissed for good ("don't ask again" on some builds): send the holder to Default apps. */
    override fun openDefaultAppsSettings(): Boolean = runCatching {
        context.startActivity(Intent(Settings.ACTION_MANAGE_DEFAULT_APPS_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }.isSuccess

    override suspend fun requestPermissions(names: List<String>): List<PermissionState> {
        val missing = names.filter { it in DeviceState.uiPermissionNames && !DeviceState.granted(context, it) }.map { "android.permission.$it" }
        if (missing.isNotEmpty() && bridge != null) {
            val done = CompletableDeferred<Unit>()
            bridge.requestPermissions(missing.toTypedArray(), done)
            done.await()
        }
        return DeviceState.permissions(context, DeviceState.uiPermissionNames)
    }

    override suspend fun requestDefaultDialerRole(): Boolean {
        val roles = context.getSystemService(RoleManager::class.java)
        if (roles.isRoleHeld(RoleManager.ROLE_DIALER)) return true
        val done = CompletableDeferred<Boolean>()
        bridge?.requestRole(roles.createRequestRoleIntent(RoleManager.ROLE_DIALER), done) ?: return false
        return done.await() || roles.isRoleHeld(RoleManager.ROLE_DIALER)
    }

    override fun openFullScreenIntentSettings() {
        val intent = if (Build.VERSION.SDK_INT >= 34) Intent(Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT, Uri.parse("package:${context.packageName}"))
            else Oem.appDetails(context)
        runCatching { context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
    }

    override fun addContact(number: String) {
        val intent = Intent(Intent.ACTION_INSERT, android.provider.ContactsContract.Contacts.CONTENT_URI)
            .putExtra(android.provider.ContactsContract.Intents.Insert.PHONE, number).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        runCatching { (bridge?.activity ?: context).startActivity(intent) }
    }

    override fun messageNumber(number: String) {
        val intent = Intent(Intent.ACTION_SENDTO, Uri.fromParts("smsto", number, null)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        runCatching { (bridge?.activity ?: context).startActivity(intent) }
    }

    override fun openBatteryOptimisationSettings() {
        Oem.open(context, "battery_optimisation")
    }

    override fun openOemSetting(id: String): Boolean = Oem.open(context, id)

    override fun openAppSettings() {
        runCatching { context.startActivity(Oem.appDetails(context).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
    }

    override fun setSecureScreen(secure: Boolean) {
        bridge?.activity?.runOnUiThread {
            if (secure) bridge.activity?.window?.addFlags(WindowManager.LayoutParams.FLAG_SECURE) else bridge.activity?.window?.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
        }
    }

    /** The system photo picker (no storage permission); the image is copied into the cache for the QR decoder. */
    override suspend fun pickImage(): String? {
        val bridge = bridge ?: return null
        val done = CompletableDeferred<Uri?>()
        bridge.pickImage(done)
        val uri = done.await() ?: return null
        return io {
            val dir = java.io.File(context.cacheDir, "qr").apply { mkdirs(); listFiles()?.forEach { it.delete() } }
            val file = java.io.File(dir, "picked")
            context.contentResolver.openInputStream(uri)?.use { input -> file.outputStream().use { input.copyTo(it) } } ?: return@io null
            file.absolutePath
        }
    }

    // --- Background task queue -----------------------------------------------------------------------------------

    override fun startup(): StartupState {
        val key = DatabaseKey.get(context)
        DatabaseKey.ensureRawKey(context, key)
        return StartupState(
            databasePath = DatabaseKey.path(context), databaseKey = key, isDefaultDialer = CallsFeature.isDefaultDialer(context),
            manufacturer = Build.MANUFACTURER, brand = Build.BRAND, sdkInt = Build.VERSION.SDK_INT.toLong(), removed = Revocation.consumeRemoved(context),
        )
    }

    override fun permissions(): List<PermissionState> = DeviceState.permissions(context, DeviceState.uiPermissionNames)
    override fun deviceFacts(): DeviceFacts = DeviceState.facts(context)
    override fun serviceStatus(): ServiceStatus = DeviceState.serviceStatus(context)
    override fun oemSettings(): List<String> = Oem.available(context)
    override fun consumeLaunch(): LaunchTarget? = LaunchIntent.consume()
    override fun callsStatus(): CallsStatus = CallsStatus(
        enabled = CallsFeature.enabled(context), isDefaultDialer = CallsFeature.isDefaultDialer(context),
        dialerRoleAvailable = context.getSystemService(RoleManager::class.java).isRoleAvailable(RoleManager.ROLE_DIALER),
        canUseFullScreenIntent = CallsFeature.canUseFullScreenIntent(context), missingPermissions = CallsFeature.missingPermissions(context),
    )

    override fun hasDeviceKey() = DeviceKey.exists()
    override fun deleteDeviceKey() = DeviceKey.delete()

    override fun syncNow() {
        SyncTrigger.ensureScheduled(context)
        SyncTrigger.now(context)
    }

    override fun wipe() = Revocation.wipe(context)

    // --- Dispatchers.IO ------------------------------------------------------------------------------------------

    override suspend fun sims() = io { DeviceState.sims(context) }
    override suspend fun thumbnail(uri: String, maxPx: Long) = io { Thumbnails.get(context, uri, maxPx.toInt()) }

    override suspend fun canBlockNumbers() = io { Blocking.canBlock(context) }
    override suspend fun blockNumber(address: String) = io { Blocking.block(context, address).also { SyncTrigger.now(context) } }
    override suspend fun unblockNumber(address: String) = io { Blocking.unblock(context, address).also { SyncTrigger.now(context) } }
    override suspend fun blockedNumbers() = io { Blocking.list(context) }

    override suspend fun createDeviceKey(attestationChallenge: ByteArray): KeyInfo = io {
        DeviceKey.create(context, attestationChallenge).let { KeyInfo(publicKeySpki = it.publicKeySpki, attestationChain = it.chain, strongBox = it.strongBox) }
    }

    override suspend fun sign(message: ByteArray) = io { DeviceKey.sign(message) }

    override suspend fun placeCall(number: String, subscriptionId: Long?, origin: String, callbackTask: String?): String = io {
        Dialer.place(context, number, subscriptionId, origin, callbackTask).also { if (it == "placed" && callbackTask != null) CallbackTasks.report(context, callbackTask, "dialed") }
    }
    override suspend fun recentCalls(limit: Long, offset: Long) = io { DialerData.recent(context, limit.toInt(), offset.toInt()) }
    override suspend fun phoneContacts(limit: Long) = io { DialerData.contacts(context, limit.toInt()) }
    override suspend fun callbackTasks() = io { DialerData.callbacks(context) }
    override suspend fun reportCallback(id: String, state: String) = io { CallbackTasks.report(context, id, state) }
    override suspend fun deleteRecentCall(id: Long) = io { DialerData.delete(context, id) }

    override suspend fun http(request: HttpRequestData): HttpResponseData = io {
        SecureHttp.transport().send(request.method, request.url, request.headers, request.body).let { HttpResponseData(status = it.status.toLong(), body = it.body) }
    }
}

/**
 * Where an intent asked the app to go, consumed once by the router: dial (DIAL / VIEW tel: from other apps; only pre-fills
 * the keypad), enroll (an ocmphone://enroll link; the server allow-list and the monitoring notice still apply) and route
 * (the app's own notifications: ocmphone://phone/recents, /callbacks, /keypad).
 */
object LaunchIntent {
    @Volatile private var target: LaunchTarget? = null

    private val phoneRoutes = setOf("/phone", "/phone/keypad", "/phone/recents", "/phone/contacts", "/phone/callbacks")

    fun set(intent: Intent?) {
        val data = intent?.data
        target = when {
            data == null && intent?.action == Intent.ACTION_DIAL -> LaunchTarget("route", "/phone/keypad")
            data == null -> null
            // DIAL / VIEW / CALL tel: only pre-fill the keypad (a protected ACTION_CALL was placed before this); the person taps Call.
            data.scheme == "tel" -> LaunchTarget("dial", data.schemeSpecificPart.orEmpty())
            data.scheme == "ocmphone" -> when (data.host) {
                "enroll" -> LaunchTarget("enroll", data.toString())
                "phone" -> "/phone${data.path.orEmpty()}".takeIf { it in phoneRoutes }?.let { LaunchTarget("route", it) }
                "route" -> data.path?.takeIf { it == "/settings/sync" }?.let { LaunchTarget("route", it) }
                else -> null
            }
            else -> null
        } ?: target
        if (target != null) EventBus.emit("launch")
    }

    fun consume(): LaunchTarget? = target.also { target = null }
}
