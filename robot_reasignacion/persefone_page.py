"""
Interacciones con el DOM real de Persefone
(https://persefone.gibobs.gibobs.one/dashboard).

Este es el único archivo que depende de la estructura concreta de la
interfaz de Persefone: si algo cambia en el DOM, se toca aquí.
robot_reasignacion.py no debe conocer selectores.

⚠️ ESTADO: TODO CONFIRMADO contra el sistema real (login, búsqueda,
apertura de resultado, apertura del modal, desplegable con búsqueda por
texto, "Confirmar", "Cancelar", banner de operación cerrada y lectura del
analista actual en la ficha). No quedan TODO pendientes de selectores.

El botón "Reasignar" se localiza con `.first` sobre todo el texto
"Reasignar" de la página. Confirmado como definitivo: el bloque "Analista"
siempre va antes que el de "Cualificador" en la ficha, así que `.first`
siempre corresponde a Analista.
"""
import re
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

# Confirmado por codegen: get_by_role("dialog", name="Reasignar operación").
DIALOG_NAME = "Reasignar operación"

# Nombre a usar para BUSCAR/SELECCIONAR en el desplegable del modal.
# Confirmado por codegen: al escribir "Ana" en el combobox aparece "Ana
# Gonçalves" (sin "Gisela"); al escribir "Miguel" aparece "Miguel Cerezal
# Jiménez". Esto es SOLO la etiqueta corta que usa ese desplegable en
# concreto — no es necesariamente lo mismo que muestra la ficha después.
NOMBRE_MOSTRADO_PERSEFONE = {
    "Miguel Cerezal": "Miguel Cerezal Jiménez",
    "Ana Gisela Gonçalves": "Ana Gonçalves",
}

# Nombre completo real tal como lo muestra la propia ficha (bloque
# "Analista") una vez aplicada la reasignación — usado para el caso "ya
# asignada" y para verificar tras confirmar. NO es siempre igual al de
# arriba: confirmado en producción que, aunque el desplegable muestra "Ana
# Gonçalves", la ficha muestra el nombre completo "Ana Gisela Gonçalves"
# (igual que el CSV). Bug real visto en producción: comparar contra el
# nombre corto del desplegable hacía que TODAS las reasignaciones a Ana
# salieran como error aunque se hubieran aplicado bien.
NOMBRE_FICHA_PERSEFONE = {
    "Miguel Cerezal": "Miguel Cerezal Jiménez",
    "Ana Gisela Gonçalves": "Ana Gisela Gonçalves",
}


def nombre_mostrado(analista_csv):
    """Traduce el nombre del CSV al texto que hay que buscar/seleccionar
    en el desplegable del modal."""
    return NOMBRE_MOSTRADO_PERSEFONE.get(analista_csv, analista_csv)


def nombre_ficha(analista_csv):
    """Traduce el nombre del CSV al texto que debería mostrar la propia
    ficha una vez aplicada la reasignación (para comparar, no para
    buscar en el desplegable)."""
    return NOMBRE_FICHA_PERSEFONE.get(analista_csv, analista_csv)


class SesionCaducadaError(Exception):
    """Persefone ha devuelto la pantalla de login: la sesión guardada en
    storage_state.json ha caducado. Debe cortar el lote entero al instante,
    no solo la operación en curso."""


def click_texto_visible(page, texto, exact=True, timeout=5000):
    """Hace clic en la única coincidencia de texto que esté realmente
    visible. Útil para desplegables tipo Ant Design que dejan momentáneamente
    un nodo duplicado (oculto) con el mismo texto mientras se abren/cierran:
    en vez de adivinar un índice fijo (nth), se espera activamente a que
    aparezca una opción visible y se hace clic en esa.

    Reutilizado tal cual de hadmin_page.py (helper genérico, no depende del
    DOM de un sistema en concreto). Recibe `page` (no un locator acotado)
    porque el desplegable del modal (confirmado por codegen) monta sus
    opciones fuera del propio diálogo."""
    locator = page.get_by_text(texto, exact=exact)
    limite = time.time() + timeout / 1000
    while time.time() < limite:
        for i in range(locator.count()):
            candidato = locator.nth(i)
            if candidato.is_visible():
                candidato.click()
                return
        page.wait_for_timeout(100)
    raise PlaywrightTimeoutError(f"No se encontró un elemento visible con texto '{texto}'")


