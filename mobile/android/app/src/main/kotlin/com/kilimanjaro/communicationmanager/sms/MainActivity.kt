package com.kilimanjaro.communicationmanager.sms

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import androidx.activity.result.contract.ActivityResultContracts
import com.kilimanjaro.communicationmanager.sms.bridge.ActivityBridge
import com.kilimanjaro.communicationmanager.sms.bridge.EventBus
import com.kilimanjaro.communicationmanager.sms.bridge.HostApiImpl
import com.kilimanjaro.communicationmanager.sms.bridge.LaunchIntent
import com.kilimanjaro.communicationmanager.sms.bridge.TelephonyHostApi
import io.flutter.embedding.android.FlutterFragmentActivity
import io.flutter.embedding.engine.FlutterEngine
import kotlinx.coroutines.CompletableDeferred

/** The only Activity. Also handles ACTION_SEND/SENDTO for sms:, smsto:, mms:, mmsto: (required for the SMS role). */
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

    override val activity: Activity get() = this

    override fun onCreate(savedInstanceState: Bundle?) {
        LaunchIntent.set(intent)
        super.onCreate(savedInstanceState)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        LaunchIntent.set(intent)
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        TelephonyHostApi.setUp(flutterEngine.dartExecutor.binaryMessenger, HostApiImpl(applicationContext, this))
        EventBus.register(flutterEngine.dartExecutor.binaryMessenger)
    }

    override fun requestRole(intent: Intent, done: CompletableDeferred<Boolean>) {
        roleResult = done
        runOnUiThread { roleLauncher.launch(intent) }
    }

    override fun requestPermissions(names: Array<String>, done: CompletableDeferred<Unit>) {
        permissionResult = done
        runOnUiThread { permissionLauncher.launch(names) }
    }
}
