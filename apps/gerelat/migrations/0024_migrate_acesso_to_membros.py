from django.db import migrations


def copy_acessos_to_membros(apps, schema_editor):
    AcessoPrograma = apps.get_model("gerelat", "AcessoPrograma")
    AcessoProjeto = apps.get_model("gerelat", "AcessoProjeto")
    MembroPrograma = apps.get_model("gerelat", "MembroPrograma")
    MembroProjeto = apps.get_model("gerelat", "MembroProjeto")

    for acesso in AcessoPrograma.objects.all():
        MembroPrograma.objects.get_or_create(user=acesso.user, programa=acesso.programa)

    for acesso in AcessoProjeto.objects.all():
        if not MembroPrograma.objects.filter(
            user=acesso.user, programa=acesso.projeto.programa
        ).exists():
            MembroProjeto.objects.get_or_create(
                user=acesso.user, projeto=acesso.projeto
            )


class Migration(migrations.Migration):
    dependencies = [
        ("gerelat", "0023_membroprograma_membroprojeto"),
    ]

    operations = [
        migrations.RunPython(copy_acessos_to_membros, migrations.RunPython.noop),
    ]
