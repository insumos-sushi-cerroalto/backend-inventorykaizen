# Generated manually for multi-user support

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0006_alter_producto_precio_unitario'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.AddField(
            model_name='compra',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='compras', to='auth.user'),
        ),
        migrations.AddField(
            model_name='comprapadre',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='compras_padre', to='auth.user'),
        ),
        migrations.AddField(
            model_name='producto',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='productos', to='auth.user'),
        ),
        migrations.AddField(
            model_name='venta',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='ventas', to='auth.user'),
        ),
    ]