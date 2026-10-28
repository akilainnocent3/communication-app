package com.kilimanjaro.communicationmanager.sms.bridge

import android.Manifest
import android.app.Activity
import android.app.role.RoleManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import android.os.BatteryManager
import android.os.Build
import android.os.Debug
import android.os.PowerManager
import android.provider.Settings
import android.provider.Telephony
import android.telephony.SubscriptionManager
import android.telephony.TelephonyManager
import android.util.Log
import android.view.WindowManager
import androidx.core.content.ContextCompat
import com.kilimanjaro.communicationmanager.sms.BuildConfig
import com.kilimanjaro.communicationmanager.sms.data.SyncStore
import com.kilimanjaro.communicationmanager.sms.security.DatabaseKey
import com.kilimanjaro.communicationmanager.sms.security.DeviceKey
import com.kilimanjaro.communicationmanager.sms.security.SecureHttp
import com.kilimanjaro.communicationmanager.sms.sync.SyncService
import com.kilimanjaro.communicationmanager.sms.telephony.Blocking
import com.kilimanjaro.communicationmanager.sms.telephony.Contacts
import com.kilimanjaro.communicationmanager.sms.telephony.Provider
import com.kilimanjaro.communicationmanager.sms.telephony.SmsSender
import com.kilimanjaro.communicationmanager.sms.telephony.SyncTrigger
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File

/** Callbacks only an Activity can serve (role request, runtime permissions). */
interface ActivityBridge {
    val activity: Activity?
    fun requestRole(intent: Intent, done: CompletableDeferred<Boolean>)
    fun requestPermissions(names: Array<String>, done: CompletableDeferred<Unit>)
}

class HostApiImpl(private val context: Context, private val bridge: ActivityBridge? = null) : TelephonyHostApi {
    private val permissionNames = listOf(
        "RECEIVE_SMS", "READ_SMS", "SEND_SMS", "RECEIVE_MMS", "RECEIVE_WAP_PUSH", "READ_CONTACTS", "READ_PHONE_STATE", "READ_PHONE_NUMBERS",
    ) + if (Build.VERSION.SDK_INT >= 33) listOf("POST_NOTIFICATIONS") else emptyList()

    private fun granted(name: String) = ContextCompat.checkSelfPermission(context, "android.permission.$name") == PackageManager.PERMISSION_GRANTED

    override fun roleStatus(): RoleStatus {
        val roles = context.getSystemService(RoleManager::class.java)
        return RoleStatus(isDefaultSmsApp = roles.isRoleHeld(RoleManager.ROLE_SMS), roleAvailable = roles.isRoleAvailable(RoleManager.ROLE_SMS))
    }

    override suspend fun requestDefaultSmsRole(): Boolean {
        val roles = context.getSystemService(RoleManager::class.java)
        if (roles.isRoleHeld(RoleManager.ROLE_SMS)) return true
        val done = CompletableDeferred<Boolean>()
        bridge?.requestRole(roles.createRequestRoleIntent(RoleManager.ROLE_SMS), done) ?: return false
        return done.await()
    }

    override fun permissions(): List<PermissionState> = permissionNames.map { PermissionState(name = it, granted = granted(it)) }

    override suspend fun requestPermissions(names: List<String>): List<PermissionState> {
        val missing = names.filter { it in permissionNames && !granted(it) }.map { "android.permission.$it" }
        if (missing.isNotEmpty() && bridge != null) {
            val done = CompletableDeferred<Unit>()
            bridge.requestPermissions(missing.toTypedArray(), done)
            done.await()
        }
        return permissions()
    }

    override fun sims(): List<SimInfo> {
        if (!granted("READ_PHONE_STATE")) return emptyList()
        val manager = context.getSystemService(SubscriptionManager::class.java)
        val default = SubscriptionManager.getDefaultSmsSubscriptionId()
        @Suppress("MissingPermission")
        val list = manager.activeSubscriptionInfoList ?: emptyList()
        return list.map { info ->
            @Suppress("MissingPermission") // READ_PHONE_NUMBERS checked; a SecurityException is caught
            val number = if (granted("READ_PHONE_NUMBERS")) runCatching {
                if (Build.VERSION.SDK_INT >= 33) manager.getPhoneNumber(info.subscriptionId) else @Suppress("DEPRECATION") info.number
            }.getOrNull() else null
            SimInfo(subscriptionId = info.subscriptionId.toLong(), slot = info.simSlotIndex.toLong(), carrier = info.carrierName?.toString() ?: "",
                countryIso = info.countryIso ?: "", number = number?.takeIf { it.isNotBlank() }, isDefault = info.subscriptionId == default)
        }
    }

    override fun deviceFacts(): DeviceFacts = DeviceFacts(
        manufacturer = Build.MANUFACTURER, model = Build.MODEL, androidVersion = Build.VERSION.RELEASE, sdkInt = Build.VERSION.SDK_INT.toLong(),
        appVersion = BuildConfig.VERSION_NAME, isEmulator = RiskSignals.emulator(), isRooted = RiskSignals.rooted(), debuggerAttached = Debug.isDebuggerConnected(),
    )

    override fun threads(limit: Long, offset: Long) = Provider.threads(context, limit.toInt(), offset.toInt())
    override fun messages(threadId: Long, limit: Long, beforeDate: Long?) = Provider.messages(context, threadId, limit.toInt(), beforeDate)
    override fun messagesSince(sinceDate: Long, limit: Long, offset: Long) = Provider.messagesSince(context, sinceDate, limit.toInt(), offset.toInt())

