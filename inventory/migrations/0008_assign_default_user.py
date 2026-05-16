# Data migration to assign default user to existing data

from django.db import migrations
from django.contrib.auth.models import User


def create_default_user_and_assign_data(apps, schema_editor):
    """Create a default user and assign all existing data to it"""
    # Get the User model
    User = apps.get_model('auth', 'User')

    # Create default user if it doesn't exist
    default_user, created = User.objects.get_or_create(
        username='default_user',
        defaults={
            'email': 'default@example.com',
            'first_name': 'Usuario',
            'last_name': 'Predeterminado',
            'is_active': True,
        }
    )

    # Get all models
    Producto = apps.get_model('inventory', 'Producto')
    CompraPadre = apps.get_model('inventory', 'CompraPadre')
    Compra = apps.get_model('inventory', 'Compra')
    Venta = apps.get_model('inventory', 'Venta')

    # Assign user to all existing records
    Producto.objects.filter(user__isnull=True).update(user=default_user)
    CompraPadre.objects.filter(user__isnull=True).update(user=default_user)
    Compra.objects.filter(user__isnull=True).update(user=default_user)
    Venta.objects.filter(user__isnull=True).update(user=default_user)


def reverse_migration(apps, schema_editor):
    """Reverse migration - remove user assignments"""
    # This would be complex to reverse safely, so we'll leave it empty
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0007_add_user_fields'),
    ]

    operations = [
        migrations.RunPython(
            create_default_user_and_assign_data,
            reverse_migration
        ),
    ]