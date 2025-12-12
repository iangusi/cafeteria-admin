from django.db import models
from django.core.validators import MinValueValidator
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from django.contrib.auth.hashers import make_password, check_password as django_check_password
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone


class Empleado(models.Model):
    ROLES = [
        ('barista', 'Barista'),
        ('mesero', 'Mesero'),
        ('gerente', 'Gerente'),
        ('cocinero', 'Cocinero'),
        ('otro', 'Otro'),
    ]
    
    nombre = models.CharField(max_length=100)
    correo = models.EmailField(unique=True, null=True, blank=True)
    celular = models.CharField(max_length=20, null=True, blank=True)
    rol = models.CharField(max_length=20, choices=ROLES)
    pago_por_hora = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)])
    fecha_contratacion = models.DateField(auto_now_add=True)
    activo = models.BooleanField(default=True)
    fecha_desactivacion = models.DateField(null=True, blank=True)

    password = models.CharField(max_length=128, blank=True, help_text="Hash de la contraseña")
    
    class Meta:
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre
    
    def desactivar(self):
        """Marca el empleado como inactivo"""
        self.activo = False
        self.fecha_desactivacion = datetime.now().date()
        self.save()
    
    # Métodos de manejo de contraseña
    def set_password(self, raw_password):
        """Hashea y guarda la contraseña"""
        self.password = make_password(raw_password)
        # NOTA: no hace save() automático para permitir uso en formularios
        return self.password

    def check_password(self, raw_password):
        """Verifica la contraseña (usa Django hashers)"""
        if not self.password:
            return False
        return django_check_password(raw_password, self.password)



class Horario(models.Model):
    DIAS_SEMANA = [
        (0, 'Lunes'),
        (1, 'Martes'),
        (2, 'Miércoles'),
        (3, 'Jueves'),
        (4, 'Viernes'),
        (5, 'Sábado'),
        (6, 'Domingo'),
    ]
    
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='horarios')
    fecha = models.DateField()
    dia_semana = models.IntegerField(choices=DIAS_SEMANA)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    
    class Meta:
        unique_together = ('empleado', 'fecha', 'dia_semana')
        ordering = ['fecha', 'dia_semana', 'hora_inicio']
    
    def __str__(self):
        return f"{self.empleado.nombre} - {self.get_dia_semana_display()} ({self.fecha})"
    
    def get_fecha_dia(self):
        """Retorna la fecha exacta del día en cuestión"""
        fecha_inicio = self.fecha
        fecha_dia = fecha_inicio + timedelta(days=self.dia_semana)
        return fecha_dia


class Asistencia(models.Model):
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='asistencias')
    fecha = models.DateField()
    hora_entrada = models.TimeField(null=True, blank=True)
    hora_salida = models.TimeField(null=True, blank=True)
    notas = models.TextField(null=True, blank=True)  # opcional para observaciones
    
    class Meta:
        # Un empleado solo puede tener una asistencia por fecha (si tu flujo necesita >1, quítalo)
        unique_together = ('empleado', 'fecha')
        ordering = ['-fecha', 'empleado']
    
    def __str__(self):
        return f"{self.empleado.nombre} - {self.fecha}"
    
    def calcular_horas_trabajadas(self):
        """Calcula las horas realmente trabajadas (float horas). Maneja cruces de medianoche."""
        if self.hora_entrada and self.hora_salida:
            entrada_dt = datetime.combine(self.fecha, self.hora_entrada)
            salida_dt = datetime.combine(self.fecha, self.hora_salida)
            # si salida <= entrada asumimos que cruzó a la madrugada siguiente
            if salida_dt <= entrada_dt:
                salida_dt += timedelta(days=1)
            duracion = (salida_dt - entrada_dt).total_seconds() / 3600.0
            return max(0.0, duracion)
        # Si no hay horas completas, intentar calcular con lo que haya
        if self.hora_entrada and not self.hora_salida:
            # no hay salida registrada -> contamos 0 (o podríamos contar hasta ahora)
            return 0.0
        return 0.0


