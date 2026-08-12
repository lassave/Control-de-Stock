plugins {
    id("com.android.application") version "8.4.0" apply false
    id("org.jetbrains.kotlin.android") version "1.9.23" apply false
    id("org.jetbrains.kotlin.jvm") version "1.9.23" apply false
    id("org.jetbrains.kotlin.plugin.serialization") version "1.9.23" apply false
    // La versión de KSP se ata a la de Kotlin: el sufijo es su propio número.
    id("com.google.devtools.ksp") version "1.9.23-1.0.20" apply false
}
