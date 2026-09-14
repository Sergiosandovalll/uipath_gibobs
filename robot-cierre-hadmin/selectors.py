"""
Selectores del DOM real de Hadmin (https://hadmin.gibobs.com/).

PENDIENTE DE RELLENAR. Todos los valores marcados como "PENDIENTE" deben
sustituirse por los selectores reales, obtenidos ejecutando en tu propio
equipo (con sesión iniciada en Hadmin):

    playwright codegen https://hadmin.gibobs.com/

y haciendo una vez, a mano, el flujo completo: buscar un HP -> clic en el
resultado -> clic en "Finalizar" -> rellenar el modal "Cerrar hipoteca" ->
(cancelar en vez de confirmar si no quieres cerrar una operación real).
Del código Python que genera Playwright se copian aquí los selectores de
cada paso.

Este es el ÚNICO archivo que hay que tocar para adaptar el robot a cambios
de interfaz en Hadmin: el resto de la lógica (robot_cierre_hadmin.py) no
depende de la estructura concreta del DOM.
"""

# Barra de búsqueda superior de Hadmin
SEARCH_INPUT = "PENDIENTE"

# Enlace/número de la operación en la lista de resultados de búsqueda
# (el primer resultado que aparece debajo de la barra al escribir el HP)
SEARCH_RESULT_LINK = "PENDIENTE"

# Botón rojo "Finalizar" (arriba a la derecha de la ficha, junto a "Dormir")
BTN_FINALIZAR = "PENDIENTE"

# Modal "Cerrar hipoteca"
# --------------------------------------------------------------------------

# Desplegable "¿Quieres cerrar también las tareas asociadas a esta operación?"
SELECT_CERRAR_TAREAS = "PENDIENTE"
OPCION_CERRAR_TAREAS_SI = "Si"

# Desplegable "Solicitante de Finalización"
SELECT_SOLICITANTE = "PENDIENTE"
OPCION_SOLICITANTE_GIBOBS = "Por solicitud de Gibobs"

# Desplegable "Motivos de Finalización" (aparece SOLO tras elegir
# "Por solicitud de Gibobs" en el desplegable anterior)
SELECT_MOTIVO = "PENDIENTE"
OPCION_MOTIVO_ILOCALIZABLE = "Ilocalizable"

# Editor de texto enriquecido "Contenido"
CONTENIDO_EDITOR = "PENDIENTE"

# Botones del modal
BTN_CERRAR_MODAL = "PENDIENTE"  # confirma el cierre real
BTN_CANCELAR_MODAL = "PENDIENTE"  # cierra el modal sin aplicar cambios
