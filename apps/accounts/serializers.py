from typing import cast

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.gerelat.models import (
    Cliente,
    MembroCliente,
    MembroGeRelat,
    MembroPrograma,
    MembroProjeto,
    SolicitacaoCliente,
)

from .models import UserManager

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    cliente = serializers.PrimaryKeyRelatedField(
        queryset=Cliente.objects.all(), required=False, allow_null=True, write_only=True
    )

    class Meta:
        model = User
        fields = ["full_name", "email", "password", "cliente"]

    def create(self, validated_data):
        cliente = validated_data.pop("cliente", None)
        manager = cast(UserManager, User.objects)
        user = manager.create_user(**validated_data)
        if cliente is not None:
            SolicitacaoCliente.objects.get_or_create(user=user, cliente=cliente)
        return user


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Senha atual incorreta.")
        return value

    def save(self):
        assert isinstance(self.validated_data, dict), (
            "save() chamado antes de is_valid()"
        )
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()


class UserSerializer(serializers.ModelSerializer):
    contextos_acesso = serializers.SerializerMethodField()
    possui_contexto_acesso = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "email",
            "created_at",
            "possui_contexto_acesso",
            "contextos_acesso",
        ]

    def get_contextos_acesso(self, user):
        if hasattr(self, "_contextos_acesso_cache"):
            return self._contextos_acesso_cache

        admin_gerelat = MembroGeRelat.objects.filter(user=user).exists() or bool(
            getattr(user, "is_superuser", False)
        )
        if admin_gerelat:
            clientes_admin = [
                {
                    "id": cliente.id,
                    "nome": cliente.nome,
                    "papel": "admin",
                    "logomarca": cliente.logomarca_url,
                }
                for cliente in Cliente.objects.select_related("logomarca").order_by(
                    "nome"
                )
            ]
        else:
            clientes_admin = [
                {
                    "id": membro.cliente_id,
                    "nome": membro.cliente.nome,
                    "papel": "admin",
                    "logomarca": membro.cliente.logomarca_url,
                }
                for membro in MembroCliente.objects.select_related(
                    "cliente__logomarca"
                ).filter(user=user)
            ]
        programas = [
            {
                "id": membro.programa_id,
                "nome": membro.programa.nome,
                "cliente_id": membro.programa.cliente_id,
                "cliente_nome": membro.programa.cliente.nome
                if membro.programa.cliente
                else None,
                "cliente_logomarca": membro.programa.cliente.logomarca_url
                if membro.programa.cliente
                else "",
                "papel": "membro",
            }
            for membro in MembroPrograma.objects.select_related(
                "programa__cliente__logomarca"
            ).filter(user=user)
        ]
        projetos = [
            {
                "id": membro.projeto_id,
                "nome": membro.projeto.nome,
                "programa_id": membro.projeto.programa_id,
                "cliente_id": membro.projeto.programa.cliente_id
                if membro.projeto.programa
                else None,
                "cliente_nome": membro.projeto.programa.cliente.nome
                if membro.projeto.programa and membro.projeto.programa.cliente
                else None,
                "cliente_logomarca": membro.projeto.programa.cliente.logomarca_url
                if membro.projeto.programa and membro.projeto.programa.cliente
                else "",
                "papel": "membro",
            }
            for membro in MembroProjeto.objects.select_related(
                "projeto__programa__cliente__logomarca"
            ).filter(user=user)
        ]
        solicitacoes_pendentes = [
            {"id": solicitacao.id, "cliente_id": solicitacao.cliente_id}
            for solicitacao in SolicitacaoCliente.objects.filter(
                user=user, status=SolicitacaoCliente.STATUS_PENDENTE
            )
        ]
        resultado = {
            "admin_gerelat": admin_gerelat,
            "clientes_admin": clientes_admin,
            "programas": programas,
            "projetos": projetos,
            "solicitacoes_pendentes": solicitacoes_pendentes,
        }
        self._contextos_acesso_cache = resultado
        return resultado

    def get_possui_contexto_acesso(self, user):
        contextos = self.get_contextos_acesso(user)
        return bool(
            contextos["admin_gerelat"]
            or contextos["clientes_admin"]
            or contextos["programas"]
            or contextos["projetos"]
        )
