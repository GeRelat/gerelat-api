# Generated manually to restructure ClasseEvento (Programa scope only) and Evento (Projeto scope only)

import django.db.models.deletion
from django.db import migrations, models


def migrar_dados_escopo_classe_e_evento(apps, schema_editor):
    ClasseEvento = apps.get_model("gerelat", "ClasseEvento")
    Evento = apps.get_model("gerelat", "Evento")
    Programa = apps.get_model("gerelat", "Programa")
    Projeto = apps.get_model("gerelat", "Projeto")

    for ce in ClasseEvento.objects.filter(programa__isnull=True):
        if getattr(ce, "projeto_id", None):
            proj = Projeto.objects.filter(id=ce.projeto_id).first()
            if proj and proj.programa_id:
                ce.programa_id = proj.programa_id
                ce.save(update_fields=["programa"])
                continue
        if getattr(ce, "cliente_id", None):
            prog = Programa.objects.filter(cliente_id=ce.cliente_id).first()
            if prog:
                ce.programa_id = prog.id
                ce.save(update_fields=["programa"])
                continue
        prog = Programa.objects.first()
        if prog:
            ce.programa_id = prog.id
            ce.save(update_fields=["programa"])
        else:
            ce.delete()

    for ev in Evento.objects.filter(projeto__isnull=True):
        if getattr(ev, "programa_id", None):
            proj = Projeto.objects.filter(programa_id=ev.programa_id).first()
            if proj:
                ev.projeto_id = proj.id
                ev.save(update_fields=["projeto"])
                continue
        if getattr(ev, "cliente_id", None):
            proj = Projeto.objects.filter(programa__cliente_id=ev.cliente_id).first()
            if proj:
                ev.projeto_id = proj.id
                ev.save(update_fields=["projeto"])
                continue
        proj = Projeto.objects.first()
        if proj:
            ev.projeto_id = proj.id
            ev.save(update_fields=["projeto"])
        else:
            ev.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("gerelat", "0040_remove_relatorio_arquivo_gerado"),
    ]

    operations = [
        migrations.RunPython(
            migrar_dados_escopo_classe_e_evento,
            migrations.RunPython.noop,
        ),
        migrations.RemoveConstraint(
            model_name="classeevento",
            name="classe_evento_exactly_one_scope",
        ),
        migrations.RemoveConstraint(
            model_name="evento",
            name="evento_exactly_one_scope",
        ),
        migrations.RemoveField(
            model_name="classeevento",
            name="cliente",
        ),
        migrations.RemoveField(
            model_name="classeevento",
            name="projeto",
        ),
        migrations.AlterField(
            model_name="classeevento",
            name="programa",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="classes_evento",
                to="gerelat.programa",
            ),
        ),
        migrations.AlterModelOptions(
            name="classeevento",
            options={"ordering": ["nome_classe"]},
        ),
        migrations.RemoveField(
            model_name="evento",
            name="cliente",
        ),
        migrations.RemoveField(
            model_name="evento",
            name="programa",
        ),
        migrations.AlterField(
            model_name="evento",
            name="projeto",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="eventos",
                to="gerelat.projeto",
            ),
        ),
        migrations.AlterModelOptions(
            name="evento",
            options={"ordering": ["-data", "nome"]},
        ),
    ]
