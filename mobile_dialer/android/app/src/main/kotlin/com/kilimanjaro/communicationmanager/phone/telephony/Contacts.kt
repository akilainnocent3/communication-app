package com.kilimanjaro.communicationmanager.phone.telephony

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.database.ContentObserver
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.provider.ContactsContract
import android.util.LruCache
import androidx.core.content.ContextCompat
import com.kilimanjaro.communicationmanager.phone.bridge.EventBus

/**
 * Names and photos from the phone's address book for caller ID and recents (never a full export). Results, including
 * "no contact", are kept in an LRU that a ContactsContract observer clears, so a ringing call never waits on a query twice.
 */
object Contacts {
    private data class Entry(val name: String?, val photo: String?)
    private val cache = LruCache<String, Entry>(1024)
    private var observer: ContentObserver? = null

    private fun allowed(context: Context) = ContextCompat.checkSelfPermission(context, Manifest.permission.READ_CONTACTS) == PackageManager.PERMISSION_GRANTED

    /** Clears the cache when the address book changes and tells the UI to refresh names. */
    fun watch(context: Context) {
        val main = Handler(Looper.getMainLooper())
        main.post {
            if (observer != null || !allowed(context)) return@post
            observer = object : ContentObserver(main) {
                override fun onChange(selfChange: Boolean) {
                    cache.evictAll()
                    EventBus.emit("contacts_changed")
                }
            }.also { context.contentResolver.registerContentObserver(ContactsContract.Contacts.CONTENT_URI, true, it) }
        }
    }

    private fun entry(context: Context, address: String): Entry {
        cache.get(address)?.let { return it }
        val found = if (!allowed(context) || address.isBlank()) Entry(null, null) else try {
            val uri = Uri.withAppendedPath(ContactsContract.PhoneLookup.CONTENT_FILTER_URI, Uri.encode(address))
            context.contentResolver.query(uri, arrayOf(ContactsContract.PhoneLookup.DISPLAY_NAME, ContactsContract.PhoneLookup.PHOTO_THUMBNAIL_URI), null, null, null)
                ?.use { if (it.moveToFirst()) Entry(it.getString(0), it.getString(1)) else null } ?: Entry(null, null)
        } catch (e: IllegalArgumentException) {
            Entry(null, null) // sender IDs like "M-PESA" are not phone numbers
        }
        cache.put(address, found)
        return found
    }

    fun name(context: Context, address: String): String? = entry(context, address).name
    fun photo(context: Context, address: String): String? = entry(context, address).photo
}
