"""
Exporta la tabla de la página "T1-Sin sabadell" del análisis de QuickSight
y la importa en la pestaña "Cruce" del Google Sheet de seguimiento.

Uso:
    python importar_tabla.py                  # con ventana de navegador visible
    python importar_tabla.py --headless        # sin ventana

Requiere:
- Haber ejecutado antes `python auth_setup.py` para generar
  storage_state.json con la sesión de QuickSight iniciada.
- Un JSON de credenciales de cuenta de servicio de Google (por defecto
  'service_account.json' en esta carpeta, o indícalo con --credenciales),
  con la hoja de destino compartida con su email como Editor.
"""
import argparse
import os
import sys

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

import quicksight_page as qs_page
import sheets_client

QUICKSIGHT_URL = (
    "https://eu-central-1.quicksight.aws.amazon.com/sn/account/"
    "quicksight-report-accounts/analyses/3c0f26de-3942-4240-aca3-58fa7018d892"
)
STORAGE_STATE_PATH = "storage_state.json"
DOWNLOAD_DIR = "downloads"

PAGINA_QUICKSIGHT_DEFAULT = "T1-Sin sabadell"

GOOGLE_SHEET_ID = "169IF75Pilomo7S5dY04JyMOqI8zslh_-hUVdNRqYjCQ"
PESTANA_DESTINO_DEFAULT = "Cruce"
CREDENCIALES_DEFAULT = "service_account.json"


def main():
    parser = argparse.ArgumentParser(
        description="Importa la tabla de una página de QuickSight en una pestaña de Google Sheets"
    )
    parser.add_argument("--pagina", default=PAGINA_QUICKSIGHT_DEFAULT,
                         help=f"Página (sheet) del análisis a exportar (default: '{PAGINA_QUICKSIGHT_DEFAULT}')")
    parser.add_argument("--visual", default=None,
                         help="Título del visual de tabla a exportar, si hay varias tablas en la página")
    parser.add_argument("--sheet-id", default=GOOGLE_SHEET_ID,
                         help="ID del Google Sheet destino (el trozo de la URL entre /d/ y /edit)")
    parser.add_argument("--pestana", default=PESTANA_DESTINO_DEFAULT,
                         help=f"Pestaña destino en el Google Sheet (default: '{PESTANA_DESTINO_DEFAULT}')")
    parser.add_argument("--credenciales", default=CREDENCIALES_DEFAULT,
                         help=f"Ruta al JSON de credenciales de la cuenta de servicio (default: '{CREDENCIALES_DEFAULT}')")
    parser.add_argument("--no-limpiar", action="store_true",
                         help="No borrar el contenido previo de la pestaña antes de pegar")
    parser.add_argument("--headless", action="store_true",
                         help="Ejecuta el navegador sin ventana visible")
    args = parser.parse_args()

    if not os.path.exists(STORAGE_STATE_PATH):
        sys.exit(f"No existe '{STORAGE_STATE_PATH}'. Ejecuta primero: python auth_setup.py")
    if not os.path.exists(args.credenciales):
        sys.exit(
            f"No existe '{args.credenciales}'. Genera una cuenta de servicio de Google Cloud, "
            "descarga su JSON, guárdalo con ese nombre en esta carpeta y comparte el Google Sheet "
            "con su 'client_email' como Editor."
        )

    print(f"Exportando página '{args.pagina}' del análisis de QuickSight...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context(storage_state=STORAGE_STATE_PATH, accept_downloads=True)
        page = context.new_page()
        page.goto(QUICKSIGHT_URL)
        page.wait_for_load_state("networkidle")

        qs_page.cerrar_aviso_bienvenida(page)

        try:
            qs_page.ir_a_pagina(page, args.pagina)
        except PlaywrightTimeoutError as exc:
            browser.close()
            sys.exit(f"No se pudo abrir la página '{args.pagina}' del análisis: {exc}")

        try:
            csv_path = qs_page.exportar_tabla_csv(page, DOWNLOAD_DIR, nombre_visual=args.visual)
        except PlaywrightTimeoutError as exc:
            browser.close()
            sys.exit(f"No se pudo exportar la tabla a CSV: {exc}")

        browser.close()

    print(f"CSV descargado en '{csv_path}'.")

    filas = sheets_client.leer_csv(csv_path)
    if not filas:
        sys.exit("El CSV exportado está vacío, no se importa nada.")
    print(f"Leídas {len(filas)} filas (incluyendo cabecera).")

    print(f"Conectando con Google Sheets ({args.sheet_id}, pestaña '{args.pestana}')...")
    cliente = sheets_client.conectar(args.credenciales)
    hoja = sheets_client.obtener_hoja(cliente, args.sheet_id, args.pestana)
    sheets_client.volcar_tabla(hoja, filas, limpiar=not args.no_limpiar)

    print(f"Listo: {len(filas) - 1} filas de datos importadas en la pestaña '{args.pestana}'.")


if __name__ == "__main__":
    main()
