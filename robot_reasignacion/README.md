# Robot de reasignación masiva de analista en Persefone

Automatiza con Playwright la reasignación del analista asignado a un
listado de operaciones en **Persefone**
(`https://persefone.gibobs.gibobs.one/dashboard`, no es Hadmin, sin
Citrix), usando el botón "Reasignar" del bloque "Analista" de la ficha.

## Estado actual

⚠️ **PARCIALMENTE CONFIRMADO con `playwright codegen` real.** Confirmado:
login (redirección a `/login` cuando no hay sesión), buscador "Búsqueda
general", resultado de búsqueda por HP, apertura del modal "Reasignar
operación" (combobox con búsqueda de texto) y botón "Confirmar". **Sin
confirmar todavía** (ver los `TODO` en `persefone_page.py`):

- `leer_analista_actual` — no se grabó el bloque "Analista" de "Ficha
  cliente" (necesario para el caso "ya asignada" y para la verificación
  posterior a confirmar).
- `operacion_esta_cerrada` — no se grabó ningún indicador de cierre.
- `cancelar` — solo se probó "Confirmar", no "Cancelar" (el que usa el
  dry-run).
- El botón "Reasignar" se localiza con `.first` sobre todo el texto
  "Reasignar" de la página. Funcionó en la grabación real, pero **depende
  del orden del DOM** entre los bloques "Analista" y "Cualificador" y no
  está verificado de forma robusta. Ver el aviso completo al principio de
  `persefone_page.py`.
- El nombre que muestra el desplegable para "Ana Gisela Gonçalves" es, en
  realidad, **"Ana Gonçalves"** (sin "Gisela") — ya está mapeado en
  `NOMBRE_MOSTRADO_PERSEFONE` en `persefone_page.py`. Falta confirmar si
  "Miguel Cerezal" aparece igual o distinto.

### Verificación obligatoria antes de `--produccion`

1. Ejecuta primero en dry-run (por defecto) contra una o dos operaciones de
   prueba.
2. Revisa `debug/<HP>_03_modal_abierto.png`: confirma a simple vista que el
   modal abierto corresponde a "Analista" y no a "Cualificador".
3. Completa los `TODO` pendientes (ideal: repetir `playwright codegen`
   sobre una ficha real, abriendo la sección "Ficha cliente" y mirando el
   bloque "Analista", y probando el botón "Cancelar" del modal) y
   sustitúyelos en `persefone_page.py` — es el único archivo que depende
   del DOM de Persefone.
4. Solo entonces usa `--produccion`.

## Reglas de negocio implementadas

- **Ya asignada al analista objetivo** → se omite sin abrir el modal
  (`omitida, "Ya estaba asignada a <nombre>"`).
- **Operación cerrada** → se reasigna igual, pero el detalle del log lo
  indica (`"... (Operación cerrada, se reasignó igualmente)"`).
- **No encontrada** → `omitida, "No encontrada"`, sigue con la siguiente.
- **Sesión caducada** (Persefone devuelve la pantalla de login) → corta el
  lote entero al instante, tanto al arrancar como a mitad, en vez de agotar
  cada operación con timeouts.
- **Dos botones "Reasignar"** en la ficha (Analista y Cualificador): el
  robot solo interactúa con el de **Analista**, acotando la búsqueda del
  botón al bloque correspondiente.
- **Post-condición tras confirmar**: en producción, si el modal se cierra
  pero el nombre del analista en la ficha no cambió al valor esperado, se
  registra como `error` en vez de darlo por bueno solo porque no hubo
  excepción.

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

Se abre un navegador. Inicia sesión manualmente en Persefone y pulsa Enter
en la terminal cuando ya estés dentro del panel. Esto guarda
`storage_state.json` (no se sube a git) para que las siguientes ejecuciones
no pidan login.

### 2. Preparar el CSV de entrada

Copia `operaciones.example.csv` como `operaciones.csv` (tampoco se sube a
git, puede contener HPs reales de clientes) con las columnas
`id_operacion` y `analista` — **ambas obligatorias**, no hay valores por
defecto:

```csv
id_operacion,analista
HP-000123456,Miguel Cerezal
HP-000123457,Ana Gisela Gonçalves
```

Si un HP aparece dos veces en el CSV (aunque sea con distinto analista), la
segunda aparición se registra en el log como `omitida, "Duplicado en el
CSV de entrada"` y no se procesa.

### 3. Ejecutar en modo simulación (por defecto)

```bash
python robot_reasignacion.py
```

Busca cada operación, abre la ficha, selecciona el analista objetivo en el
desplegable del modal y **pulsa "Cancelar" sin confirmar**. Sirve para
verificar selectores y flujo sin tocar nada real.

### 4. Ejecutar en producción (reasignación real)

```bash
python robot_reasignacion.py --produccion
```

Solo con este flag explícito el robot pulsa "Confirmar" de verdad.

### Otras opciones

- `--csv ruta.csv` — usar un CSV distinto de `operaciones.csv`.
- `--headless` — ejecutar sin ventana de navegador visible.

### Reanudar tras un corte

Si el proceso se corta a mitad (o se detiene por sesión caducada), al
volver a lanzarlo se detecta automáticamente si hay logs anteriores en
`logs/` y se pregunta si quieres continuar (omitiendo las operaciones que
ya tengan una reasignación **real** confirmada en cualquiera de los logs
anteriores, no solo el último) o empezar de cero.

### Comprobar pendientes sin abrir el navegador

```bash
python verificar_pendientes.py
```

Cuenta, a partir del CSV y de todos los logs en `logs/`, cuántas
operaciones siguen sin reasignar de verdad.

## Salida

Cada ejecución genera `logs/resultado_reasignacion_YYYYMMDD_HHMM.csv` con
columnas `id_operacion, analista_objetivo, estado (ok/error/omitida),
detalle`. Los HP duplicados en el CSV de entrada también quedan
registrados ahí como `omitida`. Al terminar se imprime un resumen
(procesadas, ok/error/omitida) y la ruta del log.

## Capturas de depuración

En `debug/` se guarda una captura por cada paso relevante de cada
operación (`HP-XXXXXXXX_NN_paso.png`): búsqueda, ficha abierta, modal
abierto, analista seleccionado, tras confirmar/cancelar, y una captura
`_99_error` si algo falla.

## Seguridad

`storage_state.json` y `operaciones.csv` están en `.gitignore` porque
pueden contener sesión autenticada y datos reales de clientes: **no se
deben subir nunca al repositorio**.
