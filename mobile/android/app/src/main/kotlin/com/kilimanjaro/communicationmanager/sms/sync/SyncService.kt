package com.kilimanjaro.communicationmanager.sms.sync

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import android.os.SystemClock
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import com.kilimanjaro.communicationmanager.sms.MainActivity
import com.kilimanjaro.communicationmanager.sms.R
import com.kilimanjaro.communicationmanager.sms.bridge.EventBus
import com.kilimanjaro.communicationmanager.sms.data.SyncStore
import com.kilimanjaro.communicationmanager.sms.safely
import com.kilimanjaro.communicationmanager.sms.telephony.Notifications
import com.kilimanjaro.communicationmanager.sms.telephony.SyncTrigger

/**
 * Foreground service (type remoteMessaging: relaying messages to the company server; dataSync would be capped at
 * 6 h/day on Android 15). It runs the native sync loop ([SyncLoop]) on its own thread, watches the network and keeps
 * working with the app closed or swiped away. START_STICKY: the system restarts it after killing the process.
 *
 * Android 12+ refuses foreground starts from the background except for exemptions (high-priority FCM, boot, package
 * replaced, battery-optimisation exemption). A refused start is remembered for 15 minutes and never retried in a
 * loop; WorkManager runs the same engine in the meantime.
 */
class SyncService : Service() {
    companion object {
        @Volatile var running = false
            private set
        @Volatile private var loop: SyncLoop? = null
        @Volatile private var refusedAt = 0L
        private const val REFUSAL_BACKOFF_MS = 15 * 60_000L
        private const val NOTIFICATION_ID = 41
        private const val ACTION_SHOW_NOTICE = "show_notice"

        /** true when the service is running or was started; false when the OS refused (remembered, not retried). */
        fun start(context: Context): Boolean {
            if (running) {
                request()
                return true
            }
            if (refusedAt != 0L && SystemClock.elapsedRealtime() - refusedAt < REFUSAL_BACKOFF_MS) return false
            return try {
                ContextCompat.startForegroundService(context, Intent(context, SyncService::class.java))
                true
            } catch (e: Exception) {
                // ForegroundServiceStartNotAllowedException (12+) or IllegalStateException (background start).
                refusedAt = SystemClock.elapsedRealtime()
                Log.i("CmSync", "service start refused: ${e.javaClass.simpleName}")
                false
            }
        }

        /** Run a cycle now in the running service (no-op when it is not running). */
        fun request(forceHeartbeat: Boolean = false) {
            loop?.request(forceHeartbeat)
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, SyncService::class.java))
        }
    }

    private var networkCallback: ConnectivityManager.NetworkCallback? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        try {
            ServiceCompat.startForeground(this, NOTIFICATION_ID, notification(), if (Build.VERSION.SDK_INT >= 34) ServiceInfo.FOREGROUND_SERVICE_TYPE_REMOTE_MESSAGING else 0)
        } catch (e: Exception) {
            refusedAt = SystemClock.elapsedRealtime()
            Log.w("CmSync", "foreground start refused: ${e.javaClass.simpleName}")
            stopSelf()
            return
        }
        running = true
        loop = SyncLoop(applicationContext) { stopSelf() }.also { it.request(forceHeartbeat = true) }
        safely("network watch") { watchNetwork() }
        safely("periodic sync") { SyncTrigger.schedulePeriodic(this) }
    }

    /**
     * The monitoring disclosure (Google Play's monitoring-app policy): shown at once, in the status bar, for as long as
     * the service runs. Silent. Android 14+ lets people swipe foreground notifications away; it is posted again.
     * Tapping it opens Settings → Sync status.
     */
    private fun notification(): Notification {
        Notifications.ensureServiceChannel(this)
        val open = PendingIntent.getActivity(this, 41, Intent(this, MainActivity::class.java).setData(Uri.parse("cmsms://route/settings/sync")),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val again = PendingIntent.getService(this, 42, Intent(this, SyncService::class.java).setAction(ACTION_SHOW_NOTICE), PendingIntent.FLAG_IMMUTABLE)
        return NotificationCompat.Builder(this, Notifications.SERVICE_CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_ocm).setContentTitle(getString(R.string.service_title)).setContentText(getString(R.string.service_text))
            .setOngoing(true).setSilent(true).setShowWhen(false).setContentIntent(open).setDeleteIntent(again)
            .setPriority(NotificationCompat.PRIORITY_LOW).setCategory(NotificationCompat.CATEGORY_SERVICE).setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE).build()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_SHOW_NOTICE) {
            safely("monitoring notice") { getSystemService(android.app.NotificationManager::class.java).notify(NOTIFICATION_ID, notification()) }
            return START_STICKY
        }
        loop?.request(forceHeartbeat = intent?.action == "network")
        return START_STICKY
    }

    /** Swiped from recents. The service normally survives; some OEMs kill the process anyway, so queue a sync too. */
    override fun onTaskRemoved(rootIntent: Intent?) {
        safely("task removed") { SyncTrigger.expedite(this) }
        super.onTaskRemoved(rootIntent)
    }

    private fun watchNetwork() {
        val cm = getSystemService(ConnectivityManager::class.java)
        val callback = object : ConnectivityManager.NetworkCallback() {
            override fun onCapabilitiesChanged(network: Network, caps: NetworkCapabilities) {
                if (caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)) loop?.networkBack()
            }
        }
        cm.registerNetworkCallback(NetworkRequest.Builder().addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET).build(), callback)
        networkCallback = callback
    }

    override fun onDestroy() {
        running = false
        networkCallback?.let { runCatching { getSystemService(ConnectivityManager::class.java).unregisterNetworkCallback(it) } }
        loop?.quit()
        loop = null
        super.onDestroy()
    }
}

