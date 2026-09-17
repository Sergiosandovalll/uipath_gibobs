"""
Interacciones con el DOM real de Persefone
(https://persefone.gibobs.gibobs.one/dashboard).

⚠️ ESTADO: PENDIENTE DE CODEGEN REAL. ⚠️
Persefone es un sistema DISTINTO de Hadmin (interfaz y DOM distintos), y
todavía no se ha grabado el flujo real con `playwright codegen`. Todos los
locators de este archivo son PLACEHOLDERS razonables basados en la
descripción funcional del flujo, no en el DOM real. Antes de usar este
robot en dry-run siquiera, hay que:

    playwright codegen https://persefone.gibobs.gibobs.one/dashboard

...hacer el flujo a mano (buscar HP, abrir ficha, pulsar "Reasignar" del
bloque Analista, elegir analista en el desplegable del modal, "Confirmar"
y "Cancelar") y sustituir cada función de abajo por los locators reales
capturados. Este es el único archivo que debería tocarse si cambia el DOM
de Persefone: robot_reasignacion.py no debe conocer selectores.

Recordatorio de negocio importante al verificar los selectores reales:
la ficha tiene DOS botones "Reasignar" (uno para "Analista" y otro para
"Cualificador"). El robot NUNCA debe pulsar el de "Cualificador".
"""
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

# TODO: confirmar con codegen. Nombre/título real del modal de reasignación.
DIALOG_NAME = "Reasignar operación"


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
    porque los desplegables tipo Ant Design suelen montar sus opciones en un
    portal fuera del propio modal."""
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

    TODO: confirmar con codegen. Placeholder: se asume que la pantalla de
    login tiene un campo de contraseña visible y/o un botón "Iniciar
    sesión"."""
    try:
        return page.get_by_label("Contraseña").is_visible(timeout=3000) or \
            page.get_by_role("button", name="Iniciar sesión").is_visible(timeout=1000)
    except PlaywrightTimeoutError:
        return False


def buscar_operacion(page, hp):
    """Escribe el HP en el buscador de Persefone.

    TODO: confirmar con codegen el selector real del buscador (placeholder:
    textbox con nombre/placeholder "Buscar")."""
    caja = page.get_by_role("textbox", name="Buscar")
    caja.click()
    caja.fill("")
    caja.fill(hp)
    page.keyboard.press("Enter")


def hay_resultado(page, hp):
    """Localiza el resultado de búsqueda de la operación por su HP exacto.

    TODO: confirmar con codegen. Placeholder: un enlace/fila cuyo texto es
    el HP exacto."""
    return page.get_by_text(hp, exact=True)


def abrir_resultado(page, hp):
    hay_resultado(page, hp).first.click()


def leer_analista_actual(page):
    """Lee el nombre del analista actualmente asignado, en el bloque
    "Analista" de "Ficha cliente".

    TODO: confirmar con codegen el contenedor real. Placeholder: se busca
    un bloque con encabezado "Analista" y se lee el texto que sigue."""
    bloque = page.locator("text=Analista").first.locator("xpath=..")
    return bloque.inner_text().replace("Analista", "").strip()


def operacion_esta_cerrada(page):
    """Indica si la operación está cerrada (para añadir la nota
    correspondiente en el log, no para bloquear la reasignación).

    TODO: confirmar con codegen el indicador real. Placeholder: se asume
    que existe un botón "Finalizar" que aparece deshabilitado, o no
    aparece en absoluto, cuando la operación está cerrada."""
    boton = page.get_by_role("button", name="Finalizar")
    if boton.count() == 0:
        return True
    return boton.first.is_disabled()


def click_reasignar_analista(page):
    """Pulsa el botón "Reasignar" del bloque "Analista" (nunca el de
    "Cualificador") y espera a que se abra el modal. Devuelve el locator
    del diálogo abierto.

    TODO: confirmar con codegen. Placeholder: se acota la búsqueda del
    botón "Reasignar" al contenedor que tiene el texto "Analista", para no
    arriesgarse a pulsar el de "Cualificador" que vive en otro bloque."""
    bloque_analista = page.locator("text=Analista").first.locator(
        "xpath=ancestor-or-self::*[self::div or self::section][1]"
    )
    boton = bloque_analista.get_by_role("button", name="Reasignar")
    boton.wait_for(state="visible", timeout=5000)
    boton.click()

    dialogo = page.get_by_role("dialog", name=DIALOG_NAME)
    dialogo.wait_for(state="visible", timeout=5000)
    return dialogo


def seleccionar_analista(dialogo, analista):
    """Abre el desplegable "Analista" del modal y selecciona el nombre
    exacto pasado por parámetro.

    TODO: confirmar con codegen el selector real del desplegable
    (placeholder: se abre por su placeholder "Seleccione" y se elige la
    opción por texto visible, igual que en Hadmin)."""
    dialogo.get_by_text("Seleccione").click()
    dialogo.page.wait_for_timeout(300)
    click_texto_visible(dialogo.page, analista, exact=True)
    dialogo.page.wait_for_timeout(300)


def confirmar(dialogo):
    """Pulsa "Confirmar" en el modal: aplica la reasignación real.

    TODO: confirmar con codegen el texto/rol exacto del botón."""
    dialogo.get_by_role("button", name="Confirmar", exact=True).click()


def cancelar(dialogo):
    """Pulsa "Cancelar" en el modal: no aplica ningún cambio (dry-run).

    TODO: confirmar con codegen el texto/rol exacto del botón."""
    dialogo.get_by_role("button", name="Cancelar", exact=True).click()