# ==================== NUEVOS MODELOS ====================

class Insumo(models.Model):
    UNIDADES = [
        ('kg', 'Kilogramos'),
        ('g', 'Gramos'),
        ('l', 'Litros'),
        ('ml', 'Mililitros'),
        ('unidad', 'Unidad')
    ]
    
    nombre = models.CharField(max_length=100, unique=True)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    cantidad_min = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    unidad = models.CharField(max_length=10, choices=UNIDADES)
    costo_por_unidad = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    activo = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre
    
    def costo_total(self):
        """Calcula el costo total del insumo en stock"""
        return self.cantidad * self.costo_por_unidad
    
    def esta_bajo_stock(self):
        """Verifica si la cantidad está por debajo del mínimo"""
        return self.cantidad <= self.cantidad_min


class Producto(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre
    
    def costo_total(self):
        """Calcula el costo total de los insumos de la receta"""
        total = 0
        for item in self.receta_items.all():
            total += item.costo_total()
        return total
    
    def margen_ganancia(self):
        """Calcula el margen de ganancia en porcentaje"""
        costo = self.costo_total()
        if costo == 0:
            return 0
        margen = ((self.precio_venta - costo) / costo) * 100
        return round(margen, 2)
    
    def ganancia_unitaria(self):
        """Calcula la ganancia por unidad"""
        return round(self.precio_venta - self.costo_total(), 2)


class ProductoReceta(models.Model):
    """Relación entre Producto e Insumo (receta)"""
    UNIDADES = [
        ('kg', 'Kilogramos'),
        ('g', 'Gramos'),
        ('l', 'Litros'),
        ('ml', 'Mililitros'),
        ('unidad', 'Unidad'),
        ('docena', 'Docena'),
    ]

    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='receta_items')
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name='productos')
    cantidad = models.DecimalField(max_digits=10, decimal_places=3, validators=[MinValueValidator(0)])
    unidad = models.CharField(max_length=10, choices=UNIDADES, default='unidad')

    class Meta:
        unique_together = ('producto', 'insumo')
        ordering = ['insumo']

    def __str__(self):
        return f"{self.producto.nombre} - {self.insumo.nombre} ({self.cantidad} {self.get_unidad_display()})"

    def cantidad_equivalente_insumo(self):
        """
        Convierte la cantidad de la receta a la unidad del insumo para calcular costo.
        Ej: insumo.unidad = 'l', receta.unidad = 'ml' -> convierte ml a litros (1000 ml = 1 l).
        Retorna Decimal en la unidad del insumo.
        """
        receta_u = self.unidad
        insumo_u = self.insumo.unidad
        q = Decimal(self.cantidad)

        # Si ya están en la misma unidad
        if receta_u == insumo_u:
            return q

        # Masa: kg <-> g
        if receta_u == 'kg' and insumo_u == 'g':
            return q * Decimal('1000')
        if receta_u == 'g' and insumo_u == 'kg':
            return q / Decimal('1000')

        # Volumen: l <-> ml
        if receta_u == 'l' and insumo_u == 'ml':
            return q * Decimal('1000')
        if receta_u == 'ml' and insumo_u == 'l':
            return q / Decimal('1000')

        # Unidad <-> Docena
        if receta_u == 'docena' and insumo_u == 'unidad':
            return q * Decimal('12')
        if receta_u == 'unidad' and insumo_u == 'docena':
            return q / Decimal('12')

        # Si son incompatibles (masa <-> volumen), asumimos que no se puede convertir:
        # retornamos la cantidad original (se podría mejorar: lanzar excepción o registrar error)
        return q

    def costo_total(self):
        """
        Calcula el costo total de este ítem de receta teniendo en cuenta la conversión de unidades.
        Se calcula en base a la unidad del insumo: costo = cantidad_equivalente_en_unidad_insumo * costo_por_unidad
        """
        cantidad_equiv = self.cantidad_equivalente_insumo()
        try:
            costo_u = Decimal(self.insumo.costo_por_unidad)
        except Exception:
            costo_u = Decimal('0')
        return round(cantidad_equiv * costo_u, 4)

