# Importar tabla de QuickSight a Google Sheets ("Cruce")

Automatiza con Playwright la exportación de la tabla de la página
**"T1-Sin sabadell"** del análisis de QuickSight

```
https://eu-central-1.quicksight.aws.amazon.com/sn/account/quicksight-report-accounts/analyses/3c0f26de-3942-4240-aca3-58fa7018d892
```

y la importa (reemplazando el contenido previo) en la pestaña **"Cruce"**
del Google Sheet

```
https://docs.google.com/spreadsheets/d/169IF75Pilomo7S5dY04JyMOqI8zslh_-hUVdNRqYjCQ/edit
```

## Estado actual

⚠️ Los selectores de `quicksight_page.py` (pestaña de página, menú "⋮" del
visual, opción "Export to CSV") están escritos a partir de la estructura
habitual de QuickSight, **no verificados contra la cuenta real**, porque
QuickSight exige sesión iniciada (SSO/MFA) y no hay acceso automatizado a
ella desde aquí. Antes de confiar en el script:

1. Ejecuta `python auth_setup.py` e inicia sesión a mano.
2. Ejecuta `python importar_tabla.py` (sin `--headless`, para ver qué pasa)
   y comprueba que:
   - cambia correctamente a la página "T1-Sin sabadell",
   - encuentra el visual de tabla y consigue exportarlo a CSV.
3. Si algún paso falla, vuelve a capturar los selectores con
   `playwright codegen <url>` haciendo el flujo a mano, y actualiza
   `quicksight_page.py` (es el único archivo que depende del DOM real de
   QuickSight, igual que en `robot-cierre-hadmin/hadmin_page.py`).

Si la página tiene más de una tabla, usa `--visual "Título del visual"`
para indicar cuál exportar.

## Instalación

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

## Configuración

### 1. Sesión de QuickSight

```bash
python auth_setup.py
```

Se abre un navegador. Inicia sesión manualmente (usuario/contraseña y
SSO/MFA si aplica) y pulsa Enter en la terminal cuando el análisis esté
cargado. Esto guarda `storage_state.json` (no se sube a git) para que las
siguientes ejecuciones no pidan login.

### 2. Credenciales de Google Sheets

El script escribe en Sheets con una **cuenta de servicio** de Google Cloud
(no con tu usuario de Google):

1. En Google Cloud Console, crea (o reutiliza) un proyecto y habilita las
   APIs "Google Sheets API" y "Google Drive API".
2. Crea una cuenta de servicio y descarga su clave en formato JSON.
3. Guarda ese JSON como `service_account.json` en esta carpeta (no se sube
   a git), o indica otra ruta con `--credenciales`.
4. Comparte el Google Sheet destino con el email de la cuenta de servicio
   (campo `client_email` del JSON) dándole permiso de **Editor**.

## Uso

```bash
python importar_tabla.py
```

Con ventana de navegador visible por defecto (útil mientras se verifican
los selectores); añade `--headless` para ejecutarlo sin ventana.

### Opciones

- `--pagina "T1-Sin sabadell"` — página (sheet) del análisis a exportar
  (default: `T1-Sin sabadell`).
- `--visual "Título"` — título del visual de tabla a exportar, si la
  página tiene más de una tabla.
- `--sheet-id ID` — ID del Google Sheet destino (por defecto, el del
  Sheet de seguimiento indicado arriba).
- `--pestana "Cruce"` — pestaña destino dentro del Sheet (default:
  `Cruce`; se crea si no existe).
- `--credenciales ruta.json` — ruta al JSON de la cuenta de servicio
  (default: `service_account.json`).
- `--no-limpiar` — no borrar el contenido previo de la pestaña antes de
  pegar la tabla nueva (por defecto sí se limpia, para que la pestaña
  quede como una foto exacta de la tabla de QuickSight).
- `--headless` — ejecutar sin ventana de navegador visible.

## Qué hace exactamente

1. Abre el análisis de QuickSight con la sesión guardada.
2. Cambia a la página `--pagina` (pestañas de sheet, abajo del análisis).
3. Localiza el visual de tabla (por `--visual` si se indica, si no el
   primero que encuentra) y usa su menú "⋮" > "Export to CSV", capturando
   la descarga directamente con Playwright (sin selector de archivos
   manual).
4. Lee el CSV descargado.
5. Conecta con Google Sheets vía la cuenta de servicio, localiza (o crea)
   la pestaña `--pestana` del Sheet `--sheet-id`, la limpia y pega ahí la
   tabla completa (cabecera + filas) empezando en A1.

## Seguridad

`storage_state.json` y `service_account.json` están en `.gitignore` porque
contienen sesión autenticada y credenciales: **no se deben subir nunca al
repositorio**.
