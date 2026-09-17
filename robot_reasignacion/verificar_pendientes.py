"""
Chequeo rápido (sin abrir navegador) de cuántas operaciones del CSV de
entrada siguen pendientes de reasignar de verdad, según los logs en logs/.

Uso:
    python verificar_pendientes.py
    python verificar_pendientes.py --csv otro.csv
"""
import argparse
import csv
import glob
import os
import sys

LOGS_DIR = "logs"
CSV_INPUT_DEFAULT = "operaciones.csv"


def leer_csv(csv_path):
    """Lee id_operacion y analista, deduplicando por id_operacion
    conservando el orden de aparición (igual criterio que el robot)."""
    vistos = set()
    operaciones = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for fila in reader:
            hp = (fila.get("id_operacion") or "").strip()
            if not hp or hp in vistos:
                continue
            vistos.add(hp)
            operaciones.append((hp, (fila.get("analista") or "").strip()))
    return operaciones


def cargar_ok_reales():
    """Recorre TODOS los logs anteriores (no solo el último) y devuelve el
    conjunto de HP con una reasignación real (no dry-run) confirmada."""
    ok = {}
    for log in sorted(glob.glob(os.path.join(LOGS_DIR, "resultado_reasignacion_*.csv"))):
        with open(log, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for fila in reader:
                detalle = fila.get("detalle") or ""
                if fila.get("estado") == "ok" and not detalle.startswith("[DRY-RUN]"):
                    ok[fila.get("id_operacion")] = log
    return ok


def main():
    parser = argparse.ArgumentParser(
        description="Comprueba cuántas operaciones del CSV siguen pendientes de reasignar de verdad"
    )
    parser.add_argument("--csv", default=CSV_INPUT_DEFAULT, help="CSV de entrada (default: operaciones.csv)")
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        sys.exit(f"No existe el CSV de entrada '{args.csv}'.")

    operaciones = leer_csv(args.csv)
    ok_reales = cargar_ok_reales()
    pendientes = [(hp, analista) for hp, analista in operaciones if hp not in ok_reales]

    print(f"Total en el CSV (únicos): {len(operaciones)}")
    print(f"Ya reasignadas de verdad (según logs): {len(ok_reales)}")
    print(f"Pendientes: {len(pendientes)}")

    if pendientes:
        print("\nPrimeras pendientes:")
        for hp, analista in pendientes[:20]:
            print(f"  {hp} -> {analista}")
        if len(pendientes) > 20:
            print(f"  ... y {len(pendientes) - 20} más")


if __name__ == "__main__":
    main()
