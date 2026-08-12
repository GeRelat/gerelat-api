import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("gerelat", "0018_migrar_projetocampo_para_campodefinicao"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MembroGeRelat",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="membro_gerelat",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="MembroCliente",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                (
                    "data_promocao",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "cliente",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="membros",
                        to="gerelat.cliente",
                    ),
                ),
                (
                    "promovido_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="promocoes_cliente",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="membros_cliente",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "cliente"), name="unique_membro_cliente"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="SolicitacaoCliente",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pendente", "Pendente"),
                            ("aprovado", "Aprovado"),
                            ("recusado", "Recusado"),
                        ],
                        default="pendente",
                        max_length=20,
                    ),
                ),
                ("data_solicitacao", models.DateTimeField(auto_now_add=True)),
                (
                    "cliente",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="solicitacoes",
                        to="gerelat.cliente",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="solicitacoes_cliente",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="equipeprograma",
            name="papel_autorizacao",
            field=models.CharField(
                choices=[("membro", "Membro"), ("moderador", "Moderador")],
                default="membro",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="equipeprograma",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="equipes_programa",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="equipeprojeto",
            name="papel_autorizacao",
            field=models.CharField(
                choices=[("membro", "Membro"), ("moderador", "Moderador")],
                default="membro",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="equipeprojeto",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="equipes_projeto",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
