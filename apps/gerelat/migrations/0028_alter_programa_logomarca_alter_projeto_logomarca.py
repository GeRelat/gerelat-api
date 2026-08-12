from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("gerelat", "0027_delete_projetocampo"),
    ]

    operations = [
        migrations.AlterField(
            model_name="programa",
            name="logomarca",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="projeto",
            name="logomarca",
            field=models.TextField(blank=True, default=""),
        ),
    ]
