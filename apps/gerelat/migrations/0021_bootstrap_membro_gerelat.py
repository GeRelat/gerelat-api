from django.db import migrations


def bootstrap_first_gerelat_admin(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    MembroGeRelat = apps.get_model("gerelat", "MembroGeRelat")

    if MembroGeRelat.objects.exists():
        return

    target_user = (
        User.objects.filter(is_superuser=True).order_by("id").first()
        or User.objects.filter(role="admin").order_by("id").first()
        or User.objects.order_by("id").first()
    )

    if target_user is None:
        return

    MembroGeRelat.objects.create(user_id=target_user.id)


class Migration(migrations.Migration):
    dependencies = [
        ("gerelat", "0020_solicitacaocliente_programa_projeto"),
    ]

    operations = [
        migrations.RunPython(bootstrap_first_gerelat_admin, migrations.RunPython.noop),
    ]
