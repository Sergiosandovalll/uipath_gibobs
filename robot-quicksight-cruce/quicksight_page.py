"""
Interacciones con el DOM real de QuickSight
(https://eu-central-1.quicksight.aws.amazon.com/...), para abrir un
análisis, cambiar a una página (sheet) concreta y exportar a CSV la tabla
de esa página.

PENDIENTE DE VERIFICAR contra la interfaz real: estos selectores son una
hipótesis razonable a partir de la estructura habitual de QuickSight
(pestañas de página abajo, menú "⋮" al pasar el ratón sobre cada visual,
opción "Export to CSV"/"Exportar a CSV"), pero QuickSight cambia el idioma
según el usuario y el DOM exacto puede variar entre cuentas/versiones. Si
algo no encaja, vuelve a capturar los selectores con:

    playwright codegen https://eu-central-1.quicksight.aws.amazon.com/...

y actualiza las funciones de este archivo (no las de importar_tabla.py).
"""
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

# Textos que puede tener el botón/menú de exportar, según idioma de la cuenta.
TEXTOS_EXPORTAR_CSV = ["Export to CSV", "Exportar a CSV"]
TEXTOS_MENU_VISUAL = ["More options", "Más opciones"]


def click_texto_visible(page, texto, exact=True, timeout=5000):
    """Hace clic en la única coincidencia de texto que esté realmente
    visible. Igual que en robot-cierre-hadmin: algunos componentes de
    QuickSight dejan nodos duplicados (ocultos) con el mismo texto mientras
    se abren/cierran, así que se espera activamente a que haya una
    coincidencia visible y se hace clic en esa."""
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


def cerrar_aviso_bienvenida(page):
    """Cierra el modal de bienvenida que QuickSight muestra a veces al
    abrir un análisis. Best-effort: si no aparece en 3s, sigue sin más."""
    try:
        page.get_by_role("button", name="Close").click(timeout=3000)
    except PlaywrightTimeoutError:
        pass


def ir_a_pagina(page, nombre_pagina):
    """Cambia a la página/sheet del análisis indicada por su nombre, tal y
    como aparece en las pestañas de la parte inferior (p.ej.
    'T1-Sin sabadell')."""
    pestana = page.get_by_role("tab", name=nombre_pagina, exact=True)
    try:
        pestana.wait_for(state="visible", timeout=8000)
        pestana.click()
    except PlaywrightTimeoutError:
        # Fallback si QuickSight no expone las pestañas con role="tab":
        # se busca por el texto visible directamente.
        click_texto_visible(page, nombre_pagina, exact=True, timeout=8000)
    page.wait_for_timeout(1000)


def _localizar_visual_tabla(page, nombre_visual=None):
    """Localiza el contenedor del visual de tipo tabla dentro de la página
    actual. Si se indica nombre_visual, se filtra por el título del visual;
    si no, se usa el primer visual de tabla encontrado."""
    if nombre_visual:
        visual = page.locator(
            f"[data-testid*='visual']:has-text('{nombre_visual}')"
        ).first
    else:
        visual = page.locator("[data-testid*='visual']").filter(
            has=page.locator("table")
        ).first
    visual.wait_for(state="visible", timeout=10000)
    return visual


def exportar_tabla_csv(page, download_dir, nombre_visual=None, nombre_archivo="tabla_quicksight.csv"):
    """Pasa el ratón por encima de la tabla, abre su menú "⋮" y elige
    "Export to CSV" / "Exportar a CSV", capturando la descarga con
    Playwright (sin depender de un selector de archivos manual). Devuelve
    la ruta local del CSV descargado."""
    import os

    visual = _localizar_visual_tabla(page, nombre_visual)
    visual.hover()
    page.wait_for_timeout(300)

    boton_menu = None
    for texto in TEXTOS_MENU_VISUAL:
        candidato = visual.get_by_label(texto)
        if candidato.count():
            boton_menu = candidato.first
            break
    if boton_menu is None:
        # Fallback: el botón de menú suele ser el icono "⋮" dentro del visual.
        boton_menu = visual.locator("button[aria-haspopup='true']").first
    boton_menu.click()
    page.wait_for_timeout(300)

    with page.expect_download(timeout=15000) as descarga_info:
        exportado = False
        for texto in TEXTOS_EXPORTAR_CSV:
            opcion = page.get_by_text(texto, exact=False)
            if opcion.count() and opcion.first.is_visible():
                opcion.first.click()
                exportado = True
                break
        if not exportado:
            raise PlaywrightTimeoutError(
                "No se encontró la opción 'Export to CSV' / 'Exportar a CSV' "
                "en el menú del visual"
            )
    descarga = descarga_info.value

    os.makedirs(download_dir, exist_ok=True)
    ruta_destino = os.path.join(download_dir, nombre_archivo)
    descarga.save_as(ruta_destino)
    return ruta_destino
