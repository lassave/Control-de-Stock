"use strict";

// Estado del panel. `filtros` vive acá para que el refresco automático no
// los pierda ni mueva el scroll: un tablero que salta mientras se lee es
// inservible.
const estado = {
  sesion: null,
  filtros: {
    texto: "", estado: "", grupo: "", ubicacion: "", solo_errores_carga: false,
  },
  // Separado de `filtros`: cada pestaña tiene sus propios controles, y
  // compartir un solo objeto haría que filtrar el tablero cambie en
  // silencio lo que exporta el reparto.
  reparto: {
    filtros: { texto: "", estado: "", ubicacion: "" },
  },
  recuento: {
    filtroTexto: "",
    // Arranca vacío a propósito: hay que marcar a mano lo que entra al
    // recuento, no al revés. Son ubicaciones, no SKU: cada una entra
    // entera, con todos sus SKU A RECONTAR.
    seleccionadas: new Set(),
    // Ubicación -> id de operario elegido en el selector de esa fila.
    operarioPorUbicacion: {},
    filas: [],
    avancePorPasada: {},
  },
};

const ESTADOS = {
  "SIN CONTAR": "estado-sin-contar",
  "CONSOLIDADO": "estado-consolidado",
  "A RECONTAR": "estado-a-recontar",
};

const ESCAPES = {
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
};

const $ = (selector) => document.querySelector(selector);

