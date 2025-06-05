# utils.py

import datetime
from flask import flash
# CORRECCIÓN: Importa db directamente desde models, no desde app para evitar circulares
from models import db, Subtarea # <--- ¡CAMBIO AQUÍ! Importa db y Subtarea

# CORRECCIÓN: Renombra la función para que coincida con la importación en app.py
# Y actualiza la lógica para usar Subtarea
def check_and_update_overdue_tasks_for_collection(subtareas_collection):
    """
    Verifica las subtareas en una colección dada y actualiza su estado a 'Retrasado'
    si la fecha límite ha pasado y el estado no es 'Finalizado', 'Cancelado' o ya 'Retrasado'.
    """
    today = datetime.date.today()
    num_overdue_updated = 0

    for subtarea in subtareas_collection: # Iterar sobre la colección pasada
        # CORRECCIÓN: Usa los atributos de Subtarea (fecha_limite, estado)
        if (subtarea.fecha_limite and
                subtarea.fecha_limite < today and
                subtarea.estado not in ['Finalizado', 'Cancelado', 'Retrasado']):
            subtarea.estado = 'Retrasado' # Marcar como retrasado
            # Si tienes un campo 'ultima_actualizacion' o 'last_updated' en Subtarea:
            # subtarea.ultima_actualizacion = datetime.datetime.utcnow()
            db.session.add(subtarea) # Añadir a la sesión para guardar cambios
            num_overdue_updated += 1

    if num_overdue_updated > 0:
        db.session.commit() # Guarda los cambios solo si hay algo que actualizar
        flash(f'¡Atención! Se actualizaron {num_overdue_updated} subtarea(s) a "Retrasado". Por favor, revisa y actualízalas.', 'danger')

# CORRECCIÓN: Función es_retrasada (asegúrate de que esta sea la que se usa)
def es_retrasada(subtarea):
    """
    Verifica si una subtarea está retrasada.
    """
    return (subtarea.fecha_limite and
            subtarea.fecha_limite < datetime.date.today() and
            subtarea.estado not in ['Finalizado', 'Suspendido', 'Cancelado'])