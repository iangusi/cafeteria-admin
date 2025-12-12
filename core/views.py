from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, View, DetailView
from django.urls import reverse_lazy, reverse
from django.db.models import Q, F, DecimalField, Sum, Case, When
from django.utils.dateparse import parse_date
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db import IntegrityError
from django.forms import inlineformset_factory, BaseInlineFormSet
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from django.core.exceptions import ValidationError

from .models import Empleado, Horario, Asistencia, Insumo, Producto, ProductoReceta, Cliente, Venta, VentaItem
from .forms import (
    EmpleadoForm, FiltroEmpleadosForm, HorarioForm, FiltroHorariosForm,
    InsumoForm, FiltroInsumoForm, ProductoForm, ProductoRecetaForm, FiltroProductoForm,
    AsistenciaRegistroForm, EmpleadoForm, ClienteForm
)
from .utils import (
    obtener_lunes_semana, calcular_horas_trabajadas,
    calcular_horas_asignadas, calcular_pago_final,
    obtener_estado_bloque_horario,
)


# ==================== VISTAS DE EMPLEADOS ====================

class EmpleadoListView(ListView):
    model = Empleado
    template_name = 'empleados/empleados_list.html'
    context_object_name = 'empleados'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = Empleado.objects.filter(activo=True)
        
        # Obtener parámetros de filtro
        rol = self.request.GET.get('rol')
        if rol:
            queryset = queryset.filter(rol=rol)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Fechas de filtro
        fecha_inicio = self.request.GET.get('fecha_inicio')
        fecha_fin = self.request.GET.get('fecha_fin')
        
        # Si no hay fechas, usar solo el día actual
        if not fecha_inicio and not fecha_fin:
            fecha_inicio = datetime.now().date()
            fecha_fin = datetime.now().date()
        else:
            if fecha_inicio:
                fecha_inicio = parse_date(fecha_inicio)
            if fecha_fin:
                fecha_fin = parse_date(fecha_fin)
        
        # Calcular datos para cada empleado
        empleados_datos = []
        for empleado in context['empleados']:
            horas_trabajadas = calcular_horas_trabajadas(empleado, fecha_inicio, fecha_fin)
            horas_asignadas = calcular_horas_asignadas(empleado, fecha_inicio, fecha_fin)
            pago_final = calcular_pago_final(empleado, fecha_inicio, fecha_fin)
            
            empleados_datos.append({
                'empleado': empleado,
                'horas_trabajadas': horas_trabajadas,
                'horas_asignadas': horas_asignadas,
                'pago_final': pago_final,
            })
        
        context['empleados'] = empleados_datos
        context['formulario_filtro'] = FiltroEmpleadosForm(self.request.GET)
        context['fecha_inicio'] = fecha_inicio
        context['fecha_fin'] = fecha_fin
        
        return context


class EmpleadoCreateView(CreateView):
    model = Empleado
    form_class = EmpleadoForm
    template_name = 'empleados/empleado_form.html'
    success_url = reverse_lazy('empleados_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Empleado creado exitosamente')
        return super().form_valid(form)


class EmpleadoUpdateView(UpdateView):
    model = Empleado
    form_class = EmpleadoForm
    template_name = 'empleados/empleado_form.html'
    success_url = reverse_lazy('empleados_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Empleado actualizado exitosamente')
        return super().form_valid(form)


class EmpleadoDeleteView(View):
    """Vista para desactivar (no eliminar) un empleado"""
    
    def get(self, request, pk):
        """Mostrar confirmación de desactivación"""
        empleado = get_object_or_404(Empleado, pk=pk)
        context = {'object': empleado}
        return render(request, 'empleados/empleado_confirm_delete.html', context)
    
    def post(self, request, pk):
        """Desactivar el empleado"""
        empleado = get_object_or_404(Empleado, pk=pk)
        nombre = empleado.nombre
        empleado.desactivar()
        messages.success(request, f'Empleado {nombre} desactivado exitosamente')
        return redirect('empleados_list')


class EmpleadoDetailView(DetailView):
    model = Empleado
    template_name = 'empleados/empleado_detail.html'
    context_object_name = 'empleado'


