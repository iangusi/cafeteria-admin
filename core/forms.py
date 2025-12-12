from django import forms
from django.forms import inlineformset_factory
from .models import Empleado, Horario, Asistencia, Insumo, Producto, ProductoReceta, Cliente, Venta, VentaItem

# ==================== FORMULARIOS EXISTENTES ====================

class EmpleadoForm(forms.ModelForm):
    # field para establecer contraseña (opcional)
    password_plain = forms.CharField(
        label='Contraseña (si deseas cambiarla)',
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Dejar vacío para no cambiar'})
    )

    class Meta:
        model = Empleado
        fields = ['nombre', 'correo', 'celular', 'rol', 'pago_por_hora', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'correo': forms.EmailInput(attrs={'class': 'form-control'}),
            'celular': forms.TextInput(attrs={'class': 'form-control'}),
            'rol': forms.Select(attrs={'class': 'form-control'}),
            'pago_por_hora': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def save(self, commit=True):
        instancia = super().save(commit=False)
        pwd = self.cleaned_data.get('password_plain')
        if pwd:
            instancia.set_password(pwd)
        if commit:
            instancia.save()
        return instancia


class AsistenciaRegistroForm(forms.Form):
    TIPO = [
        ('entrada', 'Entrada'),
        ('salida', 'Salida'),
    ]
    correo = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'}))
    contraseña = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    tipo = forms.ChoiceField(choices=TIPO, widget=forms.Select(attrs={'class': 'form-control'}))
    notas = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Opcional'}))


class FiltroEmpleadosForm(forms.Form):
    fecha_inicio = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    fecha_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    rol = forms.ChoiceField(
        required=False,
        choices=[('', '-- Todos los roles --')] + Empleado.ROLES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class HorarioForm(forms.ModelForm):
    class Meta:
        model = Horario
        fields = ['empleado', 'dia_semana', 'hora_inicio', 'hora_fin']
        widgets = {
            'empleado': forms.Select(attrs={'class': 'form-control'}),
            'dia_semana': forms.Select(attrs={'class': 'form-control'}),
            'hora_inicio': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'hora_fin': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        }


class FiltroHorariosForm(forms.Form):
    fecha = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )


# ==================== FORMULARIOS DE INSUMO ====================

class InsumoForm(forms.ModelForm):
    class Meta:
        model = Insumo
        fields = ['nombre', 'cantidad', 'cantidad_min', 'unidad', 'costo_por_unidad', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del insumo'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'step': '0.01'}),
            'cantidad_min': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'step': '0.01'}),
            'unidad': forms.Select(attrs={'class': 'form-control'}),
            'costo_por_unidad': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'step': '0.01'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class FiltroInsumoForm(forms.Form):
    ORDEN_CHOICES = [
        ('nombre', 'Por Nombre (A-Z)'),
        ('-nombre', 'Por Nombre (Z-A)'),
        ('cantidad', 'Por Cantidad (Menor a Mayor)'),
        ('-cantidad', 'Por Cantidad (Mayor a Menor)'),
        ('costo_por_unidad', 'Por Costo (Menor a Mayor)'),
        ('-costo_por_unidad', 'Por Costo (Mayor a Menor)'),
    ]
    
    busqueda = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Buscar insumo...'})
    )
    bajo_stock = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    orden = forms.ChoiceField(
        required=False,
        choices=[('', '-- Orden por defecto --')] + ORDEN_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )


# ==================== FORMULARIOS DE PRODUCTO ====================

class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['nombre', 'precio_venta', 'descripcion', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'precio_venta': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class ProductoRecetaForm(forms.ModelForm):
    class Meta:
        model = ProductoReceta
        fields = ['insumo', 'cantidad', 'unidad']
        widgets = {
            'insumo': forms.Select(attrs={'class': 'form-select'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'unidad': forms.Select(attrs={'class': 'form-select'}),
        }


class FiltroProductoForm(forms.Form):
    ORDEN_CHOICES = [
        ('nombre', 'Por Nombre (A-Z)'),
        ('-nombre', 'Por Nombre (Z-A)'),
        ('precio_venta', 'Por Precio (Menor a Mayor)'),
        ('-precio_venta', 'Por Precio (Mayor a Menor)'),
    ]
    
    busqueda = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Buscar producto por nombre...'})
    )
    insumo = forms.ModelChoiceField(
        required=False,
        queryset=Insumo.objects.filter(activo=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label='-- Filtrar por insumo --'
    )
    orden = forms.ChoiceField(
        required=False,
        choices=[('nombre', '-- Orden por defecto --')] + ORDEN_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre', 'correo', 'celular', 'puntos', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre completo'}),
            'correo': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'}),
            'celular': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+57 300 000 000'}),
            'puntos': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class ClienteCreateForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre', 'correo', 'celular']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'correo': forms.EmailInput(attrs={'class': 'form-control'}),
            'celular': forms.TextInput(attrs={'class': 'form-control'}),
        }