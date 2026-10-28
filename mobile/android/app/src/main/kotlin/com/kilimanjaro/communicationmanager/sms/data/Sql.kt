package com.kilimanjaro.communicationmanager.sms.data

import android.content.ContentValues
import android.database.Cursor
import net.zetetic.database.sqlcipher.SQLiteDatabase

/**
 * The few database operations the native layer needs. Production runs on SQLCipher ([CipherSql]); unit tests run the
 * same store code on the framework SQLite under Robolectric (SQLCipher's native library is Android-only).
 */
interface Sql {
    fun <T> query(sql: String, args: Array<String> = emptyArray(), read: (Cursor) -> T): T
    fun insert(table: String, values: ContentValues, conflict: Conflict = Conflict.ABORT): Long
    fun update(table: String, values: ContentValues, where: String, args: Array<String>): Int
    fun delete(table: String, where: String, args: Array<String>): Int
    fun <T> transaction(block: () -> T): T
    fun close()

    enum class Conflict { ABORT, IGNORE, REPLACE }
}

/** Runs a PRAGMA (or any statement) and steps it: an unstepped rawQuery cursor never executes. */
fun SQLiteDatabase.pragma(statement: String): String? = rawQuery(statement, null).use { if (it.moveToFirst() && it.columnCount > 0) it.getString(0) else null }

class CipherSql(private val db: SQLiteDatabase) : Sql {
    override fun <T> query(sql: String, args: Array<String>, read: (Cursor) -> T): T = db.rawQuery(sql, args).use(read)

    override fun insert(table: String, values: ContentValues, conflict: Sql.Conflict): Long = db.insertWithOnConflict(table, null, values, when (conflict) {
        Sql.Conflict.ABORT -> SQLiteDatabase.CONFLICT_ABORT
        Sql.Conflict.IGNORE -> SQLiteDatabase.CONFLICT_IGNORE
        Sql.Conflict.REPLACE -> SQLiteDatabase.CONFLICT_REPLACE
    })

    override fun update(table: String, values: ContentValues, where: String, args: Array<String>): Int = db.update(table, values, where, args)
    override fun delete(table: String, where: String, args: Array<String>): Int = db.delete(table, where, args)

    override fun <T> transaction(block: () -> T): T {
        db.beginTransaction()
        try {
            return block().also { db.setTransactionSuccessful() }
        } finally {
            db.endTransaction()
        }
    }

    override fun close() = db.close()
}
