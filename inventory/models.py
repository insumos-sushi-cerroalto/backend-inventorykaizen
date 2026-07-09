# backend-inventorykaizen\inventory\models.py
from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from cloudinary_storage.storage import RawMediaCloudinaryStorage

class Producto(models.Model): 
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='productos')
    id_producto = models.IntegerField(null=True, blank=True, editable=False)
    nombre = models.CharField(max_length=200)
    imagen = models.ImageField(upload_to='productos/', null=True, blank=True)
    unidad_medida = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    precio_unitario = models.IntegerField(validators=[MinValueValidator(1)], null=True, blank=True, default=None)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    marca = models.CharField(max_length=100, blank=True)
    categoria = models.CharField(max_length=100, blank=True)
    
    producto_base = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='presentaciones',
        null=True,
        blank=True
    )

    factor_conversion = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text='Cantidad de unidades base que representa este producto/presentación.'
    )

    def save(self, *args, **kwargs):
        if self.id_producto is None:
            # Encontrar el primer número disponible para este usuario
            usado = set(Producto.objects.filter(user=self.user).values_list('id_producto', flat=True).distinct())
            numero = 1
            while numero in usado:
                numero += 1
            self.id_producto = numero
        super().save(*args, **kwargs)
    
    @staticmethod
    def calcular_numero_dinámico_venta(fecha_venta, user, venta_id=None):
        """
        Calcula el número de venta agrupado por fecha para un usuario específico.
        Todas las ventas del mismo día tienen el mismo número.
        Las fechas únicas están ordenadas ascendentemente.
        """
        # Obtener todas las fechas únicas ordenadas ascendentemente para este usuario
        fechas_unicas = Venta.objects.filter(user=user).values_list('fecha', flat=True).distinct().order_by('fecha')
        
        # Buscar la posición de la fecha actual
        for numero, fecha in enumerate(fechas_unicas, 1):
            if fecha == fecha_venta:
                return numero
        
        # Si no se encuentra (venta nueva), devolver el siguiente número
        return len(list(fechas_unicas)) + 1
    
    @staticmethod
    def calcular_numero_dinámico_compra(fecha_compra, user, compra_id=None):
        """
        Calcula el número de compra agrupado por fecha para un usuario específico.
        Todas las compras del mismo día tienen el mismo número.
        Las fechas únicas están ordenadas ascendentemente.
        """
        # Obtener todas las fechas únicas ordenadas ascendentemente para este usuario
        fechas_unicas = Compra.objects.filter(user=user).values_list('fecha', flat=True).distinct().order_by('fecha')
        
        # Buscar la posición de la fecha actual
        for numero, fecha in enumerate(fechas_unicas, 1):
            if fecha == fecha_compra:
                return numero
        
        # Si no se encuentra (compra nueva), devolver el siguiente número
        return len(list(fechas_unicas)) + 1
    
    @staticmethod
    def calcular_numero_dinámico_compra_padre(fecha_compra, user, compra_padre_id=None):
        """
        Calcula el número de compra padre agrupado por fecha para un usuario específico.
        Todas las compras padre del mismo día tienen el mismo número.
        Las fechas únicas están ordenadas ascendentemente.
        """
        # Obtener todas las fechas únicas ordenadas ascendentemente para este usuario
        fechas_unicas = CompraPadre.objects.filter(user=user).values_list('fecha', flat=True).distinct().order_by('fecha')
        
        # Buscar la posición de la fecha actual
        for numero, fecha in enumerate(fechas_unicas, 1):
            if fecha == fecha_compra:
                return numero
        
        # Si no se encuentra (compra padre nueva), devolver el siguiente número
        return len(list(fechas_unicas)) + 1
    
    class Meta:
        ordering = ['nombre']
        constraints = [
            models.UniqueConstraint(fields=['user', 'id_producto'], name='unique_producto_por_usuario')
        ]
    
    def __str__(self):
        return self.nombre
    
    @property
    def producto_inventario(self):
        return self.producto_base or self

    @property
    def stock_actual(self):
        producto_base = self.producto_inventario
        productos_relacionados = Producto.objects.filter(
            Q(id=producto_base.id) | Q(producto_base=producto_base),
            user=self.user
        )

        total_compras = sum(
            compra.cantidad * compra.producto.factor_conversion
            for compra in Compra.objects.filter(
                user=self.user,
                producto__in=productos_relacionados
            ).select_related('producto')
        )

        total_ventas = sum(
            venta.cantidad * venta.producto.factor_conversion
            for venta in Venta.objects.filter(
                user=self.user,
                producto__in=productos_relacionados
            ).select_related('producto')
        )

        return total_compras - total_ventas