# ==================== VISTAS DE HORARIOS ====================

def horarios_list(request):
    """
    Vista principal de horarios — ahora combina Horarios y Asistencias para cada día de la semana.
    Muestra bloques que pueden contener:
      - horario (obligatorio si existe)
      - asistencia (si existe)
      - o solo asistencia (si no había horario)
    """
    from django.utils import timezone
    hoy = timezone.localdate()

    # Obtener la fecha de filtro
    fecha_str = request.GET.get('fecha')
    if fecha_str:
        fecha = parse_date(fecha_str)
    else:
        fecha = datetime.now().date()

    # Obtener el lunes de la semana
    lunes = obtener_lunes_semana(fecha)
    lunes_end = lunes + timedelta(days=6)

    # Genera la semana (lunes a domingo)
    dias_semana = []
    for i in range(7):
        fecha_dia = lunes + timedelta(days=i)
        dias_semana.append({
            'numero': i,
            'nombre': ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'][i],
            'fecha': fecha_dia,
            'es_futuro': fecha_dia > hoy,
        })

    # Obtener horarios del lunes (todos los horarios de esa semana)
    horarios_qs = Horario.objects.filter(
        fecha=lunes
    ).select_related('empleado')

    # Obtener asistencias de la semana
    from django.db.models import Q
    asistencias_qs = Asistencia.objects.filter(
        fecha__range=[lunes, lunes_end]
    ).select_related('empleado')

    # Agrupar horarios por día (0..6)
    horarios_por_dia = {i: [] for i in range(7)}
    # Mapa rápido para encontrar horario por (dia_semana, empleado_id)
    horario_map = {}  # key: (dia, empleado_id) -> horario_block index or object

    for horario in horarios_qs:
        dia = horario.dia_semana
        fecha_dia = horario.get_fecha_dia()
        bloque = {
            'tipo': 'con_horario',        # indica que tiene horario
            'horario': horario,
            'empleado': horario.empleado,
            'hora_inicio': horario.hora_inicio,
            'hora_fin': horario.hora_fin,
            'asistencia': None,           # se completará si existe una Asistencia para ese empleado/fecha
            'fecha_dia': fecha_dia,
            # estado será calculado por obtener_estado_bloque_horario (funciona consultando asistencias por fecha)
            'estado': obtener_estado_bloque_horario(horario),
        }
        horarios_por_dia[dia].append(bloque)
        horario_map[(dia, horario.empleado.pk)] = bloque

    # Procesar asistencias: si corresponde a un horario, pegarla en el bloque existente; si no, crear bloque 'solo_asistencia'
    for asistencia in asistencias_qs:
        dia_idx = (asistencia.fecha - lunes).days
        # Solo procesar si está en el rango [0,6]
        if dia_idx < 0 or dia_idx > 6:
            continue
        empleado_id = asistencia.empleado.pk
        key = (dia_idx, empleado_id)
        if key in horario_map:
            # Adjuntar asistencia al bloque de horario
            bloque = horario_map[key]
            bloque['asistencia'] = asistencia
            # Actualizar estado según nueva info (obtener_estado_bloque_horario ya había consultado, pero con asistencia enlazada será consistente)
            # Si la función obtener_estado_bloque_horario consulta Asistencia por fecha, no es necesario recalcular.
            bloque['estado'] = obtener_estado_bloque_horario(bloque['horario'])
        else:
            # No había horario: crear bloque solo con asistencia
            horas_trab = asistencia.calcular_horas_trabajadas()
            estado = 'blanco' if asistencia.fecha > hoy else ('verde' if horas_trab > 0 else 'rojo')
            bloque_as = {
                'tipo': 'solo_asistencia',
                'horario': None,
                'empleado': asistencia.empleado,
                'hora_inicio': None,
                'hora_fin': None,
                'asistencia': asistencia,
                'fecha_dia': asistencia.fecha,
                'estado': estado,
            }
            horarios_por_dia[dia_idx].append(bloque_as)

    # Ordenar bloques por hora de inicio (si tienen horario) o por hora_entrada (si solo asistencia)
    def sort_key(b):
        if b.get('horario'):
            return b['hora_inicio'] or (b['asistencia'].hora_entrada if b.get('asistencia') else None) or (b['asistencia'].hora_salida if b.get('asistencia') else None) or datetime.min.time()
        else:
            # para solo asistencia: ordenar por hora_entrada, luego hora_salida, luego al final
            if b.get('asistencia'):
                return b['asistencia'].hora_entrada or b['asistencia'].hora_salida or datetime.min.time()
            return datetime.min.time()

    for dia in horarios_por_dia:
        horarios_por_dia[dia].sort(key=sort_key)

    context = {
        'dias_semana': dias_semana,
        'horarios_por_dia': horarios_por_dia,
        'lunes': lunes,
        'fecha_seleccionada': fecha,
        'formulario_filtro': FiltroHorariosForm(request.GET),
        'empleados': Empleado.objects.filter(activo=True),
    }

    return render(request, 'horarios/horarios_list.html', context)

