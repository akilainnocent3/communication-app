package com.kilimanjaro.communicationmanager.phone.dialer

import android.content.Context
import com.kilimanjaro.communicationmanager.phone.data.SyncStore
import com.kilimanjaro.communicationmanager.phone.telephony.Contacts
import org.json.JSONObject

/**
 * Who is calling: the phone's own contacts first, then the company directory (names the server sends for customers
 * this phone has been in contact with, cached in the encrypted database and wiped with it on revoke).
 */
object CallerId {
    data class Identity(val name: String?, val source: String) // source: contact | directory | none

    /**
     * The company directory, indexed by exact number and by its last 9 digits, so recents and the address book (up to
     * thousands of numbers) look a name up in O(1) instead of scanning the directory for each.
     */
    class Directory(private val exact: Map<String, String>) {
        private val byTail = HashMap<String, String>(exact.size).apply {
            for ((number, name) in exact) tail(number).takeIf { it.length == 9 }?.let { putIfAbsent(it, name) }
        }

        fun name(number: String): String? {
            exact[number]?.let { return it }
            val tail = tail(number)
            if (tail.length < 7) return null
            if (tail.length == 9) return byTail[tail]
            // Short numbers (7–8 digits) are rare: match the end of any directory number.
            return exact.entries.firstOrNull { it.key.filter(Char::isDigit).endsWith(tail) }?.value
        }

        private companion object {
            fun tail(number: String) = number.filter(Char::isDigit).takeLast(9)
        }
    }

    @Volatile private var directory: Directory? = null

    fun forget() { directory = null }

    private fun load(context: Context): Directory = directory ?: runCatching {
        val json = JSONObject(SyncStore.get(context)?.value("cache.directory") ?: "{}")
        Directory(json.keys().asSequence().associateWith { json.getString(it) })
    }.getOrDefault(Directory(emptyMap())).also { directory = it }

    fun directoryName(context: Context, number: String): String? = load(context).name(number)

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
