"""
Robot de reasignación masiva de analista de operaciones en Persefone.

Uso:
    python robot_reasignacion.py                  # dry-run (por defecto, no confirma nada)
    python robot_reasignacion.py --produccion      # reasignación real

Requiere haber ejecutado antes `python auth_setup.py` para generar
storage_state.json con la sesión iniciada.

⚠️ Antes de usar este script hace falta rellenar los selectores reales de
Persefone en persefone_page.py (ver el aviso al principio de ese archivo).
"""
import argparse
import csv
import glob
import os
import random
import sys
import time
from datetime import datetime, timedelta

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

import persefone_page as pp_page

PERSEFONE_URL = "https://persefone.gibobs.gibobs.one/dashboard"
STORAGE_STATE_PATH = "storage_state.json"
CSV_INPUT_DEFAULT = "operaciones.csv"
LOGS_DIR = "logs"
DEBUG_DIR = "debug"


def leer_operaciones(csv_path):
    """Lee el CSV de entrada. Devuelve (operaciones, duplicados) deduplicando
    por id_operacion y conservando el orden de aparición.

    A diferencia del robot de cierre, aquí la columna 'analista' es
    obligatoria y no tiene valor por defecto: si falta para alguna fila no
    duplicada, se corta la carga con un error claro en vez de adivinar."""
    vistos = set()
    duplicados = []
    operaciones = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columnas_requeridas = {"id_operacion", "analista"}
        if not reader.fieldnames or not columnas_requeridas.issubset(reader.fieldnames):
            raise ValueError("El CSV debe tener las columnas 'id_operacion' y 'analista'")
        for num_fila, fila in enumerate(reader, start=2):  # fila 1 es la cabecera
            hp = (fila.get("id_operacion") or "").strip()
            if not hp:
                continue
            if hp in vistos:
                duplicados.append(hp)
                continue
            analista = (fila.get("analista") or "").strip()
            if not analista:
                raise ValueError(
                    f"Fila {num_fila} del CSV: '{hp}' no tiene un analista "
                    "asignado (la columna 'analista' es obligatoria)"
                )
            vistos.add(hp)
            operaciones.append({"id_operacion": hp, "analista": analista})
    return operaciones, duplicados


def listar_logs():
    return sorted(glob.glob(os.path.join(LOGS_DIR, "resultado_reasignacion_*.csv")))


def preguntar_reanudar():
    logs = listar_logs()
    if not logs:
        return False
    respuesta = input(
        f"Se encontraron {len(logs)} log(s) anterior(es) en '{LOGS_DIR}'. "
        "¿Continuar y omitir las operaciones ya reasignadas de verdad "
        "(ok reales, no dry-run), o empezar de cero? [continuar/cero]: "
    ).strip().lower()
    return respuesta.startswith("cont")


