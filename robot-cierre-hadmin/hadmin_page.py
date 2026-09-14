"""
Interacciones con el DOM real de Hadmin (https://hadmin.gibobs.com/),
obtenidas con `playwright codegen` sobre el flujo real de cierre.

Este es el único archivo que depende de la estructura concreta de la
interfaz de Hadmin: si algo cambia en el DOM, se toca aquí.

PENDIENTE DE CONFIRMAR: los botones "Cerrar" y "Cancelar" del modal no se
llegaron a grabar (la grabación se paró justo al hacer clic en el editor de
Contenido). Los locators de abajo (`BTN_CERRAR_MODAL` / `BTN_CANCELAR_MODAL`)
son una hipótesis razonable basada en la captura del modal, pero hay que
verificarlos en dry-run antes de confiar en ellos para producción.
"""
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

DIALOG_NAME = "Cerrar hipoteca"


def click_texto_visible(page, texto, exact=True, timeout=5000):
    """Hace clic en la única coincidencia de texto que esté realmente
    visible. Algunos desplegables de Hadmin dejan momentáneamente un nodo
    duplicado (oculto) con el mismo texto mientras se abren/cierran, así
    que en vez de adivinar un índice fijo (nth), se espera activamente a
    que aparezca una opción visible y se hace clic en esa."""
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


def buscar_operacion(page, hp):
    """Escribe el HP en la barra de búsqueda superior (sin pulsar Enter)."""
    caja = page.get_by_role("textbox", name="Buscar...")
    caja.click()
    caja.fill("")
    caja.fill(hp)


def hay_resultado(page, hp):
    """Localiza el resultado de búsqueda de la operación.

    Se filtra por el HP exacto (no solo por el prefijo "HP-") porque la
    ficha de un cliente puede mostrar un bloque "Otras operaciones" con
    hipotecas hermanas del mismo cliente, cuyos enlaces usan el mismo
    patrón de texto y pueden quedar en la página al buscar la siguiente
    operación, dando falsos "2 elementos encontrados"."""
    return page.get_by_role("link", name=hp)


def abrir_resultado(page, hp):
    hay_resultado(page, hp).click()


def click_finalizar(page):
    boton = page.get_by_role("button", name="Finalizar")
    boton.wait_for(state="visible", timeout=5000)
    # La ficha carga en dos fases: primero aparecen los botones
    # deshabilitados mientras termina de cargar, luego se activan. Se le da
    # un margen antes de concluir que sigue deshabilitado de verdad (ya
    # cerrada) en vez de que sea solo la carga inicial de la página.
    limite = time.time() + 5
    while time.time() < limite and boton.is_disabled():
        page.wait_for_timeout(200)
    if boton.is_disabled():
        raise PlaywrightTimeoutError("El botón 'Finalizar' está deshabilitado")
    boton.click()
    dialogo = page.get_by_role("dialog", name=DIALOG_NAME)
    dialogo.wait_for(state="visible", timeout=5000)
    return dialogo


def seleccionar_cerrar_tareas_si(page):
    page.locator("#NotesPostpone").click()
    click_texto_visible(page, "Si", exact=True)
    page.wait_for_timeout(300)


def seleccionar_solicitante_gibobs(page):
    page.locator("#requestReason").click()
    click_texto_visible(page, "Por solicitud de Gibobs", exact=False)
    page.wait_for_timeout(300)


def seleccionar_motivo(page, motivo):
    """El desplegable de Motivo solo existe una vez elegido el solicitante
    "Por solicitud de Gibobs". Se abre haciendo clic en su placeholder
    ("Seleccione") y se elige la opción por su texto."""
    page.get_by_text("Seleccione").click()
    page.wait_for_timeout(300)
    click_texto_visible(page, motivo, exact=True)
    page.wait_for_timeout(300)


def rellenar_contenido(page, dialogo, texto):
    """El editor de "Contenido" es un Draft.js (contenteditable gestionado
    por JS): no soporta rellenarse asignando el valor directamente
    (.fill()), hay que escribir con el teclado simulado tras enfocarlo."""
    bloque = dialogo.locator(".public-DraftStyleDefault-block").first
    bloque.click()
    page.keyboard.type(texto)


def confirmar_cierre(page, dialogo):
    """Pulsa 'Cerrar' en el modal: aplica el cierre real. PENDIENTE de
    verificar en dry-run antes de fiarse en producción."""
    dialogo.get_by_role("button", name="Cerrar", exact=True).click()


def cancelar_modal(page, dialogo):
    """Pulsa 'Cancelar' en el modal: no aplica ningún cambio. PENDIENTE de
    verificar en dry-run."""
    dialogo.get_by_role("button", name="Cancelar", exact=True).click()