// El maestro lo escribe el cliente, no nosotros. Una descripción como
// «CAÑO 3/4 <PVC>» alcanza para que el navegador se coma la fila entera sin
// avisar, así que todo dato del servidor pasa por acá antes de ir al HTML.
function esc(valor) {
  if (valor === null || valor === undefined) return "";
  return String(valor).replace(/[&<>"']/g, (caracter) => ESCAPES[caracter]);
}

async function pedir(url, opciones = {}) {
  const respuesta = await fetch(url, opciones);
  if (!respuesta.ok) {
    const cuerpo = await respuesta.json().catch(() => ({}));
    throw new Error(cuerpo.detail || "No se pudo completar la operación");
  }
  return respuesta.json();
}

function milesimasATexto(valor) {
  if (valor === null || valor === undefined) return "";
  const signo = valor < 0 ? "-" : "";
  const absoluto = Math.abs(valor);
  const entero = Math.floor(absoluto / 1000);
  const resto = absoluto % 1000;
  if (resto === 0) return `${signo}${entero}`;
  return `${signo}${entero},${String(resto).padStart(3, "0").replace(/0+$/, "")}`;
}

// --- Tablero ---------------------------------------------------------------

function dibujarMetricas(resumen) {
  const tarjetas = [
    ["Avance", `${resumen.avance_pct}%`],
    ["Contados", `${resumen.contados} / ${resumen.articulos}`],
    ["Consolidados", resumen.consolidados],
    ["A recontar", resumen.a_recontar],
    ["Posible error de carga", resumen.posibles_errores_carga],
    ["Altas rápidas", resumen.altas_rapidas],
  ];
  $("#metricas").innerHTML = tarjetas
    .map(([rotulo, valor]) =>
      `<div class="metrica"><div class="valor">${esc(valor)}</div>` +
      `<div class="rotulo">${rotulo}</div></div>`)
    .join("");
}

function dibujarFila(fila) {
  const clase = ESTADOS[fila.estado] || "";
  const marca = fila.posible_error_carga
    ? `<span class="marca" title="Revisar antes de recontar: ` +
      `${esc(fila.posible_error_carga)}">⌨ ${esc(fila.posible_error_carga)}</span>`
    : "";
  // Sin nadie asignado es la fila que más importa detectar: es la que corre
  // riesgo de no contarse. Se marca acá, no solo en el reparto, porque el
  // tablero es lo primero que se mira.
  const asignadoA = fila.asignado_a.length
    ? fila.asignado_a.map((n) => esc(n)).join(", ")
    : `<span class="marca" title="Ninguna persona tiene esta ubicación ` +
      `asignada.">⚑ sin asignar</span>`;
  const fueraDeSector = fila.fuera_asignacion
    ? `<span class="marca" title="Alguno de los conteos de este artículo se ` +
      `hizo fuera de la ubicación asignada al operario. El detalle exportado ` +
      `dice quién y dónde.">⚑ Sí</span>`
    : "";
  const fecha = (fila.fecha || "").replace("T", " ").replace("Z", "");

  return `
    <tr>
      <td class="num">${esc(fila.id_orden)}</td>
      <td>${esc(fila.tipo)}</td>
      <td>${esc(fila.material)}</td>
      <td>${esc(fila.sku)}</td>
      <td>${esc(fila.codigos_de_barra)}</td>
      <td>${esc(fila.descripcion)}</td>
      <td>${esc(fila.grupo)}</td>
      <td>${esc(fila.ubicacion)}</td>
      <td>${esc(fila.ubicacion_real)}</td>
      <td>${asignadoA}</td>
      <td>${esc(fila.unidad)}</td>
      <td class="num">${esc(milesimasATexto(fila.stock_sistema))}</td>
      <td class="num">${esc(milesimasATexto(fila.ultimo_conteo))}</td>
      <td class="num">${esc(milesimasATexto(fila.dif))}</td>
      <td>
        <span class="estado ${clase}">${esc(fila.estado)}</span>
        ${marca}
      </td>
      <td>${fueraDeSector}</td>
      <td>${esc(fecha)}</td>
      <td>${esc(fila.observaciones)}</td>
    </tr>`;
}

function dibujarFilas(filas) {
  $("#tabla tbody").innerHTML = filas.map(dibujarFila).join("");
}

function completarOpciones(select, valores, rotuloTodos) {
  const elegido = select.value;
  select.innerHTML = `<option value="">${rotuloTodos}</option>` +
    valores.map((valor) => `<option>${esc(valor)}</option>`).join("");
  select.value = elegido;
}

function parametrosDeFiltros() {
  return new URLSearchParams(estado.filtros).toString();
}

function actualizarEnlacesDeExportacion() {
  if (!estado.sesion) return;
  // Los enlaces arrastran los filtros vigentes: se exporta lo que está en
  // pantalla. Recibir el depósito entero después de acotar el tablero se
  // lee como si fuera el recorte, que es peor que no exportar nada.
  const sesionId = estado.sesion.id;
  const parametros = parametrosDeFiltros();
  $("#exportar-resumen").href =
    `/api/sesiones/${sesionId}/exportar/resumen?${parametros}`;
  $("#exportar-detalle").href =
    `/api/sesiones/${sesionId}/exportar/detalle?${parametros}`;
}

async function refrescarTablero() {
  if (!estado.sesion) return;

  const envoltorio = $("#envoltorio-tabla");
  const scroll = envoltorio.scrollTop;
  const sesionId = estado.sesion.id;

  const datos = await pedir(
    `/api/sesiones/${sesionId}/tablero?${parametrosDeFiltros()}`);

  dibujarMetricas(datos.resumen);
  dibujarFilas(datos.filas);
  actualizarEnlacesDeExportacion();

  completarOpciones($("#filtro-grupo"),
    [...new Set(datos.filas.map((f) => f.grupo).filter(Boolean))].sort(),
    "Todos los grupos");
  completarOpciones($("#filtro-ubicacion"),
    [...new Set(datos.filas.map((f) => f.ubicacion).filter(Boolean))].sort(),
    "Todas las ubicaciones");

  envoltorio.scrollTop = scroll;
}

// El refresco automático no puede tirar abajo el panel. Si el servidor no
// contesta —el equipo se durmió, se cayó el wifi del depósito— se avisa y se
// sigue intentando, en vez de dejar una pantalla congelada que miente.
async function refrescarSinRomper() {
  try {
    await refrescarTablero();
    await refrescarReparto();
    await refrescarRecuentosAbiertos();
    $("#sesion-actual").classList.remove("error");
  } catch (error) {
    $("#sesion-actual").classList.add("error");
    $("#sesion-actual").textContent = `Sin conexión con el servidor (${error.message})`;
  }
}

// --- Avance por ubicación ----------------------------------------------------

/** Una fila del detalle de un operario, dentro de su tarjeta desplegada. */
function dibujarDetalleOperario(item) {
  const clase = ESTADOS[item.estado] || "";
  return `
    <tr>
      <td>${esc(item.ubicacion)}</td>
      <td>${esc(item.sku)}</td>
      <td>${esc(item.descripcion)}</td>
      <td><span class="estado ${clase}">${esc(item.estado)}</span></td>
      <td>${item.contado ? "✓" : ""}</td>
    </tr>`;
}

/**
 * La tarjeta de un operario: resumen numérico siempre visible, detalle de
 * sus artículos solo al desplegar. `<details>` nativo, sin JavaScript propio
 * para abrir y cerrar.
 *
 * `abiertos` es el conjunto de operarios que ya estaban desplegados antes de
 * este redibujado: sin esto, el refresco automático de cada cuatro segundos
 * reconstruye las tarjetas desde cero y las cierra solas, aunque nadie haya
 * tocado la flecha.
 */
function dibujarTarjetaOperario(operario, abiertos) {
  const ubicacionesTexto = operario.ubicaciones.map((u) => esc(u)).join(", ");
  const detalle = operario.detalle.map(dibujarDetalleOperario).join("");
  const abierto = abiertos.has(operario.operario) ? " open" : "";

  return `
    <details class="tarjeta-operario" data-operario="${esc(operario.operario)}"${abierto}>
      <summary>
        <div class="resumen-operario">
          <strong>${esc(operario.operario)}</strong>
          <span class="ubicaciones-resumen">
            Ubicación asignada: ${ubicacionesTexto}
          </span>
        </div>
        <div class="resumen-numerico">
          <div class="dato">
            <span class="valor">${esc(operario.total)}</span>
            <span class="rotulo">Cantidad asignada</span>
          </div>
          <div class="dato">
            <span class="valor dato-verde">${esc(operario.contados)}</span>
            <span class="rotulo">Cantidad contada</span>
          </div>
          <div class="dato">
            <span class="valor dato-ambar">${esc(operario.sin_contar)}</span>
            <span class="rotulo">Cantidad sin contar</span>
          </div>
          <div class="dato">
            <span class="valor">${esc(operario.avance_pct)}%</span>
            <span class="rotulo">% de avance</span>
          </div>
        </div>
        <span class="flecha-desplegar" aria-hidden="true">▾</span>
      </summary>
      <table class="detalle-operario">
        <thead>
          <tr>
            <th>Ubicación</th><th>SKU</th><th>Descripción</th>
            <th>Estado</th><th>Contado</th>
          </tr>
        </thead>
        <tbody>${detalle}</tbody>
      </table>
    </details>`;
}

function parametrosDeFiltrosReparto() {
  return new URLSearchParams(estado.reparto.filtros).toString();
}

function actualizarEnlaceExportacionReparto() {
  if (!estado.sesion) return;
  const parametros = parametrosDeFiltrosReparto();
  $("#exportar-reparto").href =
    `/api/sesiones/${estado.sesion.id}/exportar/reparto?${parametros}`;
}

async function refrescarReparto() {
  if (!estado.sesion) return;
  // Sin sesión no hay reparto que mostrar, y consultarlo con la pestaña
  // escondida sería un pedido de más cada cuatro segundos para nadie.
  if ($("#vista-reparto").classList.contains("oculta")) return;

  const envoltorio = $("#reparto-envoltorio-tabla");
  const scroll = envoltorio.scrollTop;

  const datos = await pedir(
    `/api/sesiones/${estado.sesion.id}/reparto/operarios?${parametrosDeFiltrosReparto()}`);

  // Por nombre, no por posición: el operario es único (la base lo exige) y
  // el orden puede cambiar de un pedido a otro.
  const abiertos = new Set(
    [...document.querySelectorAll("#reparto-operarios details[open]")]
      .map((detalle) => detalle.dataset.operario),
  );

  $("#reparto-operarios").innerHTML = datos.operarios
    .map((o) => dibujarTarjetaOperario(o, abiertos))
    .join("") || "<p>Ningún operario tiene una ubicación asignada todavía.</p>";
  actualizarEnlaceExportacionReparto();

  const ubicaciones = datos.operarios.flatMap((o) => o.detalle.map((d) => d.ubicacion));
  completarOpciones($("#reparto-filtro-ubicacion"),
    [...new Set(ubicaciones.filter(Boolean))].sort(),
    "Todas las ubicaciones");

  envoltorio.scrollTop = scroll;
}

// --- Recuento ----------------------------------------------------------------

/** Las filas A RECONTAR agrupadas por ubicación, cada una con su cuenta. */
function agruparRecuentoPorUbicacion(filas) {
  const porUbicacion = {};
  filas.forEach((fila) => {
    if (!fila.ubicacion) return; // sin ubicación no hay a quién asignársela
    (porUbicacion[fila.ubicacion] = porUbicacion[fila.ubicacion] || []).push(fila);
  });
  return porUbicacion;
}

/** Una fila del detalle de productos de una ubicación, dentro de su desplegable. */
function dibujarProductoDeUbicacionRecuento(fila) {
  return `
    <tr>
      <td>${esc(fila.sku)}</td>
      <td>${esc(fila.descripcion)}</td>
      <td class="num">${esc(milesimasATexto(fila.stock_sistema))}</td>
      <td class="num">${esc(milesimasATexto(fila.ultimo_conteo))}</td>
      <td class="num">${esc(milesimasATexto(fila.dif))}</td>
    </tr>`;
}

/**
 * Una ubicación a recontar: casilla y operario siempre visibles en el
 * resumen, el detalle de sus productos recién al desplegar. `abiertas` es
 * el conjunto de ubicaciones que ya estaban desplegadas antes de este
 * redibujado, para que abrir un recuento no las cierre solas.
 */
function dibujarFilaUbicacionRecuento(ubicacion, filas, abiertas) {
  const marcada = estado.recuento.seleccionadas.has(ubicacion) ? " checked" : "";
  const operarioElegido = estado.recuento.operarioPorUbicacion[ubicacion] || "";
  const opciones = (estado.operarios || [])
    .map((o) => {
      const seleccionado = String(o.id) === String(operarioElegido) ? " selected" : "";
      return `<option value="${esc(o.id)}"${seleccionado}>${esc(o.nombre)}</option>`;
    })
    .join("");
  const abierta = abiertas.has(ubicacion) ? " open" : "";
  const productos = filas.map(dibujarProductoDeUbicacionRecuento).join("");

  return `
    <details class="fila-ubicacion-recuento" data-ubicacion="${esc(ubicacion)}"${abierta}>
      <summary>
        <label class="casilla">
          <input type="checkbox" data-recuento-ubicacion="${esc(ubicacion)}"${marcada}>
          ${esc(ubicacion)} — ${esc(filas.length)} SKU
        </label>
        <select data-recuento-operario="${esc(ubicacion)}">
          <option value="">Sin asignar todavía</option>
          ${opciones}
        </select>
        <span class="flecha-desplegar" aria-hidden="true">▾</span>
      </summary>
      <table class="detalle-operario">
        <thead>
          <tr>
            <th>SKU</th><th>Descripción</th>
            <th class="num">Sistema</th><th class="num">Último conteo</th>
            <th class="num">Dif.</th>
          </tr>
        </thead>
        <tbody>${productos}</tbody>
      </table>
    </details>`;
}

/**
 * La tolerancia y el listado de ubicaciones A RECONTAR. No entra al
 * refresco automático de cada 4 segundos: perdería lo que se está tipeando
 * en el formulario o recién marcando en la lista. Se refresca a propósito:
 * al entrar a la pestaña, al guardar la tolerancia y al abrir un recuento.
 */
async function refrescarRecuentoChecklist() {
  if (!estado.sesion) return;
  if ($("#vista-recuento").classList.contains("oculta")) return;

  $("#tolerancia-pct").value = estado.sesion.tolerancia_pct;
  $("#tolerancia-min-abs").value = estado.sesion.tolerancia_min_abs / 1000;

  const parametros = new URLSearchParams({
    estado: "A RECONTAR", texto: estado.recuento.filtroTexto,
  }).toString();
  const datos = await pedir(`/api/sesiones/${estado.sesion.id}/tablero?${parametros}`);
  estado.recuento.filas = datos.filas;

  const porUbicacion = agruparRecuentoPorUbicacion(datos.filas);
  const ubicaciones = Object.keys(porUbicacion).sort();

  // Por data-ubicacion, no por posición: reordenar alfabéticamente en cada
  // refresco no puede cerrar una fila que el responsable dejó abierta.
  const abiertas = new Set(
    [...document.querySelectorAll("#recuento-ubicaciones details[open]")]
      .map((detalle) => detalle.dataset.ubicacion),
  );

  $("#recuento-ubicaciones").innerHTML = ubicaciones
    .map((ubicacion) => dibujarFilaUbicacionRecuento(ubicacion, porUbicacion[ubicacion], abiertas))
    .join("") || "<p>No hay ninguna ubicación con SKU fuera de tolerancia.</p>";
}

/**
 * Abre el recuento con las ubicaciones marcadas: entran todos sus SKU A
 * RECONTAR, y de una vez se asigna a quien haya elegido cada fila.
 *
 * Agrupada por operario antes de asignar: `PUT .../asignacion` reemplaza el
 * reparto entero de esa persona en la pasada, así que si el mismo operario
 * quedó elegido en dos ubicaciones, hace falta un solo pedido con las dos
 * juntas — dos pedidos separados harían que el segundo borre al primero.
 */
async function abrirRecuento() {
  if (!estado.sesion) return;
  const ubicaciones = [...estado.recuento.seleccionadas];
  if (!ubicaciones.length) {
    alert("Marcá al menos una ubicación para recontar.");
    return;
  }

  const articulo_ids = estado.recuento.filas
    .filter((fila) => ubicaciones.includes(fila.ubicacion))
    .map((fila) => fila.id);

  try {
    const recuento = await pedir(`/api/sesiones/${estado.sesion.id}/pasadas`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ articulo_ids }),
    });

    const porOperario = {};
    ubicaciones.forEach((ubicacion) => {
      const operarioId = estado.recuento.operarioPorUbicacion[ubicacion];
      if (!operarioId) return;
      (porOperario[operarioId] = porOperario[operarioId] || []).push(ubicacion);
    });

    const fallos = [];
    for (const [operarioId, ubicacionesDeEse] of Object.entries(porOperario)) {
      try {
        await pedir(
          `/api/sesiones/${estado.sesion.id}/operarios/${operarioId}/asignacion`,
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ubicaciones: ubicacionesDeEse, pasada_id: recuento.id }),
          },
        );
      } catch (error) {
        fallos.push(error.message);
      }
    }

    estado.recuento.seleccionadas = new Set();
    estado.recuento.operarioPorUbicacion = {};
    await refrescarRecuentoChecklist();
    await refrescarRecuentosAbiertos();

    if (fallos.length) alert(fallos.join("\n"));
  } catch (error) {
    alert(error.message);
  }
}

