from apps.gerelat.models import (
    MembroCliente,
    MembroGeRelat,
    MembroPrograma,
    MembroProjeto,
)

NIVEIS = ["membro_projeto", "membro_programa", "admin_cliente", "admin_gerelat"]

_CACHE_ATTR = "_gerelat_cache"


def _get_cache(user) -> dict:
    """Retorna (criando se necessário) o namespace de cache do GeRelat no user."""
    cache = getattr(user, _CACHE_ATTR, None)
    if cache is None:
        cache = {}
        setattr(user, _CACHE_ATTR, cache)
    return cache


def invalidar_cache(user) -> None:
    """
    Limpa todo o cache de autorização do usuário.

    Chame isso após qualquer mutação de papéis (adicionar/remover
    MembroCliente, MembroPrograma, MembroProjeto, MembroGeRelat) dentro do
    mesmo ciclo de request, para que checagens subsequentes reflitam o novo
    estado do banco.
    """
    if hasattr(user, _CACHE_ATTR):
        delattr(user, _CACHE_ATTR)


def _is_platform_admin_cached(user) -> bool:
    """
    Verifica se o usuário é admin GeRelat, com cache no objeto user.

    Faz no máximo 1 query ao banco por instância de user — chamadas
    subsequentes na mesma request retornam o valor em memória.
    """
    cache = _get_cache(user)
    if "is_admin" not in cache:
        cache["is_admin"] = MembroGeRelat.objects.filter(user=user).exists()
    return cache["is_admin"]


def get_nivel_acesso(user, projeto) -> str | None:
    """Retorna o nível mais alto de acesso do usuário sobre o projeto, ou None."""
    if not user or not user.is_authenticated:
        return None
    if _is_platform_admin_cached(user):
        return "admin_gerelat"

    cache = _get_cache(user)

    if "clientes_admin_ids" in cache:
        if projeto.programa.cliente_id in cache["clientes_admin_ids"]:
            return "admin_cliente"
        if projeto.programa_id in cache["programas_membro_ids"]:
            return "membro_programa"
        if projeto.pk in cache["projetos_membro_ids"]:
            return "membro_projeto"
        return None

    projetos_cache = cache.setdefault("nivel_projeto", {})
    pk = projeto.pk
    if pk not in projetos_cache:
        if MembroCliente.objects.filter(
            user=user, cliente=projeto.programa.cliente
        ).exists():
            resultado = "admin_cliente"
        elif MembroPrograma.objects.filter(
            user=user, programa=projeto.programa
        ).exists():
            resultado = "membro_programa"
        elif MembroProjeto.objects.filter(user=user, projeto=projeto).exists():
            resultado = "membro_projeto"
        else:
            resultado = None
        projetos_cache[pk] = resultado
    return projetos_cache[pk]


def get_nivel_acesso_programa(user, programa) -> str | None:
    """Retorna o nível de acesso do usuário no programa, ou None."""
    if not user or not user.is_authenticated:
        return None
    if _is_platform_admin_cached(user):
        return "admin_gerelat"

    cache = _get_cache(user)

    if "clientes_admin_ids" in cache:
        if programa.cliente_id in cache["clientes_admin_ids"]:
            return "admin_cliente"
        if programa.pk in cache["programas_membro_ids"]:
            return "membro_programa"
        if programa.pk in cache["programas_com_membro_projeto"]:
            return "membro_projeto"
        return None

    programas_cache = cache.setdefault("nivel_programa", {})
    pk = programa.pk
    if pk not in programas_cache:
        if MembroCliente.objects.filter(user=user, cliente=programa.cliente).exists():
            resultado = "admin_cliente"
        elif MembroPrograma.objects.filter(user=user, programa=programa).exists():
            resultado = "membro_programa"
        elif MembroProjeto.objects.filter(
            user=user, projeto__programa=programa
        ).exists():
            resultado = "membro_projeto"
        else:
            resultado = None
        programas_cache[pk] = resultado
    return programas_cache[pk]


def get_nivel_acesso_cliente(user, cliente) -> str | None:
    """Retorna o nível de acesso do usuário no cliente, ou None."""
    if not user or not user.is_authenticated:
        return None
    if _is_platform_admin_cached(user):
        return "admin_gerelat"

    cache = _get_cache(user)

    if "clientes_admin_ids" in cache:
        if cliente.pk in cache["clientes_admin_ids"]:
            return "admin_cliente"
        if cliente.pk in cache["clientes_com_membro_programa"]:
            return "membro_programa"
        if cliente.pk in cache["clientes_com_membro_projeto"]:
            return "membro_projeto"
        return None

    clientes_cache = cache.setdefault("nivel_cliente", {})
    pk = cliente.pk
    if pk not in clientes_cache:
        if MembroCliente.objects.filter(user=user, cliente=cliente).exists():
            resultado = "admin_cliente"
        elif MembroPrograma.objects.filter(
            user=user, programa__cliente=cliente
        ).exists():
            resultado = "membro_programa"
        elif MembroProjeto.objects.filter(
            user=user, projeto__programa__cliente=cliente
        ).exists():
            resultado = "membro_projeto"
        else:
            resultado = None
        clientes_cache[pk] = resultado
    return clientes_cache[pk]


def precarregar_acessos(user) -> None:
    """
    Pré-carrega em até 7 queries fixas os IDs necessários para resolver
    o nível de acesso do usuário sobre qualquer cliente/programa/projeto,
    incluindo acesso por herança, sem tocar o banco de novo por objeto.
    """
    if not user or not user.is_authenticated:
        return
    if _is_platform_admin_cached(user):
        return

    cache = _get_cache(user)

    cache["clientes_admin_ids"] = set(
        MembroCliente.objects.filter(user=user).values_list("cliente_id", flat=True)
    )
    cache["programas_membro_ids"] = set(
        MembroPrograma.objects.filter(user=user).values_list("programa_id", flat=True)
    )
    cache["projetos_membro_ids"] = set(
        MembroProjeto.objects.filter(user=user).values_list("projeto_id", flat=True)
    )

    cache["programas_com_membro_projeto"] = set(
        MembroProjeto.objects.filter(user=user).values_list(
            "projeto__programa_id", flat=True
        )
    )
    cache["clientes_com_membro_programa"] = set(
        MembroPrograma.objects.filter(user=user).values_list(
            "programa__cliente_id", flat=True
        )
    )
    cache["clientes_com_membro_projeto"] = set(
        MembroProjeto.objects.filter(user=user).values_list(
            "projeto__programa__cliente_id", flat=True
        )
    )