def agregar_horario(request):
    """Agregar nuevo horario"""
    if request.method == 'POST':
        form = HorarioForm(request.POST)
        if form.is_valid():
            lunes = obtener_lunes_semana()
            dia_semana = int(request.POST.get('dia_semana'))
            fecha_dia_horario = lunes + timedelta(days=dia_semana)
            if fecha_dia_horario <= datetime.now().date():
                messages.error(request, 'No puedes agregar horarios para fechas pasadas')
                return redirect('horarios_list')

            empleado_id = request.POST.get('empleado')
            existe_horario = Horario.objects.filter(
                empleado_id=empleado_id,
                fecha=lunes,
                dia_semana=dia_semana
            ).exists()

            if existe_horario:
                messages.error(request, 'Este empleado ya tiene un horario asignado para ese día.')
                return redirect('horarios_list')

            form.instance.fecha = lunes
            try:
                horario = form.save()

                # Antes: creábamos Asistencia ligada al horario.
                # Ahora: si queremos crear un placeholder de asistencia para ese día,
                # creamos una Asistencia sin relacionarla con Horario (porque la relación se eliminó).
                fecha_dia = horario.get_fecha_dia()
                if fecha_dia <= datetime.now().date():
                    Asistencia.objects.get_or_create(
                        empleado=horario.empleado,
                        fecha=fecha_dia,
                        defaults={'hora_entrada': None, 'hora_salida': None}
                    )

                messages.success(request, 'Horario creado exitosamente')
            except IntegrityError:
                messages.error(request, 'Error: Este empleado ya tiene un horario asignado para ese día.')
                return redirect('horarios_list')

            return redirect('horarios_list')
    else:
        form = HorarioForm()
    
    context = {
        'form': form,
        'titulo': 'Agregar Horario',
    }
    return render(request, 'horarios/horario_form.html', context)


def editar_horario(request, pk):
    """Editar horario existente"""
    horario = get_object_or_404(Horario, pk=pk)
    
    # Verificar que sea futuro
    fecha_dia = horario.get_fecha_dia()
    if fecha_dia <= datetime.now().date():
        messages.error(request, 'No puedes editar horarios pasados')
        return redirect('horarios_list')
    
    if request.method == 'POST':
        form = HorarioForm(request.POST, instance=horario)
        if form.is_valid():
            # Verificar si hay conflicto con otro horario
            empleado_id = request.POST.get('empleado')
            dia_semana = int(request.POST.get('dia_semana'))
            
            existe_conflicto = Horario.objects.filter(
                empleado_id=empleado_id,
                fecha=horario.fecha,
                dia_semana=dia_semana
            ).exclude(pk=horario.pk).exists()
            
            if existe_conflicto:
                messages.error(
                    request, 
                    'Error: Este empleado ya tiene otro horario asignado para ese día.'
                )
                return redirect('horarios_list')
            
            try:
                form.save()
                messages.success(request, 'Horario actualizado exitosamente')
            except IntegrityError:
                messages.error(request, 'Error: No se pudo actualizar el horario.')
                return redirect('horarios_list')
            
            return redirect('horarios_list')
    else:
        form = HorarioForm(instance=horario)
    
    context = {
        'form': form,
        'titulo': 'Editar Horario',
    }
    return render(request, 'horarios/horario_form.html', context)


