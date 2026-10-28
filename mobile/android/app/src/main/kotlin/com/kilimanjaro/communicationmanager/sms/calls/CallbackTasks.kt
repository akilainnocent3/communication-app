package com.kilimanjaro.communicationmanager.sms.calls

import android.content.Context
import com.kilimanjaro.communicationmanager.sms.data.SyncStore
import com.kilimanjaro.communicationmanager.sms.telephony.SyncTrigger
import org.json.JSONArray
import org.json.JSONObject

/**
 * Call-back tasks from the admin (GET calls/callbacks/), cached in the encrypted database for the app's list. New tasks
 * raise a notification once ("Call back Neema — requested by Halima"); the holder taps Call. States go back to the
 * server as callback.state events.
 */
object CallbackTasks {
    data class Task(val id: String, val number: String, val name: String, val reason: String, val requestedBy: String, val priority: String, val dueAt: Long, val state: String)

    fun parse(array: JSONArray): List<Task> = (0 until array.length()).map { i ->
        val o = array.getJSONObject(i)
        Task(o.getString("id"), o.getString("number"), o.optString("name"), o.optString("reason"), o.optString("requested_by"), o.optString("priority", "normal"),
            o.optLong("due_at"), o.optString("state", "open"))
    }

    fun cached(context: Context): List<Task> = runCatching { parse(JSONArray(SyncStore.get(context)?.value("cache.callbacks") ?: "[]")) }.getOrDefault(emptyList())

    /** Store the server's list; notify tasks not seen before; report them as "notified". Returns the new ones. */
    fun update(context: Context, array: JSONArray, now: Long = System.currentTimeMillis()): List<Task> {
        val store = SyncStore.get(context) ?: return emptyList()
        val tasks = parse(array)
        val seen = JSONArray(store.value("callbacks.seen") ?: "[]").let { a -> (0 until a.length()).map { a.getString(it) }.toSet() }
        val fresh = tasks.filter { it.id !in seen && it.dueAt <= now + 60_000 }
        store.setValue("cache.callbacks", array.toString())
        store.setValue("callbacks.seen", JSONArray((seen + fresh.map { it.id }).toList().takeLast(500)).toString())
        for (task in fresh) {
            CallNotifications.callback(context, task)
            store.appendEvent("callback.state", JSONObject().put("task", task.id).put("state", "notified").put("at", now))
        }
        return fresh
    }

    fun report(context: Context, task: String, state: String, now: Long = System.currentTimeMillis()) {
        val payload = JSONObject().put("task", task).put("state", state).put("at", now)
        if (state == "snoozed") payload.put("snoozed_until", now + 60 * 60_000)
        SyncStore.get(context)?.appendEvent("callback.state", payload)
        SyncTrigger.now(context)
    }
}
