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

# Mapeo entre el nombre del analista tal como viene en el CSV (nombre
# "oficial") y el texto que muestra realmente el desplegable de Persefone.
# Ambos confirmados por codegen: al escribir "Ana" en el combobox aparece
# "Ana Gonçalves" (sin "Gisela"); al escribir "Miguel" aparece "Miguel
# Cerezal Jiménez" (con el apellido "Jiménez", que no está en el CSV). Si
# Persefone cambia el texto que muestra para alguno de los dos, ajusta este
# diccionario (es el único sitio que hay que tocar).
NOMBRE_MOSTRADO_PERSEFONE = {
    "Miguel Cerezal": "Miguel Cerezal Jiménez",
    "Ana Gisela Gonçalves": "Ana Gonçalves",
}


def nombre_mostrado(analista_csv):
    """Traduce el nombre del CSV al texto que hay que buscar/verificar en
    la interfaz de Persefone."""
    return NOMBRE_MOSTRADO_PERSEFONE.get(analista_csv, analista_csv)


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


def leer_analista_actual(page):
    """Lee el nombre del analista actualmente asignado, en el bloque
    "Analista" de "Ficha cliente".

    Confirmado por captura real: el nombre se pinta en dos líneas
    separadas (nombre y apellidos, cada una en su propio elemento), junto
    a una foto de avatar y el propio botón "Reasignar", bajo una etiqueta
    "Analista". Se localiza el bloque subiendo desde el mismo botón
    "Reasignar" que usa `click_reasignar_analista` (garantiza que es el
    bloque de Analista, no el de Cualificador) hasta el ancestro más
    cercano que también contenga el texto "Analista", sin depender de un
    número fijo de niveles del DOM.

    Se recompone el nombre concatenando el texto de los nodos hoja del
    bloque con JavaScript (`textContent`, no `inner_text()`): la interfaz
    pinta el nombre en mayúsculas con CSS (`text-transform: uppercase`),
    pero el texto real en el DOM conserva mayúsculas/minúsculas normales,
    que es como viene también en el CSV (p.ej. "Ana Gisela Gonçalves")."""
    reasignar = page.get_by_text("Reasignar").first
    bloque = reasignar.locator("xpath=ancestor::*[.//text()[contains(., 'Analista')]][1]")
    return bloque.evaluate(
        """(el) => {
            const partes = [];
            el.querySelectorAll('*').forEach((nodo) => {
                if (nodo.children.length === 0) {
                    const texto = (nodo.textContent || '').trim();
                    if (texto) partes.push(texto);
                }
            });
            return partes.filter((t) => t !== 'Analista' && t !== 'Reasignar').join(' ');
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


def click_reasignar_analista(page):
    """Pulsa el botón "Reasignar" del bloque "Analista" (nunca el de
    "Cualificador") y espera a que se abra el modal. Devuelve el locator
    del diálogo abierto.

    Confirmado por codegen que `get_by_text("Reasignar").first` abre
    efectivamente el modal de reasignación de Analista en el flujo grabado,
    y confirmado también que el bloque "Analista" siempre precede al de
    "Cualificador" en el DOM de la ficha, así que `.first` es seguro."""
    page.get_by_text("Reasignar").first.click()

    dialogo = page.get_by_role("dialog", name=DIALOG_NAME)
    dialogo.wait_for(state="visible", timeout=5000)
    return dialogo


def seleccionar_analista(dialogo, analista_objetivo):
    """Abre el desplegable "Analista" del modal (un combobox con búsqueda)
    y selecciona el analista objetivo.

    Confirmado por codegen: `get_by_role("combobox")` dentro del diálogo;
    se hace clic, se escribe el primer nombre para filtrar (igual que en la
    grabación, que escribió "Ana") y se hace clic en la opción visible con
    el texto exacto que muestra Persefone (ver `NOMBRE_MOSTRADO_PERSEFONE`,
    que no siempre coincide con el nombre completo del CSV)."""
    texto_mostrado = nombre_mostrado(analista_objetivo)
    termino_busqueda = texto_mostrado.split()[0]

    combobox = dialogo.get_by_role("combobox")
    combobox.click()
    combobox.fill(termino_busqueda)
    click_texto_visible(dialogo.page, texto_mostrado, exact=True)


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
