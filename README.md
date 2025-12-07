# Cafetería Admin

Sistema para administrar empleados, horarios, inventario, ventas y clientes de una cafetería. Backend en Django 4.x y MySQL. UI en español.

## Requisitos

- Python 3.8+
- MySQL funcionando localmente
- Django 4.x
- Acceso a tu base con credenciales:
  - BD: `make_milagrito_db`
  - Usuario: `admin_milagrito`
  - Password: `m1lagr1t0`

## Instalación

1. Clonar este repositorio.
2. Crear un entorno virtual:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```
3. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```

4. Configura tu base de datos MySQL en `cafeteria_admin/settings.py`.

## Migraciones y datos de ejemplo

1. Migrar base:
   ```bash
   python manage.py migrate
   ```

2. Crear superusuario:
   ```bash
   python manage.py createsuperuser
   ```

3. Cargar los datos de ejemplo:
   ```bash
   python manage.py seed_fixture
   ```

## Comandos personalizados

- Generar horario para semana (celdas HorarioCelda):

  ```bash
  python manage.py generate_week_schedule YYYY-MM-DD <usuario_id>
  ```

- Cargar datos iniciales:

  ```bash
  python manage.py seed_fixture
  ```

## Ejecutar servidor de desarrollo

```bash
python manage.py runserver
```

## Funcionalidad

- Empleados: agregar, filtrar por fecha, ver horas trabajadas.
- Horarios: vista semanal, editar solo fechas futuras.
- Inventario: editar, alerta si insumo bajo stock mínimo.
- Productos: relación a insumos, gestión estándar.
- Ventas: descuenta stock automáticamente y valida.
- Clientes: acumulan puntos por venta.
- Autenticación: grupos y permisos por sección.
- Reportes: ventas, ganancias, empleados, inventario bajo.
- Internacionalización: español por defecto (puedes mejorar con archivos .po).

---

### Resumen para iniciar

1. Instala requerimientos y revisa base de datos.
2. Corre migraciones y crea superusuario.
3. Carga datos ejemplo y prueba el sistema.
4. Usa vistas administrativas en `/admin` o navega las rutas proporcionadas.
5. Personaliza los templates en español según tus preferencias.

---
