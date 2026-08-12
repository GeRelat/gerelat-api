import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("gerelat", "0028_alter_programa_logomarca_alter_projeto_logomarca"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssetUso",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                (
                    "tipo_uso",
                    models.CharField(
                        choices=[
                            ("logomarca_cliente", "Logomarca de Cliente"),
                            ("logomarca_programa", "Logomarca de Programa"),
                            ("logomarca_projeto", "Logomarca de Projeto"),
                            ("campo_valor_imagem", "Variável de Imagem"),
                        ],
                        max_length=50,
                    ),
                ),
                ("data_criacao", models.DateTimeField(auto_now_add=True)),
                (
                    "asset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="usos",
                        to="gerelat.asset",
                    ),
                ),
                (
                    "campo_valor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="asset_usos",
                        to="gerelat.campovalor",
                    ),
                ),
                (
                    "cliente",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="asset_usos",
                        to="gerelat.cliente",
                    ),
                ),
                (
                    "programa",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="asset_usos",
                        to="gerelat.programa",
                    ),
                ),
                (
                    "projeto",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="asset_usos",
                        to="gerelat.projeto",
                    ),
                ),
            ],
            options={
                "verbose_name": "Uso de Asset",
                "verbose_name_plural": "Usos de Asset",
            },
        ),
    ]