/**
 * The service's sync loop on its own thread. Triggers: a request (new message, send result, FCM, "Sync now"), the
 * network coming back (with a heartbeat), and a poll timer: the server's poll interval (20 s) without FCM, five
 * minutes once an FCM token is registered (pushes then wake the phone for admin replies). Failures back off with
 * jitter; suspended and outdated apps wait 15 minutes.
 */
class SyncLoop(private val context: Context, private val onStop: () -> Unit) {
    private val thread = HandlerThread("cm-sync").apply { start() }
    private val handler = Handler(thread.looper)
    private val backoff = Backoff()
    @Volatile private var forceHeartbeat = false
    @Volatile private var lastNetworkBack = 0L
    private val cycle = Runnable { run() }

    fun request(forceHeartbeat: Boolean = false) {
        if (forceHeartbeat) this.forceHeartbeat = true
        handler.removeCallbacks(cycle)
        handler.post(cycle)
    }

    /** NetworkCallback fires several times per change; one heartbeat per 10 s is plenty. */
    fun networkBack() {
        val now = SystemClock.elapsedRealtime()
        if (now - lastNetworkBack < 10_000) return
        lastNetworkBack = now
        backoff.reset()
        request(forceHeartbeat = true)
    }

    private fun schedule(delayMs: Long) {
        handler.removeCallbacks(cycle)
        handler.postDelayed(cycle, delayMs)
    }

    private fun run() {
        val engine = NativeSyncEngine.get(context) ?: return onStop()
        val force = forceHeartbeat
        forceHeartbeat = false
        val result = engine.runOnce(force)
        EventBus.emit("sync_state", state = result.name.lowercase())
        when (result) {
            NativeSyncEngine.Result.OK -> {
                backoff.reset()
                schedule(pollMs())
            }
            NativeSyncEngine.Result.OFFLINE -> schedule(backoff.next())
            NativeSyncEngine.Result.SUSPENDED, NativeSyncEngine.Result.UPGRADE_REQUIRED -> schedule(15 * 60_000L)
            NativeSyncEngine.Result.REVOKED -> Revocation.handle(context)
            NativeSyncEngine.Result.NOT_ENROLLED -> onStop()
        }
    }

    private fun pollMs(): Long {
        val store = SyncStore.get(context) ?: return 60_000
        if (store.value("push_registered") == "1") return 5 * 60_000L
        return (store.value("poll_seconds")?.toLongOrNull() ?: 20).coerceIn(10, 600) * 1000
    }

    fun quit() {
        handler.removeCallbacksAndMessages(null)
        thread.quitSafely()
    }
}
