from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0009_make_user_fields_non_nullable'),
    ]

    operations = [
        migrations.AlterField(
            model_name='producto',
            name='id_producto',
            field=models.IntegerField(blank=True, editable=False, null=True),
        ),
        migrations.AddConstraint(
            model_name='producto',
            constraint=models.UniqueConstraint(fields=['user', 'id_producto'], name='unique_producto_por_usuario'),
        ),
    ]