def pagina_es_login(page):
    """Detecta si Persefone ha devuelto la pantalla de login en vez del
    panel (sesión caducada).

    Confirmado por codegen: sin sesión válida, Persefone redirige a
    `/login?redirect=%2Fdashboard`. Se comprueba la URL (rápido y fiable) y,
    por si acaso la URL no cambiara en algún caso, también el campo
    "Contraseña" del formulario de login como respaldo."""
    try:
        page.wait_for_load_state("domcontentloaded", timeout=5000)
    except PlaywrightTimeoutError:
        pass
    if "/login" in page.url:
        return True
    try:
        return page.get_by_role("textbox", name="Contraseña").is_visible(timeout=2000)
    except PlaywrightTimeoutError:
        return False


def buscar_operacion(page, hp):
    """Escribe el HP en el buscador general de Persefone.

    Confirmado por codegen: textbox "Búsqueda general". La búsqueda filtra
    en vivo (el codegen no pulsó Enter), así que no se envía."""
    caja = page.get_by_role("textbox", name="Búsqueda general")
    caja.click()
    caja.fill("")
    caja.fill(hp)


def hay_resultado(page, hp):
    """Localiza el resultado de búsqueda de la operación por su HP.

    Confirmado por codegen: el resultado es un link cuyo nombre accesible
    empieza por el HP y sigue con más info (tramo y analista actual, p.ej.
    "HP-000748337 T1:  Javier Pena"). Se ancla al principio del texto para
    no depender del resto, que varía por operación."""
    return page.get_by_role("link", name=re.compile(rf"^{re.escape(hp)}"))


def abrir_resultado(page, hp):
    hay_resultado(page, hp).first.click()


def obtener_boton_reasignar(page):
    """Captura UNA referencia fija (ElementHandle) al botón "Reasignar" de
    Analista, justo después de abrir la ficha.

    Bug real visto en producción: `page.get_by_text("Reasignar").first` es
    un locator posicional que se vuelve a evaluar cada vez que se usa. Tras
    pulsar "Confirmar", Persefone añade una nota nueva al historial y
    puede reordenar contenido de la página; en varias operaciones eso hizo
    que, al releer el analista DESPUÉS de confirmar, ".first" ya no
    apuntara al mismo botón de Analista sino al de Cualificador, leyendo
    el nombre de otra persona (reasignaciones que en realidad sí se habían
    aplicado bien, verificado a mano). Un ElementHandle fija el nodo
    concreto desde el principio, así que se lee siempre del mismo sitio
    antes y después de confirmar, pase lo que pase alrededor en la
    página."""
    return page.get_by_text("Reasignar").first.element_handle()


def leer_analista_actual(boton_reasignar):
    """Lee el nombre del analista actualmente asignado, en el bloque
    "Analista" de "Ficha cliente", a partir del ElementHandle fijo que
    devuelve `obtener_boton_reasignar`.

    Confirmado por captura real (HTML real inspeccionado): "Ficha
    cliente", "Analista" y "Otros datos" viven TODAS dentro de una única
    tarjeta compartida (no son tres tarjetas separadas), y dentro de esa
    misma columna, "Analista" y "Cualificador" son bloques consecutivos
    (nombre en dos líneas + avatar + "Reasignar", uno debajo del otro,
    seguidos de las fechas). Por eso NO se puede subir buscando "el
    ancestro más cercano que contenga el texto 'Analista'": esa etiqueta
    también aparece dentro del contenedor grande que engloba Cualificador
    y las fechas, y se acaba leyendo de más (bug real visto en producción:
    se leyó "... Cualificador Cristina Perez Fecha de creación...").

    En su lugar, se sube desde el propio botón "Reasignar" nivel a nivel,
    y se para en cuanto el texto acumulado empieza a incluir "Cualificador"
    o "Fecha de creaci" — así nunca se cuela el bloque de al lado. El
    nombre se recompone concatenando el texto de los nodos hoja del último
    nivel "seguro" con JavaScript (`textContent`, no `inner_text()`): la
    interfaz pinta el nombre en mayúsculas con CSS (`text-transform:
    uppercase`), pero el texto real en el DOM conserva mayúsculas/
    minúsculas normales, que es como viene también en el CSV (p.ej. "Ana
    Gisela Gonçalves")."""
    return boton_reasignar.evaluate(
        """(el) => {
            let nodo = el;
            let seguro = null;
            for (let i = 0; i < 6 && nodo.parentElement; i++) {
                nodo = nodo.parentElement;
                const texto = nodo.textContent.trim();
                if (texto.includes('Cualificador') || texto.includes('Fecha de creaci')) {
                    break;
                }
                seguro = nodo;
            }
            const contenedor = seguro || el.parentElement || el;
            const partes = [];
            contenedor.querySelectorAll('*').forEach((hijo) => {
                if (hijo.children.length === 0) {
                    const texto = (hijo.textContent || '').trim();
                    if (texto && texto !== 'Analista' && texto !== 'Reasignar') {
                        partes.push(texto);
                    }
                }
            });
            return partes.join(' ');
        }"""
    )