function dibujarFilaAvanceRecuento(item) {
  return `
    <tr>
      <td>${esc(item.operario)}</td>
      <td>${item.ubicaciones.map((u) => esc(u)).join(", ")}</td>
      <td class="num">${esc(item.total)}</td>
      <td class="num">${esc(item.contados)}</td>
      <td class="num">${esc(item.sin_contar)}</td>
      <td class="num">${esc(item.avance_pct)}%</td>
    </tr>`;
}

/** Un botón "Sectores" por operario activo, para asignarlo a este recuento. */
function dibujarOperarioDeRecuento(operario, pasadaId) {
  return `
    <span class="operario-recuento">
      ${esc(operario.nombre)}
      <button class="secundario" type="button"
              data-recuento-sectores="${esc(operario.id)}"
              data-recuento-pasada="${esc(pasadaId)}">
        Sectores
      </button>
    </span>`;
}

function dibujarTarjetaRecuento(pasada, avance) {
  const operarios = (estado.operarios || [])
    .map((o) => dibujarOperarioDeRecuento(o, pasada.id)).join("");
  const filasAvance = avance.map(dibujarFilaAvanceRecuento).join("");

  return `
    <div class="tarjeta-recuento">
      <div class="encabezado-tarjeta-recuento">
        <h4>${esc(pasada.etiqueta)} — ${esc(pasada.cantidad_sku)} SKU</h4>
        <button class="secundario" type="button" data-recuento-borrar="${esc(pasada.id)}">
          Borrar
        </button>
      </div>
      <div class="operarios-del-recuento">${operarios}</div>
      <table class="detalle-operario">
        <thead>
          <tr>
            <th>Operario</th><th>Ubicaciones</th>
            <th class="num">Asignado</th><th class="num">Contado</th>
            <th class="num">Sin contar</th><th class="num">% avance</th>
          </tr>
        </thead>
        <tbody>${filasAvance || '<tr><td colspan="6">Todavía nadie tiene esto asignado.</td></tr>'}</tbody>
      </table>
    </div>`;
}

