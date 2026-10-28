package com.kilimanjaro.communicationmanager.sms.security

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyPermanentlyInvalidatedException
import android.security.keystore.KeyProperties
import android.util.Base64
import android.util.Log
import java.io.File
import java.security.KeyStore
import java.security.SecureRandom
import java.security.UnrecoverableKeyException
import javax.crypto.AEADBadTagException
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Passphrase of the SQLCipher sync database: 32 random bytes, stored wrapped (AES-256-GCM) by a non-exportable
 * Keystore key. Both the native writers and Dart (drift) open the same file with it. Excluded from backups.
 */
object DatabaseKey {
    private const val ALIAS = "cm_db_wrap"
    private const val PREFS = "cm_secure"
    private const val ENTRY = "db_key"

    @Volatile private var cached: String? = null

    fun get(context: Context): String {
        cached?.let { return it }
        synchronized(this) {
            cached?.let { return it }
            val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            val stored = prefs.getString(ENTRY, null)
            val value = stored?.let { unwrapOrLost(it) } ?: create(context)
            cached = value
            return value
        }
    }

    /**
     * A new passphrase. A database file left without its passphrase (wrapping key lost or invalidated, or the stored
     * entry gone) can never be opened again; it is removed so the app starts clean and asks to enroll again instead
     * of failing on every start and every incoming SMS.
     */
    private fun create(context: Context): String {
        val path = path(context)
        if (File(path).exists()) Log.w("CmSms", "sync database key lost; resetting the sync database")
        listOf(path, "$path-wal", "$path-shm", "$path-journal").forEach { File(it).delete() }
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val raw = ByteArray(32).also { SecureRandom().nextBytes(it) }
        val hex = raw.joinToString("") { "%02x".format(it) }
        prefs.edit().putString(ENTRY, wrap(hex)).commit()
        return hex
    }

    /** null when the wrapped passphrase can never be recovered; transient Keystore errors are rethrown. */
    private fun unwrapOrLost(stored: String): String? = try {
        unwrap(stored)
    } catch (e: Exception) {
        val permanent = e is AEADBadTagException || e is KeyPermanentlyInvalidatedException || e is UnrecoverableKeyException || e is IllegalArgumentException
        if (!permanent) throw e
        Log.w("CmSms", "sync database key unusable: ${e.javaClass.name}")
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        if (store.containsAlias(ALIAS)) store.deleteEntry(ALIAS)
        null
    }

    fun path(context: Context): String = context.getDatabasePath("cm_sync.db").absolutePath

    fun delete(context: Context) {
        cached = null
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().clear().commit()
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        if (store.containsAlias(ALIAS)) store.deleteEntry(ALIAS)
    }

    private fun secretKey(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(ALIAS, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").run {
            init(
                KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setKeySize(256)
                    .build(),
            )
            generateKey()
        }
    }

    private fun wrap(value: String): String {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, secretKey()) }
        val sealed = cipher.iv + cipher.doFinal(value.toByteArray())
        return Base64.encodeToString(sealed, Base64.NO_WRAP)
    }

    private fun unwrap(value: String): String {
        val sealed = Base64.decode(value, Base64.NO_WRAP)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.DECRYPT_MODE, secretKey(), GCMParameterSpec(128, sealed, 0, 12)) }
        return String(cipher.doFinal(sealed, 12, sealed.size - 12))
    }
}
