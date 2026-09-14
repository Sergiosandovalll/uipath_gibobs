"""
Genera o regenera storage_state.json: la sesión guardada de Hadmin que usa
robot_cierre_hadmin.py para no tener que hacer login en cada ejecución.

Uso (ejecutar cada vez que la sesión caduque o antes del primer uso):

    python auth_setup.py

Se abre un navegador visible. Inicia sesión manualmente en Hadmin y, cuando
ya veas el panel cargado, vuelve a esta terminal y pulsa Enter.
"""
import sys

from playwright.sync_api import sync_playwright

STORAGE_STATE_PATH = "storage_state.json"
HADMIN_URL = "https://hadmin.gibobs.com/"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(HADMIN_URL)

        input(
            "\nInicia sesión manualmente en la ventana del navegador.\n"
            "Cuando estés dentro de Hadmin, vuelve aquí y pulsa Enter para "
            "guardar la sesión...\n"
        )

        context.storage_state(path=STORAGE_STATE_PATH)
        print(f"Sesión guardada en '{STORAGE_STATE_PATH}'.")
        browser.close()


if __name__ == "__main__":
    sys.exit(main())