/**
 * Las tarjetas de los recuentos abiertos, con su avance. Sí entra al
 * refresco automático: son datos de solo lectura y un botón, sin nada que
 * el redibujado pueda perder.
 */
async function refrescarRecuentosAbiertos() {
  if (!estado.sesion) return;
  if ($("#vista-recuento").classList.contains("oculta")) return;

  const pasadas = await pedir(`/api/sesiones/${estado.sesion.id}/pasadas`);
  const recuentos = pasadas.filter((p) => p.es_parcial && p.estado === "abierta");

  estado.recuento.avancePorPasada = {};
  const tarjetas = [];
  for (const pasada of recuentos) {
    const avance = await pedir(
      `/api/sesiones/${estado.sesion.id}/pasadas/${pasada.id}/avance`);
    estado.recuento.avancePorPasada[pasada.id] = avance;
    tarjetas.push(dibujarTarjetaRecuento(pasada, avance));
  }

  $("#recuentos-abiertos").innerHTML = tarjetas.join("")
    || "<p>Ningún recuento abierto todavía.</p>";
}

/**
 * Borra un recuento abierto por error. El servidor es quien manda: rechaza
 * con 409 en cuanto tiene un conteo cargado, y ese mensaje es el que se le
 * muestra al responsable — no hay que adivinarlo acá con lo que ya bajó.
 */
