package com.kilimanjaro.communicationmanager.sms

import android.app.Activity
import android.app.AlertDialog
import android.os.Bundle

/** Class 0 ("flash") SMS: shown immediately as a dialog and not stored, as the standard requires. */
class ClassZeroActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        AlertDialog.Builder(this)
            .setTitle(intent.getStringExtra("address") ?: getString(R.string.flash_message))
            .setMessage(intent.getStringExtra("body") ?: "")
            .setPositiveButton(android.R.string.ok) { _, _ -> finish() }
            .setOnDismissListener { finish() }
            .show()
    }
}
