package com.kilimanjaro.communicationmanager.sms.calls

import android.app.NotificationManager
import android.content.Context
import android.media.AudioAttributes
import android.media.AudioManager
import android.media.Ringtone
import android.media.RingtoneManager
import android.net.Uri
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.provider.ContactsContract
import com.kilimanjaro.communicationmanager.sms.bridge.DeviceState
import com.kilimanjaro.communicationmanager.sms.safely

/**
 * With IN_CALL_SERVICE_RINGING the dialer itself rings. It follows the phone's own rules: ringer mode (silent, vibrate,
 * normal), Do Not Disturb (rings only when the person's DND settings let this caller through, decision 76), the contact's own
 * ringtone, and it stops at once on answer, decline, or a volume key ("silence").
 */
object Ringer {
    private var ringtone: Ringtone? = null
    private var vibrator: Vibrator? = null
    private val pattern = longArrayOf(0, 900, 700)

    /** Pure decision, unit-tested: ring (sound), vibrate, both or neither. */
    data class Plan(val sound: Boolean, val vibrate: Boolean)

    fun plan(ringerMode: Int, dndAllows: Boolean, vibrateWhenRinging: Boolean): Plan = when {
        !dndAllows -> Plan(sound = false, vibrate = false)
        ringerMode == AudioManager.RINGER_MODE_SILENT -> Plan(sound = false, vibrate = false)
        ringerMode == AudioManager.RINGER_MODE_VIBRATE -> Plan(sound = false, vibrate = true)
        else -> Plan(sound = true, vibrate = vibrateWhenRinging)
    }

    /**
     * Whether Do Not Disturb lets this call ring. Pure, unit-tested. [systemMatch] is `matchesCallFilter` (Android 13+);
     * before that, the public policy: calls allowed, and the caller is anyone / a contact / a starred contact as the
     * person chose. Repeat callers are not detected there. When in doubt: silent (the call still shows).
     */
    fun dndAllows(filter: Int, systemMatch: Boolean?, callsAllowed: Boolean, senders: Int, isContact: Boolean, isStarred: Boolean): Boolean = when {
        filter == NotificationManager.INTERRUPTION_FILTER_ALL -> true
        systemMatch != null -> systemMatch
        filter != NotificationManager.INTERRUPTION_FILTER_PRIORITY || !callsAllowed -> false
        else -> when (senders) {
            NotificationManager.Policy.PRIORITY_SENDERS_ANY -> true
            NotificationManager.Policy.PRIORITY_SENDERS_CONTACTS -> isContact
            NotificationManager.Policy.PRIORITY_SENDERS_STARRED -> isStarred
            else -> false
        }
    }

    @Synchronized
    fun start(context: Context, number: String?) {
        stop()
        val audio = context.getSystemService(AudioManager::class.java)
        val notifications = context.getSystemService(NotificationManager::class.java)
        val contactUri = contactUri(context, number)
        val filter = notifications.currentInterruptionFilter
        val dndAllows = filter == NotificationManager.INTERRUPTION_FILTER_ALL || runCatching {
            if (Build.VERSION.SDK_INT >= 33) {
                // The system's own answer, also for unknown numbers (a tel: URI) and repeat callers.
                val caller = contactUri ?: number?.takeIf { it.isNotBlank() }?.let { Uri.fromParts("tel", it, null) }
                dndAllows(filter, caller?.let { notifications.matchesCallFilter(it) }, callsAllowed = false, senders = -1, isContact = false, isStarred = false)
            } else {
                val policy = notifications.notificationPolicy
                dndAllows(filter, null, callsAllowed = policy.priorityCategories and NotificationManager.Policy.PRIORITY_CATEGORY_CALLS != 0,
                    senders = policy.priorityCallSenders, isContact = contactUri != null, isStarred = isStarred(context, contactUri))
            }
        }.getOrDefault(false)
        val plan = plan(audio.ringerMode, dndAllows, vibrateSetting(context))
        if (plan.sound) safely("ringtone") {
            val uri = customRingtone(context, contactUri) ?: RingtoneManager.getActualDefaultRingtoneUri(context, RingtoneManager.TYPE_RINGTONE)
            ringtone = RingtoneManager.getRingtone(context, uri)?.apply {
                audioAttributes = AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_NOTIFICATION_RINGTONE).setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build()
                isLooping = true
                play()
            }
        }
        if (plan.vibrate) safely("vibrate") {
            vibrator = (if (Build.VERSION.SDK_INT >= 31) context.getSystemService(VibratorManager::class.java).defaultVibrator else @Suppress("DEPRECATION") context.getSystemService(Vibrator::class.java))
                .also { it.vibrate(VibrationEffect.createWaveform(pattern, 1), AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_NOTIFICATION_RINGTONE).build()) }
        }
    }

    @Synchronized
    fun stop() {
        runCatching { ringtone?.stop() }
        runCatching { vibrator?.cancel() }
        ringtone = null
        vibrator = null
    }

    val ringing: Boolean get() = ringtone != null || vibrator != null

    private fun vibrateSetting(context: Context): Boolean =
        runCatching { android.provider.Settings.System.getInt(context.contentResolver, "vibrate_when_ringing", 1) == 1 }.getOrDefault(true)

    private fun contactUri(context: Context, number: String?): Uri? {
        if (number.isNullOrBlank() || !DeviceState.granted(context, "READ_CONTACTS")) return null
        return runCatching {
            context.contentResolver.query(Uri.withAppendedPath(ContactsContract.PhoneLookup.CONTENT_FILTER_URI, Uri.encode(number)),
                arrayOf(ContactsContract.PhoneLookup.LOOKUP_KEY, ContactsContract.PhoneLookup._ID), null, null, null)?.use { c ->
                if (c.moveToFirst()) ContactsContract.Contacts.getLookupUri(c.getLong(1), c.getString(0)) else null
            }
        }.getOrNull()
    }

    private fun isStarred(context: Context, contactUri: Uri?): Boolean = contactUri != null && runCatching {
        context.contentResolver.query(contactUri, arrayOf(ContactsContract.Contacts.STARRED), null, null, null)?.use { c -> c.moveToFirst() && c.getInt(0) == 1 }
    }.getOrNull() == true

    private fun customRingtone(context: Context, contactUri: Uri?): Uri? = contactUri?.let { uri ->
        runCatching {
            context.contentResolver.query(uri, arrayOf(ContactsContract.Contacts.CUSTOM_RINGTONE), null, null, null)?.use { c ->
                if (c.moveToFirst()) c.getString(0)?.let(Uri::parse) else null
            }
        }.getOrNull()
    }
}
