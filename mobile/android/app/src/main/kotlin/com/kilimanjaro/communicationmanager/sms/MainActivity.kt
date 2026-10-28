package com.kilimanjaro.communicationmanager.sms

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import com.kilimanjaro.communicationmanager.sms.bridge.ActivityBridge
import com.kilimanjaro.communicationmanager.sms.bridge.EventBus
import com.kilimanjaro.communicationmanager.sms.bridge.HostApiImpl
import com.kilimanjaro.communicationmanager.sms.bridge.LaunchIntent
import com.kilimanjaro.communicationmanager.sms.bridge.TelephonyHostApi
import com.kilimanjaro.communicationmanager.sms.calls.Dialer
import com.kilimanjaro.communicationmanager.sms.telephony.Provider
import io.flutter.embedding.android.FlutterFragmentActivity
import io.flutter.embedding.engine.FlutterEngine
import kotlinx.coroutines.CompletableDeferred

/**
 * The only Activity. Also handles ACTION_SEND/SENDTO for sms:, smsto:, mms:, mmsto: (required for the SMS role),
 * cmsms://enroll links and the app's own notification/shortcut intents (see LaunchIntent).
 */
class MainActivity : FlutterFragmentActivity(), ActivityBridge {
    private companion object {
        const val STALE_OUTBOX_MS = 10 * 60 * 1000L
    }

    private var roleResult: CompletableDeferred<Boolean>? = null
    private var permissionResult: CompletableDeferred<Unit>? = null

    private val roleLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        roleResult?.complete(it.resultCode == Activity.RESULT_OK)
        roleResult = null
    }
    private val permissionLauncher = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {
        permissionResult?.complete(Unit)
        permissionResult = null
    }
    private var pickResult: CompletableDeferred<Uri?>? = null
    private val pickLauncher = registerForActivityResult(ActivityResultContracts.PickVisualMedia()) {
        pickResult?.complete(it)
        pickResult = null
    }

    override val activity: Activity get() = this

    override fun onCreate(savedInstanceState: Bundle?) {
        handle(intent)
        super.onCreate(savedInstanceState)
        Thread { safely("stale outbox") { Provider.failStaleOutbox(applicationContext, STALE_OUTBOX_MS) } }.start()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handle(intent)
    }

    /**
     * ACTION_CALL reaches us only through the CallIntentHandler alias, which requires the caller to hold CALL_PHONE: the
     * call is placed (as the system dialer would). Everything else pre-fills or routes.
     */
    private fun handle(intent: Intent?) {
        if (intent?.action == Intent.ACTION_CALL && intent.data?.scheme == "tel") {
            safely("call intent") { Dialer.place(applicationContext, intent.data!!.schemeSpecificPart.orEmpty()) }
            return
        }
        LaunchIntent.set(intent)
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        TelephonyHostApi.setUp(flutterEngine.dartExecutor.binaryMessenger, HostApiImpl(applicationContext, this))
        EventBus.register(flutterEngine.dartExecutor.binaryMessenger, applicationContext)
    }

    override fun requestRole(intent: Intent, done: CompletableDeferred<Boolean>) {
        roleResult = done
        runOnUiThread { roleLauncher.launch(intent) }
    }

    override fun requestPermissions(names: Array<String>, done: CompletableDeferred<Unit>) {
        permissionResult = done
        runOnUiThread { permissionLauncher.launch(names) }
    }

    override fun pickImage(done: CompletableDeferred<Uri?>) {
        pickResult = done
        runOnUiThread { pickLauncher.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) }
    }
}
