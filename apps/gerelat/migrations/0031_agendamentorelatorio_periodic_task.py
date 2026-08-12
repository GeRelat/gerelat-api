import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_celery_beat", "0001_initial"),
        ("gerelat", "0030_agendamentorelatorio"),
    ]

    operations = [
        migrations.AddField(
            model_name="agendamentorelatorio",
            name="periodic_task",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="agendamento_relatorio",
                to="django_celery_beat.periodictask",
            ),
        ),
    ]
