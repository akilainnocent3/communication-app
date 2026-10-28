package com.kilimanjaro.communicationmanager.sms.telephony

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.media.MediaMetadataRetriever
import android.net.Uri
import java.io.ByteArrayOutputStream
import kotlin.math.max

/**
 * Small JPEGs for the UI: MMS image and video parts inline in the chat, contact photos in the list. Decoded at display
 * size (inSampleSize, then scaled), so a 12-megapixel photo never reaches Flutter at full resolution. Only MMS parts and
 * contact photos may be read.
 */
object Thumbnails {
    private val allowed = listOf("content://mms/part/", "content://com.android.contacts/")

    fun get(context: Context, uri: String, maxPx: Int): ByteArray? {
        require(allowed.any { uri.startsWith(it) }) { "Not a thumbnail source" }
        val target = maxPx.coerceIn(32, 1024)
        val parsed = Uri.parse(uri)
        val type = context.contentResolver.getType(parsed) ?: ""
        val bitmap = if (type.startsWith("video/")) video(context, parsed, target) else image(context, parsed, target)
        return bitmap?.let { jpeg(it) }
    }

    private fun image(context: Context, uri: Uri, target: Int): Bitmap? {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) } ?: return null
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return null
        var sample = 1
        while (max(bounds.outWidth, bounds.outHeight) / (sample * 2) >= target) sample *= 2
        val options = BitmapFactory.Options().apply { inSampleSize = sample }
        val decoded = context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, options) } ?: return null
        return scale(decoded, target)
    }

    private fun video(context: Context, uri: Uri, target: Int): Bitmap? {
        val retriever = MediaMetadataRetriever()
        return try {
            retriever.setDataSource(context, uri)
            retriever.getScaledFrameAtTime(0, MediaMetadataRetriever.OPTION_CLOSEST_SYNC, target, target)
        } catch (e: Exception) {
            null
        } finally {
            retriever.release()
        }
    }

    private fun scale(bitmap: Bitmap, target: Int): Bitmap {
        val longest = max(bitmap.width, bitmap.height)
        if (longest <= target) return bitmap
        val ratio = target.toFloat() / longest
        return Bitmap.createScaledBitmap(bitmap, (bitmap.width * ratio).toInt().coerceAtLeast(1), (bitmap.height * ratio).toInt().coerceAtLeast(1), true)
            .also { if (it !== bitmap) bitmap.recycle() }
    }

    private fun jpeg(bitmap: Bitmap): ByteArray = ByteArrayOutputStream().use { out ->
        bitmap.compress(Bitmap.CompressFormat.JPEG, 82, out)
        bitmap.recycle()
        out.toByteArray()
    }
}
