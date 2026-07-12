from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Compra, Producto, Venta, MovimientoFinanciero, CategoriaDistribucion


class FinanzasAPITests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='tester', password='12345678')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.producto = Producto.objects.create(
            user=self.user,
            nombre='Producto test',
            unidad_medida='und',
            descripcion='desc',
            precio_unitario=1000,
            marca='marca',
            categoria='cat'
        )

    def test_crea_movimiento_automatico_al_crear_venta(self):
        venta = Venta.objects.create(
            user=self.user,
            producto=self.producto,
            fecha='2026-07-08',
            cliente='Cliente A',
            precio_unitario=5000,
            cantidad=2,
            pagado=True,
        )

        movimiento = MovimientoFinanciero.objects.filter(user=self.user, origen_model='venta', origen_id=venta.id).first()

        self.assertIsNotNone(movimiento)
        self.assertEqual(movimiento.tipo_movimiento, 'ingreso')
        self.assertEqual(movimiento.monto, venta.total)

    def test_crea_movimiento_automatico_al_crear_compra(self):
        compra = Compra.objects.create(
            user=self.user,
            producto=self.producto,
            fecha='2026-07-08',
            cantidad=3,
            costo_unitario=2000,
            valor_venta=2500,
            proveedor='Proveedor A',
        )

        movimiento = MovimientoFinanciero.objects.filter(user=self.user, origen_model='compra', origen_id=compra.id).first()

        self.assertIsNotNone(movimiento)
        self.assertEqual(movimiento.tipo_movimiento, 'egreso')
        self.assertEqual(movimiento.monto, compra.costo_total)

    def test_api_compra_devuelve_todas_las_compras_sin_paginacion(self):
        for index in range(105):
            Compra.objects.create(
                user=self.user,
                producto=self.producto,
                fecha='2026-07-08',
                cantidad=1,
                costo_unitario=1000 + index,
                valor_venta=1200 + index,
                proveedor='Proveedor A',
            )

        response = self.client.get('/api/compras/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 105)

    def test_api_venta_persista_monto_pendiente(self):
        response = self.client.post('/api/ventas/', {
            'producto': self.producto.id,
            'fecha': '2026-07-08',
            'cliente': 'Cliente B',
            'cantidad': 1,
            'precio_unitario': 4500,
            'pagado': False,
            'monto_pendiente': 4500,
        }, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['monto_pendiente'], 4500)

    def test_balance_y_distribucion_api(self):
        MovimientoFinanciero.objects.create(
            user=self.user,
            fecha='2026-07-08',
            tipo_movimiento='ingreso',
            categoria='ventas',
            descripcion='Venta',
            monto=100000,
            es_manual=False,
        )
        MovimientoFinanciero.objects.create(
            user=self.user,
            fecha='2026-07-08',
            tipo_movimiento='egreso',
            categoria='gasto',
            descripcion='Compra',
            monto=30000,
            es_manual=False,
        )

        balance_response = self.client.get('/api/movimientos/balance/')
        self.assertEqual(balance_response.status_code, 200)
        self.assertEqual(balance_response.json()['total_ingresos'], 100000)
        self.assertEqual(balance_response.json()['total_egresos'], 30000)
        self.assertEqual(balance_response.json()['saldo_actual'], 70000)

        create_response = self.client.post('/api/distribuciones/', {'nombre': 'Ahorro', 'porcentaje': 30}, format='json')
        self.assertEqual(create_response.status_code, 201)

        second_response = self.client.post('/api/distribuciones/', {'nombre': 'Reinversión', 'porcentaje': 70}, format='json')
        self.assertEqual(second_response.status_code, 201)

        distribution_response = self.client.get('/api/distribuciones/calculada/')
        self.assertEqual(distribution_response.status_code, 200)
        self.assertEqual(distribution_response.json()['utilidad'], 70000)
        self.assertEqual(distribution_response.json()['items'][0]['monto'], 21000)
