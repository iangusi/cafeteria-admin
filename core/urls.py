from django.urls import path
from .import views

urlpatterns = [
    # Empleados
    path('empleados/', views.EmpleadoListView.as_view(), name='empleados_list'),
    path('empleados/crear/', views.EmpleadoCreateView.as_view(), name='empleado_crear'),
    path('empleados/<int:pk>/editar/', views.EmpleadoUpdateView.as_view(), name='empleado_editar'),
    path('empleados/<int:pk>/eliminar/', views.EmpleadoDeleteView.as_view(), name='empleado_eliminar'),
    path('empleados/<int:pk>/', views.EmpleadoDetailView.as_view(), name='empleado_detalle'),
    
    # Horarios
    path('horarios/', views.horarios_list, name='horarios_list'),
    path('horarios/crear/', views.agregar_horario, name='horario_crear'),
    path('horarios/<int:pk>/editar/', views.editar_horario, name='horario_editar'),
    path('horarios/<int:pk>/eliminar/', views.eliminar_horario, name='horario_eliminar'),
    
    # Inventario
    path('insumos/', views.InsumoListView.as_view(), name='insumo_list'),
    path('insumos/crear/', views.InsumoCreateView.as_view(), name='insumo_crear'),
    path('insumos/<int:pk>/editar/', views.InsumoUpdateView.as_view(), name='insumo_editar'),
    path('insumos/<int:pk>/eliminar/', views.InsumoDeleteView.as_view(), name='insumo_eliminar'),
    
    # Productos
    path('productos/', views.ProductoListView.as_view(), name='producto_list'),
    path('productos/crear/', views.ProductoCreateView.as_view(), name='producto_crear'),
    path('productos/<int:pk>/editar/', views.ProductoUpdateView.as_view(), name='producto_editar'),
    path('productos/<int:pk>/eliminar/', views.ProductoDeleteView.as_view(), name='producto_eliminar'),
    path('productos/<int:pk>/', views.producto_detalle, name='producto_detalle'),
    path('productos/<int:producto_id>/receta/agregar/', views.agregar_receta, name='agregar_receta'),
    path('receta/<int:receta_id>/editar/', views.editar_receta, name='editar_receta'),
    path('receta/<int:receta_id>/eliminar/', views.eliminar_receta, name='eliminar_receta'),

    # Asistencias
    path('asistencia/registrar/', views.registrar_asistencia, name='registrar_asistencia'),

    # Cliente
    path('clientes/', views.ClienteListView.as_view(), name='clientes_list'),
    path('clientes/crear/', views.ClienteCreateView.as_view(), name='cliente_crear'),
    path('clientes/<int:pk>/editar/', views.ClienteUpdateView.as_view(), name='cliente_editar'),
    path('clientes/<int:pk>/eliminar/', views.ClienteDeleteView.as_view(), name='cliente_eliminar'),

]