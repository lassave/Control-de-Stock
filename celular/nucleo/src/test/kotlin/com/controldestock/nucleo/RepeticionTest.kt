package com.controldestock.nucleo

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class RepeticionTest {

    private fun conteo(
        cantidad: Int,
        ubicacionReal: String? = null,
        estado: EstadoSync = EstadoSync.PENDIENTE,
        cuando: String = "2026-08-12T13:32:00Z",
        anula: String? = null,
    ) = ConteoLocal(
        EventoConteo(
            uuid = "uuid-$cantidad-$cuando",
            codigo = "7790001",
            cantidad = cantidad,
            timestampDispositivo = cuando,
            ubicacionReal = ubicacionReal,
            anulaUuid = anula,
        ),
        estado,
    )

    @Test
    fun `avisa cuando ya se conto ese articulo en esa ubicacion`() {
        val repetido = Repeticion.buscar(listOf(conteo(24000)), "P-1", null)

        assertEquals(Repeticion.YaContado(24000, "2026-08-12T13:32:00Z"), repetido)
    }

    @Test
    fun `no avisa cuando el conteo anterior fue en otra ubicacion`() {
        // El mismo producto sí puede estar en dos estantes: ahí los conteos
        // suman y preguntar sería estorbar.
        val repetido = Repeticion.buscar(listOf(conteo(24000, ubicacionReal = "P-9")), "P-1", null)

        assertNull(repetido)
    }

    @Test
    fun `no avisa cuando el operario corrige la ubicacion del nuevo conteo`() {
        val repetido = Repeticion.buscar(listOf(conteo(24000)), "P-1", "P-9")

        assertNull(repetido)
    }

    @Test
    fun `sin ubicacion tambien se repite consigo misma`() {
        // Un artículo sin ubicación en el maestro se cuenta igual, y contarlo
        // dos veces es el mismo error.
        val repetido = Repeticion.buscar(listOf(conteo(24000)), null, null)

        assertEquals(24000, repetido?.milesimas)
    }

    @Test
    fun `un conteo rechazado no cuenta como ya contado`() {
        // El servidor no lo aceptó: nunca entró al inventario, así que
        // frenar al operario por él sería frenarlo por algo que no existe.
        val repetido = Repeticion.buscar(
            listOf(conteo(24000, estado = EstadoSync.RECHAZADO)), "P-1", null,
        )

        assertNull(repetido)
    }

    @Test
    fun `una anulacion no cuenta como ya contado`() {
        // Una anulación no es un conteo: es su baja.
        val repetido = Repeticion.buscar(
            listOf(conteo(0, anula = "uuid-original")), "P-1", null,
        )

        assertNull(repetido)
    }

    @Test
    fun `avisa con el ultimo conteo, que es el que el operario recuerda`() {
        val repetido = Repeticion.buscar(
            listOf(
                conteo(10000, cuando = "2026-08-12T13:00:00Z"),
                conteo(24000, cuando = "2026-08-12T13:32:00Z"),
            ),
            "P-1", null,
        )

        assertEquals(24000, repetido?.milesimas)
    }

    @Test
    fun `sin conteos previos no avisa nada`() {
        assertNull(Repeticion.buscar(emptyList(), "P-1", null))
    }
}