async function borrarRecuento(pasadaId) {
  if (!estado.sesion) return;
  if (!confirm("¿Borrar este recuento? No se puede deshacer.")) return;

  try {
    await pedir(`/api/sesiones/${estado.sesion.id}/pasadas/${pasadaId}`, {
      method: "DELETE",
    });
    await refrescarRecuentosAbiertos();
  } catch (error) {
    alert(error.message);
  }
}

// --- Sesiones --------------------------------------------------------------

function dibujarSesion(sesion) {
  const boton = sesion.estado === "abierta"
    ? `<button class="secundario" data-cerrar="${esc(sesion.id)}">Cerrar</button>`
    : "";
  return `<li><strong>${esc(sesion.nombre)}</strong> — ${esc(sesion.estado)} ${boton}</li>`;
}

async function cargarSesiones() {
  const sesiones = await pedir("/api/sesiones");
  const abierta = sesiones.find((s) => s.estado === "abierta") || null;
  // El listado no trae la pasada: hace falta el detalle para saber cuál es
  // la general, la que usa el diálogo "Sectores" de Operarios.
  estado.sesion = abierta ? await pedir(`/api/sesiones/${abierta.id}`) : null;

  $("#sesion-actual").classList.remove("error");
  $("#sesion-actual").textContent = estado.sesion
    ? `Sesión: ${estado.sesion.nombre}`
    : "Sin sesión abierta";

  $("#lista-sesiones").innerHTML = sesiones.map(dibujarSesion).join("")
    || "<li>Todavía no hay sesiones.</li>";

  if (estado.sesion) {
    actualizarEnlacesDeExportacion();
    await refrescarTablero();
    actualizarEnlaceExportacionReparto();
    await refrescarReparto();
  } else {
    $("#tabla tbody").innerHTML = "";
    $("#metricas").innerHTML = "";
    $("#reparto-operarios").innerHTML = "";
  }
}

// --- Importación del maestro -----------------------------------------------

const CAMPOS = [
  ["id_orden", "Número de orden"], ["tipo", "Tipo"], ["material", "Material"],
  ["sku", "SKU (obligatorio)"], ["descripcion", "Descripción (obligatorio)"],
  ["grupo", "Grupo"], ["ubicacion", "Ubicación"], ["unidad", "Unidad"],
  ["stock_sistema", "Stock del sistema"], ["costo_unitario", "Costo unitario"],
  ["codigo_barras", "Código de barras"],
];

let archivoElegido = null;

function dibujarMapeo(encabezados) {
  return CAMPOS.map(([campo, rotulo]) => {
    const opciones = encabezados.map((encabezado) => {
      const coincide = encabezado.toLowerCase() === campo ? " selected" : "";
      return `<option${coincide}>${esc(encabezado)}</option>`;
    }).join("");

    return `
      <tr>
        <td><label for="mapeo-${campo}">${rotulo}</label></td>
        <td>
          <select id="mapeo-${campo}" data-campo="${campo}">
            <option value="">— sin asignar —</option>
            ${opciones}
          </select>
        </td>
      </tr>`;
  }).join("");
}

function dibujarCelda(celda) {
  return `<td>${esc(celda)}</td>`;
}

function dibujarFilaDeVistaPrevia(celdas) {
  return `<tr>${celdas.map(dibujarCelda).join("")}</tr>`;
}

function dibujarVistaPrevia(encabezados, filas) {
  const cabecera = encabezados.map((e) => `<th>${esc(e)}</th>`).join("");
  const cuerpo = filas.map(dibujarFilaDeVistaPrevia).join("");
  return `<thead><tr>${cabecera}</tr></thead><tbody>${cuerpo}</tbody>`;
}

async function previsualizarArchivo(archivo) {
  archivoElegido = archivo;
  const cuerpo = new FormData();
  cuerpo.append("archivo", archivo);

  try {
    const vista = await pedir("/api/maestro/previsualizar",
      { method: "POST", body: cuerpo });

    $("#tabla-mapeo").querySelector("tbody").innerHTML =
      dibujarMapeo(vista.encabezados);
    $("#tabla-vista-previa").innerHTML =
      dibujarVistaPrevia(vista.encabezados, vista.filas);
    $("#mapeo").classList.remove("oculta");
    $("#resultado-importacion").innerHTML = "";
  } catch (error) {
    $("#mapeo").classList.add("oculta");
    $("#resultado-importacion").innerHTML =
      `<p class="error">${esc(error.message)}</p>`;
  }
}

