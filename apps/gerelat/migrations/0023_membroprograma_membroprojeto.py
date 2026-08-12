import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("gerelat", "0022_remove_equipeprograma_papel_autorizacao_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MembroPrograma",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("data_criacao", models.DateTimeField(auto_now_add=True)),
                (
                    "programa",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="membros",
                        to="gerelat.programa",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="membros_programa",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "programa"), name="unique_membro_programa"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="MembroProjeto",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("data_criacao", models.DateTimeField(auto_now_add=True)),
                (
                    "projeto",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="membros",
                        to="gerelat.projeto",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="membros_projeto",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "projeto"), name="unique_membro_projeto"
                    )
                ],
            },
        ),
    ]