def eliminar_horario(request, pk):
    """Eliminar horario"""
    horario = get_object_or_404(Horario, pk=pk)
    
    # Verificar que sea futuro
    fecha_dia = horario.get_fecha_dia()
    if fecha_dia <= datetime.now().date():
        messages.error(request, 'No puedes eliminar horarios pasados')
        return redirect('horarios_list')
    
    if request.method == 'POST':
        empleado_nombre = horario.empleado.nombre
        dia_nombre = horario.get_dia_semana_display()
        hora_inicio = horario.hora_inicio.strftime('%H:%M')
        hora_fin = horario.hora_fin.strftime('%H:%M')
        
        horario.delete()
        
        messages.success(
            request, 
            f'✓ Horario de {empleado_nombre} el {dia_nombre} ({hora_inicio} - {hora_fin}) eliminado exitosamente'
        )
        return redirect('horarios_list')
    
    context = {'horario': horario}
    return render(request, 'horarios/horario_confirm_delete.html', context)


# ==================== VISTAS DE INVENTARIO ====================

class InsumoListView(ListView):
    model = Insumo
    template_name = 'inventario/insumo_list.html'
    context_object_name = 'insumos'
    paginate_by = 15
    
    def get_queryset(self):
        queryset = Insumo.objects.filter(activo=True)
        
        # Filtro de búsqueda
        busqueda = self.request.GET.get('busqueda')
        if busqueda:
            queryset = queryset.filter(
                Q(nombre__icontains=busqueda) | Q(codigo_barra__icontains=busqueda)
            )
        
        # Filtro de bajo stock
        bajo_stock = self.request.GET.get('bajo_stock')
        if bajo_stock:
            queryset = queryset.filter(cantidad__lte=F('cantidad_min'))
        
        # Ordenamiento
        orden = self.request.GET.get('orden', 'nombre')
        queryset = queryset.order_by(orden)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Calcular totales
        total_insumos = Insumo.objects.filter(activo=True).count()
        bajo_stock_count = Insumo.objects.filter(
            activo=True, 
            cantidad__lte=F('cantidad_min')
        ).count()
        
        # Calcular costo total del inventario
        costo_total = sum([i.costo_total() for i in context['insumos']])
        
        context['formulario_filtro'] = FiltroInsumoForm(self.request.GET)
        context['total_insumos'] = total_insumos
        context['bajo_stock_count'] = bajo_stock_count
        context['costo_total'] = costo_total
        
        return context


class InsumoCreateView(CreateView):
    model = Insumo
    form_class = InsumoForm
    template_name = 'inventario/insumo_form.html'
    success_url = reverse_lazy('insumo_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Insumo creado exitosamente')
        return super().form_valid(form)


class InsumoUpdateView(UpdateView):
    model = Insumo
    form_class = InsumoForm
    template_name = 'inventario/insumo_form.html'
    success_url = reverse_lazy('insumo_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Insumo actualizado exitosamente')
        return super().form_valid(form)


class InsumoDeleteView(View):
    """Vista para desactivar (no eliminar) un insumo"""
    
    def get(self, request, pk):
        """Mostrar confirmación de desactivación"""
        insumo = get_object_or_404(Insumo, pk=pk)
        context = {'object': insumo}
        return render(request, 'inventario/insumo_confirm_delete.html', context)
    
    def post(self, request, pk):
        """Desactivar el insumo"""
        insumo = get_object_or_404(Insumo, pk=pk)
        nombre = insumo.nombre
        insumo.activo = False
        insumo.save()
        messages.success(request, f'Insumo {nombre} desactivado exitosamente')
        return redirect('insumo_list')


# ==================== VISTAS DE PRODUCTOS ====================

