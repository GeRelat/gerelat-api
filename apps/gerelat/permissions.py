from typing import Any

from django.contrib.auth import get_user_model
from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.gerelat.models import MembroCliente, MembroGeRelat, Projeto
from apps.gerelat.services.autorizacao import (
    get_nivel_acesso,
    get_nivel_acesso_cliente,
    get_nivel_acesso_programa,
)

User = get_user_model()


def is_authenticated(user: Any) -> bool:
    return bool(user and getattr(user, "is_authenticated", False))


def is_platform_admin(user: Any) -> bool:
    return is_authenticated(user) and (
        getattr(user, "is_superuser", False)
        or MembroGeRelat.objects.filter(user=user).exists()
    )


def is_cliente_admin(user: Any, cliente: Any) -> bool:
    if is_platform_admin(user):
        return True
    if cliente is None:
        return False
    return MembroCliente.objects.filter(user=user, cliente=cliente).exists()


class IsPlatformAdmin(BasePermission):
    def has_permission(self, request, view):
        return is_platform_admin(request.user)

    def has_object_permission(self, request, view, obj):
        return is_platform_admin(request.user)


class PodeAcessarCliente(BasePermission):
    """
    Admin GeRelat: CRUD.
    Admin Cliente: RU (sem D).
    Membro Programa / Membro Projeto: R (somente leitura).
    """

    def has_permission(self, request, view):
        action = getattr(view, "action", None)
        if action == "publicos":
            return True
        if not is_authenticated(request.user):
            return False
        if request.method in SAFE_METHODS:
            return True
        if request.method == "POST":
            # Detail actions (usuarios, remover_usuario, atualizar_permissoes)
            # são verificados em has_object_permission — permitem admin de cliente.
            # Apenas criação de Cliente exige platform admin.
            if action in (
                "usuarios",
                "remover_usuario",
                "atualizar_permissoes",
                "create",
            ):
                return action != "create" or is_platform_admin(request.user)
            return is_platform_admin(request.user)
        return True

    def has_object_permission(self, request, view, obj):
        nivel = get_nivel_acesso_cliente(request.user, obj)
        if nivel is None:
            return False
        if request.method in SAFE_METHODS:
            return True
        if request.method == "DELETE":
            return nivel == "admin_gerelat"
        return nivel in ("admin_gerelat", "admin_cliente")


class PodeAcessarPrograma(BasePermission):
    """
    Admin GeRelat / Admin Cliente: CRUD.
    Membro Programa: RU (sem D).
    Membro Projeto: R (somente leitura).
    """

    def has_permission(self, request, view):
        return is_authenticated(request.user)

    def has_object_permission(self, request, view, obj):
        nivel = get_nivel_acesso_programa(request.user, obj)
        if nivel is None:
            return False
        if request.method in SAFE_METHODS:
            return True
        if request.method == "DELETE":
            return nivel in ("admin_gerelat", "admin_cliente")
        return nivel in ("admin_gerelat", "admin_cliente", "membro_programa")


class PodeAcessarProjeto(BasePermission):
    """
    Admin GeRelat / Admin Cliente / Membro Programa: CRUD.
    Membro Projeto: RU (sem D).
    """

    def has_permission(self, request, view):
        return is_authenticated(request.user)

    def has_object_permission(self, request, view, obj):
        nivel = get_nivel_acesso(request.user, obj)
        if nivel is None:
            return False
        if request.method in SAFE_METHODS:
            return True
        if request.method == "DELETE":
            return nivel in ("admin_gerelat", "admin_cliente", "membro_programa")
        return True


class PodeAcessarConteudoProjeto(BasePermission):
    """
    Qualquer nível com acesso ao Projeto (inclusive Membro Projeto) tem CRUD
    completo no conteúdo do Projeto.
    """

    def has_permission(self, request, view):
        return is_authenticated(request.user)

    def has_object_permission(self, request, view, obj):
        projeto = getattr(obj, "projeto", None)
        if projeto:
            return get_nivel_acesso(request.user, projeto) is not None
        # Para modelos associados via evento (ex: Relatorio -> Evento -> Projeto)
        evento = getattr(obj, "evento", None)
        if evento and getattr(evento, "projeto", None):
            return get_nivel_acesso(request.user, evento.projeto) is not None
        return True


