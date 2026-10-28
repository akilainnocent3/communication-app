package com.kilimanjaro.communicationmanager.sms

import androidx.work.Configuration
import io.flutter.app.FlutterApplication

/**
 * WorkManager initialises on first use instead of at every process start (its androidx.startup initializer is removed
 * in the manifest): the UI's cold start and every incoming-SMS receiver start skip opening WorkManager's database
 * on the main thread until something actually schedules work.
 */
class CmApplication : FlutterApplication(), Configuration.Provider {
    override val workManagerConfiguration: Configuration
        get() = Configuration.Builder().setMinimumLoggingLevel(android.util.Log.WARN).build()
}
