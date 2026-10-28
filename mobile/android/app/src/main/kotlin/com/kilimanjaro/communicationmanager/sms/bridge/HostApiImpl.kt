package com.kilimanjaro.communicationmanager.sms.bridge

import android.app.Activity
import android.app.role.RoleManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import android.provider.Telephony
import android.util.Log
import android.view.WindowManager
import com.kilimanjaro.communicationmanager.sms.Oem
import com.kilimanjaro.communicationmanager.sms.data.SyncStore
import com.kilimanjaro.communicationmanager.sms.security.DatabaseKey
import com.kilimanjaro.communicationmanager.sms.security.DeviceKey
import com.kilimanjaro.communicationmanager.sms.security.SecureHttp
import com.kilimanjaro.communicationmanager.sms.sync.Revocation
import com.kilimanjaro.communicationmanager.sms.sync.SyncService
import com.kilimanjaro.communicationmanager.sms.telephony.Blocking
import com.kilimanjaro.communicationmanager.sms.telephony.Contacts
import com.kilimanjaro.communicationmanager.sms.telephony.Notifications
import com.kilimanjaro.communicationmanager.sms.telephony.Provider
import com.kilimanjaro.communicationmanager.sms.telephony.SmsSender
import com.kilimanjaro.communicationmanager.sms.telephony.SyncTrigger
import com.kilimanjaro.communicationmanager.sms.telephony.Thumbnails
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject

/** Callbacks only an Activity can serve (role request, runtime permissions, photo picker). */
interface ActivityBridge {
    val activity: Activity?
    fun requestRole(intent: Intent, done: CompletableDeferred<Boolean>)
    fun requestPermissions(names: Array<String>, done: CompletableDeferred<Unit>)
    fun pickImage(done: CompletableDeferred<Uri?>)
}

/**
 * The Pigeon host API. Every provider, contacts, Keystore and network call runs on Dispatchers.IO ([io]) so nothing
 * blocks the Android main thread (which also draws Flutter's platform views and handles input); quick binder
 * getters run on Pigeon's background task queue; only Activity calls stay on main.
 */
class HostApiImpl(private val context: Context, private val bridge: ActivityBridge? = null) : TelephonyHostApi {
    private suspend fun <T> io(block: () -> T): T = withContext(Dispatchers.IO) { block() }

    // --- Main thread ---------------------------------------------------------------------------------------------

