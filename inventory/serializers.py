#backend-inventorykaizen\inventory\serializers.py
from django.http import QueryDict
from rest_framework import serializers
from .models import Producto, Compra, CompraPadre, Venta

class ProductoSerializer(serializers.ModelSerializer):
    stock_actual = serializers.ReadOnlyField()
    precio_unitario = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    
    class Meta:
        model = Producto
        fields = ['id', 'id_producto', 'nombre', 'imagen', 'unidad_medida', 'descripcion', 
                  'precio_unitario', 'fecha_creacion', 'stock_actual']
        read_only_fields = ['fecha_creacion', 'id_producto']
    
    def to_internal_value(self, data):
        # Si imagen es string vacío, setear None
        if 'imagen' in data and data['imagen'] == '':
            data['imagen'] = None
        if 'precio_unitario' in data and data['precio_unitario'] == '':
            data['precio_unitario'] = None
        return super().to_internal_value(data)


class CompraSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    costo_total = serializers.ReadOnlyField()
    numero = serializers.SerializerMethodField()
    
    class Meta:
        model = Compra
        fields = ['id', 'numero', 'compra_padre', 'producto', 'producto_nombre', 'fecha', 'cantidad', 
                  'costo_unitario', 'costo_total', 'valor_venta', 'proveedor', 
                  'notas', 'fecha_registro']
        read_only_fields = ['id', 'numero', 'fecha_registro']
    
    def get_numero(self, obj):
        """Calcula dinámicamente el número basado en la fecha"""
        return Producto.calcular_numero_dinámico_compra(obj.fecha, obj.user)

    def validate_producto(self, value):
        request = self.context.get('request')
        if request and value.user != request.user:
            raise serializers.ValidationError('El producto no pertenece al usuario autenticado.')
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        compra_padre = attrs.get('compra_padre')
        if request and compra_padre and compra_padre.user != request.user:
            raise serializers.ValidationError('La compra padre no pertenece al usuario autenticado.')
        return attrs


class CompraPadreSerializer(serializers.ModelSerializer):
    """Serializer para CompraPadre con compras anidadas"""
    compras = CompraSerializer(many=True, read_only=True)
    costo_total = serializers.ReadOnlyField()
    cantidad_productos = serializers.ReadOnlyField()
    numero = serializers.SerializerMethodField()
    factura = serializers.FileField(required=False, allow_null=True)
    factura_url = serializers.SerializerMethodField()
    
    class Meta:
        model = CompraPadre
        fields = ['id', 'numero', 'fecha', 'proveedor', 'notas', 'factura', 'factura_url', 'compras', 
                  'costo_total', 'cantidad_productos', 'fecha_registro']
        read_only_fields = ['id', 'numero', 'fecha_registro']

    def get_factura_url(self, obj):
        if obj.factura:
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.factura.url)
            return obj.factura.url
        return None
    
    def get_numero(self, obj):
        """Calcula dinámicamente el número basado en la fecha"""
        return Producto.calcular_numero_dinámico_compra_padre(obj.fecha, obj.user)


class CompraPadreCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer para crear/actualizar CompraPadre con items"""
    compras_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False
    )
    compras = CompraSerializer(many=True, read_only=True)
    costo_total = serializers.ReadOnlyField()
    cantidad_productos = serializers.ReadOnlyField()
    numero = serializers.SerializerMethodField()
    factura = serializers.FileField(required=False, allow_null=True)
    factura_url = serializers.SerializerMethodField()
    
    class Meta:
        model = CompraPadre
        fields = ['id', 'numero', 'fecha', 'proveedor', 'notas', 'factura', 'factura_url', 'compras_data', 'compras',
                  'costo_total', 'cantidad_productos', 'fecha_registro']
        read_only_fields = ['id', 'numero', 'fecha_registro']

    def get_factura_url(self, obj):
        if obj.factura:
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.factura.url)
            return obj.factura.url
        return None

    def to_internal_value(self, data):
        if isinstance(data, QueryDict):
            data = data.dict()
        else:
            data = data.copy()

        compras_data = data.get('compras_data')
        if isinstance(compras_data, str):
            try:
                import json
                data['compras_data'] = json.loads(compras_data)
            except (ValueError, TypeError):
                pass
        return super().to_internal_value(data)
    
    def get_numero(self, obj):
        """Calcula dinámicamente el número basado en la fecha"""
        return Producto.calcular_numero_dinámico_compra_padre(obj.fecha, obj.user)
    
    def create(self, validated_data):
        compras_data = validated_data.pop('compras_data', [])
        compra_padre = CompraPadre.objects.create(**validated_data)
        
        for compra_item in compras_data:
            try:
                compra_item['compra_padre'] = compra_padre
                compra_item['notas'] = compra_item.get('notas', '')
                compra_item['user'] = compra_padre.user
                
                campos_requeridos = ['producto', 'fecha', 'cantidad', 'costo_unitario', 'valor_venta', 'proveedor']
                for campo in campos_requeridos:
                    if campo not in compra_item:
                        raise ValueError(f"Falta el campo requerido: {campo}")
                
                if isinstance(compra_item['producto'], int):
                    try:
                        compra_item['producto'] = Producto.objects.get(id=compra_item['producto'], user=compra_padre.user)
                    except Producto.DoesNotExist:
                        raise ValueError(f"Producto con ID {compra_item['producto']} no existe o no pertenece al usuario")
                elif compra_item['producto'].user != compra_padre.user:
                    raise ValueError('El producto no pertenece al usuario autenticado')
                
                Compra.objects.create(**compra_item)
            except Exception as e:
                compra_padre.delete()
                raise serializers.ValidationError(f"Error al crear item de compra: {str(e)}")
        
        return compra_padre
    
    def update(self, instance, validated_data):
        compras_data = validated_data.pop('compras_data', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if compras_data is not None:
            instance.compras.all().delete()
            for compra_item in compras_data:
                try:
                    compra_item['compra_padre'] = instance
                    compra_item['notas'] = compra_item.get('notas', '')
                    compra_item['user'] = instance.user
                    
                    campos_requeridos = ['producto', 'fecha', 'cantidad', 'costo_unitario', 'valor_venta', 'proveedor']
                    for campo in campos_requeridos:
                        if campo not in compra_item:
                            raise ValueError(f"Falta el campo requerido: {campo}")
                    
                    if isinstance(compra_item['producto'], int):
                        try:
                            compra_item['producto'] = Producto.objects.get(id=compra_item['producto'], user=instance.user)
                        except Producto.DoesNotExist:
                            raise ValueError(f"Producto con ID {compra_item['producto']} no existe o no pertenece al usuario")
                    elif compra_item['producto'].user != instance.user:
                        raise ValueError('El producto no pertenece al usuario autenticado')
                    
                    Compra.objects.create(**compra_item)
                except Exception as e:
                    raise serializers.ValidationError(f"Error al crear item de compra: {str(e)}")
        
        return instance


class VentaSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    total = serializers.ReadOnlyField()
    numero = serializers.SerializerMethodField()
    
    class Meta:
        model = Venta
        fields = ['id', 'numero', 'producto', 'producto_nombre', 'fecha', 'canal_venta', 
                  'cliente', 'metodo_pago', 'cantidad', 'precio_unitario', 
                  'total', 'pagado', 'notas', 'fecha_registro']
        read_only_fields = ['id', 'numero', 'fecha_registro']
    
    def get_numero(self, obj):
        """Calcula dinámicamente el número basado en la fecha"""
        return Producto.calcular_numero_dinámico_venta(obj.fecha, obj.user)

    def validate_producto(self, value):
        request = self.context.get('request')
        if request and value.user != request.user:
            raise serializers.ValidationError('El producto no pertenece al usuario autenticado.')
        return value


class InventarioSerializer(serializers.Serializer):
    producto_id = serializers.IntegerField()
    producto_nombre = serializers.CharField()
    producto_imagen = serializers.URLField(allow_null=True)
    unidad_medida = serializers.CharField()
    stock_actual = serializers.IntegerField()
    total_compras = serializers.IntegerField()
    total_ventas = serializers.IntegerField()


class ReporteFinancieroSerializer(serializers.Serializer):
    total_ingresos = serializers.IntegerField()
    total_gastos = serializers.IntegerField()
    ganancia_perdida = serializers.IntegerField()
    ventas_pagadas = serializers.IntegerField()
    ventas_pendientes = serializers.IntegerField()
    cantidad_ventas = serializers.IntegerField()
    cantidad_compras = serializers.IntegerField()