function dibujarResultadoImportacion(resultado) {
  const descartadas = resultado.descartadas.length
    ? `<p>Se descartaron ${esc(resultado.descartadas.length)} filas sin SKU.</p>`
    : "";
  const advertencias = resultado.advertencias.length
    ? `<p class="aviso">${esc(resultado.advertencias.length)} filas con datos ` +
      `corregidos: ${esc(resultado.advertencias[0].motivo)}…</p>`
    : "";

  return `<p>Se importaron <strong>${esc(resultado.importados)}</strong> ` +
    `artículos y ${esc(resultado.codigos)} códigos de barras.</p>` +
    descartadas + advertencias;
}

async function confirmarImportacion() {
  if (!estado.sesion) {
    $("#resultado-importacion").innerHTML =
      '<p class="error">Primero creá una sesión.</p>';
    return;
  }

  const mapeo = {};
  document.querySelectorAll("[data-campo]").forEach((select) => {
    if (select.value) mapeo[select.dataset.campo] = select.value;
  });

  const cuerpo = new FormData();
  cuerpo.append("archivo", archivoElegido);
  cuerpo.append("mapeo", JSON.stringify(mapeo));
  cuerpo.append("unidad_por_defecto", $("#unidad-defecto").value);

  const sesionId = estado.sesion.id;
  try {
    const resultado = await pedir(
      `/api/sesiones/${sesionId}/maestro`,
      { method: "POST", body: cuerpo });

    $("#resultado-importacion").innerHTML = dibujarResultadoImportacion(resultado);
    await refrescarTablero();
  } catch (error) {
    $("#resultado-importacion").innerHTML =
      `<p class="error">${esc(error.message)}</p>`;
  }
}

// --- Operarios -------------------------------------------------------------

function dibujarOperario(operario, haySesion) {
  // Sin sesión abierta no hay pasada a la cual asignar nada: el enlace no
  // aparece.
  const sectores = haySesion
    ? `<button class="secundario" data-sectores="${esc(operario.id)}">Sectores</button>`
    : "";
  // Sin ubicaciones asignadas no se muestra el renglón: un «Sectores: »
  // vacío no le dice nada a quien mira la tarjeta.
  const sectoresAsignados = operario.ubicaciones_asignadas.length
    ? `<p class="sectores-asignados">Sectores: ` +
      `${operario.ubicaciones_asignadas.map((u) => esc(u)).join(", ")}</p>`
    : "";
  // El token es lo único con lo que se vincula un celular. Va en un campo
  // de solo lectura para poder seleccionarlo y copiarlo: son 43 caracteres
  // al azar y copiarlos a ojo es garantía de error. El QR lo evita del
  // todo, y además le pasa al celular la dirección del servidor.
  return `
    <li class="operario">
      <div>
        <strong>${esc(operario.nombre)}</strong>
        <div class="token">
          <input readonly value="${esc(operario.token_dispositivo)}"
                 aria-label="Token de ${esc(operario.nombre)}">
          <button class="secundario" data-copiar="${esc(operario.token_dispositivo)}">
            Copiar
          </button>
        </div>
        ${sectores ? `<div class="fila-sectores">${sectores}</div>` : ""}
        <p class="ayuda">Escaneá este código desde la app para vincular el celular.</p>
        ${sectoresAsignados}
      </div>
      <img class="qr" src="/api/operarios/${esc(operario.id)}/qr"
           alt="Código QR de vinculación de ${esc(operario.nombre)}">
    </li>`;
}

/** Una casilla de ubicación para el diálogo de sectores, tildada si ya está asignada. */
function dibujarCasillaUbicacion(ubicacion, asignadas) {
  const marcada = asignadas.includes(ubicacion) ? " checked" : "";
  return `<label class="casilla">
    <input type="checkbox" value="${esc(ubicacion)}"${marcada}> ${esc(ubicacion)}
  </label>`;
}

/**
 * Abre el diálogo de sectores para un operario.
 *
 * Sin `pasadaId`, reparte para la pasada general —el uso de siempre, desde
 * Operarios—. La pestaña Recuento pasa el id del recuento puntual, y las
 * casillas ya asignadas de esa pasada en particular (no las de la pasada
 * activa del operario, que puede ser otra).
 */
async function abrirSectores(operarioId, pasadaId = null, asignadasEnEsaPasada = null) {
  const operario = estado.operarios.find((o) => String(o.id) === String(operarioId));
  const idPasada = pasadaId || (estado.sesion && estado.sesion.pasada && estado.sesion.pasada.id);
  // Sin pasada general abierta (solo quedan recuentos en curso) y sin una
  // pasada puntual indicada, no hay nada que repartir desde acá.
  if (!operario || !estado.sesion || !idPasada) return;

  const asignadas = asignadasEnEsaPasada !== null
    ? asignadasEnEsaPasada
    : operario.ubicaciones_asignadas;

  try {
    const ubicaciones = await pedir(`/api/sesiones/${estado.sesion.id}/ubicaciones`);

    // Por textContent: es el nombre de una persona, dato como cualquier otro.
    $("#sectores-titulo").textContent = `Sectores de ${operario.nombre}`;
    $("#sectores-lista").innerHTML = ubicaciones.length
      ? ubicaciones.map((u) => dibujarCasillaUbicacion(u, asignadas)).join("")
      : "<p>El maestro todavía no tiene ubicaciones cargadas.</p>";

    $("#dialogo-sectores").dataset.operario = operarioId;
    $("#dialogo-sectores").dataset.pasada = idPasada;
    $("#dialogo-sectores").showModal();
  } catch (error) {
    alert(error.message);
  }
}

