from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("gerelat", "0012_template_is_locked_template_locked_at_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="template",
            name="modelo_json",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
