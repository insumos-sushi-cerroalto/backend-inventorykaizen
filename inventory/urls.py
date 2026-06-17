# backend-inventorykaizen\inventory\urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductoViewSet, CompraViewSet, CompraPadreViewSet, VentaViewSet, InventarioViewSet

router = DefaultRouter()
router.register(r'productos', ProductoViewSet, basename='producto')
router.register(r'compras-padre', CompraPadreViewSet, basename='compra-padre')
router.register(r'compras', CompraViewSet, basename='compra')
router.register(r'ventas', VentaViewSet, basename='venta')
router.register(r'inventario', InventarioViewSet, basename='inventario')

urlpatterns = [
    path('', include(router.urls)),
]