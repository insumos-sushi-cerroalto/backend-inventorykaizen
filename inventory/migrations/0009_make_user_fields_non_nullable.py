# Make user fields non-nullable

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0008_assign_default_user'),
    ]

    operations = [
        migrations.AlterField(
            model_name='compra',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='compras', to='auth.user'),
        ),
        migrations.AlterField(
            model_name='comprapadre',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='compras_padre', to='auth.user'),
        ),
        migrations.AlterField(
            model_name='producto',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='productos', to='auth.user'),
        ),
        migrations.AlterField(
            model_name='venta',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ventas', to='auth.user'),
        ),
    ]