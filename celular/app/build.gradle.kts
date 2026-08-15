import java.time.LocalDate
import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.serialization")
    id("com.google.devtools.ksp")
}

/**
 * La firma vive fuera del proyecto: esta carpeta se copia a la PC del
 * cliente, y la firma es lo único que impide que un tercero publique una
 * actualización que los celulares acepten como nuestra.
 */
val archivoDeFirma = File(
    System.getenv("CONTROL_DE_STOCK_FIRMA")
        ?: "C:/clientes/claves/control-de-stock.properties",
)

/**
 * Solo el release necesita la clave y el número de versión de verdad.
 *
 * Sin esta distinción, cualquier compilación de debug —o sea todas las de
 * todos los días— exigiría la clave y el historial de git.
 *
 * "publicar" cuenta como release aunque su propio nombre no lleve "elease":
 * depende de assembleRelease, pero taskNames solo trae lo que se tipeó en la
 * línea de comandos, no las tareas de las que depende. Sin este agregado,
 * `gradle :app:publicar` compila con la firma de debug sin avisar.
 */
val esRelease = gradle.startParameter.taskNames.any {
    it.contains("elease") || it.contains("ublicar")
}

fun exigirLaFirma(): Properties {
    if (!archivoDeFirma.exists()) {
        throw GradleException(
            "Falta el archivo con la clave para firmar la app:\n" +
                "  ${archivoDeFirma.absolutePath}\n\n" +
                "Copiá celular/claves-de-ejemplo.properties a esa ruta y completá " +
                "las contraseñas, o poné otra ruta en la variable de entorno " +
                "CONTROL_DE_STOCK_FIRMA.\n\n" +
                "Sin firma, Android no instala la app.",
        )
    }
    val claves = Properties().apply { archivoDeFirma.inputStream().use { load(it) } }

    val faltantes = listOf("almacen", "clave", "alias", "claveDelAlias")
        .filter { claves.getProperty(it).isNullOrBlank() }
    if (faltantes.isNotEmpty()) {
        throw GradleException(
            "El archivo de firma le falta completar: ${faltantes.joinToString(", ")}\n" +
                "  ${archivoDeFirma.absolutePath}\n\n" +
                "Es el archivo que quedó al copiar celular/claves-de-ejemplo.properties " +
                "sin completar las contraseñas.",
        )
    }
    if (!File(claves.getProperty("almacen")).exists()) {
        throw GradleException(
            "El archivo de firma señala un almacén de claves que no existe:\n" +
                "  ${claves.getProperty("almacen")}\n\n" +
                "Revisá la propiedad \"almacen\" en:\n  ${archivoDeFirma.absolutePath}",
        )
    }
    return claves
}

/**
 * El número de versión sale de cuántos commits lleva el repositorio.
 *
 * Sube solo, así que no hay forma de olvidarse ni de publicar dos veces el
 * mismo número — y Android rechaza una actualización cuyo número no sea
 * mayor que el instalado, con un error que no explica nada.
 */
fun contarCommits(): Int {
    val proceso = ProcessBuilder("git", "rev-list", "--count", "HEAD")
        .directory(rootDir)
        .redirectErrorStream(true)
        .start()
    val salida = proceso.inputStream.bufferedReader().readText().trim()
    val numero = salida.toIntOrNull()

    if (proceso.waitFor() != 0 || numero == null) {
        throw GradleException(
            "No se pudo averiguar el número de versión con git:\n  $salida\n\n" +
                "La app se publica desde una copia del repositorio, con git " +
                "disponible. Un número inventado produce un APK que no se " +
                "instala encima del anterior, y eso se descubre recién en el " +
                "celular del operario.",
        )
    }
    return numero
}

// LocalDate importado arriba: escrito como "java.time.LocalDate" acá adentro
// no compila, porque el plugin de Android agrega una propiedad "java" al
// proyecto que tapa el paquete del mismo nombre.
val versionPublicada: String by lazy {
    LocalDate.now().toString()
}

