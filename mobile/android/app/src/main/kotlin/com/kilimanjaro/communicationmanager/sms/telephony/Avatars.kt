package com.kilimanjaro.communicationmanager.sms.telephony

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import androidx.core.graphics.ColorUtils

/** Coloured initials like the app's list (lib/ui/widgets/avatar.dart): the same hue per address, "#" for numbers. */
object Avatars {
    fun hue(address: String): Int = address.fold(0) { h, c -> (h * 31 + c.code) and 0x7fffffff } % 360

    fun label(address: String, name: String?): String {
        val words = name?.trim()?.split(Regex("\\s+"))?.filter { it.isNotEmpty() }.orEmpty()
        if (words.isNotEmpty()) return (words.first().take(1) + if (words.size > 1) words.last().take(1) else "").uppercase()
        return if (address.any { it.isLetter() }) address.take(1).uppercase() else "#"
    }

    fun initials(address: String, name: String?, size: Int = 192): Bitmap {
        val bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        val fill = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = ColorUtils.HSLToColor(floatArrayOf(hue(address).toFloat(), 0.5f, 0.42f)) }
        canvas.drawCircle(size / 2f, size / 2f, size / 2f, fill)
        val text = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE; textSize = size * 0.38f; textAlign = Paint.Align.CENTER; typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
        }
        canvas.drawText(label(address, name), size / 2f, size / 2f - (text.descent() + text.ascent()) / 2, text)
        return bitmap
    }
}