def operacion_esta_cerrada(page):
    """Indica si la operación está cerrada (para añadir la nota
    correspondiente en el log, no para bloquear la reasignación).

    Confirmado por captura real: Persefone muestra un banner rojo en la
    parte superior de la ficha con el texto "Operación cerrada por: <nombre
    o '-'>" y "Fecha de cierre: <fecha>" (además de motivo/nota, que sí
    varían). Se busca solo "Operación cerrada por", la parte estable del
    banner."""
    return page.get_by_text("Operación cerrada por", exact=False).first.is_visible()


def click_reasignar_analista(boton_reasignar, page):
    """Pulsa el botón "Reasignar" del bloque "Analista" (nunca el de
    "Cualificador"), usando el mismo ElementHandle fijo de
    `obtener_boton_reasignar`, y espera a que se abra el modal. Devuelve el
    locator del diálogo abierto.

    Confirmado por codegen que este botón abre efectivamente el modal de
    reasignación de Analista, y confirmado también que el bloque
    "Analista" siempre precede al de "Cualificador" en el DOM de la
    ficha."""
    boton_reasignar.click()

    dialogo = page.get_by_role("dialog", name=DIALOG_NAME)
    dialogo.wait_for(state="visible", timeout=5000)
    return dialogo


def seleccionar_analista(dialogo, analista_objetivo):
    """Abre el desplegable "Analista" del modal (un combobox con búsqueda)
    y selecciona el analista objetivo.

    Confirmado por codegen: `get_by_role("combobox")` dentro del diálogo;
    se hace clic y se escribe para filtrar. Se usan las dos primeras
    palabras del nombre mostrado (no solo la primera) como término de
    búsqueda: con solo el nombre de pila (p.ej. "Miguel") pueden aparecer
    varios analistas distintos en la lista (visto en producción: salía
    también "Miguel Ángel Sánchez"), lo que aumenta el riesgo de que la
    lista virtualizada del desplegable tape o recicle la fila justo al
    hacer clic. Tras seleccionar, se espera activamente (no una espera fija)
    a que el propio texto elegido dentro del combobox quede estable y no
    haya ya ningún listado de opciones visible, para no bloquear el clic de
    "Confirmar" (visto en producción) sin perder tiempo de más cuando el
    desplegable cierra rápido."""
    texto_mostrado = nombre_mostrado(analista_objetivo)
    partes = texto_mostrado.split()
    termino_busqueda = " ".join(partes[:2]) if len(partes) >= 2 else texto_mostrado

    combobox = dialogo.get_by_role("combobox")
    combobox.click()
    combobox.fill(termino_busqueda)
    # El desplegable busca contra el backend (se ve un estado de "cargando"
    # mientras filtra), así que puede tardar más de los 5s por defecto bajo
    # carga (visto en producción, con la opción ya visible en pantalla pero
    # el robot dándose por vencido antes de encontrarla).
    click_texto_visible(dialogo.page, texto_mostrado, exact=True, timeout=8000)

    listbox = dialogo.page.get_by_role("listbox")
    limite = time.time() + 2
    while time.time() < limite and listbox.count() > 0 and listbox.first.is_visible():
        dialogo.page.wait_for_timeout(50)


def confirmar(dialogo):
    """Pulsa "Confirmar" en el modal: aplica la reasignación real.

    Confirmado por codegen: get_by_role("button", name="Confirmar"). Tras
    confirmar aparece una notificación de éxito con un botón "Close", pero
    es solo del panel de la ficha (para cerrarla y volver a buscar), no
    parte del flujo de confirmación en sí: la reasignación ya queda
    aplicada al pulsar "Confirmar", sin pasos adicionales."""
    dialogo.get_by_role("button", name="Confirmar", exact=True).click()


def cancelar(dialogo):
    """Pulsa "Cancelar" en el modal: no aplica ningún cambio (dry-run).

    Confirmado por codegen: get_by_role("button", name="Cancelar")."""
    dialogo.get_by_role("button", name="Cancelar", exact=True).click()