class Cliente(models.Model):
    nombre = models.CharField(max_length=150)
    correo = models.EmailField(unique=True, null=True, blank=True)
    celular = models.CharField(max_length=30, null=True, blank=True)
    puntos = models.IntegerField(default=0)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha_creacion']

    def __str__(self):
        return self.nombre

    def desactivar(self):
        """Marca el cliente como inactivo (soft-delete)."""
        self.activo = False
        self.save()



# clases de Venta

class Venta(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('finalizada', 'Finalizada'),
    ]

    titulo = models.CharField(max_length=150)
    cliente = models.ForeignKey('Cliente', null=True, blank=True, on_delete=models.SET_NULL, related_name='ventas')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    precio_total_cache = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    costo_total_cache = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    puntos_usados = models.IntegerField(default=0)
    fecha = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f"{self.titulo} ({self.get_estado_display()})"

    def puede_modificar(self):
        return self.estado == 'pendiente'

    def calcular_totales(self):
        precio = Decimal('0.00')
        costo = Decimal('0.00')
        for it in self.items.all():
            precio += (it.precio or Decimal('0.00')) * it.cantidad
            costo += it.calcular_costo_total()
        self.precio_total_cache = precio.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.costo_total_cache = costo.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return self.precio_total_cache, self.costo_total_cache

    @property
    def precio_final(self):
        final = (Decimal(self.precio_total_cache) - Decimal(self.puntos_usados)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if final < Decimal('0.00'):
            final = Decimal('0.00')
        return final

    def aplicar_puntos_auto(self):
        if not self.cliente:
            self.puntos_usados = 0
            return 0
        puntos_disponibles = int(self.cliente.puntos or 0)
        usar = min(puntos_disponibles, int(self.precio_total_cache))
        self.puntos_usados = int(usar)
        return self.puntos_usados

    def descontar_inventario(self):
        for it in self.items.all():
            it.descontar_insumos()

    def asignar_puntos_cliente(self):
        if not self.cliente:
            return 0
        puntos = int(Decimal(self.precio_final) // Decimal('10'))
        if puntos > 0:
            self.cliente.puntos = (self.cliente.puntos or 0) + puntos
            self.cliente.save()
        return puntos

    def finalizar(self):
        if not self.puede_modificar():
            return False
        self.calcular_totales()
        self.aplicar_puntos_auto()
        self.descontar_inventario()
        if self.cliente and self.puntos_usados:
            self.cliente.puntos = max(0, (self.cliente.puntos or 0) - int(self.puntos_usados))
            self.cliente.save()
        self.asignar_puntos_cliente()
        self.estado = 'finalizada'
        self.save()
        return True

    def cancelar(self):
        if self.estado != 'pendiente':
            return False
        self.delete()
        return True


class VentaItem(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey('Producto', null=True, blank=True, on_delete=models.SET_NULL)
    precio = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(0)])
    cantidad = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['id']

    def __str__(self):
        # Como ya no existe nombre, usamos el nombre del producto o un placeholder
        return f"{self.producto.nombre if self.producto else 'Producto'} x{self.cantidad}"

    def calcular_costo_total(self):
        """
        Calcula costo del item en base a la receta del producto (ProductoReceta).
        Ya no se usan recetas personalizadas por item.
        """
        costo = Decimal('0.00')
        if self.producto:
            for pr in self.producto.receta_items.all():
                costo += pr.costo_total()
        return (costo * Decimal(self.cantidad)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def descontar_insumos(self):
        """
        Descuenta del inventario usando la receta del producto.
        """
        if self.producto:
            for pr in self.producto.receta_items.all():
                cantidad_equiv = pr.cantidad_equivalente_insumo()
                total = cantidad_equiv * Decimal(self.cantidad)
                ins = pr.insumo
                ins.cantidad = (ins.cantidad - total).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                ins.save()