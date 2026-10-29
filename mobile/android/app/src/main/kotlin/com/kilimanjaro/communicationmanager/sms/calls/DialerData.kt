package com.kilimanjaro.communicationmanager.sms.calls

import android.content.Context
import android.provider.CallLog
import android.provider.ContactsContract
import com.kilimanjaro.communicationmanager.sms.bridge.CallbackTaskData
import com.kilimanjaro.communicationmanager.sms.bridge.DeviceState
import com.kilimanjaro.communicationmanager.sms.bridge.PhoneContact
import com.kilimanjaro.communicationmanager.sms.bridge.RecentCall

/** What the Flutter Phone screens read: recents (the system call log), the address book, call-back tasks. */
object DialerData {
    fun recent(context: Context, limit: Int, offset: Int): List<RecentCall> {
        if (!DeviceState.granted(context, "READ_CALL_LOG")) return emptyList()
        val projection = arrayOf(CallLog.Calls._ID, CallLog.Calls.NUMBER, CallLog.Calls.TYPE, CallLog.Calls.DATE, CallLog.Calls.DURATION, CallLog.Calls.PHONE_ACCOUNT_ID)
        val uri = CallLog.Calls.CONTENT_URI.buildUpon().appendQueryParameter(CallLog.Calls.LIMIT_PARAM_KEY, "${limit + offset}").build()
        val rows = context.contentResolver.query(uri, projection, null, null, "${CallLog.Calls.DATE} DESC")?.use { c ->
            buildList {
                var index = 0
                while (c.moveToNext()) {
                    if (index++ < offset) continue
                    val number = c.getString(1).orEmpty()
                    if (CallPrivacy.isMmi(number)) continue // USSD sessions are never shown or kept by OCM
                    val type = c.getInt(2)
                    val duration = c.getLong(4)
                    val (direction, result) = when (type) {
                        CallLogMapper.INCOMING -> "in" to "answered"
                        CallLogMapper.OUTGOING -> "out" to if (duration > 0) "answered" else "no_answer"
                        CallLogMapper.MISSED -> "in" to "missed"
                        CallLogMapper.VOICEMAIL -> "in" to "voicemail"
                        CallLogMapper.REJECTED -> "in" to "rejected"
                        CallLogMapper.BLOCKED -> "in" to "blocked"
                        else -> "in" to "answered_elsewhere"
                    }
                    val identity = CallerId.identify(context, number)
                    add(RecentCall(id = c.getLong(0), number = number, name = identity.name, nameSource = identity.source, direction = direction, result = result,
                        date = c.getLong(3), durationSeconds = duration, subscriptionId = Dialer.subscriptionFor(context, c.getString(5))))
                }
            }
        } ?: emptyList()
        return rows
    }

    fun contacts(context: Context, limit: Int): List<PhoneContact> {
        if (!DeviceState.granted(context, "READ_CONTACTS")) return emptyList()
        val projection = arrayOf(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME, ContactsContract.CommonDataKinds.Phone.NUMBER,
            ContactsContract.CommonDataKinds.Phone.STARRED, ContactsContract.CommonDataKinds.Phone.PHOTO_THUMBNAIL_URI)
        return context.contentResolver.query(ContactsContract.CommonDataKinds.Phone.CONTENT_URI, projection, null, null,
            "${ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME} COLLATE LOCALIZED ASC")?.use { c ->
            buildList {
                val seen = HashSet<String>()
                while (c.moveToNext() && size < limit) {
                    val number = c.getString(1)?.trim().orEmpty()
                    val name = c.getString(0).orEmpty()
                    if (number.isEmpty() || !seen.add(name + number.filter(Char::isDigit).takeLast(9))) continue
                    add(PhoneContact(name = name, number = number, starred = c.getInt(2) == 1, photoUri = c.getString(3), directoryName = CallerId.directoryName(context, number)))
                }
            }
        } ?: emptyList()
    }

    fun callbacks(context: Context): List<CallbackTaskData> = CallbackTasks.cached(context).map {
        CallbackTaskData(id = it.id, number = it.number, name = it.name, reason = it.reason, requestedBy = it.requestedBy, priority = it.priority, dueAt = it.dueAt, state = it.state)
    }

    fun delete(context: Context, id: Long) {
        if (DeviceState.granted(context, "WRITE_CALL_LOG")) context.contentResolver.delete(CallLog.Calls.CONTENT_URI, "${CallLog.Calls._ID} = ?", arrayOf("$id"))
    }

}
