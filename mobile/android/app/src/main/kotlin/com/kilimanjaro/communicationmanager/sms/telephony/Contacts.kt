package com.kilimanjaro.communicationmanager.sms.telephony

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
import com.kilimanjaro.communicationmanager.sms.bridge.ContactInfo
import com.kilimanjaro.communicationmanager.sms.bridge.EventBus

/**
 * Names and photos from the phone's address book, looked up only for numbers in conversations (never a full export).
 * Results, including "no contact", are kept in an LRU that a ContactsContract observer clears, so the list and the
 * notifications don't query the address book once per number on every refresh.
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

    fun lookup(context: Context, addresses: List<String>): List<ContactInfo> =
        addresses.distinct().map { address -> entry(context, address).let { ContactInfo(address = address, displayName = it.name, photoUri = it.photo) } }

    fun search(context: Context, query: String, limit: Int): List<ContactInfo> {
        if (!allowed(context)) return emptyList()
        val uri = Uri.withAppendedPath(ContactsContract.CommonDataKinds.Phone.CONTENT_FILTER_URI, Uri.encode(query))
        val columns = arrayOf(ContactsContract.CommonDataKinds.Phone.NUMBER, ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME, ContactsContract.CommonDataKinds.Phone.PHOTO_THUMBNAIL_URI)
        return context.contentResolver.query(uri, columns, null, null, null)?.use { c ->
            buildList { while (c.moveToNext() && size < limit) add(ContactInfo(address = c.getString(0), displayName = c.getString(1), photoUri = c.getString(2))) }
        } ?: emptyList()
    }
}
