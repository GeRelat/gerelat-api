# Generated manually: migração de dados de ProjetoCampo (definição+valor
# conflados por Projeto) para o novo par CampoDefinicao (schema)/CampoValor
# (valor por instância). Cada ProjetoCampo vira uma CampoDefinicao escopada
# diretamente no mesmo Projeto (nivel_aplicacao="projeto"), preservando o
# comportamento atual sem vazar o campo para projetos irmãos.

from django.db import migrations


def migrar_projeto_campo(apps, schema_editor):
    ProjetoCampo = apps.get_model("gerelat", "ProjetoCampo")
    CampoDefinicao = apps.get_model("gerelat", "CampoDefinicao")
    CampoValor = apps.get_model("gerelat", "CampoValor")

    for campo in ProjetoCampo.objects.all():
        definicao = CampoDefinicao.objects.create(
            projeto_id=campo.projeto_id,
            nivel_aplicacao="projeto",
            referencia=campo.referencia,
            descricao=campo.descricao,
            tipo=campo.tipo,
            obrigatorio=campo.obrigatorio,
            escopo_key=f"projeto:{campo.projeto_id}",
            legacy_projeto_campo_id=campo.id,
        )
        CampoValor.objects.create(
            definicao=definicao,
            projeto_id=campo.projeto_id,
            alvo_key=f"projeto:{campo.projeto_id}",
            valor=campo.valor,
        )


def reverter_migracao(apps, schema_editor):
    CampoDefinicao = apps.get_model("gerelat", "CampoDefinicao")
    CampoValor = apps.get_model("gerelat", "CampoValor")

    CampoValor.objects.filter(
        definicao__legacy_projeto_campo_id__isnull=False
    ).delete()
    CampoDefinicao.objects.filter(legacy_projeto_campo_id__isnull=False).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("gerelat", "0017_alter_template_nivel"),
    ]

    operations = [
        migrations.RunPython(migrar_projeto_campo, reverter_migracao),
    ]
