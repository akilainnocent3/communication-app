package com.kilimanjaro.communicationmanager.sms.calls

import android.content.Context
import com.kilimanjaro.communicationmanager.sms.data.SyncStore
import com.kilimanjaro.communicationmanager.sms.telephony.Contacts
import org.json.JSONObject

/**
 * Who is calling: the phone's own contacts first, then the company directory (names the server sends for customers
 * this phone has been in contact with, cached in the encrypted database and wiped with it on revoke).
 */
object CallerId {
    data class Identity(val name: String?, val source: String) // source: contact | directory | none

    @Volatile private var directory: Map<String, String>? = null

    fun forget() { directory = null }

    private fun load(context: Context): Map<String, String> = directory ?: runCatching {
        val raw = SyncStore.get(context)?.value("cache.directory") ?: "{}"
        val json = JSONObject(raw)
        json.keys().asSequence().associateWith { json.getString(it) }
    }.getOrDefault(emptyMap()).also { directory = it }

    fun directoryName(context: Context, number: String): String? {
        val names = load(context)
        names[number]?.let { return it }
        val tail = number.filter { it.isDigit() }.takeLast(9)
        if (tail.length < 7) return null
        return names.entries.firstOrNull { it.key.filter(Char::isDigit).endsWith(tail) }?.value
    }

    fun identify(context: Context, number: String?): Identity {
        if (number.isNullOrBlank()) return Identity(null, "none")
        Contacts.name(context, number)?.let { return Identity(it, "contact") }
        directoryName(context, number)?.let { return Identity(it, "directory") }
        return Identity(null, "none")
    }

    /** Applies a page of the server's directory delta to the cache. */
    fun apply(context: Context, entries: List<Triple<String, String, Boolean>>) {
        val store = SyncStore.get(context) ?: return
        val current = JSONObject(store.value("cache.directory") ?: "{}")
        for ((number, name, removed) in entries) if (removed || name.isBlank()) current.remove(number) else current.put(number, name)
        store.setValue("cache.directory", current.toString())
        directory = null
    }
}
