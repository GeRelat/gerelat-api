from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("gerelat", "0024_migrate_acesso_to_membros"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="acessoprograma",
            name="unique_acesso_programa",
        ),
        migrations.RemoveConstraint(
            model_name="acessoprojeto",
            name="unique_acesso_projeto",
        ),
        migrations.RemoveField(
            model_name="acessoprojeto",
            name="projeto",
        ),
        migrations.RemoveField(
            model_name="acessoprojeto",
            name="user",
        ),
        migrations.DeleteModel(
            name="AcessoPrograma",
        ),
        migrations.DeleteModel(
            name="AcessoProjeto",
        ),
    ]
