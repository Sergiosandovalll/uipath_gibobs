"""
Interacciones con el DOM real de Persefone
(https://persefone.gibobs.gibobs.one/dashboard).

Este es el único archivo que depende de la estructura concreta de la
interfaz de Persefone: si algo cambia en el DOM, se toca aquí.
robot_reasignacion.py no debe conocer selectores.

⚠️ ESTADO: PARCIALMENTE CONFIRMADO con `playwright codegen` real (login,
búsqueda, apertura de resultado, apertura del modal, desplegable con
búsqueda por texto y "Confirmar"). Lo que queda como TODO explícito abajo
NO se llegó a grabar todavía y sigue siendo una hipótesis razonable:

- `leer_analista_actual`: no se grabó el bloque "Analista" de "Ficha
  cliente" (no es algo que capture `codegen`, que solo graba acciones, no
  lecturas). Sigue como placeholder hasta tener el locator exacto — la
  forma más simple de conseguirlo sin tocar código a ciegas es con el botón
  "Pick locator" del Playwright Inspector (icono de mira en la barra de
  herramientas que aparece junto al navegador al lanzar `codegen`): clic
  ahí y luego clic sobre el nombre del analista en la ficha, sin que se
  dispare ninguna acción real, y copiar el locator que muestra el panel.
- `cancelar`: no se probó el botón "Cancelar" del modal (solo "Confirmar").
- El botón "Reasignar" se localiza con `.first` sobre todo el texto
  "Reasignar" de la página. Confirmado como definitivo: el bloque
  "Analista" siempre va antes que el de "Cualificador" en la ficha, así que
  `.first` siempre corresponde a Analista.
"""
import re
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

# Confirmado por codegen: get_by_role("dialog", name="Reasignar operación").
DIALOG_NAME = "Reasignar operación"

# Mapeo entre el nombre del analista tal como viene en el CSV (nombre
# completo "oficial") y el texto que muestra realmente el desplegable de
# Persefone. Confirmado por codegen para Ana Gisela Gonçalves: al escribir
# "Ana" en el combobox, la opción que aparece es "Ana Gonçalves" (sin
# "Gisela"). Para Miguel Cerezal se asume que coincide tal cual porque no
# hay indicio de lo contrario, pero **falta confirmarlo** con un dry-run
# real. Si Persefone muestra otro texto para alguno de los dos, ajusta este
# diccionario (es el único sitio que hay que tocar).
NOMBRE_MOSTRADO_PERSEFONE = {
    "Miguel Cerezal": "Miguel Cerezal",  # TODO: confirmar en dry-run
    "Ana Gisela Gonçalves": "Ana Gonçalves",  # confirmado por codegen
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

    TODO: NO CONFIRMADO CON CODEGEN. No se grabó este paso todavía. Hace
    falta abrir una ficha real y capturar cómo se muestra este dato para
    reemplazar el placeholder de abajo."""
    bloque = page.locator("text=Analista").first.locator("xpath=..")
    return bloque.inner_text().replace("Analista", "").strip()


def operacion_esta_cerrada(page):
    """Indica si la operación está cerrada (para añadir la nota
    correspondiente en el log, no para bloquear la reasignación).

    Persefone muestra un banner rojo en la parte superior de la ficha
    avisando de que está cerrada. Se busca cualquier texto visible que
    contenga "cerrad" (cubre "cerrada"/"cerrado") en vez de un texto
    literal exacto, porque no se ha confirmado la redacción exacta del
    banner — es un heurístico de bajo riesgo ya que solo añade una nota al
    log, nunca bloquea la reasignación. Si el texto exacto del banner se
    confirma más adelante, se puede ajustar aquí para mayor precisión."""
    banner = page.get_by_text(re.compile("cerrad", re.IGNORECASE))
    for i in range(banner.count()):
        if banner.nth(i).is_visible():
            return True
    return False


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

    Confirmado por codegen: get_by_role("button", name="Confirmar")."""
    dialogo.get_by_role("button", name="Confirmar", exact=True).click()


def cancelar(dialogo):
    """Pulsa "Cancelar" en el modal: no aplica ningún cambio (dry-run).

    TODO: NO CONFIRMADO CON CODEGEN. La grabación solo probó "Confirmar".
    Se asume que el botón se llama "Cancelar" (mismo patrón que Hadmin y que
    el resto de modales de la aplicación), pero hay que verificarlo en el
    primer dry-run real."""
    dialogo.get_by_role("button", name="Cancelar", exact=True).click()