class PodeAcessarConteudoPrograma(BasePermission):
    """
    Equipe fixa do Programa:
    - Escrita (POST, PUT, PATCH, DELETE): admin_gerelat, admin_cliente, membro_programa.
    - Leitura (GET): admin_gerelat, admin_cliente, membro_programa, membro_projeto.
    """

    def has_permission(self, request, view):
        return is_authenticated(request.user)

    def has_object_permission(self, request, view, obj):
        programa = getattr(obj, "programa", None)
        if not programa:
            return True
        nivel = get_nivel_acesso_programa(request.user, programa)
        if nivel is None:
            return False
        if request.method in SAFE_METHODS:
            return True
        return nivel in ("admin_gerelat", "admin_cliente", "membro_programa")


class PodeAcessarConteudoCliente(BasePermission):
    """CRUD completo para qualquer nível com acesso ao Cliente."""

    def has_permission(self, request, view):
        return is_authenticated(request.user)

    def has_object_permission(self, request, view, obj):
        cliente = getattr(obj, "cliente", None)
        if not cliente:
            return True
        return get_nivel_acesso_cliente(request.user, cliente) is not None


class PodeAcessarConteudoPorEscopo(BasePermission):
    """
    Para models com escopo multi-nível (Asset, ClasseEvento, Evento, Template, CampoDefinicao, CampoValor, TemplateClasseEvento):
    resolve dinamicamente qual FK (projeto, programa, cliente) está preenchida e aplica o get_nivel_acesso_* correspondente.
    """

    def has_permission(self, request, view):
        return is_authenticated(request.user)

    def has_object_permission(self, request, view, obj):
        is_safe = request.method in SAFE_METHODS

        # 1. Se tem projeto direto ou via relação
        projeto = getattr(obj, "projeto", None)
        if not projeto and hasattr(obj, "projeto_id") and obj.projeto_id:
            projeto = getattr(obj, "projeto", None)
        if projeto:
            return get_nivel_acesso(request.user, projeto) is not None

        # 2. Se tem programa direto
        programa = getattr(obj, "programa", None)
        if not programa and hasattr(obj, "programa_id") and obj.programa_id:
            programa = getattr(obj, "programa", None)
        if programa:
            nivel = get_nivel_acesso_programa(request.user, programa)
            if is_safe:
                return nivel is not None
            return nivel in ["admin_gerelat", "admin_cliente", "membro_programa"]

        # 3. Se tem cliente direto
        cliente = getattr(obj, "cliente", None)
        if not cliente and hasattr(obj, "cliente_id") and obj.cliente_id:
            cliente = getattr(obj, "cliente", None)
        if cliente:
            nivel = get_nivel_acesso_cliente(request.user, cliente)
            if is_safe:
                return nivel is not None
            return nivel in ["admin_gerelat", "admin_cliente"]

        # 4. Caso de TemplateClasseEvento (tem template e classe_evento)
        template = getattr(obj, "template", None)
        if template:
            return self.has_object_permission(request, view, template)

        # 5. Caso de CampoValor (pode apontar para definicao ou ter evento)
        evento = getattr(obj, "evento", None)
        if evento:
            return self.has_object_permission(request, view, evento)

        definicao = getattr(obj, "definicao", None)
        if definicao:
            return self.has_object_permission(request, view, definicao)

        return False


class PodeAcessarAssinaturaTemplate(BasePermission):
    """
    Para AssinaturaTemplate (via equipe_programa ou equipe_projeto).
    """

    def has_permission(self, request, view):
        return is_authenticated(request.user)

    def has_object_permission(self, request, view, obj):
        if getattr(obj, "equipe_programa_id", None):
            return (
                get_nivel_acesso_programa(request.user, obj.equipe_programa.programa)
                is not None
            )
        if getattr(obj, "equipe_projeto_id", None):
            return (
                get_nivel_acesso(request.user, obj.equipe_projeto.projeto) is not None
            )
        return False


class PodeGerenciarMembros(BasePermission):
    """Quem edita o Programa também gerencia seus membros e os de seus Projetos."""

    def has_permission(self, request, view):
        return is_authenticated(request.user)

    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Projeto):
            nivel = get_nivel_acesso(request.user, obj)
        else:
            nivel = get_nivel_acesso_programa(request.user, obj)
        return nivel in ("admin_gerelat", "admin_cliente", "membro_programa")