async function guardarSectores() {
  const dialogo = $("#dialogo-sectores");
  const operarioId = dialogo.dataset.operario;
  const pasadaId = Number(dialogo.dataset.pasada);
  const ubicaciones = [...dialogo.querySelectorAll("input[type=checkbox]:checked")]
    .map((casilla) => casilla.value);

  try {
    await pedir(
      `/api/sesiones/${estado.sesion.id}/operarios/${operarioId}/asignacion`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ubicaciones, pasada_id: pasadaId }),
      },
    );
    dialogo.close();
    await cargarOperarios();
    // Si el diálogo se abrió desde un recuento, su avance cambió: quién
    // tiene qué asignado ahí ya no es lo que se veía antes de guardar.
    await refrescarRecuentosAbiertos();
  } catch (error) {
    alert(error.message);
  }
}

async function cargarInstalacion() {
  const estado = await pedir("/api/instalacion");
  $("#instalacion").classList.toggle("oculta", !estado.disponible);
  // El `src` va acá y no en el HTML. Un `src` fijo se descarga aunque el
  // bloque esté escondido, y el navegador no reintenta: si el APK se copia
  // con el panel abierto, el bloque se desesconde con el QR roto y hay que
  // apretar F5. Poniéndolo recién cuando hay APK, aparece siempre entero.
  if (estado.disponible) {
    $("#qr-instalacion").src = "/api/instalacion/qr";
    // Por textContent: la versión sale de un archivo del disco, y un
    // archivo es dato como cualquier otro.
    $("#version-apk").textContent = descripcionDeLaVersion(estado);
  }
}

/** Qué versión está ofreciendo el panel, en una línea legible. */
function descripcionDeLaVersion(estado) {
  // Mismo formato de fecha que el tablero: sin la T ni la Z, que no le dicen
  // nada a quien lo lee.
  const cuando = (estado.publicado || "").replace("T", " ").replace("Z", "");

  // Si version no viene o viene vacía, tratar como desconocida. Normalizar
  // también para evitar "Versión undefined" o "Versión null" en pantalla.
  const version = (estado.version || "").trim();

  if (!version) {
    if (cuando) return `Versión desconocida · publicada el ${cuando}`;
    return "No sabemos qué versión es";
  }

  if (cuando) return `Versión ${version} · publicada el ${cuando}`;
  return `Versión ${version}`;
}

async function cargarOperarios() {
  const lista = await pedir("/api/operarios");
  // Se guarda para poder buscar por id al abrir el diálogo de sectores:
  // el click solo trae el id, no todo el operario.
  estado.operarios = lista;
  $("#lista-operarios").innerHTML =
    lista.map((o) => dibujarOperario(o, !!(estado.sesion && estado.sesion.pasada))).join("")
    || "<li>Todavía no hay operarios.</li>";
  await cargarInstalacion();
}

async function copiarToken(boton) {
  const token = boton.dataset.copiar;
  try {
    // El portapapeles del navegador solo existe en contextos seguros, y el
    // panel también se abre por IP (http://192.168.x.x). El campo de al lado
    // queda siempre como salida: se selecciona y se copia a mano.
    await navigator.clipboard.writeText(token);
    boton.textContent = "Copiado";
  } catch (error) {
    boton.previousElementSibling.select();
    boton.textContent = "Copiá con Ctrl+C";
  }
  setTimeout(() => { boton.textContent = "Copiar"; }, 2500);
}

// --- Arranque --------------------------------------------------------------

