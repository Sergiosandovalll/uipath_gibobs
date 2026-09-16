"""
Genera o regenera storage_state.json: la sesión guardada de QuickSight que
usa importar_tabla.py para no tener que hacer login (SSO) en cada ejecución.

Uso (ejecutar cada vez que la sesión caduque o antes del primer uso):

    python auth_setup.py

Se abre un navegador visible. Inicia sesión manualmente (usuario/contraseña
y, si aplica, el paso de SSO/MFA) y, cuando ya veas el análisis o el listado
de QuickSight cargado, vuelve a esta terminal y pulsa Enter.
"""
import sys

from playwright.sync_api import sync_playwright

STORAGE_STATE_PATH = "storage_state.json"
QUICKSIGHT_URL = (
    "https://eu-central-1.quicksight.aws.amazon.com/sn/account/"
    "quicksight-report-accounts/analyses/3c0f26de-3942-4240-aca3-58fa7018d892"
)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(QUICKSIGHT_URL)

        input(
            "\nInicia sesión manualmente en la ventana del navegador "
            "(usuario/contraseña y SSO/MFA si aplica).\n"
            "Cuando el análisis de QuickSight esté cargado, vuelve aquí y "
            "pulsa Enter para guardar la sesión...\n"
        )

        context.storage_state(path=STORAGE_STATE_PATH)
        print(f"Sesión guardada en '{STORAGE_STATE_PATH}'.")
        browser.close()


if __name__ == "__main__":
    sys.exit(main())