class ProductoListView(ListView):
    model = Producto
    template_name = 'productos/producto_list.html'
    context_object_name = 'productos'
    paginate_by = 15
    
    def get_queryset(self):
        queryset = Producto.objects.filter(activo=True).prefetch_related('receta_items')
        
        # Filtro de búsqueda por nombre
        busqueda = self.request.GET.get('busqueda')
        if busqueda:
            queryset = queryset.filter(nombre__icontains=busqueda)
        
        # Filtro por insumo
        insumo_id = self.request.GET.get('insumo')
        if insumo_id:
            queryset = queryset.filter(receta_items__insumo_id=insumo_id).distinct()
        
        # Ordenamiento
        orden = self.request.GET.get('orden', 'nombre')
        queryset = queryset.order_by(orden)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Agregar datos calculados a cada producto
        for producto in context['productos']:
            producto.costo_calculado = producto.costo_total()
            producto.margen = producto.margen_ganancia()
            producto.ganancia = producto.ganancia_unitaria()
        
        context['formulario_filtro'] = FiltroProductoForm(self.request.GET)
        
        return context


class BaseProductoRecetaFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        seen = set()
        duplicates = []
        for form in self.forms:
            # Skip deleted/new empty forms
            if getattr(form, 'cleaned_data', None) is None:
                continue
            if self.can_delete and self._should_delete_form(form):
                continue
            insumo = form.cleaned_data.get('insumo')
            if insumo:
                if insumo.pk in seen:
                    duplicates.append(insumo.nombre)
                else:
                    seen.add(insumo.pk)
        if duplicates:
            # Agregar error al formset (non_form_error) para que aparezca en template
            raise ValidationError("La receta contiene insumos repetidos: %s" % ", ".join(duplicates))


ProductoRecetaFormSet = inlineformset_factory(
    Producto,
    ProductoReceta,
    form=ProductoRecetaForm,
    formset=BaseProductoRecetaFormSet,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False
)


class ProductoCreateView(CreateView):
    model = Producto
    form_class = ProductoForm
    template_name = 'productos/producto_form.html'
    success_url = reverse_lazy('producto_list')

    def get_context_data(self, **kwargs):
        context = {}
        context['form'] = kwargs.get('form', self.get_form())
        context['formset'] = kwargs.get('formset', ProductoRecetaFormSet())
        # expose empty_form HTML for JS cloning
        context['empty_form_html'] = ProductoRecetaFormSet().empty_form.as_table()
        return context

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        formset = ProductoRecetaFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                producto = form.save(commit=False)
                # asegurar activo=True por defecto si no enviado
                if form.cleaned_data.get('activo') is None:
                    producto.activo = True
                producto.save()
                formset.instance = producto
                formset.save()
                messages.success(request, 'Producto creado con su receta.')
                return redirect(self.success_url)
        # si hay errores, re-render con errores (incluyendo formset.non_form_errors)
        context = self.get_context_data(form=form, formset=formset)
        return self.render_to_response(context)


class ProductoUpdateView(UpdateView):
    model = Producto
    form_class = ProductoForm
    template_name = 'productos/producto_form.html'
    success_url = reverse_lazy('producto_list')

    def get_context_data(self, **kwargs):
        context = {}
        context['form'] = kwargs.get('form', self.get_form())
        producto = self.object
        context['formset'] = kwargs.get('formset', ProductoRecetaFormSet(instance=producto))
        context['empty_form_html'] = ProductoRecetaFormSet(instance=producto).empty_form.as_table()
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        formset = ProductoRecetaFormSet(request.POST, instance=self.object)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                producto = form.save()
                formset.instance = producto
                formset.save()
                messages.success(request, 'Producto y receta actualizados.')
                next_url = request.GET.get('next') or self.success_url
                return redirect(next_url)
        context = self.get_context_data(form=form, formset=formset)
        return self.render_to_response(context)

class ProductoDeleteView(View):
    """Vista para desactivar (no eliminar) un producto"""
    
    def get(self, request, pk):
        """Mostrar confirmación de desactivación"""
        producto = get_object_or_404(Producto, pk=pk)
        context = {'object': producto}
        return render(request, 'productos/producto_confirm_delete.html', context)
    
    def post(self, request, pk):
        """Desactivar el producto"""
        producto = get_object_or_404(Producto, pk=pk)
        nombre = producto.nombre
        producto.activo = False
        producto.save()
        messages.success(request, f'Producto {nombre} desactivado exitosamente')
        return redirect('producto_list')


