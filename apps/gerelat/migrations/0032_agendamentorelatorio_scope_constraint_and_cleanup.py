from django.db import migrations, models
from django.db.models import Q


def remover_task_fantasma_e_agendamentos_invalidos(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    try:
        PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
        PeriodicTask.objects.using(db_alias).filter(
            name="Processar agendamentos de relatórios"
        ).delete()
    except Exception:
        pass

    try:
        AgendamentoRelatorio = apps.get_model("gerelat", "AgendamentoRelatorio")
        invalid = AgendamentoRelatorio.objects.using(db_alias).exclude(
            Q(cliente__isnull=False, programa__isnull=True, projeto__isnull=True)
            | Q(programa__isnull=False, cliente__isnull=True, projeto__isnull=True)
            | Q(projeto__isnull=False, cliente__isnull=True, programa__isnull=True)
        )
        invalid.delete()
    except Exception:
        pass


class Migration(migrations.Migration):
    dependencies = [
        ("gerelat", "0031_agendamentorelatorio_periodic_task"),
    ]

    operations = [
        migrations.RunPython(
            remover_task_fantasma_e_agendamentos_invalidos,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="agendamentorelatorio",
            name="dia_semana",
            field=models.IntegerField(
                blank=True,
                help_text="Dia da semana (1=Segunda-feira, 7=Domingo)",
                null=True,
            ),
        ),
        migrations.AddConstraint(
            model_name="agendamentorelatorio",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("cliente__isnull", False),
                        ("programa__isnull", True),
                        ("projeto__isnull", True),
                    ),
                    models.Q(
                        ("cliente__isnull", True),
                        ("programa__isnull", False),
                        ("projeto__isnull", True),
                    ),
                    models.Q(
                        ("cliente__isnull", True),
                        ("programa__isnull", True),
                        ("projeto__isnull", False),
                    ),
                    _connector="OR",
                ),
                name="agendamento_relatorio_exactly_one_scope",
            ),
        ),
    ]
