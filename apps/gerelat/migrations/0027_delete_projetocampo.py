from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("gerelat", "0026_asset_cliente_asset_programa_asset_projeto_and_more"),
    ]

    operations = [
        migrations.DeleteModel(
            name="ProjetoCampo",
        ),
    ]
