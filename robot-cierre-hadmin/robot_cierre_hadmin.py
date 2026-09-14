"""
Robot de cierre masivo de operaciones en Hadmin.

Uso:
    python robot_cierre_hadmin.py                  # dry-run (por defecto, no confirma nada)
    python robot_cierre_hadmin.py --produccion      # cierre real

Requiere haber ejecutado antes `python auth_setup.py` para generar
storage_state.json con la sesión iniciada.
"""
import argparse
import csv
import glob
import os
import random
import sys
import time
from datetime import datetime

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

import hadmin_page as hp_page

HADMIN_URL = "https://hadmin.gibobs.com/"
STORAGE_STATE_PATH = "storage_state.json"
CSV_INPUT_DEFAULT = "operaciones.csv"
LOGS_DIR = "logs"
DEBUG_DIR = "debug"

MOTIVO_DEFAULT = "Ilocalizable"
CONTENIDO_DEFAULT = (
    "El cliente no ha contestado los intentos de contacto - "
    "Acción puntual Stock de Allbanks"
)


def leer_operaciones(csv_path):
    """Lee el CSV de entrada. Devuelve (operaciones, duplicados) deduplicando
    por id_operacion y conservando el orden de aparición."""
    vistos = set()
    duplicados = []
    operaciones = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "id_operacion" not in reader.fieldnames:
            raise ValueError("El CSV debe tener una columna 'id_operacion'")
        for fila in reader:
            hp = (fila.get("id_operacion") or "").strip()
            if not hp:
                continue
            if hp in vistos:
                duplicados.append(hp)
                continue
            vistos.add(hp)
            operaciones.append({
                "id_operacion": hp,
                "motivo": (fila.get("motivo") or "").strip() or MOTIVO_DEFAULT,
                "contenido": (fila.get("contenido") or "").strip() or CONTENIDO_DEFAULT,
            })
    return operaciones, duplicados


def ultimo_log():
    logs = sorted(glob.glob(os.path.join(LOGS_DIR, "resultado_cierre_*.csv")))
    return logs[-1] if logs else None


def preguntar_reanudar():
    log = ultimo_log()
    if not log:
        return False
    respuesta = input(
        f"Se encontró un log anterior ({log}). "
        "¿Continuar desde ahí y omitir las operaciones ya marcadas 'ok', "
        "o empezar de cero? [continuar/cero]: "
    ).strip().lower()
    return respuesta.startswith("c")


def cargar_ya_ok(reanudar):
    if not reanudar:
        return set()
    log = ultimo_log()
    ok = set()
    with open(log, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for fila in reader:
            if fila.get("estado") == "ok":
                ok.add(fila.get("id_operacion"))
    print(f"Reanudando: {len(ok)} operaciones ya cerradas en '{log}' se omitirán.")
    return ok


def nombre_log():
    os.makedirs(LOGS_DIR, exist_ok=True)
    nombre = datetime.now().strftime("resultado_cierre_%Y%m%d_%H%M.csv")
    return os.path.join(LOGS_DIR, nombre)


def captura(page, hp, paso):
    """Guarda una captura de pantalla en debug/ para poder revisar después
    qué se veía en cada paso, sin depender de verlo en directo."""
    os.makedirs(DEBUG_DIR, exist_ok=True)
    nombre = f"{hp}_{paso}.png"
    try:
        page.screenshot(path=os.path.join(DEBUG_DIR, nombre))
    except Exception:
        pass  # una captura fallida no debe tumbar el proceso


def procesar_operacion(page, hp, motivo, contenido, produccion):
    """Devuelve (estado, detalle). estado en {"ok", "error", "omitida"}.

    En modo no-producción (dry-run) llega hasta el modal relleno y lo
    cancela sin confirmar el cierre real.
    """
    try:
        hp_page.buscar_operacion(page, hp)

        resultado = hp_page.hay_resultado(page)
        try:
            resultado.first.wait_for(state="visible", timeout=8000)
        except PlaywrightTimeoutError:
            captura(page, hp, "01_sin_resultado")
            return "omitida", "No se encontró resultado de búsqueda para el HP"
        captura(page, hp, "01_resultado_busqueda")
        hp_page.abrir_resultado(page)

        try:
            dialogo = hp_page.click_finalizar(page)
        except PlaywrightTimeoutError:
            captura(page, hp, "02_sin_finalizar_o_modal")
            return "omitida", "No aparece el botón 'Finalizar' o el modal (¿la operación ya estaba cerrada?)"
        captura(page, hp, "02_modal_abierto")

        hp_page.seleccionar_cerrar_tareas_si(page)
        captura(page, hp, "03_tareas_si")

        hp_page.seleccionar_solicitante_gibobs(page)
        captura(page, hp, "04_solicitante_gibobs")

        hp_page.seleccionar_motivo(page, motivo)
        captura(page, hp, "05_motivo_seleccionado")

        hp_page.rellenar_contenido(page, dialogo, contenido)
        captura(page, hp, "06_contenido_relleno")

        if produccion:
            hp_page.confirmar_cierre(page, dialogo)
            captura(page, hp, "07_cerrado")
            return "ok", "Cerrada correctamente"
        else:
            hp_page.cancelar_modal(page, dialogo)
            captura(page, hp, "07_cancelado")
            return "ok", "[DRY-RUN] Formulario verificado, no se confirmó el cierre"

    except Exception as exc:
        captura(page, hp, "99_error")
        return "error", str(exc)


def main():
    parser = argparse.ArgumentParser(description="Robot de cierre masivo de operaciones en Hadmin")
    parser.add_argument("--csv", default=CSV_INPUT_DEFAULT, help="CSV de entrada (default: operaciones.csv)")
    parser.add_argument("--produccion", action="store_true", help="Confirma cierres reales (por defecto es dry-run)")
    parser.add_argument("--headless", action="store_true", help="Ejecuta sin ventana de navegador visible")
    args = parser.parse_args()

    if not os.path.exists(STORAGE_STATE_PATH):
        sys.exit(f"No existe '{STORAGE_STATE_PATH}'. Ejecuta primero: python auth_setup.py")

    if not os.path.exists(args.csv):
        sys.exit(f"No existe el CSV de entrada '{args.csv}'.")

    operaciones, duplicados = leer_operaciones(args.csv)

    reanudar = preguntar_reanudar()
    ya_ok = cargar_ya_ok(reanudar)
    pendientes = [op for op in operaciones if op["id_operacion"] not in ya_ok]

    modo = "PRODUCCIÓN (cierre real)" if args.produccion else "DRY-RUN (simulación, no confirma)"
    print(f"Modo: {modo}. Operaciones a procesar: {len(pendientes)} (de {len(operaciones)} en el CSV)")

    log_path = nombre_log()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context(storage_state=STORAGE_STATE_PATH)
        page = context.new_page()
        page.goto(HADMIN_URL)

        with open(log_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id_operacion", "estado", "detalle"])

            for hp in duplicados:
                writer.writerow([hp, "omitida", "Duplicado en el CSV de entrada"])
            f.flush()

            for op in pendientes:
                hp = op["id_operacion"]
                estado, detalle = procesar_operacion(
                    page, hp, op["motivo"], op["contenido"], args.produccion
                )
                writer.writerow([hp, estado, detalle])
                f.flush()
                print(f"{hp}: {estado} - {detalle}")
                time.sleep(random.uniform(1, 3))

        browser.close()

    print(f"\nLog guardado en '{log_path}'.")


if __name__ == "__main__":
    main()
