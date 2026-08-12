import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("gerelat", "0019_clienteadmin_equipeprogramamembro_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="solicitacaocliente",
            name="programa",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="solicitacoes_cliente",
                to="gerelat.programa",
            ),
        ),
        migrations.AddField(
            model_name="solicitacaocliente",
            name="projeto",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="solicitacoes_cliente",
                to="gerelat.projeto",
            ),
        ),
    ]