def producto_detalle(request, pk):
    """Vista detallada de un producto con su receta"""
    producto = get_object_or_404(Producto, pk=pk)
    receta = producto.receta_items.all()
    
    context = {
        'producto': producto,
        'receta': receta,
        'costo_total': producto.costo_total(),
        'margen_ganancia': producto.margen_ganancia(),
        'ganancia_unitaria': producto.ganancia_unitaria(),
    }
    return render(request, 'productos/producto_detalle.html', context)


def agregar_receta(request, producto_id):
    """Agregar insumo a la receta de un producto"""
    producto = get_object_or_404(Producto, pk=producto_id)

    if request.method == 'POST':
        form = ProductoRecetaForm(request.POST)
        if form.is_valid():
            # Verificar si el insumo ya existe en la receta
            existe = ProductoReceta.objects.filter(
                producto=producto,
                insumo=form.cleaned_data['insumo']
            ).exists()

            if existe:
                messages.error(request, 'Este insumo ya está en la receta del producto')
                return redirect('producto_detalle', pk=producto_id)

            receta = form.save(commit=False)
            receta.producto = producto
            receta.save()
            messages.success(request, 'Insumo agregado a la receta exitosamente')
            return redirect('producto_detalle', pk=producto_id)
        else:
            messages.error(request, 'Corrige los errores del formulario')
    else:
        form = ProductoRecetaForm()

    context = {
        'form': form,
        'producto': producto,
    }
    return render(request, 'productos/agregar_receta.html', context)


def editar_receta(request, receta_id):
    """Editar cantidad y unidad de insumo en la receta"""
    receta = get_object_or_404(ProductoReceta, pk=receta_id)
    producto = receta.producto

    if request.method == 'POST':
        # Aseguramos que el campo 'insumo' esté presente en POST (en caso de usar input hidden en template)
        post_data = request.POST.copy()
        if 'insumo' not in post_data:
            # si por alguna razón no está, lo tomamos de la receta existente
            post_data['insumo'] = receta.insumo.pk

        form = ProductoRecetaForm(post_data, instance=receta)
        if form.is_valid():
            form.save()
            messages.success(request, 'Insumo de receta actualizado exitosamente')
            return redirect('producto_detalle', pk=producto.pk)
        else:
            # LOG para depuración: imprime errores en consola del servidor
            import logging
            logger = logging.getLogger(__name__)
            logger.error("Errores de formulario editar_receta: %s", form.errors.as_json())
            # También ponemos un mensaje para el usuario
            messages.error(request, 'Corrige los errores del formulario (revisa los mensajes y la consola).')
    else:
        form = ProductoRecetaForm(instance=receta)

    context = {
        'form': form,
        'receta': receta,
    }
    return render(request, 'productos/editar_receta.html', context)

def eliminar_receta(request, receta_id):
    """Eliminar insumo de la receta"""
    receta = get_object_or_404(ProductoReceta, pk=receta_id)
    producto_id = receta.producto.pk
    
    if request.method == 'POST':
        insumo_nombre = receta.insumo.nombre
        receta.delete()
        messages.success(request, f'Insumo {insumo_nombre} eliminado de la receta')
        return redirect('producto_detalle', pk=producto_id)
    
    context = {'receta': receta}
    return render(request, 'productos/receta_confirm_delete.html', context)

