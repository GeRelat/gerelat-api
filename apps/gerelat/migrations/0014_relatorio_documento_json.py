from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("gerelat", "0013_template_modelo_json"),
    ]

    operations = [
        migrations.AddField(
            model_name="relatorio",
            name="documento_json",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
