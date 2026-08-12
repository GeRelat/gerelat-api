import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("gerelat", "0029_assetuso"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AgendamentoRelatorio",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("nome", models.CharField(max_length=255)),
                ("documento_json", models.JSONField(blank=True, default=dict)),
                (
                    "tipo_agendamento",
                    models.CharField(
                        choices=[("pontual", "Pontual"), ("recorrente", "Recorrente")],
                        default="pontual",
                        max_length=20,
                    ),
                ),
                ("data_hora_execucao", models.DateTimeField(blank=True, null=True)),
                (
                    "recorrencia",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("diario", "Diário"),
                            ("semanal", "Semanal"),
                            ("mensal", "Mensal"),
                        ],
                        max_length=20,
                        null=True,
                    ),
                ),
                ("horario_execucao", models.TimeField(blank=True, null=True)),
                ("dia_semana", models.IntegerField(blank=True, null=True)),
                ("dia_mes", models.IntegerField(blank=True, null=True)),
                ("ativo", models.BooleanField(default=True)),
                ("data_criacao", models.DateTimeField(auto_now_add=True)),
                ("ultima_atualizacao", models.DateTimeField(auto_now=True)),
                ("ultima_execucao", models.DateTimeField(blank=True, null=True)),
                ("proxima_execucao", models.DateTimeField(blank=True, null=True)),
                (
                    "cliente",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="agendamentos",
                        to="gerelat.cliente",
                    ),
                ),
                (
                    "criado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="agendamentos_relatorio",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "evento",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="agendamentos",
                        to="gerelat.evento",
                    ),
                ),
                (
                    "programa",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="agendamentos",
                        to="gerelat.programa",
                    ),
                ),
                (
                    "projeto",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="agendamentos",
                        to="gerelat.projeto",
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="agendamentos",
                        to="gerelat.template",
                    ),
                ),
            ],
        ),
    ]
