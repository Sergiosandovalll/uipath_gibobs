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

DIALOG_NAME = "Cerrar hipoteca"


def buscar_operacion(page, hp):
    """Escribe el HP en la barra de búsqueda superior (sin pulsar Enter)."""
    caja = page.get_by_role("textbox", name="Buscar...")
    caja.click()
    caja.fill("")
    caja.fill(hp)


def hay_resultado(page):
    """Localiza el resultado de búsqueda de la operación."""
    return page.get_by_role("link", name="double-right home HP-")


def abrir_resultado(page):
    hay_resultado(page).click()


def click_finalizar(page):
    boton = page.get_by_role("button", name="Finalizar")
    boton.wait_for(state="visible", timeout=5000)
    boton.click()
    dialogo = page.get_by_role("dialog", name=DIALOG_NAME)
    dialogo.wait_for(state="visible", timeout=5000)
    return dialogo


def seleccionar_cerrar_tareas_si(page):
    page.locator("#NotesPostpone").click()
    page.get_by_text("Si", exact=True).click()


def seleccionar_solicitante_gibobs(page):
    page.locator("#requestReason").click()
    page.get_by_text("Por solicitud de Gibobs").nth(1).click()


def seleccionar_motivo(page, motivo):
    """El desplegable de Motivo solo existe una vez elegido el solicitante
    "Por solicitud de Gibobs". Se abre haciendo clic en su placeholder
    ("Seleccione") y se elige la opción por su texto."""
    page.get_by_text("Seleccione").click()
    page.get_by_text(motivo, exact=True).nth(1).click()


def rellenar_contenido(page, dialogo, texto):
    editor = dialogo.get_by_role("textbox")
    editor.click()
    editor.fill(texto)


def confirmar_cierre(page, dialogo):
    """Pulsa 'Cerrar' en el modal: aplica el cierre real. PENDIENTE de
    verificar en dry-run antes de fiarse en producción."""
    dialogo.get_by_role("button", name="Cerrar", exact=True).click()


def cancelar_modal(page, dialogo):
    """Pulsa 'Cancelar' en el modal: no aplica ningún cambio. PENDIENTE de
    verificar en dry-run."""
    dialogo.get_by_role("button", name="Cancelar", exact=True).click()
