package com.kilimanjaro.communicationmanager.sms

import android.content.ContentValues
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import com.kilimanjaro.communicationmanager.sms.data.Sql

/** The store's SQL on the framework SQLite (Robolectric), with drift's real schema (test/resources/sync_schema.sql). */
class FrameworkSql(private val db: SQLiteDatabase) : Sql {
    companion object {
        fun withDriftSchema(): FrameworkSql {
            val db = SQLiteDatabase.create(null)
            val ddl = FrameworkSql::class.java.getResource("/sync_schema.sql")!!.readText()
            ddl.split(";\n").map { it.trim() }.filter { it.isNotEmpty() }.forEach { db.execSQL(it) }
            return FrameworkSql(db)
        }
    }

    override fun <T> query(sql: String, args: Array<String>, read: (Cursor) -> T): T = db.rawQuery(sql, args).use(read)
    override fun insert(table: String, values: ContentValues, conflict: Sql.Conflict): Long = db.insertWithOnConflict(table, null, values, when (conflict) {
        Sql.Conflict.ABORT -> SQLiteDatabase.CONFLICT_ABORT
        Sql.Conflict.IGNORE -> SQLiteDatabase.CONFLICT_IGNORE
        Sql.Conflict.REPLACE -> SQLiteDatabase.CONFLICT_REPLACE
    })
    override fun update(table: String, values: ContentValues, where: String, args: Array<String>) = db.update(table, values, where, args)
    override fun delete(table: String, where: String, args: Array<String>) = db.delete(table, where, args)
    override fun <T> transaction(block: () -> T): T {
        db.beginTransaction()
        try {
            return block().also { db.setTransactionSuccessful() }
        } finally {
            db.endTransaction()
        }
    }
    override fun close() = db.close()

    fun exec(sql: String) = db.execSQL(sql)
}
