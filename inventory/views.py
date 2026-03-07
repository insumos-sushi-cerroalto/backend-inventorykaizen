# inventory/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework.permissions import IsAuthenticated
from decimal import Decimal
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce
from datetime import datetime, timedelta
from .models import Producto, Compra, CompraPadre, Venta
from .serializers import (
    ProductoSerializer, CompraSerializer, CompraPadreSerializer, 
    CompraPadreCreateUpdateSerializer, VentaSerializer,
    InventarioSerializer, ReporteFinancieroSerializer
)

class ProductoViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Producto.objects.all()
    serializer_class = ProductoSerializer
    
    def destroy(self, request, *args, **kwargs):
        """
        Elimina un producto junto con todas sus ventas y compras asociadas.
        Las compras padre que queden sin items se eliminan automáticamente.
        """
        instance = self.get_object()
        producto_id = instance.id
        
        # Obtener las compras padre asociadas a este producto
        compras_padre_ids = CompraPadre.objects.filter(
            compras__producto_id=producto_id
        ).values_list('id', flat=True)
        
        # Eliminar el producto (esto elimina cascada todas sus ventas y compras)
        self.perform_destroy(instance)
        
        # Eliminar compras padre que quedaron vacías
        for compra_padre_id in compras_padre_ids:
            try:
                compra_padre = CompraPadre.objects.get(id=compra_padre_id)
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
        queryset = super().get_queryset()
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
    queryset = CompraPadre.objects.all()
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return CompraPadreCreateUpdateSerializer
        return CompraPadreSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
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


class VentaViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Venta.objects.all()
    serializer_class = VentaSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        fecha_inicio = self.request.query_params.get('fecha_inicio')
        fecha_fin = self.request.query_params.get('fecha_fin')
        producto = self.request.query_params.get('producto')
        canal = self.request.query_params.get('canal')
        pagado = self.request.query_params.get('pagado')
        
        if fecha_inicio:
            queryset = queryset.filter(fecha__gte=fecha_inicio)
        if fecha_fin:
            queryset = queryset.filter(fecha__lte=fecha_fin)
        if producto:
            queryset = queryset.filter(producto_id=producto)
        if canal:
            queryset = queryset.filter(canal_venta=canal)
        if pagado is not None:
            queryset = queryset.filter(pagado=pagado.lower() == 'true')
        
        return queryset
    
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


class InventarioViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Producto.objects.all()
    def list(self, request):
        productos = Producto.objects.all()
        inventario = []
        
        for producto in productos:
            total_compras = producto.compras.aggregate(
                total=Coalesce(
                    Sum('cantidad'),
                    Decimal('0.00'),
                    output_field=DecimalField()
                )
            )['total']

            total_ventas = producto.ventas.aggregate(
                total=Coalesce(
                    Sum('cantidad'),
                    Decimal('0.00'),
                    output_field=DecimalField()
                )
            )['total']
            
            stock = total_compras - total_ventas
            
            inventario.append({
                'producto_id': producto.id,
                'producto_nombre': producto.nombre,
                'producto_imagen': producto.imagen.url if producto.imagen else None,
                'unidad_medida': producto.unidad_medida,
                'stock_actual': stock,
                'total_compras': total_compras,
                'total_ventas': total_ventas
            })
        
        serializer = InventarioSerializer(inventario, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def reporte_financiero(self, request):
        fecha_inicio = request.query_params.get('fecha_inicio')
        fecha_fin = request.query_params.get('fecha_fin')

        compras = Compra.objects.all()
        ventas = Venta.objects.all()

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