from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.gerelat.models import MembroGeRelat


class Command(BaseCommand):
    help = "Cria o usuário Administrador inicial (Superuser + MembroGeRelat)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            default="admin@gerelat.tech",
            help="E-mail do administrador (padrão: admin@gerelat.tech)",
        )
        parser.add_argument(
            "--password",
            type=str,
            default="admin123",
            help="Senha do administrador (padrão: admin123)",
        )
        parser.add_argument(
            "--name",
            type=str,
            default="Administrador GeRelat",
            help="Nome completo do administrador",
        )

    def handle(self, *args, **options):
        email = options["email"]
        password = options["password"]
        full_name = options["name"]

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "full_name": full_name,
                "is_superuser": True,
                "is_staff": True,
                "role": "admin",
            },
        )

        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Usuário administrador '{email}' criado com sucesso!"
                )
            )
        else:
            user.is_superuser = True
            user.is_staff = True
            user.role = "admin"
            user.set_password(password)
            user.save()
            self.stdout.write(
                self.style.SUCCESS(f"Usuário administrador '{email}' atualizado.")
            )

        MembroGeRelat.objects.get_or_create(user=user)
        self.stdout.write(
            self.style.SUCCESS(f"Vínculo de MembroGeRelat garantido para '{email}'.")
        )
