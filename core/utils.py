from datetime import datetime, timedelta, date, timezone
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction

from .models import Horario, Asistencia, Producto, ProductoReceta

def obtener_lunes_semana(fecha=None):
    """
    Obtiene el lunes de la semana de la fecha indicada.
    Si fecha es None, toma hoy.
    """
    if fecha is None:
        fecha = datetime.now().date()
    if isinstance(fecha, datetime):
        fecha = fecha.date()
    dia_semana = fecha.weekday()  # 0 = lunes
    lunes = fecha - timedelta(days=dia_semana)
    return lunes

def _time_diff_in_hours(h_inicio, h_fin):
    """
    Calcula la diferencia en horas entre dos objetos time.
    Si h_fin <= h_inicio se asume que cruza a la siguiente jornada (añade 1 día).
    Retorna Decimal de horas.
    """
    if h_inicio is None or h_fin is None:
        return Decimal('0')
    dt_base = date(2000, 1, 1)
    inicio = datetime.combine(dt_base, h_inicio)
    fin = datetime.combine(dt_base, h_fin)
    if fin <= inicio:
        fin += timedelta(days=1)
    segundos = (fin - inicio).total_seconds()
    horas = Decimal(str(segundos / 3600.0))
    return horas

def calcular_horas_asignadas(empleado, fecha_inicio=None, fecha_fin=None):
    """
    Calcula las horas asignadas a un empleado entre fecha_inicio y fecha_fin.
    - fecha_inicio/fecha_fin pueden ser date o None. Si ambos None se toma hoy.
    - Los registros Horario guardan la fecha del LUNES de la semana y dia_semana (0-6).
      Por eso hay que convertir cada Horario a la fecha real y comprobar si está dentro del rango.
    - Se hace una consulta limitada por el rango de 'lunes' entre lunes_inicio y lunes_fin,
      para evitar traer todos los horarios.
    Devuelve Decimal redondeado a 2 decimales.
    """
    # Normalizar fechas
    hoy = datetime.now().date()
    if fecha_inicio is None and fecha_fin is None:
        fecha_inicio = fecha_fin = hoy
    elif fecha_inicio is None:
        fecha_inicio = fecha_fin
    elif fecha_fin is None:
        fecha_fin = fecha_inicio

    # Asegurar que son objetos date
    if isinstance(fecha_inicio, datetime):
        fecha_inicio = fecha_inicio.date()
    if isinstance(fecha_fin, datetime):
        fecha_fin = fecha_fin.date()

    # Si el rango viene invertido, corregirlo
    if fecha_inicio > fecha_fin:
        fecha_inicio, fecha_fin = fecha_fin, fecha_inicio

    # Calcular lunes de los límites para filtrar horarios
    lunes_inicio = obtener_lunes_semana(fecha_inicio)
    lunes_fin = obtener_lunes_semana(fecha_fin)

    total_horas = Decimal('0')

    # Obtener horarios cuyo 'lunes' está entre lunes_inicio y lunes_fin
    horarios = Horario.objects.filter(
        empleado=empleado,
        fecha__range=[lunes_inicio, lunes_fin]
    )

    for horario in horarios:
        fecha_dia = horario.get_fecha_dia()  # fecha real del día (lunes + dia_semana)
        # Incluir solo si la fecha real del bloque está dentro del intervalo solicitado
        if fecha_inicio <= fecha_dia <= fecha_fin:
            horas = _time_diff_in_hours(horario.hora_inicio, horario.hora_fin)
            total_horas += horas

    # Redondear a 2 decimales
    total_horas = total_horas.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return total_horas

def calcular_horas_trabajadas(empleado, fecha_inicio, fecha_fin):
    # Normalizar fechas simple (se asume que caller garantiza)
    if isinstance(fecha_inicio, datetime):
        fecha_inicio = fecha_inicio.date()
    if isinstance(fecha_fin, datetime):
        fecha_fin = fecha_fin.date()

    # Contar asistencias donde haya por lo menos hora_entrada o hora_salida
    from django.db.models import Q
    asistencias = Asistencia.objects.filter(
        empleado=empleado,
        fecha__range=[fecha_inicio, fecha_fin]
    ).filter(Q(hora_entrada__isnull=False) | Q(hora_salida__isnull=False))

    total = Decimal('0')
    for a in asistencias:
        horas = Decimal(str(a.calcular_horas_trabajadas()))
        total += horas

    total = total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return total

def calcular_pago_final(empleado, fecha_inicio, fecha_fin):
    """
    Calcula el pago final según horas trabajadas y pago_por_hora.
    """
    horas_trabajadas = calcular_horas_trabajadas(empleado, fecha_inicio, fecha_fin)
    pago_por_hora = Decimal(str(empleado.pago_por_hora or 0))
    pago = (horas_trabajadas * pago_por_hora).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return pago

def obtener_estado_bloque_horario(horario):
    """
    Ahora determina el estado del bloque consultando las asistencias del empleado
    para la fecha real del bloque (fecha_dia), no por relación FK.
    Estados:
      - 'blanco' = fecha futura
      - 'rojo'   = sin asistencia (no hay hora_entrada/ salida)
      - 'amarillo' = asistencia parcial (horas_trabajadas > 0 pero < horas_asignadas)
      - 'verde'  = cumplió (>= 95% de horas asignadas)
    """
    fecha_dia = horario.get_fecha_dia()
    hoy = datetime.now().date()

    if fecha_dia > hoy:
        return 'blanco'

    from django.db.models import Q
    asistencia = Asistencia.objects.filter(
        empleado=horario.empleado,
        fecha=fecha_dia
    ).filter(Q(hora_entrada__isnull=False) | Q(hora_salida__isnull=False)).first()

    if not asistencia:
        return 'rojo'

    horas_trabajadas = asistencia.calcular_horas_trabajadas()
    inicio_dt = datetime.combine(fecha_dia, horario.hora_inicio)
    fin_dt = datetime.combine(fecha_dia, horario.hora_fin)
    if fin_dt <= inicio_dt:
        fin_dt += timedelta(days=1)
    horas_asignadas = (fin_dt - inicio_dt).total_seconds() / 3600.0

    if horas_trabajadas >= (horas_asignadas * 0.95):
        return 'verde'
    elif horas_trabajadas > 0:
        return 'amarillo'
    else:
        return 'rojo'