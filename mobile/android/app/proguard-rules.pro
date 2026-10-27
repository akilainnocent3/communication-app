# SQLCipher uses JNI; keep its classes.
-keep class net.zetetic.database.** { *; }
# Pigeon-generated bridge and our receivers/services referenced from the manifest are kept by AAPT rules.
-keep class com.kilimanjaro.communicationmanager.sms.bridge.** { *; }
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**
