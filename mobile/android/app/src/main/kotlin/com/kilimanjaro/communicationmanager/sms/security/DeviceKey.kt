package com.kilimanjaro.communicationmanager.sms.security

import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.security.keystore.StrongBoxUnavailableException
import android.util.Base64
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.PrivateKey
import java.security.Signature
import java.security.spec.ECGenParameterSpec

/**
 * The phone's identity: an EC P-256 key generated inside the Android Keystore (StrongBox when available). The private
 * key is non-exportable; the server only ever sees the public key, its attestation chain and signatures.
 * The attestation challenge is SHA-256(enrollment token), which binds the key to one enrollment.
 */
object DeviceKey {
    private const val ALIAS = "cm_device_identity"
    private const val KEYSTORE = "AndroidKeyStore"

    data class Created(val publicKeySpki: String, val chain: List<String>, val strongBox: Boolean)

    private fun keyStore(): KeyStore = KeyStore.getInstance(KEYSTORE).apply { load(null) }

    fun exists(): Boolean = keyStore().containsAlias(ALIAS)

    fun create(context: Context, challenge: ByteArray): Created {
        delete()
        val strongBox = Build.VERSION.SDK_INT >= Build.VERSION_CODES.P &&
            context.packageManager.hasSystemFeature(PackageManager.FEATURE_STRONGBOX_KEYSTORE)
        val usedStrongBox = try {
            generate(challenge, strongBox)
            strongBox
        } catch (e: StrongBoxUnavailableException) {
            generate(challenge, false)
            false
        }
        val store = keyStore()
        val chain = store.getCertificateChain(ALIAS).map { Base64.encodeToString(it.encoded, Base64.NO_WRAP) }
        val spki = Base64.encodeToString(store.getCertificate(ALIAS).publicKey.encoded, Base64.NO_WRAP)
        return Created(spki, chain, usedStrongBox)
    }

    private fun generate(challenge: ByteArray, strongBox: Boolean) {
        val spec = KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_SIGN)
            .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
            .setDigests(KeyProperties.DIGEST_SHA256)
            .setAttestationChallenge(challenge)
            .apply { if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) setIsStrongBoxBacked(strongBox) }
            .build()
        KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, KEYSTORE).run {
            initialize(spec)
            generateKeyPair()
        }
    }

    /** ECDSA P-256 / SHA-256, DER-encoded — what the server verifies. */
    fun sign(message: ByteArray): ByteArray {
        val key = keyStore().getKey(ALIAS, null) as? PrivateKey ?: throw IllegalStateException("No device key")
        return Signature.getInstance("SHA256withECDSA").run {
            initSign(key)
            update(message)
            sign()
        }
    }

    fun delete() {
        val store = keyStore()
        if (store.containsAlias(ALIAS)) store.deleteEntry(ALIAS)
    }
}