    override suspend fun requestDefaultSmsRole(): Boolean {
        val roles = context.getSystemService(RoleManager::class.java)
        if (roles.isRoleHeld(RoleManager.ROLE_SMS)) return true
        val done = CompletableDeferred<Boolean>()
        bridge?.requestRole(roles.createRequestRoleIntent(RoleManager.ROLE_SMS), done) ?: return false
        return done.await() || roles.isRoleHeld(RoleManager.ROLE_SMS)
    }

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
            databasePath = DatabaseKey.path(context), databaseKey = key, isDefaultSmsApp = SmsSender.isDefaultSmsApp(context),
            manufacturer = Build.MANUFACTURER, brand = Build.BRAND, sdkInt = Build.VERSION.SDK_INT.toLong(), removed = Revocation.consumeRemoved(context),
        )
    }

    override fun roleStatus(): RoleStatus {
        val roles = context.getSystemService(RoleManager::class.java)
        return RoleStatus(isDefaultSmsApp = roles.isRoleHeld(RoleManager.ROLE_SMS), roleAvailable = roles.isRoleAvailable(RoleManager.ROLE_SMS))
    }

    override fun permissions(): List<PermissionState> = DeviceState.permissions(context, DeviceState.uiPermissionNames)
    override fun deviceFacts(): DeviceFacts = DeviceState.facts(context)
    override fun serviceStatus(): ServiceStatus = DeviceState.serviceStatus(context)
    override fun oemSettings(): List<String> = Oem.available(context)
    override fun consumeLaunch(): LaunchTarget? = LaunchIntent.consume()
    override fun hasDeviceKey() = DeviceKey.exists()
    override fun deleteDeviceKey() = DeviceKey.delete()

    override fun syncNow() = SyncTrigger.now(context)

    override fun startSyncService() {
        if (!SyncService.start(context)) SyncTrigger.expedite(context)
    }

    override fun stopSyncService() = SyncService.stop(context)

    override fun wipe() = Revocation.wipe(context)

    // --- Dispatchers.IO ------------------------------------------------------------------------------------------

    override suspend fun sims() = io { DeviceState.sims(context) }
    override suspend fun threads(limit: Long, offset: Long) = io { Provider.threads(context, limit.toInt(), offset.toInt()) }
    override suspend fun thread(threadId: Long) = io { Provider.thread(context, threadId) }
    override suspend fun messages(threadId: Long, limit: Long, beforeDate: Long?) = io { Provider.messages(context, threadId, limit.toInt(), beforeDate) }
    override suspend fun searchMessages(query: String, limit: Long, offset: Long) = io { Provider.search(context, query, limit.toInt(), offset.toInt()) }
    override suspend fun thumbnail(uri: String, maxPx: Long) = io { Thumbnails.get(context, uri, maxPx.toInt()) }
    override suspend fun lookupContacts(addresses: List<String>) = io { Contacts.lookup(context, addresses) }
    override suspend fun searchContacts(query: String, limit: Long) = io { Contacts.search(context, query, limit.toInt()) }

    override suspend fun sendMessage(request: SendRequest): SendResult = io {
        try {
            SmsSender.send(context, request).also { SyncTrigger.now(context) }
        } catch (e: Exception) {
            // Admin messages already carry a durable "sending" mark, so the sync engine reports them; never resend here.
            Log.w("CmSms", "send failed: ${e.javaClass.name}")
            SendResult(clientUuid = request.clientUuid, state = "failed", errorCode = SmsSender.ERROR_REFUSED.toLong())
        }
    }

    /** Only when something was unread: reading a chat that is already read must not write or sync anything. */
    override suspend fun markThreadRead(threadId: Long) = io {
        if (Provider.markThreadRead(context, threadId) > 0) {
            SyncStore.get(context)?.appendEvent("thread.read", JSONObject().put("thread_id", threadId))
            SyncTrigger.now(context)
        }
        Notifications.cancel(context, threadId)
    }

    override suspend fun deleteMessage(kind: String, providerId: Long) = io {
        val message = if (kind == "mms") Provider.mms(context, providerId) else Provider.sms(context, Uri.withAppendedPath(Telephony.Sms.CONTENT_URI, providerId.toString()))
        Provider.deleteMessage(context, kind, providerId)
        message?.let { SyncStore.get(context)?.appendEvent("message.delete", JSONObject().put("kind", kind).put("provider_id", providerId).put("date", it.date)) }
        SyncTrigger.now(context)
    }

    override suspend fun deleteThread(threadId: Long) = io {
        Provider.deleteThread(context, threadId)
        Notifications.removeShortcut(context, threadId)
        SyncStore.get(context)?.appendEvent("thread.delete", JSONObject().put("thread_id", threadId))
        SyncTrigger.now(context)
    }

    override suspend fun canBlockNumbers() = io { Blocking.canBlock(context) }
    override suspend fun blockNumber(address: String) = io { Blocking.block(context, address).also { SyncTrigger.now(context) } }
    override suspend fun unblockNumber(address: String) = io { Blocking.unblock(context, address).also { SyncTrigger.now(context) } }
    override suspend fun blockedNumbers() = io { Blocking.list(context) }

    override suspend fun createDeviceKey(attestationChallenge: ByteArray): KeyInfo = io {
        DeviceKey.create(context, attestationChallenge).let { KeyInfo(publicKeySpki = it.publicKeySpki, attestationChain = it.chain, strongBox = it.strongBox) }
    }

    override suspend fun sign(message: ByteArray) = io { DeviceKey.sign(message) }

    override suspend fun http(request: HttpRequestData): HttpResponseData = io {
        SecureHttp.transport().send(request.method, request.url, request.headers, request.body).let { HttpResponseData(status = it.status.toLong(), body = it.body) }
    }
}

/**
 * Where an intent asked the app to go, consumed once by the router: compose (sms:, smsto:, mms:, mmsto: from other
 * apps), chat (notifications and conversation shortcuts), enroll (a cmsms://enroll link; the server allow-list and
 * the monitoring notice still apply) and route (the sync notification).
 */
object LaunchIntent {
    @Volatile private var target: LaunchTarget? = null

    fun set(intent: Intent?) {
        val data = intent?.data ?: return
        target = when (data.scheme) {
            "sms", "smsto", "mms", "mmsto" -> data.schemeSpecificPart?.substringBefore('?')?.takeIf { it.isNotBlank() }?.let { LaunchTarget("compose", it) }
            "cmsms" -> when (data.host) {
                "chat" -> data.lastPathSegment?.toLongOrNull()?.let { LaunchTarget("chat", "$it") }
                "enroll" -> LaunchTarget("enroll", data.toString())
                "route" -> data.path?.takeIf { it == "/settings/sync" }?.let { LaunchTarget("route", it) }
                else -> null
            }
            else -> null
        } ?: target
        if (target != null) EventBus.emit("launch")
    }

    fun consume(): LaunchTarget? = target.also { target = null }
}