def registrar_asistencia(request):
    """
    Formulario público (o interno) que pide correo + contraseña + tipo (entrada/salida).
    Si tipo == 'entrada' -> crea o completa la Asistencia del día con hora_entrada = now.time()
    Si tipo == 'salida'  -> busca la Asistencia del día con hora_entrada existente y hora_salida NULL; pone hora_salida = now.time()
    """
    if request.method == 'POST':
        form = AsistenciaRegistroForm(request.POST)
        if form.is_valid():
            correo = form.cleaned_data['correo'].strip().lower()
            contraseña = form.cleaned_data['contraseña']
            tipo = form.cleaned_data['tipo']
            notas = form.cleaned_data.get('notas', '').strip()

            empleado = Empleado.objects.filter(correo__iexact=correo, activo=True).first()
            if not empleado:
                messages.error(request, 'Empleado no encontrado o no activo.')
                return redirect('registrar_asistencia')

            # Autenticación con método del modelo
            if not empleado.check_password(contraseña):
                messages.error(request, 'Correo o contraseña incorrectos.')
                return redirect('registrar_asistencia')

            ahora = timezone.localtime()
            fecha_hoy = ahora.date()
            hora_actual = ahora.time()

            # Entrada
            if tipo == 'entrada':
                # obtener o crear la asistencia del día
                asistencia, created = Asistencia.objects.get_or_create(
                    empleado=empleado,
                    fecha=fecha_hoy,
                    defaults={'hora_entrada': hora_actual, 'hora_salida': None, 'notas': notas or None}
                )
                if created:
                    messages.success(request, f'Entrada registrada para {empleado.nombre} a las {hora_actual.strftime("%H:%M:%S")}.')
                else:
                    # Si ya existe: si hora_entrada no está puesta -> setear; si ya estaba puesta -> error
                    if asistencia.hora_entrada is None:
                        asistencia.hora_entrada = hora_actual
                        if notas:
                            asistencia.notas = (asistencia.notas or '') + '\n' + notas
                        asistencia.save()
                        messages.success(request, f'Entrada registrada para {empleado.nombre} a las {hora_actual.strftime("%H:%M:%S")}.')
                    else:
                        messages.error(request, 'Ya existe una entrada registrada para hoy.')
                return redirect('registrar_asistencia')

            # Salida
            else:
                # Buscamos la asistencia del día con hora_entrada presente y sin hora_salida
                asistencia = Asistencia.objects.filter(
                    empleado=empleado,
                    fecha=fecha_hoy
                ).first()

                if not asistencia:
                    messages.error(request, 'No hay registro de entrada para hoy. No se puede registrar salida.')
                    return redirect('registrar_asistencia')

                if asistencia.hora_salida is not None:
                    messages.error(request, 'La salida ya fue registrada para hoy.')
                    return redirect('registrar_asistencia')

                # Verificar que exista hora_entrada, si no, rechazamos
                if asistencia.hora_entrada is None:
                    messages.error(request, 'No existe hora de entrada; no se puede registrar salida.')
                    return redirect('registrar_asistencia')

                asistencia.hora_salida = hora_actual
                if notas:
                    asistencia.notas = (asistencia.notas or '') + '\n' + notas
                asistencia.save()
                messages.success(request, f'Salida registrada para {empleado.nombre} a las {hora_actual.strftime("%H:%M:%S")}.')
                return redirect('registrar_asistencia')
        else:
            messages.error(request, 'Formulario inválido. Corrige los datos.')
    else:
        form = AsistenciaRegistroForm()

    return render(request, 'asistencias/asistencia_form.html', {'form': form})

class ClienteListView(ListView):
    model = Cliente
    template_name = 'clientes/clientes_list.html'
    context_object_name = 'clientes'
    paginate_by = 15

    def get_queryset(self):
        qs = Cliente.objects.filter(activo=True)
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(nombre__icontains=q) | qs.filter(correo__icontains=q)
        return qs.order_by('-fecha_creacion')


class ClienteCreateView(CreateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/cliente_form.html'
    success_url = reverse_lazy('clientes_list')

    def form_valid(self, form):
        messages.success(self.request, 'Cliente creado exitosamente')
        return super().form_valid(form)


class ClienteUpdateView(UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/cliente_form.html'
    success_url = reverse_lazy('clientes_list')

    def form_valid(self, form):
        messages.success(self.request, 'Cliente actualizado exitosamente')
        return super().form_valid(form)


class ClienteDeleteView(View):
    """
    Soft-delete: marca activo=False.
    GET -> muestra confirmación.
    POST -> desactiva y redirige.
    """
    def get(self, request, pk):
        cliente = get_object_or_404(Cliente, pk=pk)
        return render(request, 'clientes/cliente_confirm_delete.html', {'object': cliente})

    def post(self, request, pk):
        cliente = get_object_or_404(Cliente, pk=pk)
        cliente.desactivar()
        messages.success(request, f'Cliente {cliente.nombre} desactivado exitosamente')
        return redirect('clientes_list')