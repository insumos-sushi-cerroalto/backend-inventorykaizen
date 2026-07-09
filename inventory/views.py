# inventory/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework.permissions import IsAuthenticated
from decimal import Decimal
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from django.db.models import Q
from django.db.models.functions import Coalesce
from datetime import datetime, timedelta
from .models import Producto, Compra, CompraPadre, Venta, MovimientoFinanciero, CategoriaDistribucion
from .serializers import (
    ProductoSerializer, CompraSerializer, CompraPadreSerializer, 
    CompraPadreCreateUpdateSerializer, VentaSerializer,
    InventarioSerializer, ReporteFinancieroSerializer,
    MovimientoFinancieroSerializer, CategoriaDistribucionSerializer,
)

class ProductoViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Producto.objects.all()
    serializer_class = ProductoSerializer
    
    def get_queryset(self):
        """Filtrar productos por usuario autenticado"""
        return Producto.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Asignar el usuario actual al crear un producto"""
        serializer.save(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        """
        Soporta creación simple (dict) y masiva (lista de dicts).
        """
        is_many = isinstance(request.data, list)
        serializer = self.get_serializer(data=request.data, many=is_many)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def destroy(self, request, *args, **kwargs):
        """
        Elimina un producto junto con todas sus ventas y compras asociadas.
        Las compras padre que queden sin items se eliminan automáticamente.
        """
        instance = self.get_object()
        producto_id = instance.id
        
        # Obtener las compras padre asociadas a este producto para este usuario
        compras_padre_ids = CompraPadre.objects.filter(
            user=request.user,
            compras__producto_id=producto_id
        ).values_list('id', flat=True)
        
        # Eliminar el producto (esto elimina cascada todas sus ventas y compras)
        self.perform_destroy(instance)
        
        # Eliminar compras padre que quedaron vacías
        for compra_padre_id in compras_padre_ids:
            try:
                compra_padre = CompraPadre.objects.get(id=compra_padre_id, user=request.user)
                if compra_padre.compras.count() == 0:
                    compra_padre.delete()
            except CompraPadre.DoesNotExist:
                pass
        
        return Response(
            {'detail': 'Producto y todos sus registros de ventas/compras eliminados exitosamente.'},
            status=status.HTTP_204_NO_CONTENT
        )
    
    @action(detail=False, methods=['get'])
    def con_stock(self, request):
        productos = self.get_queryset()
        data = []
        for producto in productos:
            data.append({
                'id': producto.id,
                'nombre': producto.nombre,
                'stock_actual': producto.stock_actual,
                'unidad_medida': producto.unidad_medida
            })
        return Response(data)


class CompraViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Compra.objects.all()
    serializer_class = CompraSerializer
    
    def get_queryset(self):
        """Filtrar compras por usuario autenticado"""
        queryset = Compra.objects.filter(user=self.request.user)
        fecha_inicio = self.request.query_params.get('fecha_inicio')
        fecha_fin = self.request.query_params.get('fecha_fin')
        producto = self.request.query_params.get('producto')
        compra_padre = self.request.query_params.get('compra_padre')
        
        if fecha_inicio:
            queryset = queryset.filter(fecha__gte=fecha_inicio)
        if fecha_fin:
            queryset = queryset.filter(fecha__lte=fecha_fin)
        if producto:
            queryset = queryset.filter(producto_id=producto)
        if compra_padre:
            queryset = queryset.filter(compra_padre_id=compra_padre)
        
        return queryset
    
    def perform_create(self, serializer):
        """Asignar el usuario actual al crear una compra"""
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def resumen(self, request):
        total_compras = self.get_queryset().aggregate(
            total=Sum(F('cantidad') * F('costo_unitario'), output_field=DecimalField())
        )['total'] or 0
        
        cantidad = self.get_queryset().count()
        
        return Response({
            'total_gastado': total_compras,
            'cantidad_compras': cantidad
        })


class CompraPadreViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar compras padre con múltiples productos"""
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    queryset = CompraPadre.objects.all()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            print('CompraPadre create invalid data:', request.data)
            print('CompraPadre create invalid files:', request.FILES)
            print('CompraPadre create errors:', serializer.errors)
        return super().create(request, *args, **kwargs)
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return CompraPadreCreateUpdateSerializer
        return CompraPadreSerializer
    
    def get_queryset(self):
        """Filtrar compras padre por usuario autenticado"""
        queryset = CompraPadre.objects.filter(user=self.request.user)
        fecha_inicio = self.request.query_params.get('fecha_inicio')
        fecha_fin = self.request.query_params.get('fecha_fin')
        proveedor = self.request.query_params.get('proveedor')
        
        if fecha_inicio:
            queryset = queryset.filter(fecha__gte=fecha_inicio)
        if fecha_fin:
            queryset = queryset.filter(fecha__lte=fecha_fin)
        if proveedor:
            queryset = queryset.filter(proveedor__icontains=proveedor)
        
        return queryset
    
    def perform_create(self, serializer):
        """Asignar el usuario actual al crear una compra padre"""
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def resumen(self, request):
        """Resumen de todas las compras padre"""
        compras_padre = self.get_queryset()
        
        total_gastado = sum(compra.costo_total for compra in compras_padre)
        cantidad_compras = compras_padre.count()
        cantidad_productos = sum(compra.cantidad_productos for compra in compras_padre)
        
        return Response({
            'total_gastado': total_gastado,
            'cantidad_compras': cantidad_compras,
            'cantidad_productos_comprados': cantidad_productos
        })


class VentaPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 50


class VentaViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = VentaPagination
    queryset = Venta.objects.all()
    serializer_class = VentaSerializer
    
    def get_queryset(self):
        """Filtrar ventas por usuario autenticado"""
        queryset = Venta.objects.filter(user=self.request.user)
        params = self.request.query_params

        fecha_inicio = params.get('fecha_inicio')
        fecha_fin = params.get('fecha_fin')
        producto = params.get('producto')
        producto_nombre = params.get('producto_nombre')
        cliente = params.get('cliente')
        canal = params.get('canal') or params.get('canal_venta')
        pagado = params.get('pagado')
        numero = params.get('numero')
        cantidad = params.get('cantidad')
        precio_unitario = params.get('precio_unitario')
        total = params.get('total')
        fecha = params.get('fecha')
        mes = params.get('mes')
        anio = params.get('anio')
        ordering = params.get('ordering')

        def split_values(value):
            if not value:
                return []
            return [item.strip() for item in value.split(',') if item.strip() != '']

        if fecha_inicio:
            queryset = queryset.filter(fecha__gte=fecha_inicio)
        if fecha_fin:
            queryset = queryset.filter(fecha__lte=fecha_fin)
        if fecha:
            fechas = split_values(fecha)
            if fechas:
                queryset = queryset.filter(fecha__in=fechas)
        if producto:
            queryset = queryset.filter(producto_id=producto)
        if producto_nombre:
            nombres = split_values(producto_nombre)
            if nombres:
                queryset = queryset.filter(producto__nombre__in=nombres)
        if cliente:
            clientes = split_values(cliente)
            if clientes:
                queryset = queryset.filter(cliente__in=clientes)
        if canal:
            canales = split_values(canal)
            if canales:
                queryset = queryset.filter(canal_venta__in=canales)
        if pagado:
            valores = []
            for item in split_values(pagado):
                if item.lower() == 'true':
                    valores.append(True)
                elif item.lower() == 'false':
                    valores.append(False)
            if valores:
                queryset = queryset.filter(pagado__in=valores)
        if numero:
            ids = [int(item) for item in split_values(numero) if item.isdigit()]
            if ids:
                queryset = queryset.filter(numero__in=ids)
        if cantidad:
            cantidades = [int(item) for item in split_values(cantidad) if item.isdigit()]
            if cantidades:
                queryset = queryset.filter(cantidad__in=cantidades)
        if precio_unitario:
            precios = [int(item) for item in split_values(precio_unitario) if item.isdigit()]
            if precios:
                queryset = queryset.filter(precio_unitario__in=precios)
        if total:
            totales = [int(item) for item in split_values(total) if item.isdigit()]
            if totales:
                queryset = queryset.annotate(total=F('cantidad') * F('precio_unitario')).filter(total__in=totales)

        if mes is not None and mes.lower() != 'todos':
            try:
                queryset = queryset.filter(fecha__month=int(mes))
            except (ValueError, TypeError):
                pass
        if anio is not None:
            try:
                queryset = queryset.filter(fecha__year=int(anio))
            except (ValueError, TypeError):
                pass

        if ordering:
            direction = ''
            order_field = ordering
            if ordering.startswith('-'):
                direction = '-'
                order_field = ordering[1:]

            field_map = {
                'numero': 'numero',
                'fecha': 'fecha',
                'producto_nombre': 'producto__nombre',
                'cliente': 'cliente',
                'canal_venta': 'canal_venta',
                'cantidad': 'cantidad',
                'precio_unitario': 'precio_unitario',
                'pagado': 'pagado',
                'total': 'total'
            }

            if order_field in field_map:
                order_by = f"{direction}{field_map[order_field]}"
                if order_field == 'total':
                    queryset = queryset.annotate(total=F('cantidad') * F('precio_unitario'))
                queryset = queryset.order_by(order_by)

        return queryset
            
    def perform_create(self, serializer):
        """Asignar el usuario actual al crear una venta"""
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def resumen(self, request):
        ventas = self.get_queryset()
        
        total_ventas = ventas.aggregate(
            total=Sum(F('cantidad') * F('precio_unitario'), output_field=DecimalField())
        )['total'] or 0
        
        ventas_pagadas = ventas.filter(pagado=True).aggregate(
            total=Sum(F('cantidad') * F('precio_unitario'), output_field=DecimalField())
        )['total'] or 0
        
        ventas_pendientes = ventas.filter(pagado=False).aggregate(
            total=Sum(F('cantidad') * F('precio_unitario'), output_field=DecimalField())
        )['total'] or 0
        
        cantidad = ventas.count()
        
        return Response({
            'total_ingresos': total_ventas,
            'ingresos_pagados': ventas_pagadas,
            'ingresos_pendientes': ventas_pendientes,
            'cantidad_ventas': cantidad
        })


class MovimientoFinancieroViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = MovimientoFinanciero.objects.all()
    serializer_class = MovimientoFinancieroSerializer

    def get_queryset(self):
        queryset = MovimientoFinanciero.objects.filter(user=self.request.user)
        fecha_inicio = self.request.query_params.get('fecha_inicio')
        fecha_fin = self.request.query_params.get('fecha_fin')
        tipo_movimiento = self.request.query_params.get('tipo_movimiento')
        categoria = self.request.query_params.get('categoria')
        origen_model = self.request.query_params.get('origen_model')

        if fecha_inicio:
            queryset = queryset.filter(fecha__gte=fecha_inicio)
        if fecha_fin:
            queryset = queryset.filter(fecha__lte=fecha_fin)
        if tipo_movimiento:
            queryset = queryset.filter(tipo_movimiento=tipo_movimiento)
        if categoria:
            queryset = queryset.filter(categoria__icontains=categoria)
        if origen_model:
            queryset = queryset.filter(origen_model=origen_model)

        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def balance(self, request):
        movimientos = self.get_queryset()
        total_ingresos = movimientos.filter(tipo_movimiento='ingreso').aggregate(total=Sum('monto'))['total'] or 0
        total_egresos = movimientos.filter(tipo_movimiento='egreso').aggregate(total=Sum('monto'))['total'] or 0
        saldo_actual = total_ingresos - total_egresos

        return Response({
            'total_ingresos': total_ingresos,
            'total_egresos': total_egresos,
            'saldo_actual': saldo_actual,
            'balance_general': saldo_actual,
        })


class CategoriaDistribucionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = CategoriaDistribucion.objects.all()
    serializer_class = CategoriaDistribucionSerializer

    def get_queryset(self):
        return CategoriaDistribucion.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def calculada(self, request):
        categorias = self.get_queryset().filter(activo=True)
        total_porcentaje = sum(categoria.porcentaje for categoria in categorias)

        if not categorias.exists():
            return Response({'detail': 'No hay categorías de distribución configuradas.'}, status=400)

        if total_porcentaje != 100:
            return Response({'detail': 'La distribución debe sumar exactamente 100%.', 'total_porcentaje': total_porcentaje}, status=400)

        utilidad = MovimientoFinanciero.objects.filter(user=request.user, tipo_movimiento='ingreso').aggregate(total=Sum('monto'))['total'] or 0
        egresos = MovimientoFinanciero.objects.filter(user=request.user, tipo_movimiento='egreso').aggregate(total=Sum('monto'))['total'] or 0
        utilidad_actual = utilidad - egresos

        items = []
        for categoria in categorias:
            items.append({
                'id': categoria.id,
                'nombre': categoria.nombre,
                'porcentaje': categoria.porcentaje,
                'monto': categoria.calcular_monto(utilidad_actual),
            })

        return Response({
            'utilidad': utilidad_actual,
            'total_porcentaje': total_porcentaje,
            'items': items,
        })


class InventarioViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Producto.objects.all()
    
    def get_queryset(self):
        """Filtrar productos por usuario autenticado"""
        return Producto.objects.filter(
            user=self.request.user,
            producto_base__isnull=True
        )
    
    def list(self, request):
        productos = self.get_queryset()
        inventario = []

        for producto in productos:
            productos_relacionados = Producto.objects.filter(
                Q(id=producto.id) | Q(producto_base=producto),
                user=request.user
            )

            total_compras = sum(
                compra.cantidad * compra.producto.factor_conversion
                for compra in Compra.objects.filter(
                    user=request.user,
                    producto__in=productos_relacionados
                ).select_related('producto')
            )

            total_ventas = sum(
                venta.cantidad * venta.producto.factor_conversion
                for venta in Venta.objects.filter(
                    user=request.user,
                    producto__in=productos_relacionados
                ).select_related('producto')
            )

            inventario.append({
                'producto_id': producto.id,
                'producto_nombre': producto.nombre,
                'producto_imagen': producto.imagen.url if producto.imagen else None,
                'unidad_medida': producto.unidad_medida,
                'marca': producto.marca,
                'categoria': producto.categoria,
                'stock_actual': total_compras - total_ventas,
                'total_compras': total_compras,
                'total_ventas': total_ventas,
            })

        serializer = InventarioSerializer(inventario, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def reporte_financiero(self, request):
        fecha_inicio = request.query_params.get('fecha_inicio')
        fecha_fin = request.query_params.get('fecha_fin')

        compras = Compra.objects.filter(user=request.user)
        ventas = Venta.objects.filter(user=request.user)

        if fecha_inicio:
            compras = compras.filter(fecha__gte=fecha_inicio)
            ventas = ventas.filter(fecha__gte=fecha_inicio)

        if fecha_fin:
            compras = compras.filter(fecha__lte=fecha_fin)
            ventas = ventas.filter(fecha__lte=fecha_fin)

        total_gastos = compras.aggregate(
            total=Coalesce(
                Sum(
                    ExpressionWrapper(
                        F('cantidad') * F('costo_unitario'),
                        output_field=DecimalField(max_digits=12, decimal_places=2)
                    )
                ),
                Decimal('0.00'),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )['total']

        total_ingresos = ventas.aggregate(
            total=Coalesce(
                Sum(
                    ExpressionWrapper(
                        F('cantidad') * F('precio_unitario'),
                        output_field=DecimalField(max_digits=12, decimal_places=2)
                    )
                ),
                Decimal('0.00'),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )['total']

        ventas_pagadas = ventas.filter(pagado=True).aggregate(
            total=Coalesce(
                Sum(
                    ExpressionWrapper(
                        F('cantidad') * F('precio_unitario'),
                        output_field=DecimalField(max_digits=12, decimal_places=2)
                    )
                ),
                Decimal('0.00'),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )['total']

        ventas_pendientes = ventas.filter(pagado=False).aggregate(
            total=Coalesce(
                Sum(
                    ExpressionWrapper(
                        F('cantidad') * F('precio_unitario'),
                        output_field=DecimalField(max_digits=12, decimal_places=2)
                    )
                ),
                Decimal('0.00'),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )['total']

        ganancia = total_ingresos - total_gastos

        data = {
            'total_ingresos': total_ingresos,
            'total_gastos': total_gastos,
            'ganancia_perdida': ganancia,
            'ventas_pagadas': ventas_pagadas,
            'ventas_pendientes': ventas_pendientes,
            'cantidad_ventas': ventas.count(),
            'cantidad_compras': compras.count(),
        }

        return Response(data)