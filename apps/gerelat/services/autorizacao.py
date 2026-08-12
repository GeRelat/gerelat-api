from apps.gerelat.models import (
    MembroCliente,
    MembroGeRelat,
    MembroPrograma,
    MembroProjeto,
)

NIVEIS = ["membro_projeto", "membro_programa", "admin_cliente", "admin_gerelat"]


def get_nivel_acesso(user, projeto) -> str | None:
    """Retorna o nível mais alto de acesso do usuário sobre o projeto, ou None."""
    if not user or not user.is_authenticated:
        return None
    if MembroGeRelat.objects.filter(user=user).exists():
        return "admin_gerelat"
    if MembroCliente.objects.filter(
        user=user, cliente=projeto.programa.cliente
    ).exists():
        return "admin_cliente"
    if MembroPrograma.objects.filter(user=user, programa=projeto.programa).exists():
        return "membro_programa"
    if MembroProjeto.objects.filter(user=user, projeto=projeto).exists():
        return "membro_projeto"
    return None


def get_nivel_acesso_programa(user, programa) -> str | None:
    """Retorna o nível de acesso do usuário no programa."""
    if not user or not user.is_authenticated:
        return None
    if MembroGeRelat.objects.filter(user=user).exists():
        return "admin_gerelat"
    if MembroCliente.objects.filter(user=user, cliente=programa.cliente).exists():
        return "admin_cliente"
    if MembroPrograma.objects.filter(user=user, programa=programa).exists():
        return "membro_programa"
    if MembroProjeto.objects.filter(user=user, projeto__programa=programa).exists():
        return "membro_projeto"
    return None


def get_nivel_acesso_cliente(user, cliente) -> str | None:
    """Retorna o nível de acesso do usuário no cliente."""
    if not user or not user.is_authenticated:
        return None
    if MembroGeRelat.objects.filter(user=user).exists():
        return "admin_gerelat"
    if MembroCliente.objects.filter(user=user, cliente=cliente).exists():
        return "admin_cliente"
    if MembroPrograma.objects.filter(user=user, programa__cliente=cliente).exists():
        return "membro_programa"
    if MembroProjeto.objects.filter(
        user=user, projeto__programa__cliente=cliente
    ).exists():
        return "membro_projeto"
    return None
