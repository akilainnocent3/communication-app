# SQLCipher uses JNI; keep its classes.
-keep class net.zetetic.database.** { *; }
# WorkManager's Room database (WorkDatabase_Impl) is created by reflection; without this R8 strips its
# no-arg constructor and the release app crashes at startup in androidx.startup.InitializationProvider.
-keep class * extends androidx.room.RoomDatabase { <init>(); }
# Pigeon-generated bridge and our receivers/services referenced from the manifest are kept by AAPT rules.
-keep class com.kilimanjaro.communicationmanager.sms.bridge.** { *; }
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**
