"""
Escritura en Google Sheets vía gspread + una cuenta de servicio.

Requiere un JSON de credenciales de cuenta de servicio de Google Cloud
(APIs "Google Sheets API" y "Google Drive API" habilitadas) y que la hoja
de cálculo destino esté compartida con el email de esa cuenta de servicio
(campo "client_email" del JSON) con permiso de Editor.
"""
import csv

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


def conectar(credenciales_path):
    creds = Credentials.from_service_account_file(credenciales_path, scopes=SCOPES)
    return gspread.authorize(creds)


def obtener_hoja(cliente, sheet_id, nombre_pestana):
    """Devuelve la worksheet 'nombre_pestana' del spreadsheet 'sheet_id',
    creándola si no existe todavía."""
    spreadsheet = cliente.open_by_key(sheet_id)
    try:
        return spreadsheet.worksheet(nombre_pestana)
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=nombre_pestana, rows=1000, cols=26)


def leer_csv(csv_path):
    """Lee el CSV exportado de QuickSight y devuelve una lista de filas
    (listas de strings), tal cual, para volcar directamente en Sheets."""
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        return [fila for fila in csv.reader(f)]


def volcar_tabla(hoja, filas, limpiar=True):
    """Escribe 'filas' (incluyendo cabecera) empezando en A1. Si 'limpiar'
    es True, primero borra el contenido previo de la pestaña para que la
    importación deje la tabla exactamente como viene de QuickSight."""
    if limpiar:
        hoja.clear()
    if not filas:
        return
    hoja.update(range_name="A1", values=filas, value_input_option="USER_ENTERED")
