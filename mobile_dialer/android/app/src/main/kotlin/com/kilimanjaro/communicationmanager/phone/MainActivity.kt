package com.kilimanjaro.communicationmanager.phone

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import com.kilimanjaro.communicationmanager.phone.bridge.ActivityBridge
import com.kilimanjaro.communicationmanager.phone.bridge.EventBus
import com.kilimanjaro.communicationmanager.phone.bridge.HostApiImpl
import com.kilimanjaro.communicationmanager.phone.bridge.LaunchIntent
import com.kilimanjaro.communicationmanager.phone.bridge.TelephonyHostApi
import com.kilimanjaro.communicationmanager.phone.dialer.Dialer
import io.flutter.embedding.android.FlutterFragmentActivity
import io.flutter.embedding.engine.FlutterEngine
import kotlinx.coroutines.CompletableDeferred

/**
 * The Flutter Activity: Keypad, Recents, Contacts, Call-backs, settings. Handles DIAL / VIEW tel: (required for the
 * default Phone app role; they only pre-fill the keypad), ACTION_CALL through the protected alias, ocmphone://enroll
 * links and the app's own notification intents (see LaunchIntent). The call screen is native (dialer/InCallActivity).
 */
class MainActivity : FlutterFragmentActivity(), ActivityBridge {
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
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handle(intent)
    }

    /**
     * ACTION_CALL through the CallIntentHandler alias (the caller must hold CALL_PHONE) places the call, as the system
     * dialer would. Everything else pre-fills or routes.
     */
    private fun handle(intent: Intent?) {
        // MainActivity itself is exported without a permission and explicit intents ignore intent filters: an ACTION_CALL
        // addressed to it only pre-fills the keypad, like DIAL.
        if (intent != null && Dialer.placesAtOnce(intent.action, intent.data?.scheme, intent.component?.className, packageName)) {
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
