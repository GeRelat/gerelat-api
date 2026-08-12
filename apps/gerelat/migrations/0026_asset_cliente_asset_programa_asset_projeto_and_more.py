import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("gerelat", "0025_remove_acessoprograma_unique_acesso_programa_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="cliente",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="assets",
                to="gerelat.cliente",
            ),
        ),
        migrations.AddField(
            model_name="asset",
            name="programa",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="assets",
                to="gerelat.programa",
            ),
        ),
        migrations.AddField(
            model_name="asset",
            name="projeto",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="assets",
                to="gerelat.projeto",
            ),
        ),
        migrations.AddField(
            model_name="classeevento",
            name="cliente",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="classes_evento",
                to="gerelat.cliente",
            ),
        ),
        migrations.AddField(
            model_name="classeevento",
            name="programa",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="classes_evento",
                to="gerelat.programa",
            ),
        ),
        migrations.AddField(
            model_name="evento",
            name="cliente",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="eventos",
                to="gerelat.cliente",
            ),
        ),
        migrations.AddField(
            model_name="evento",
            name="programa",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="eventos",
                to="gerelat.programa",
            ),
        ),
        migrations.AlterField(
            model_name="asset",
            name="id",
            field=models.AutoField(primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name="classeevento",
            name="projeto",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="classes_evento",
                to="gerelat.projeto",
            ),
        ),
        migrations.AlterField(
            model_name="evento",
            name="projeto",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="eventos",
                to="gerelat.projeto",
            ),
        ),
        migrations.AddConstraint(
            model_name="asset",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("cliente__isnull", False),
                        ("programa__isnull", True),
                        ("projeto__isnull", True),
                    ),
                    models.Q(
                        ("cliente__isnull", True),
                        ("programa__isnull", False),
                        ("projeto__isnull", True),
                    ),
                    models.Q(
                        ("cliente__isnull", True),
                        ("programa__isnull", True),
                        ("projeto__isnull", False),
                    ),
                    _connector="OR",
                ),
                name="asset_exactly_one_scope",
            ),
        ),
        migrations.AddConstraint(
            model_name="classeevento",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("cliente__isnull", False),
                        ("programa__isnull", True),
                        ("projeto__isnull", True),
                    ),
                    models.Q(
                        ("cliente__isnull", True),
                        ("programa__isnull", False),
                        ("projeto__isnull", True),
                    ),
                    models.Q(
                        ("cliente__isnull", True),
                        ("programa__isnull", True),
                        ("projeto__isnull", False),
                    ),
                    _connector="OR",
                ),
                name="classe_evento_exactly_one_scope",
            ),
        ),
        migrations.AddConstraint(
            model_name="evento",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("cliente__isnull", False),
                        ("programa__isnull", True),
                        ("projeto__isnull", True),
                    ),
                    models.Q(
                        ("cliente__isnull", True),
                        ("programa__isnull", False),
                        ("projeto__isnull", True),
                    ),
                    models.Q(
                        ("cliente__isnull", True),
                        ("programa__isnull", True),
                        ("projeto__isnull", False),
                    ),
                    _connector="OR",
                ),
                name="evento_exactly_one_scope",
            ),
        ),
    ]
