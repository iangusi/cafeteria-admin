from django.test import TestCase
from .models import Empleado, Insumo

class EmpleadoTestCase(TestCase):
    def setUp(self):
        Empleado.objects.create(nombre="Ana", sueldo_por_hora=40, rol="staff")

    def test_creacion_empleado(self):
        ana = Empleado.objects.get(nombre="Ana")
        self.assertEqual(ana.sueldo_por_hora, 40)
        self.assertEqual(ana.rol, "staff")

class InsumoTestCase(TestCase):
    def setUp(self):
        Insumo.objects.create(nombre="Azúcar", unidad="kg", cantidad_actual=2, cantidad_minima=5)

    def test_insumo_bajo(self):
        azucar = Insumo.objects.get(nombre="Azúcar")
        self.assertTrue(azucar.esta_bajo())