    override fun readMmsPart(uri: String): ByteArray {
        require(uri.startsWith("content://mms/part/")) { "Only MMS parts can be read" }
        return context.contentResolver.openInputStream(Uri.parse(uri))?.use { it.readBytes() } ?: ByteArray(0)
    }

    override fun lookupContacts(addresses: List<String>) = Contacts.lookup(context, addresses)
    override fun searchContacts(query: String, limit: Long) = Contacts.search(context, query, limit.toInt())

    override suspend fun sendMessage(request: SendRequest): SendResult = withContext(Dispatchers.IO) {
        try {
            SmsSender.send(context, request)
        } catch (e: Exception) {
            // Admin messages already carry a durable "sending" mark, so the sync loop reports them; never resend here.
            Log.w("CmSms", "send failed: ${e.javaClass.name}")
            SendResult(clientUuid = request.clientUuid, state = "failed", errorCode = SmsSender.ERROR_REFUSED.toLong())
        }
    }

    override fun markThreadRead(threadId: Long) {
        Provider.markThreadRead(context, threadId)
        SyncStore.get(context)?.appendEvent("thread.read", JSONObject().put("thread_id", threadId))
        SyncTrigger.now(context)
    }

    override fun deleteMessage(kind: String, providerId: Long) {
        val message = if (kind == "mms") Provider.mms(context, providerId) else Provider.sms(context, Uri.withAppendedPath(Telephony.Sms.CONTENT_URI, providerId.toString()))
        Provider.deleteMessage(context, kind, providerId)
        message?.let { SyncStore.get(context)?.appendEvent("message.delete", JSONObject().put("kind", kind).put("provider_id", providerId).put("date", it.date)) }
        SyncTrigger.now(context)
    }

    override fun deleteThread(threadId: Long) {
        Provider.deleteThread(context, threadId)
        SyncStore.get(context)?.appendEvent("thread.delete", JSONObject().put("thread_id", threadId))
        SyncTrigger.now(context)
    }

    override fun canBlockNumbers() = Blocking.canBlock(context)
    override fun blockNumber(address: String) = Blocking.block(context, address)
    override fun unblockNumber(address: String) = Blocking.unblock(context, address)
    override fun blockedNumbers() = Blocking.list(context)

    override fun databaseKey() = DatabaseKey.get(context)
    override fun databasePath() = DatabaseKey.path(context)
    override fun hasDeviceKey() = DeviceKey.exists()

    override fun createDeviceKey(attestationChallenge: ByteArray): KeyInfo =
        DeviceKey.create(context, attestationChallenge).let { KeyInfo(publicKeySpki = it.publicKeySpki, attestationChain = it.chain, strongBox = it.strongBox) }

    override fun sign(message: ByteArray) = DeviceKey.sign(message)
    override fun deleteDeviceKey() = DeviceKey.delete()

    override suspend fun http(request: HttpRequestData): HttpResponseData = withContext(Dispatchers.IO) {
        try {
            SecureHttp.execute(request.method, request.url, request.headers, request.body).let { HttpResponseData(status = it.status.toLong(), body = it.body) }
        } catch (e: java.io.IOException) {
            HttpResponseData(status = 0, body = ByteArray(0)) // offline / TLS / pin failure: the engine backs off
        }
    }

    override fun startSyncService() = SyncService.start(context)
    override fun stopSyncService() = SyncService.stop(context)

    override fun serviceStatus(): ServiceStatus {
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
            running = SyncService.running, batteryOptimised = !power.isIgnoringBatteryOptimizations(context.packageName),
            networkAvailable = caps?.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED) == true, networkType = type,
            battery = battery.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY).toLong(), charging = battery.isCharging, signal = signal,
        )
    }

    /** Private distribution only (Play does not allow this for most apps): asks to be exempt from battery optimisation. */
    override fun openBatteryOptimisationSettings() {
        val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:${context.packageName}")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        runCatching { context.startActivity(intent) }.onFailure {
            context.startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }
    }

    override fun launchAddress(): String? = LaunchIntent.consume()

    override fun setSecureScreen(secure: Boolean) {
        bridge?.activity?.runOnUiThread {
            if (secure) bridge.activity?.window?.addFlags(WindowManager.LayoutParams.FLAG_SECURE) else bridge.activity?.window?.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
        }
    }

    override fun wipe() {
        SyncService.stop(context)
        SyncStore.close()
        DeviceKey.delete()
        val path = DatabaseKey.path(context)
        listOf(path, "$path-wal", "$path-shm", "$path-journal").forEach { File(it).delete() }
        DatabaseKey.delete(context)
    }
}

/** The number from an sms:/smsto:/mms: intent that opened the app (consumed once by the router). */
object LaunchIntent {
    @Volatile private var address: String? = null
    fun set(intent: Intent?) {
        val data = intent?.data ?: return
        if (data.scheme in setOf("sms", "smsto", "mms", "mmsto")) address = data.schemeSpecificPart?.substringBefore('?')?.takeIf { it.isNotBlank() }
    }
    fun consume(): String? = address.also { address = null }
}

/** Root / emulator signals reported in the heartbeat. Reported, never blocking (they are easy to fake both ways). */
object RiskSignals {
    fun emulator(): Boolean = Build.FINGERPRINT.startsWith("generic") || Build.FINGERPRINT.contains("emulator") || Build.MODEL.contains("sdk_gphone") ||
        Build.HARDWARE.contains("ranchu") || Build.HARDWARE.contains("goldfish")

    fun rooted(): Boolean = listOf("/system/bin/su", "/system/xbin/su", "/sbin/su", "/system/app/Superuser.apk").any { File(it).exists() } ||
        Build.TAGS?.contains("test-keys") == true
}
