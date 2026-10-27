package com.kilimanjaro.communicationmanager.sms.telephony

import android.content.ContentValues
import android.content.Context
import android.provider.BlockedNumberContract
import android.provider.BlockedNumberContract.BlockedNumbers
import com.kilimanjaro.communicationmanager.sms.data.SyncStore
import org.json.JSONObject

/** Android's system block list (BlockedNumberContract); the default SMS app may read and write it. Synced to the server. */
object Blocking {
    fun canBlock(context: Context): Boolean = BlockedNumberContract.canCurrentUserBlockNumbers(context)

    fun isBlocked(context: Context, address: String): Boolean = try {
        BlockedNumberContract.isBlocked(context, address)
    } catch (e: Exception) {
        false
    }

    fun block(context: Context, address: String) {
        if (isBlocked(context, address)) return
        context.contentResolver.insert(BlockedNumbers.CONTENT_URI, ContentValues().apply { put(BlockedNumbers.COLUMN_ORIGINAL_NUMBER, address) })
        SyncStore.get(context)?.appendEvent("block.add", JSONObject().put("address", address))
    }

    fun unblock(context: Context, address: String) {
        BlockedNumberContract.unblock(context, address)
        SyncStore.get(context)?.appendEvent("block.remove", JSONObject().put("address", address))
    }

    fun list(context: Context): List<String> =
        context.contentResolver.query(BlockedNumbers.CONTENT_URI, arrayOf(BlockedNumbers.COLUMN_ORIGINAL_NUMBER), null, null, null)?.use { c ->
            buildList { while (c.moveToNext()) add(c.getString(0)) }
        } ?: emptyList()
}
