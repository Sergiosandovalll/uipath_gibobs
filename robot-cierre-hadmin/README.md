# Robot de cierre masivo de operaciones en Hadmin

Automatiza con Playwright el cierre de operaciones en **Hadmin**
(`https://hadmin.gibobs.com/`, no es Persefone, sin Citrix), rellenando el
modal "Cerrar hipoteca" con los mismos valores fijos para cada HP de un
listado.

## Estado actual

⚠️ **Pendiente de selectores reales.** El archivo `selectors.py` tiene
placeholders (`"PENDIENTE"`) en vez de los selectores del DOM de Hadmin.
El resto del robot (lectura de CSV, deduplicado, dry-run/producción, log,
reanudación) ya está completo y no hace falta tocarlo.

### Cómo obtener y rellenar los selectores

1. En tu propio equipo (con acceso a Hadmin), ejecuta:
   ```bash
   playwright codegen https://hadmin.gibobs.com/
   ```
2. Inicia sesión y haz una vez, a mano, el flujo completo: buscar un HP →
   clic en el resultado → clic en "Finalizar" → rellenar el modal "Cerrar
   hipoteca" (tareas asociadas, solicitante, motivo, contenido) →
   **cancelar** el modal en vez de confirmar si no quieres cerrar una
   operación real de verdad.
3. Copia del código Python que genera Playwright los selectores de cada
   elemento y pégalos en `selectors.py`, sustituyendo cada `"PENDIENTE"`.

## Instalación

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

## Uso

### 1. Iniciar sesión (una vez, o cuando caduque)

```bash
python auth_setup.py
```

Se abre un navegador. Inicia sesión manualmente en Hadmin y pulsa Enter en
la terminal cuando ya estés dentro. Esto guarda `storage_state.json` (no se
sube a git) para que las siguientes ejecuciones no pidan login.

### 2. Preparar el CSV de entrada

Copia `operaciones.example.csv` como `operaciones.csv` (tampoco se sube a
git, puede contener HPs reales de clientes) con al menos la columna
`id_operacion`:

```csv
id_operacion,motivo,contenido
HP-000123456,,
```

Las columnas `motivo` y `contenido` son opcionales: si vienen vacías o no
existen, se usan los valores fijos por defecto (`Ilocalizable` y el texto
estándar de contenido).

### 3. Ejecutar en modo simulación (por defecto)

```bash
python robot_cierre_hadmin.py
```

Busca cada operación, abre la ficha, rellena el modal y **cancela sin
confirmar**. Sirve para verificar selectores y flujo sin tocar nada real.

### 4. Ejecutar en producción (cierre real)

```bash
python robot_cierre_hadmin.py --produccion
```

Solo con este flag explícito el robot pulsa "Cerrar" de verdad.

### Otras opciones

- `--csv ruta.csv` — usar un CSV distinto de `operaciones.csv`.
- `--headless` — ejecutar sin ventana de navegador visible.

### Reanudar tras un corte

Si el proceso se corta a mitad, al volver a lanzarlo se detecta
automáticamente el último log en `logs/` y se pregunta si quieres continuar
(omitiendo las operaciones ya marcadas `ok`) o empezar de cero.

## Salida

Cada ejecución genera `logs/resultado_cierre_YYYYMMDD_HHMM.csv` con columnas
`id_operacion, estado (ok/error/omitida), detalle`. Los HP duplicados en el
CSV de entrada también quedan registrados ahí como `omitida`.

## Seguridad

`storage_state.json` y `operaciones.csv` están en `.gitignore` porque
pueden contener sesión autenticada y datos reales de clientes: **no se
deben subir nunca al repositorio**.
