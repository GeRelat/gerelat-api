import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("gerelat", "0021_bootstrap_membro_gerelat"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveField(
            model_name="equipeprograma",
            name="papel_autorizacao",
        ),
        migrations.RemoveField(
            model_name="equipeprograma",
            name="user",
        ),
        migrations.RemoveField(
            model_name="equipeprojeto",
            name="papel_autorizacao",
        ),
        migrations.RemoveField(
            model_name="equipeprojeto",
            name="user",
        ),
        migrations.RemoveField(
            model_name="solicitacaocliente",
            name="programa",
        ),
        migrations.RemoveField(
            model_name="solicitacaocliente",
            name="projeto",
        ),
        migrations.CreateModel(
            name="AcessoPrograma",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                (
                    "papel",
                    models.CharField(
                        choices=[("membro", "Membro"), ("moderador", "Moderador")],
                        default="membro",
                        max_length=20,
                    ),
                ),
                ("data_criacao", models.DateTimeField(auto_now_add=True)),
                (
                    "programa",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="acessos",
                        to="gerelat.programa",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="acessos_programa",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "programa"), name="unique_acesso_programa"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="AcessoProjeto",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                (
                    "papel",
                    models.CharField(
                        choices=[("membro", "Membro"), ("moderador", "Moderador")],
                        default="membro",
                        max_length=20,
                    ),
                ),
                ("data_criacao", models.DateTimeField(auto_now_add=True)),
                (
                    "projeto",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="acessos",
                        to="gerelat.projeto",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="acessos_projeto",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "projeto"), name="unique_acesso_projeto"
                    )
                ],
            },
        ),
    ]