function conectarEventos() {
  document.querySelectorAll(".pestanas button").forEach((boton) => {
    boton.addEventListener("click", () => {
      document.querySelectorAll(".pestanas button")
        .forEach((otro) => otro.classList.remove("activa"));
      boton.classList.add("activa");
      document.querySelectorAll(".vista")
        .forEach((vista) => vista.classList.add("oculta"));
      $(`#vista-${boton.dataset.vista}`).classList.remove("oculta");
      // Sin esto, la pestaña recién abierta queda vacía hasta el próximo
      // tick del refresco automático, hasta 4 segundos después.
      if (boton.dataset.vista === "reparto") refrescarReparto();
      if (boton.dataset.vista === "recuento") {
        refrescarRecuentoChecklist();
        refrescarRecuentosAbiertos();
      }
    });
  });

  $("#filtro-texto").addEventListener("input", (evento) => {
    estado.filtros.texto = evento.target.value;
    refrescarSinRomper();
  });

  ["estado", "grupo", "ubicacion"].forEach((campo) => {
    $(`#filtro-${campo}`).addEventListener("change", (evento) => {
      estado.filtros[campo] = evento.target.value;
      refrescarSinRomper();
    });
  });

  $("#filtro-errores-carga").addEventListener("change", (evento) => {
    estado.filtros.solo_errores_carga = evento.target.checked;
    refrescarSinRomper();
  });

  $("#limpiar-filtros").addEventListener("click", () => {
    estado.filtros = {
      texto: "", estado: "", grupo: "", ubicacion: "", solo_errores_carga: false,
    };
    $("#filtro-texto").value = "";
    $("#filtro-errores-carga").checked = false;
    ["estado", "grupo", "ubicacion"].forEach((campo) => {
      $(`#filtro-${campo}`).value = "";
    });
    refrescarSinRomper();
  });

  $("#reparto-filtro-texto").addEventListener("input", (evento) => {
    estado.reparto.filtros.texto = evento.target.value;
    refrescarReparto();
  });

  ["estado", "ubicacion"].forEach((campo) => {
    $(`#reparto-filtro-${campo}`).addEventListener("change", (evento) => {
      estado.reparto.filtros[campo] = evento.target.value;
      refrescarReparto();
    });
  });

  $("#reparto-limpiar-filtros").addEventListener("click", () => {
    estado.reparto.filtros = { texto: "", estado: "", ubicacion: "" };
    $("#reparto-filtro-texto").value = "";
    ["estado", "ubicacion"].forEach((campo) => {
      $(`#reparto-filtro-${campo}`).value = "";
    });
    refrescarReparto();
  });

  $("#form-tolerancia").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    if (!estado.sesion) return;
    const pct = Number($("#tolerancia-pct").value);
    const minAbs = Math.round(Number($("#tolerancia-min-abs").value) * 1000);
    try {
      const sesion = await pedir(`/api/sesiones/${estado.sesion.id}/tolerancia`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pct, min_abs: minAbs }),
      });
      estado.sesion.tolerancia_pct = sesion.tolerancia_pct;
      estado.sesion.tolerancia_min_abs = sesion.tolerancia_min_abs;
      await refrescarRecuentoChecklist();
      await refrescarTablero();
    } catch (error) {
      alert(error.message);
    }
  });

  $("#recuento-filtro-texto").addEventListener("input", (evento) => {
    estado.recuento.filtroTexto = evento.target.value;
    refrescarRecuentoChecklist();
  });

  $("#recuento-ubicaciones").addEventListener("change", (evento) => {
    const ubicacionCasilla = evento.target.dataset.recuentoUbicacion;
    if (ubicacionCasilla) {
      if (evento.target.checked) estado.recuento.seleccionadas.add(ubicacionCasilla);
      else estado.recuento.seleccionadas.delete(ubicacionCasilla);
      return;
    }
    const ubicacionSelector = evento.target.dataset.recuentoOperario;
    if (ubicacionSelector) {
      if (evento.target.value) {
        estado.recuento.operarioPorUbicacion[ubicacionSelector] = evento.target.value;
      } else {
        delete estado.recuento.operarioPorUbicacion[ubicacionSelector];
      }
    }
  });

  $("#recuento-seleccionar-todos").addEventListener("click", () => {
    Object.keys(agruparRecuentoPorUbicacion(estado.recuento.filas))
      .forEach((ubicacion) => estado.recuento.seleccionadas.add(ubicacion));
    refrescarRecuentoChecklist();
  });

  $("#recuento-deseleccionar-todos").addEventListener("click", () => {
    estado.recuento.seleccionadas.clear();
    refrescarRecuentoChecklist();
  });

  $("#abrir-recuento").addEventListener("click", abrirRecuento);

  $("#recuentos-abiertos").addEventListener("click", (evento) => {
    const pasadaABorrar = evento.target.dataset.recuentoBorrar;
    if (pasadaABorrar) {
      borrarRecuento(Number(pasadaABorrar));
      return;
    }

    const operarioId = evento.target.dataset.recuentoSectores;
    if (!operarioId) return;
    const pasadaId = Number(evento.target.dataset.recuentoPasada);
    const operario = estado.operarios.find((o) => String(o.id) === String(operarioId));
    const avance = (estado.recuento.avancePorPasada[pasadaId] || [])
      .find((item) => operario && item.operario === operario.nombre);
    abrirSectores(operarioId, pasadaId, avance ? avance.ubicaciones : []);
  });

  $("#archivo").addEventListener("change", (evento) => {
    if (evento.target.files.length) previsualizarArchivo(evento.target.files[0]);
  });

  $("#confirmar-importacion").addEventListener("click", confirmarImportacion);

  $("#lista-operarios").addEventListener("click", (evento) => {
    if (evento.target.dataset.copiar) copiarToken(evento.target);
    if (evento.target.dataset.sectores) abrirSectores(evento.target.dataset.sectores);
  });

  $("#guardar-sectores").addEventListener("click", guardarSectores);
  $("#cerrar-sectores").addEventListener("click", () => $("#dialogo-sectores").close());

  $("#form-operario").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    try {
      await pedir("/api/operarios", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nombre: $("#nombre-operario").value }),
      });
      $("#nombre-operario").value = "";
      await cargarOperarios();
    } catch (error) {
      alert(error.message);
    }
  });

  $("#form-sesion").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    try {
      await pedir("/api/sesiones", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nombre: $("#nombre-sesion").value }),
      });
      $("#nombre-sesion").value = "";
      await cargarSesiones();
    } catch (error) {
      alert(error.message);
    }
  });

  $("#lista-sesiones").addEventListener("click", async (evento) => {
    const id = evento.target.dataset.cerrar;
    if (!id) return;
    if (!confirm("¿Cerrar la sesión? No se van a poder cargar más conteos.")) return;
    try {
      await pedir(`/api/sesiones/${id}/cerrar`, { method: "POST" });
      await cargarSesiones();
    } catch (error) {
      alert(error.message);
    }
  });
}

async function iniciar() {
  conectarEventos();
  try {
    await cargarSesiones();
    await cargarOperarios();
  } catch (error) {
    $("#sesion-actual").classList.add("error");
    $("#sesion-actual").textContent = `No se pudo conectar: ${error.message}`;
  }
  setInterval(refrescarSinRomper, 4000);
}

iniciar();
