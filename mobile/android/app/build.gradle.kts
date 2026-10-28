import java.util.Base64
import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

/** --dart-define values (base64, comma separated) passed by `flutter build`. */
fun dartDefines(): Map<String, String> {
    val raw = (project.findProperty("dart-defines") as String?) ?: return emptyMap()
    return raw.split(",").mapNotNull {
        val decoded = String(Base64.getDecoder().decode(it))
        decoded.split("=", limit = 2).takeIf { pair -> pair.size == 2 }?.let { pair -> pair[0] to pair[1] }
    }.toMap()
}
val defines = dartDefines()

// Release signing comes from android/key.properties (git-ignored); see mobile/README.md.
val keyProperties = Properties().apply {
    val file = rootProject.file("key.properties")
    if (file.exists()) file.inputStream().use { load(it) }
}

android {
    namespace = "com.kilimanjaro.communicationmanager.sms"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        buildConfig = true
    }

    defaultConfig {
        applicationId = "com.kilimanjaro.communicationmanager.sms"
        // Android 10: RoleManager.ROLE_SMS.
        minSdk = 29
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
        buildConfigField("String", "ALLOWED_SERVER_HOSTS", "\"${defines["ALLOWED_SERVER_HOSTS"] ?: ""}\"")
        buildConfigField("String", "PINNED_SPKI", "\"${defines["PINNED_SPKI"] ?: ""}\"")
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    // play: Google Play (managed or public); omits REQUEST_IGNORE_BATTERY_OPTIMIZATIONS and only guides the holder
    // to the setting. private: MDM / signed APK; declares it (src/private/AndroidManifest.xml). See mobile/README.md.
    flavorDimensions += "distribution"
    productFlavors {
        create("play") {
            dimension = "distribution"
            buildConfigField("boolean", "DIRECT_BATTERY_REQUEST", "false")
        }
        create("private") {
            dimension = "distribution"
            buildConfigField("boolean", "DIRECT_BATTERY_REQUEST", "true")
        }
    }

    signingConfigs {
        create("release") {
            if (keyProperties.isNotEmpty()) {
                storeFile = file(keyProperties.getProperty("storeFile"))
                storePassword = keyProperties.getProperty("storePassword")
                keyAlias = keyProperties.getProperty("keyAlias")
                keyPassword = keyProperties.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            // Without key.properties the release build is signed with the debug key so CI can still build it.
            signingConfig = if (keyProperties.isNotEmpty()) signingConfigs.getByName("release") else signingConfigs.getByName("debug")
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    // Compress native libraries in the APK (decision 58): phones get the APK file itself, and stored libraries made the
    // arm64 split about 28 MB; deflated it is about 16 MB. Android extracts them once at install.
    packaging {
        jniLibs {
            useLegacyPackaging = true
        }
    }

    testOptions {
        unitTests.isIncludeAndroidResources = true
    }

    // Measurement tools (seeding) exist only in debug and profile builds, never in release.
    sourceSets.matching { it.name == "debug" || it.name == "profile" }.configureEach {
        java.srcDir("src/devtools/kotlin")
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
    implementation("com.squareup.okhttp3:okhttp:5.1.0")
    implementation("androidx.work:work-runtime-ktx:2.10.3")
    implementation("androidx.core:core-ktx:1.16.0")
    implementation("androidx.activity:activity-ktx:1.10.1")
    implementation("net.zetetic:sqlcipher-android:4.10.0@aar")
    implementation("androidx.sqlite:sqlite:2.5.2")
    implementation("com.google.firebase:firebase-messaging:25.0.0")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.robolectric:robolectric:4.15.1")
    testImplementation("androidx.test:core:1.6.1")
    testImplementation("com.squareup.okhttp3:mockwebserver:5.1.0")
}

flutter {
    source = "../.."
}

// google-services.json is optional (FCM). Apply the plugin only when the file is present.
if (file("google-services.json").exists()) {
    apply(plugin = "com.google.gms.google-services")
}

// Robolectric tests package the merged assets, which the Flutter plugin also writes: order them explicitly.
tasks.configureEach {
    for (flavor in listOf("Play", "Private")) {
        if (name == "package${flavor}DebugUnitTestForUnitTest") dependsOn("copyFlutterAssets${flavor}Debug")
        if (name == "package${flavor}ReleaseUnitTestForUnitTest") dependsOn("copyFlutterAssets${flavor}Release")
    }
}
