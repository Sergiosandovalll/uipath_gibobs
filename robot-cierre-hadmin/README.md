# Robot de cierre masivo de operaciones en Hadmin

Automatiza con Playwright el cierre de operaciones en **Hadmin**
(`https://hadmin.gibobs.com/`, no es Persefone, sin Citrix), rellenando el
modal "Cerrar hipoteca" con los mismos valores fijos para cada HP de un
listado.

## Estado actual

✅ Flujo completo verificado de punta a punta contra Hadmin real (dry-run y
`--produccion`, incluyendo un cierre real de una operación de prueba):
búsqueda, apertura de ficha, modal "Cerrar hipoteca" (tareas, solicitante,
motivo, contenido en el editor Draft.js) y confirmación con "Cerrar" /
"Cancelar". Los selectores viven en `hadmin_page.py`.

Detalles que costó averiguar y conviene recordar si algo deja de funcionar:

- Los desplegables del modal son componentes custom (no `<select>`
  nativos): hay que hacer clic para abrirlos y luego clic en el texto de
  la opción. Algunas opciones dejan momentáneamente un nodo duplicado
  (oculto) con el mismo texto mientras se abren/cierran, así que en vez de
  un índice fijo (`nth`) se usa `click_texto_visible()`, que espera a que
  haya una coincidencia realmente visible y hace clic en esa.
- El editor de "Contenido" es Draft.js: no acepta `.fill()` de forma
  fiable, hay que enfocarlo y escribir con `page.keyboard.type()`.

### Si algo cambia en la interfaz de Hadmin

Todo lo que depende del DOM real vive en `hadmin_page.py` (no en
`robot_cierre_hadmin.py`). Para volver a capturar selectores:

```bash
playwright codegen https://hadmin.gibobs.com/
```

haz el flujo a mano y actualiza la función correspondiente en
`hadmin_page.py`.

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