def cargar_ya_ok(reanudar):
    """Suma los 'ok' reales (no dry-run) de TODOS los logs anteriores en
    logs/, no solo del último, igual que pide la reanudación de este
    robot."""
    if not reanudar:
        return set()
    ok = set()
    logs = listar_logs()
    for log in logs:
        with open(log, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for fila in reader:
                detalle = fila.get("detalle") or ""
                if fila.get("estado") == "ok" and not detalle.startswith("[DRY-RUN]"):
                    ok.add(fila.get("id_operacion"))
    print(f"Reanudando: {len(ok)} operaciones ya reasignadas de verdad en {len(logs)} log(s) anteriores se omitirán.")
    return ok


def formatear_duracion(segundos):
    segundos = int(segundos)
    horas, resto = divmod(segundos, 3600)
    minutos, _ = divmod(resto, 60)
    if horas:
        return f"{horas}h {minutos}min"
    return f"{minutos}min"


def nombre_log():
    os.makedirs(LOGS_DIR, exist_ok=True)
    nombre = datetime.now().strftime("resultado_reasignacion_%Y%m%d_%H%M.csv")
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


def procesar_operacion(page, hp, analista_objetivo, produccion):
    """Devuelve (estado, detalle). estado en {"ok", "error", "omitida"}.

    En modo no-producción (dry-run) llega hasta tener el analista
    seleccionado en el desplegable y pulsa "Cancelar" en vez de "Confirmar".

    Deja propagar SesionCaducadaError: eso corta el lote entero, no se trata
    como un error puntual de esta operación."""
    try:
        page.goto(PERSEFONE_URL)  # estado limpio: sin restos de la operación anterior
        if pp_page.pagina_es_login(page):
            raise pp_page.SesionCaducadaError(
                "Persefone ha devuelto la pantalla de login: la sesión ha caducado"
            )

        pp_page.buscar_operacion(page, hp)
        resultado = pp_page.hay_resultado(page, hp)
        try:
            resultado.first.wait_for(state="visible", timeout=8000)
        except PlaywrightTimeoutError:
            captura(page, hp, "01_sin_resultado")
            return "omitida", "No encontrada"
        captura(page, hp, "01_resultado_busqueda")

        pp_page.abrir_resultado(page, hp)
        captura(page, hp, "02_ficha_abierta")

        # Referencia fija al botón "Reasignar" de Analista, capturada una
        # sola vez: evita que una relectura posicional (".first") acabe
        # apuntando al bloque de Cualificador si la página cambia algo
        # alrededor tras confirmar (bug real visto en producción).
        boton_reasignar = pp_page.obtener_boton_reasignar(page)

        texto_esperado = pp_page.nombre_ficha(analista_objetivo)
        analista_actual = pp_page.leer_analista_actual(boton_reasignar)
        if analista_actual and analista_actual.strip() == texto_esperado.strip():
            # Se registra como "ok" (no "omitida"): el estado objetivo ya
            # está conseguido, así que en una reanudación futura debe
            # contar como hecha y no reabrir esta ficha otra vez.
            return "ok", f"Ya estaba asignada a {analista_actual}"

        nota_cerrada = ""
        if pp_page.operacion_esta_cerrada(page):
            nota_cerrada = " (Operación cerrada, se reasignó igualmente)"

        try:
            dialogo = pp_page.click_reasignar_analista(boton_reasignar, page)
        except PlaywrightTimeoutError:
            captura(page, hp, "03_sin_boton_reasignar")
            return "error", "No aparece el botón 'Reasignar' de Analista"
        captura(page, hp, "03_modal_abierto")

        try:
            pp_page.seleccionar_analista(dialogo, analista_objetivo)
        except PlaywrightTimeoutError:
            captura(page, hp, "04_sin_opcion_analista")
            return "error", f"El desplegable no marcó la opción '{analista_objetivo}'"
        captura(page, hp, "04_analista_seleccionado")

        if produccion:
            pp_page.confirmar(dialogo)
        else:
            pp_page.cancelar(dialogo)
        captura(page, hp, "05_confirmado" if produccion else "05_cancelado")

        try:
            dialogo.wait_for(state="hidden", timeout=5000)
        except PlaywrightTimeoutError:
            captura(page, hp, "99_error")
            return "error", "El modal no se cerró tras confirmar/cancelar"

        if produccion:
            # Post-condición: si algo bloqueó el envío sin lanzar excepción,
            # no dar el resultado por bueno solo porque el modal se cerró.
            # La ficha puede tardar un instante en refrescar el nombre tras
            # confirmar (visto varias veces en producción: reasignaciones
            # que sí se habían aplicado de verdad se leyeron con el nombre
            # antiguo por comprobarlo demasiado pronto), así que se
            # reintenta durante varios segundos antes de dar el error por
            # bueno. Con el ritmo más rápido entre operaciones hay menos
            # margen "gratis" para que el backend se ponga al día, así que
            # la ventana se amplió de 4 a 10 segundos.
            limite_verificacion = time.time() + 10
            nuevo_analista = pp_page.leer_analista_actual(boton_reasignar)
            while (
                nuevo_analista.strip() != texto_esperado.strip()
                and time.time() < limite_verificacion
            ):
                time.sleep(0.5)
                nuevo_analista = pp_page.leer_analista_actual(boton_reasignar)

            if not nuevo_analista or nuevo_analista.strip() != texto_esperado.strip():
                captura(page, hp, "99_error")
                return "error", (
                    f"Tras confirmar, la ficha muestra '{nuevo_analista}' "
                    f"en vez de '{analista_objetivo}'"
                )
            return "ok", f"Reasignada a {analista_objetivo}{nota_cerrada}"
        else:
            return "ok", (
                f"[DRY-RUN] Analista '{analista_objetivo}' verificado en el "
                f"desplegable, no se confirmó{nota_cerrada}"
            )

    except pp_page.SesionCaducadaError:
        raise
    except Exception as exc:
        captura(page, hp, "99_error")
        return "error", str(exc)


def main():
    parser = argparse.ArgumentParser(description="Robot de reasignación masiva de analista en Persefone")
    parser.add_argument("--csv", default=CSV_INPUT_DEFAULT, help="CSV de entrada (default: operaciones.csv)")
    parser.add_argument("--produccion", action="store_true", help="Confirma reasignaciones reales (por defecto es dry-run)")
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

    modo = "PRODUCCIÓN (reasignación real)" if args.produccion else "DRY-RUN (simulación, no confirma)"
    print(f"Modo: {modo}. Operaciones a procesar: {len(pendientes)} (de {len(operaciones)} en el CSV)")

    log_path = nombre_log()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context(storage_state=STORAGE_STATE_PATH)
        page = context.new_page()
        page.goto(PERSEFONE_URL)

        # Detectar sesión inválida al arrancar el lote, no solo a mitad.
        if pp_page.pagina_es_login(page):
            browser.close()
            sys.exit(
                "Persefone ha devuelto la pantalla de login: la sesión ha "
                "caducado. Ejecuta 'python auth_setup.py' y vuelve a lanzar el robot."
            )

        with open(log_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id_operacion", "analista_objetivo", "estado", "detalle"])

            for hp in duplicados:
                writer.writerow([hp, "", "omitida", "Duplicado en el CSV de entrada"])
            f.flush()

            total = len(pendientes)
            inicio = time.time()
            for idx, op in enumerate(pendientes, start=1):
                hp = op["id_operacion"]
                analista_objetivo = op["analista"]
                try:
                    estado, detalle = procesar_operacion(page, hp, analista_objetivo, args.produccion)
                except pp_page.SesionCaducadaError as exc:
                    writer.writerow([hp, analista_objetivo, "error", "Sesión caducada: lote detenido"])
                    f.flush()
                    print(
                        f"\n⚠ {exc}\n"
                        "Se detiene el lote (quedan operaciones sin procesar). "
                        "Ejecuta 'python auth_setup.py' e inténtalo de nuevo."
                    )
                    break

                writer.writerow([hp, analista_objetivo, estado, detalle])
                f.flush()

                transcurrido = time.time() - inicio
                promedio = transcurrido / idx
                restantes = total - idx
                eta_segundos = promedio * restantes
                hora_fin = (datetime.now() + timedelta(seconds=eta_segundos)).strftime("%H:%M")
                print(
                    f"[{idx}/{total}] {hp}: {estado} - {detalle} "
                    f"| {analista_objetivo} | restan ~{formatear_duracion(eta_segundos)} (fin aprox. {hora_fin})"
                )

                time.sleep(random.uniform(0.4, 1))
            else:
                duracion_total = formatear_duracion(time.time() - inicio) if total else "0min"
                print(f"\nProcesadas {total}/{total} operaciones en {duracion_total}.")

        browser.close()

    _imprimir_resumen_final(log_path)


def _imprimir_resumen_final(log_path):
    contadores = {"ok": 0, "error": 0, "omitida": 0}
    with open(log_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for fila in reader:
            estado = fila.get("estado")
            if estado in contadores:
                contadores[estado] += 1
    total = sum(contadores.values())
    print(
        f"\nResumen: {total} filas en el log | ok: {contadores['ok']} | "
        f"error: {contadores['error']} | omitida: {contadores['omitida']}"
    )
    print(f"Log guardado en '{log_path}'.")


if __name__ == "__main__":
    main()
