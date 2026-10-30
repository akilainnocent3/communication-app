package com.kilimanjaro.communicationmanager.phone.dialer

import android.content.Context
import android.media.AudioManager
import android.media.ToneGenerator
import android.provider.Settings

/** The keypad's tones, as the phone's own dialer plays them: system "Dial pad tones" on and ringer in normal mode. */
object KeypadTone {
    private const val DURATION_MS = 120
    private var generator: ToneGenerator? = null

    private val tones = mapOf(
        '0' to ToneGenerator.TONE_DTMF_0, '1' to ToneGenerator.TONE_DTMF_1, '2' to ToneGenerator.TONE_DTMF_2, '3' to ToneGenerator.TONE_DTMF_3,
        '4' to ToneGenerator.TONE_DTMF_4, '5' to ToneGenerator.TONE_DTMF_5, '6' to ToneGenerator.TONE_DTMF_6, '7' to ToneGenerator.TONE_DTMF_7,
        '8' to ToneGenerator.TONE_DTMF_8, '9' to ToneGenerator.TONE_DTMF_9, '*' to ToneGenerator.TONE_DTMF_S, '#' to ToneGenerator.TONE_DTMF_P,
    )

    @Synchronized
    fun play(context: Context, key: String) {
        val tone = key.singleOrNull()?.let(tones::get) ?: return
        if (Settings.System.getInt(context.contentResolver, Settings.System.DTMF_TONE_WHEN_DIALING, 1) != 1) return
        if (context.getSystemService(AudioManager::class.java)?.ringerMode != AudioManager.RINGER_MODE_NORMAL) return
        val player = generator ?: runCatching { ToneGenerator(AudioManager.STREAM_DTMF, 80) }.getOrNull()?.also { generator = it } ?: return
        player.startTone(tone, DURATION_MS)
    }
}
