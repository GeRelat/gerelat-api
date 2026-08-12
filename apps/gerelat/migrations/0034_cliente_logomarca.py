from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("gerelat", "0033_alter_agendamentorelatorio_dia_mes_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="cliente",
            name="logomarca",
            field=models.TextField(blank=True, default=""),
        ),
    ]
