package com.kilimanjaro.communicationmanager.sms.sync

import android.app.Notification
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.database.ContentObserver
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import com.kilimanjaro.communicationmanager.sms.R
import com.kilimanjaro.communicationmanager.sms.bridge.EventBus
import com.kilimanjaro.communicationmanager.sms.bridge.HostApiImpl
import com.kilimanjaro.communicationmanager.sms.bridge.TelephonyHostApi
import com.kilimanjaro.communicationmanager.sms.safely
import com.kilimanjaro.communicationmanager.sms.telephony.Notifications
import com.kilimanjaro.communicationmanager.sms.telephony.SyncTrigger
import io.flutter.FlutterInjector
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.embedding.engine.dart.DartExecutor

/**
 * Foreground service (type remoteMessaging: relaying messages to the company server; dataSync would be capped at
 * 6 h/day on Android 15). It hosts a headless Flutter engine running `backgroundMain` (the Dart sync loop), watches
 * the network ("always watching the internet") and the Telephony provider, and keeps working with the app closed.
 */
class SyncService : Service() {
    companion object {
        @Volatile var running = false
            private set
        private const val NOTIFICATION_ID = 41

        fun start(context: Context) {
            if (running) {
                EventBus.emit("sync_requested")
                return
            }
            ContextCompat.startForegroundService(context, Intent(context, SyncService::class.java))
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, SyncService::class.java))
        }
    }

    private var engine: FlutterEngine? = null
    private var networkCallback: ConnectivityManager.NetworkCallback? = null
    private var observer: ContentObserver? = null
    private val main = Handler(Looper.getMainLooper())

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        Notifications.ensureServiceChannel(this)
        val notification: Notification = NotificationCompat.Builder(this, Notifications.SERVICE_CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_message).setContentTitle(getString(R.string.service_title)).setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_MIN).setCategory(NotificationCompat.CATEGORY_SERVICE).build()
        val type = if (Build.VERSION.SDK_INT >= 34) ServiceInfo.FOREGROUND_SERVICE_TYPE_REMOTE_MESSAGING else 0
        try {
            ServiceCompat.startForeground(this, NOTIFICATION_ID, notification, type)
        } catch (e: Exception) {
            // Android 12+ can refuse a foreground start from the background (ForegroundServiceStartNotAllowedException);
            // WorkManager's periodic job keeps syncing until the app is opened again.
            Log.w("CmSms", "sync service start refused: ${e.javaClass.name}")
            stopSelf()
            return
        }
        running = true
        safely("sync engine") { startEngine() }
        safely("network watch") { watchNetwork() }
        safely("provider watch") { watchProvider() }
        safely("periodic sync") { SyncTrigger.schedulePeriodic(this) }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        EventBus.emit(if (intent?.action == "push") "push" else "sync_requested")
        return START_STICKY
    }

    private fun startEngine() {
        val loader = FlutterInjector.instance().flutterLoader()
        loader.startInitialization(applicationContext)
        loader.ensureInitializationComplete(applicationContext, null)
        val engine = FlutterEngine(applicationContext)
        TelephonyHostApi.setUp(engine.dartExecutor.binaryMessenger, HostApiImpl(applicationContext))
        EventBus.register(engine.dartExecutor.binaryMessenger)
        engine.dartExecutor.executeDartEntrypoint(DartExecutor.DartEntrypoint(loader.findAppBundlePath(), "backgroundMain"))
        this.engine = engine
    }

    private fun watchNetwork() {
        val cm = getSystemService(ConnectivityManager::class.java)
        val callback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) = EventBus.emit("network", state = "available")
            override fun onLost(network: Network) = EventBus.emit("network", state = "lost")
        }
        cm.registerNetworkCallback(NetworkRequest.Builder().addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET).build(), callback)
        networkCallback = callback
    }

    /** Changes made outside this app (another app, the system) to the message store. */
    private fun watchProvider() {
        val observer = object : ContentObserver(main) {
            override fun onChange(selfChange: Boolean, uri: Uri?) = EventBus.emit("message_changed")
        }
        contentResolver.registerContentObserver(Uri.parse("content://mms-sms/"), true, observer)
        this.observer = observer
    }

    override fun onDestroy() {
        running = false
        networkCallback?.let { getSystemService(ConnectivityManager::class.java).unregisterNetworkCallback(it) }
        observer?.let { contentResolver.unregisterContentObserver(it) }
        engine?.destroy()
        engine = null
        super.onDestroy()
    }
}
