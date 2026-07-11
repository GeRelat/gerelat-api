from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.gerelat.models import Banco, Programa, Projeto, EquipePrograma, Equ

User =  get_user_model()

class Command(BaseCommand):
    help = "Popular o banco de dados com dados de teste"

    def handle(self, *args, **kwargs):
        self.stdout.write("Limpando dados antigos...")

        self.stdout.write("Criando usuários de teste...")
        usuario_teste, created = User.objects.get_or_create(
            username="usuario_teste", 
            defaults={"email": "teste@cliente.com"}
        )
        if created:
            usuario_teste.set_password("senha123")
            usuario_teste.save()
            self.stdout.write("Usuário de teste criado com sucesso.")

        self.stdout.write("Criando dados falsos...")

        self.stdout.write(self.style.SUCCESS("Banco de dados populado com sucesso! Usuario : cliente_teste, senha: senha123"))