# Modelo CompraPadre para agrupar múltiples compras
class CompraPadre(models.Model):
    """Agrupa múltiples productos en una sola compra"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='compras_padre')
    numero = models.IntegerField(null=True, blank=True, editable=False)
    fecha = models.DateField()
    proveedor = models.CharField(max_length=200)
    notas = models.TextField(blank=True)
    factura = models.FileField(
        upload_to='facturas/', 
        storage=RawMediaCloudinaryStorage(), # <--- ESTO OBLIGA A CLOUDINARY A TRATARLO COMO PDF/RAW
        blank=True, 
        null=True
    )   
    fecha_registro = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        # Asignar número basado en la fecha (agrupado por día) para este usuario
        if self.numero is None:
            existente = CompraPadre.objects.filter(user=self.user, fecha=self.fecha).first()
            if existente:
                self.numero = existente.numero
            else:
                total_fechas = CompraPadre.objects.filter(user=self.user).values('fecha').distinct().count()
                self.numero = total_fechas + 1
        super().save(*args, **kwargs)
    
    class Meta:
        ordering = ['-fecha', '-fecha_registro']
    
    @property
    def costo_total(self):
        return sum(compra.costo_total for compra in self.compras.all())
    
    @property
    def cantidad_productos(self):
        return self.compras.count()
    
    def __str__(self):
        return f"Compra Padre #{self.id} - {self.proveedor} ({self.fecha})"

# Modelo Compra vinculado a CompraPadre
class Compra(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='compras')
    numero = models.IntegerField(null=True, blank=True, editable=False)
    compra_padre = models.ForeignKey(CompraPadre, on_delete=models.CASCADE, related_name='compras', null=True, blank=True)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='compras')
    fecha = models.DateField()
    cantidad = models.IntegerField(validators=[MinValueValidator(1)])
    costo_unitario = models.IntegerField(validators=[MinValueValidator(1)])
    valor_venta = models.IntegerField(validators=[MinValueValidator(1)])
    proveedor = models.CharField(max_length=200)
    notas = models.TextField(blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        # Asignar número basado en la fecha (agrupado por día) para este usuario
        if self.numero is None:
            existente = Compra.objects.filter(user=self.user, fecha=self.fecha).first()
            if existente:
                self.numero = existente.numero
            else:
                total_fechas = Compra.objects.filter(user=self.user).values('fecha').distinct().count()
                self.numero = total_fechas + 1
        super().save(*args, **kwargs)
    
    class Meta:
        ordering = ['-fecha', '-fecha_registro']
    
    @property
    def costo_total(self):
        return self.cantidad * self.costo_unitario
    
    def __str__(self):
        return f"Compra #{self.numero} - {self.producto.nombre}"


class Venta(models.Model):
    CANALES = [
        ('local', 'Local'),
        ('whatsapp', 'WhatsApp'),
        ('messenger', 'Messenger'),
        ('instagram', 'Instagram'),
        ('telefono', 'Teléfono'),
        ('otro', 'Otro'),
    ]
    
    METODOS_PAGO = [
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia'),
        ('factura', 'Factura'),
        ('debito', 'Debito'),
        ('credito', 'Crédito'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ventas')
    numero = models.IntegerField(null=True, blank=True, editable=False)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='ventas')
    fecha = models.DateField()
    canal_venta = models.CharField(max_length=20, choices=CANALES, default='local')
    cliente = models.CharField(max_length=200)
    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO, default='efectivo')
    cantidad = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    precio_unitario = models.IntegerField(validators=[MinValueValidator(1)])
    pagado = models.BooleanField(default=True)
    notas = models.TextField(blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        # Asignar número basado en la fecha (agrupado por día) para este usuario
        if self.numero is None:
            existente = Venta.objects.filter(user=self.user, fecha=self.fecha).first()
            if existente:
                self.numero = existente.numero
            else:
                total_fechas = Venta.objects.filter(user=self.user).values('fecha').distinct().count()
                self.numero = total_fechas + 1
        super().save(*args, **kwargs)
    
    class Meta:
        ordering = ['-fecha', '-fecha_registro']
    
    @property
    def total(self):
        return self.cantidad * self.precio_unitario
    
    def __str__(self):
        return f"Venta #{self.numero} - {self.producto.nombre}"


class MovimientoFinanciero(models.Model):
    TIPOS_MOVIMIENTO = [
        ('ingreso', 'Ingreso'),
        ('egreso', 'Egreso'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='movimientos_financieros')
    fecha = models.DateField()
    tipo_movimiento = models.CharField(max_length=20, choices=TIPOS_MOVIMIENTO)
    categoria = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=255)
    monto = models.IntegerField(validators=[MinValueValidator(1)])
    observaciones = models.TextField(blank=True)
    usuario_responsable = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='movimientos_financieros_responsables',
        null=True,
        blank=True,
    )
    origen_model = models.CharField(max_length=50, blank=True, default='')
    origen_id = models.IntegerField(null=True, blank=True)
    es_manual = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha', '-fecha_creacion']

    def clean(self):
        super().clean()
        if self.monto is None or self.monto <= 0:
            raise ValidationError({'monto': 'El monto debe ser mayor a cero.'})
        if self.tipo_movimiento not in dict(self.TIPOS_MOVIMIENTO):
            raise ValidationError({'tipo_movimiento': 'El tipo de movimiento no es válido.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_tipo_movimiento_display()} - {self.descripcion}"


class CategoriaDistribucion(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categorias_distribucion')
    nombre = models.CharField(max_length=100)
    porcentaje = models.IntegerField(validators=[MinValueValidator(1)])
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['orden', 'nombre']
        constraints = [
            models.UniqueConstraint(fields=['user', 'nombre'], name='unique_categoria_distribucion_por_usuario')
        ]

    def clean(self):
        super().clean()
        if self.porcentaje < 1 or self.porcentaje > 100:
            raise ValidationError({'porcentaje': 'El porcentaje debe estar entre 1 y 100.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def calcular_monto(self, utilidad):
        return int(round(utilidad * self.porcentaje / 100))

    def __str__(self):
        return self.nombre


@receiver(post_save, sender=Venta)
def sincronizar_movimiento_venta(sender, instance, **kwargs):
    MovimientoFinanciero.objects.update_or_create(
        user=instance.user,
        origen_model='venta',
        origen_id=instance.id,
        defaults={
            'fecha': instance.fecha,
            'tipo_movimiento': 'ingreso',
            'categoria': 'ventas',
            'descripcion': f"Venta #{instance.numero or instance.id}",
            'monto': instance.total,
            'observaciones': 'Creado automáticamente desde una venta.',
            'usuario_responsable': instance.user,
            'es_manual': False,
        },
    )


@receiver(post_delete, sender=Venta)
def eliminar_movimiento_venta(sender, instance, **kwargs):
    MovimientoFinanciero.objects.filter(user=instance.user, origen_model='venta', origen_id=instance.id).delete()


@receiver(post_save, sender=Compra)
def sincronizar_movimiento_compra(sender, instance, **kwargs):
    MovimientoFinanciero.objects.update_or_create(
        user=instance.user,
        origen_model='compra',
        origen_id=instance.id,
        defaults={
            'fecha': instance.fecha,
            'tipo_movimiento': 'egreso',
            'categoria': 'compras',
            'descripcion': f"Compra #{instance.numero or instance.id}",
            'monto': instance.costo_total,
            'observaciones': 'Creado automáticamente desde una compra.',
            'usuario_responsable': instance.user,
            'es_manual': False,
        },
    )


@receiver(post_delete, sender=Compra)
def eliminar_movimiento_compra(sender, instance, **kwargs):
    MovimientoFinanciero.objects.filter(user=instance.user, origen_model='compra', origen_id=instance.id).delete()
    
######
# Modelo para la tienda web
######
