import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("gerelat", "0032_agendamentorelatorio_scope_constraint_and_cleanup"),
    ]

    operations = [
        migrations.AlterField(
            model_name="agendamentorelatorio",
            name="dia_mes",
            field=models.IntegerField(
                blank=True,
                help_text="Dia do mês (1 a 31)",
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(31),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="agendamentorelatorio",
            name="dia_semana",
            field=models.IntegerField(
                blank=True,
                help_text="Dia da semana (1=Segunda-feira, 7=Domingo)",
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(7),
                ],
            ),
        ),
    ]
