package com.kilimanjaro.communicationmanager.sms.devtools

import android.content.BroadcastReceiver
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import android.util.Log
import kotlin.random.Random

/**
 * Debug and profile builds only (src/devtools, never in release): fills the Telephony provider with synthetic
 * conversations for performance measurements. The receiver is guarded by android.permission.DUMP, so only adb shell
 * can trigger it:
 *
 *   adb shell am broadcast -n com.kilimanjaro.communicationmanager.sms/.devtools.SeedReceiver \
 *     --ei threads 300 --ei messages 20000 --ei big 2000
 *
 * Thread 1 gets `big` messages (the "open a long conversation" measurement); the rest are spread over the others.
 * Needs the default SMS role (only the default app may write the provider).
 */
class SeedReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val threads = intent.getIntExtra("threads", 300)
        val messages = intent.getIntExtra("messages", 20000)
        val big = intent.getIntExtra("big", 2000).coerceAtMost(messages)
        // Not inside goAsync(): 20 000 inserts take longer than a broadcast may (the app's service keeps the process up).
        Thread { seed(context.applicationContext, threads, messages, big) }.start()
    }

    private fun seed(context: Context, threads: Int, messages: Int, big: Int) {
        val random = Random(42)
        val now = System.currentTimeMillis()
        val day = 24 * 60 * 60 * 1000L
        val texts = listOf(
            "Habari, nimefika ofisini.", "Asante sana!", "Tafadhali nipigie ukipata nafasi.", "OK", "Sawa, tutaonana kesho saa tatu asubuhi.",
            "The delivery is on its way and should arrive before 4 pm.", "Your M-PESA payment of TSh 25,000 was received. Ref QJK7H2", "Ndiyo",
            "Can you confirm the booking for Saturday? We have two rooms left at the lodge near the park gate.", "Nitachelewa kidogo, foleni ni kubwa sana leo.",
        )
        val started = System.currentTimeMillis()
        var written = 0
        val batch = ArrayList<ContentValues>(500)
        fun flush() {
            if (batch.isEmpty()) return
            written += context.contentResolver.bulkInsert(Telephony.Sms.CONTENT_URI, batch.toTypedArray())
            batch.clear()
        }
        for (i in 0 until messages) {
            val thread = if (i < big) 0 else 1 + (i - big) % (threads - 1).coerceAtLeast(1)
            val address = "+2557%08d".format(10_000_000 + thread * 7919 % 89_999_999)
            val inbox = random.nextInt(100) < 55
            // Spread over 120 days; the long conversation is the most recent one.
            val date = now - (if (thread == 0) i.toLong() * 60_000L else random.nextLong(120 * day))
            batch += ContentValues().apply {
                put(Telephony.Sms.ADDRESS, address)
                put(Telephony.Sms.BODY, texts[random.nextInt(texts.size)])
                put(Telephony.Sms.DATE, date)
                put(Telephony.Sms.DATE_SENT, date)
                put(Telephony.Sms.TYPE, if (inbox) Telephony.Sms.MESSAGE_TYPE_INBOX else Telephony.Sms.MESSAGE_TYPE_SENT)
                val unread = inbox && random.nextInt(100) < 3
                put(Telephony.Sms.READ, if (unread) 0 else 1)
                put(Telephony.Sms.SEEN, if (unread) 0 else 1)
            }
            if (batch.size == 500) flush()
        }
        flush()
        Log.i("CmSmsSeed", "seeded $written messages in $threads threads in ${System.currentTimeMillis() - started} ms")
    }
}
