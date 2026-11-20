import java.util.Properties

plugins {
    id("com.android.application")
    id("com.google.gms.google-services")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

val signingKeys = listOf("storeFile", "storePassword", "keyAlias", "keyPassword")
val envSigning: Map<String, String?> = mapOf(
    "storeFile" to System.getenv("ASTROPLAN_STORE_FILE"),
    "storePassword" to System.getenv("ASTROPLAN_STORE_PASSWORD"),
    "keyAlias" to System.getenv("ASTROPLAN_KEY_ALIAS"),
    "keyPassword" to System.getenv("ASTROPLAN_KEY_PASSWORD"),
)
val envSigningConfigured = signingKeys.all { !envSigning[it].isNullOrBlank() }

val signingPropertiesFile = rootProject.file("key.properties")
val signingProperties = Properties().apply {
    if (signingPropertiesFile.exists()) {
        signingPropertiesFile.inputStream().use { load(it) }
    }
}
val fileSigningConfigured = signingPropertiesFile.exists() &&
    signingKeys.all { !signingProperties.getProperty(it).isNullOrBlank() }
val signingConfigured = envSigningConfigured || fileSigningConfigured

fun signingValue(key: String): String =
    if (envSigningConfigured) envSigning.getValue(key)!! else signingProperties.getProperty(key)

if (!signingConfigured) {
    gradle.taskGraph.whenReady {
        if (allTasks.any { it.name.contains("Release") }) {
            throw GradleException(
                "Release signing is not configured. Set ASTROPLAN_STORE_FILE, " +
                    "ASTROPLAN_STORE_PASSWORD, ASTROPLAN_KEY_ALIAS, ASTROPLAN_KEY_PASSWORD, " +
                    "or create android/key.properties with " + signingKeys.joinToString(", ") +
                    " (storeFile may be an absolute path). Release builds fail closed " +
                    "until a real upload keystore is provided."
            )
        }
    }
}

android {
    namespace = "in.astroplan.astroplan"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        isCoreLibraryDesugaringEnabled = true
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "in.astroplan.astroplan"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        if (signingConfigured) {
            create("release") {
                storeFile = file(signingValue("storeFile"))
                storePassword = signingValue("storePassword")
                keyAlias = signingValue("keyAlias")
                keyPassword = signingValue("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            if (signingConfigured) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}

dependencies {
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4")
}
