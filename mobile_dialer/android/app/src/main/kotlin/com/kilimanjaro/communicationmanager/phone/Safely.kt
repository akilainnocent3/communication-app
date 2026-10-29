package com.kilimanjaro.communicationmanager.phone

import android.util.Log

/**
 * Runs one step of receiver/service work so that a failure is logged instead of killing the process. An uncaught
 * exception in a receiver thread crashes the app on every incoming SMS ("keeps stopping"), which is worse than
 * skipping one optional step. Linkage errors (an API missing on an older Android or OEM build) are caught too; VM
 * errors such as OutOfMemoryError are not. Only the class is logged: messages can contain SQL or message content.
 */
internal inline fun safely(step: String, block: () -> Unit) {
    try {
        block()
    } catch (e: Throwable) {
        if (e is VirtualMachineError) throw e
        Log.w("CmSms", "$step failed: ${e.javaClass.name}")
    }
}
