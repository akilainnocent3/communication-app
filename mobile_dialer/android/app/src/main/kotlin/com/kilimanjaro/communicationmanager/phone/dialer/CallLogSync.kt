package com.kilimanjaro.communicationmanager.phone.dialer

import android.content.Context
import android.database.ContentObserver
import android.os.Handler
import android.os.HandlerThread
import android.provider.CallLog
import android.util.Log
import com.kilimanjaro.communicationmanager.phone.bridge.DeviceState
import com.kilimanjaro.communicationmanager.phone.data.SyncStore
import com.kilimanjaro.communicationmanager.phone.safely
import com.kilimanjaro.communicationmanager.phone.telephony.SyncTrigger
import org.json.JSONObject

/**
 * The system call log (Telecom writes it for every call, also those this dialer never saw). Backfill once within the
 * enrollment window, newest first, then a debounced ContentObserver copies new rows. Each row becomes a call.upsert
 * with its CallLog _ID; the server merges it with the live events of the same call. USSD/MMI and emergency rows are
 * skipped (CallLogMapper). Only ids, counts and codes are logged.
 */
object CallLogSync {
    private const val TAG = "CmCalls"
    private const val DEBOUNCE_MS = 1_500L
    private val projection = arrayOf(CallLog.Calls._ID, CallLog.Calls.NUMBER, CallLog.Calls.TYPE, CallLog.Calls.DATE, CallLog.Calls.DURATION,
        CallLog.Calls.NUMBER_PRESENTATION, CallLog.Calls.PHONE_ACCOUNT_ID, CallLog.Calls.CACHED_NAME)
    private var observer: ContentObserver? = null
    private val thread by lazy { HandlerThread("cm-calllog").apply { start() } }
    private val handler by lazy { Handler(thread.looper) }
    private val run = Runnable { safely("call log copy") { copyNew(appContext ?: return@safely) } }
    @Volatile private var appContext: Context? = null

    fun allowed(context: Context) = CallsFeature.enabled(context) && DeviceState.granted(context, "READ_CALL_LOG")

    fun watch(context: Context) {
        appContext = context.applicationContext
        if (observer != null || !allowed(context)) return
        observer = object : ContentObserver(handler) {
            override fun onChange(selfChange: Boolean) {
                handler.removeCallbacks(run)
                handler.postDelayed(run, DEBOUNCE_MS)
            }
        }.also { context.contentResolver.registerContentObserver(CallLog.Calls.CONTENT_URI, true, it) }
        handler.post(run)
    }

    private fun rows(context: Context, selection: String, args: Array<String>, order: String, limit: Int): List<CallLogRow> =
        context.contentResolver.query(CallLog.Calls.CONTENT_URI.buildUpon().appendQueryParameter(CallLog.Calls.LIMIT_PARAM_KEY, "$limit").build(),
            projection, selection, args, order)?.use { c ->
            buildList {
                while (c.moveToNext()) add(CallLogRow(id = c.getLong(0), number = c.getString(1), type = c.getInt(2), date = c.getLong(3), durationSeconds = c.getLong(4),
                    presentation = c.getInt(5), subId = Dialer.subscriptionFor(context, c.getString(6)), cachedName = c.getString(7)))
            }
        } ?: emptyList()

    /** New rows since the highest id copied (the observer, and after the backfill). */
    @Synchronized
    fun copyNew(context: Context): Int {
        if (!allowed(context)) return 0
        val store = SyncStore.get(context) ?: return 0
        if (store.value("calls_backfill_done") != "1") return backfill(context, store)
        val last = store.value("calls_log_last_id")?.toLongOrNull() ?: 0
        val new = rows(context, "${CallLog.Calls._ID} > ?", arrayOf("$last"), "${CallLog.Calls._ID} ASC", 500)
        var copied = 0
        for (row in new) {
            CallLogMapper.payload(row) { CallsFeature.isEmergency(context, it) }?.let { store.appendEvent("call.upsert", it); copied++ }
        }
        new.maxOfOrNull { it.id }?.let { store.setValue("calls_log_last_id", "$it") }
        if (copied > 0) {
            SyncTrigger.now(context)
            com.kilimanjaro.communicationmanager.phone.bridge.EventBus.emit("calls_changed")
        }
        return copied
    }

    /** History within the backfill window, newest first, in pages; then remember the highest id. */
    private fun backfill(context: Context, store: SyncStore): Int {
        val days = store.value("backfill_days")?.toIntOrNull() ?: 90
        val since = System.currentTimeMillis() - days * 86_400_000L
        val highest = rows(context, "1", emptyArray(), "${CallLog.Calls._ID} DESC", 1).firstOrNull()?.id ?: 0
        var before = Long.MAX_VALUE
        var copied = 0
        store.appendEvent("call_log.backfill", JSONObject().put("phase", "running").put("done", 0).put("total", 0))
        while (true) {
            val page = rows(context, "${CallLog.Calls.DATE} >= ? AND ${CallLog.Calls._ID} < ?", arrayOf("$since", "$before"), "${CallLog.Calls._ID} DESC", 200)
            if (page.isEmpty()) break
            for (row in page) CallLogMapper.payload(row) { CallsFeature.isEmergency(context, it) }?.let { store.appendEvent("call.upsert", it); copied++ }
            before = page.minOf { it.id }
            if (page.size < 200) break
        }
        store.appendEvent("call_log.backfill", JSONObject().put("phase", "done").put("done", copied).put("total", copied))
        store.setValue("calls_log_last_id", "$highest")
        store.setValue("calls_backfill_done", "1")
        Log.i(TAG, "call log backfill queued $copied calls")
        SyncTrigger.now(context)
        return copied
    }
}
