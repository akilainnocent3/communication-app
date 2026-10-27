package com.kilimanjaro.communicationmanager.sms.telephony

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.ContactsContract
import androidx.core.content.ContextCompat
import com.kilimanjaro.communicationmanager.sms.bridge.ContactInfo

/** Names from the phone's address book, looked up only for numbers in conversations (never a full export). */
object Contacts {
    private fun allowed(context: Context) = ContextCompat.checkSelfPermission(context, Manifest.permission.READ_CONTACTS) == PackageManager.PERMISSION_GRANTED

    fun name(context: Context, address: String): String? {
        if (!allowed(context) || address.isBlank()) return null
        val uri = Uri.withAppendedPath(ContactsContract.PhoneLookup.CONTENT_FILTER_URI, Uri.encode(address))
        return try {
            context.contentResolver.query(uri, arrayOf(ContactsContract.PhoneLookup.DISPLAY_NAME), null, null, null)?.use { if (it.moveToFirst()) it.getString(0) else null }
        } catch (e: IllegalArgumentException) {
            null // sender IDs like "M-PESA" are not phone numbers
        }
    }

    fun lookup(context: Context, addresses: List<String>): List<ContactInfo> = addresses.distinct().map { ContactInfo(address = it, displayName = name(context, it)) }

    fun search(context: Context, query: String, limit: Int): List<ContactInfo> {
        if (!allowed(context)) return emptyList()
        val uri = Uri.withAppendedPath(ContactsContract.CommonDataKinds.Phone.CONTENT_FILTER_URI, Uri.encode(query))
        return context.contentResolver.query(uri, arrayOf(ContactsContract.CommonDataKinds.Phone.NUMBER, ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME), null, null, null)?.use { c ->
            buildList { while (c.moveToNext() && size < limit) add(ContactInfo(address = c.getString(0), displayName = c.getString(1))) }
        } ?: emptyList()
    }
}
