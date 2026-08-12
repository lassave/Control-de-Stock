package com.controldestock.nucleo

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * El núcleo se prueba en la PC en segundos porque no depende del framework.
 * Un solo import de `android.*` obliga a un emulador o un celular enchufado
 * para correr los tests, y ahí se termina la disciplina.
 */
class NucleoSinAndroidTest {

    @Test
    fun `ningun archivo del nucleo importa android`() {
        val fuentes = File("src/main/kotlin").walkTopDown().filter { it.extension == "kt" }

        val contaminados = fuentes.filter { archivo ->
            archivo.readLines().any { it.trimStart().startsWith("import android") }
        }.map { it.name }.toList()

        assertEquals(emptyList<String>(), contaminados)
    }

    @Test
    fun `el test anterior mira los archivos que tiene que mirar`() {
        // Sin esto, un cambio de ruta dejaría el guardián recorriendo una
        // carpeta vacía y aprobando cualquier cosa.
        val fuentes = File("src/main/kotlin").walkTopDown().filter { it.extension == "kt" }

        assertTrue(fuentes.count() >= 5)
    }
}