android {
    namespace = "com.controldestock"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.controldestock"
        minSdk = 26
        targetSdk = 34
        // En debug queda el 1 de siempre: el número solo importa al publicar,
        // y pedirle git a cada compilación del día a día es un estorbo.
        versionCode = if (esRelease) contarCommits() else 1
        versionName = if (esRelease) versionPublicada else "desarrollo"
    }

    signingConfigs {
        create("publicacion") {
            if (esRelease) {
                val claves = exigirLaFirma()
                storeFile = File(claves.getProperty("almacen"))
                storePassword = claves.getProperty("clave")
                keyAlias = claves.getProperty("alias")
                keyPassword = claves.getProperty("claveDelAlias")
            }
        }
    }

    buildTypes {
        getByName("release") {
            signingConfig = signingConfigs.getByName("publicacion")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    testOptions {
        unitTests.isIncludeAndroidResources = true
    }

    buildFeatures {
        compose = true
    }

    composeOptions {
        // Atada a Kotlin 1.9.23: una combinación distinta no compila.
        kotlinCompilerExtensionVersion = "1.5.11"
    }
}

// Room escribe acá el esquema de cada versión de la base. Van al repo: son
// la referencia de cómo era antes de cada migración, y sin ellos una
// migración solo se puede probar a ojo.
ksp {
    arg("room.schemaLocation", "$projectDir/schemas")
}

dependencies {
    implementation(project(":nucleo"))

    implementation("androidx.room:room-runtime:2.6.1")
    implementation("androidx.room:room-ktx:2.6.1")
    ksp("androidx.room:room-compiler:2.6.1")

    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.work:work-runtime-ktx:2.9.0")

    implementation(platform("androidx.compose:compose-bom:2024.05.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")
    implementation("androidx.activity:activity-compose:1.9.0")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.0")

    implementation("androidx.camera:camera-core:1.3.3")
    implementation("androidx.camera:camera-camera2:1.3.3")
    implementation("androidx.camera:camera-lifecycle:1.3.3")
    implementation("androidx.camera:camera-view:1.3.3")
    // La variante con el modelo adentro del APK. La otra lo descarga de Play
    // Services la primera vez, y en el depósito no hay internet.
    implementation("com.google.mlkit:barcode-scanning:17.2.0")

    testImplementation("junit:junit:4.13.2")
    // Para probar las pantallas sin celular: lo que el operario ve en la
    // ficha es una regla de negocio y no puede depender de que alguien la
    // mire.
    testImplementation("androidx.compose.ui:ui-test-junit4")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
    testImplementation("com.squareup.okhttp3:mockwebserver:4.12.0")
    testImplementation("org.robolectric:robolectric:4.12.2")
    testImplementation("androidx.test:core:1.5.0")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.8.0")
}

/**
 * Deja el APK donde el panel lo busca, con su versión al lado.
 *
 * El panel sirve `<raíz>/app.apk`, y la versión va en un archivo aparte
 * porque adentro del APK está en un formato binario que solo saben leer las
 * herramientas del SDK, que en la PC del cliente no están. Los dos los
 * escribe esta tarea, en el mismo movimiento, así no pueden separarse.
 */
tasks.register("publicar") {
    dependsOn("assembleRelease")

    doLast {
        val compilado = layout.buildDirectory
            .file("outputs/apk/release/app-release.apk").get().asFile

        // El panel busca el APK en `servidor/app.apk`, no en la raíz del
        // proyecto: la ruta la arma `panel.py` desde su propia ubicación.
        // Dejarlo en la raíz lo deja invisible, y el síntoma es que el bloque
        // de instalación no aparece, sin decir por qué.
        val carpetaDelServidor = File(rootDir.parentFile, "servidor")
        if (!File(carpetaDelServidor, "app/api/panel.py").exists()) {
            throw GradleException(
                "No encontré la carpeta del servidor donde esperaba:\n" +
                    "  ${carpetaDelServidor.absolutePath}\n\n" +
                    "Ahí es donde panel.py busca el APK. Si la estructura de " +
                    "carpetas del proyecto cambió, hay que actualizar esta tarea.",
            )
        }
        val destino = File(carpetaDelServidor, "app.apk")
        val version = "$versionPublicada (build ${contarCommits()})"

        compilado.copyTo(destino, overwrite = true)
        File(carpetaDelServidor, "app.apk.txt").writeText(version, Charsets.UTF_8)

        println("")
        println("Publicada la version $version")
        println("Queda en ${destino.absolutePath}")
        println("El panel ya la ofrece en la pestania de Operarios.")
    }
}
