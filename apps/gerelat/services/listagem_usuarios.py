"""
Serviço de listagem e agregação de usuários por cliente.

Centraliza a lógica de busca e agregação de todos os usuários
com acesso a um cliente, independente da fonte (admin, programa, projeto).
"""

from ..models import MembroCliente, MembroPrograma, MembroProjeto


def listar_usuarios_cliente(cliente):
    """
    Retorna lista agregada de TODOS os usuários com qualquer acesso
    neste cliente — independente da fonte do acesso.

    Args:
        cliente: instância de Cliente

    Returns:
        list[dict]: cada item contém:
            - user: int (ID do usuário)
            - user_email: str
            - user_nome: str
            - is_admin_cliente: bool
            - membro_cliente_id: int | None
            - membros_programa: [{"id": int, "programa_id": int, "programa_nome": str}]
            - membros_projeto: [{"id": int, "projeto_id": int, "projeto_nome": str}]
            - acessos_programa: [...]  # alias de membros_programa
            - acessos_projeto: [...]   # alias de membros_projeto
    """
    admin_records = MembroCliente.objects.filter(cliente=cliente).select_related("user")
    prog_records = MembroPrograma.objects.filter(
        programa__cliente=cliente
    ).select_related("user", "programa")
    proj_records = MembroProjeto.objects.filter(
        projeto__programa__cliente=cliente
    ).select_related("user", "projeto")

    membros = {}

    def _get_or_init(u):
        uid = u.id
        if uid not in membros:
            membros[uid] = {
                "user": uid,
                "user_email": u.email,
                "user_nome": getattr(u, "full_name", "") or "",
                "is_admin_cliente": False,
                "membro_cliente_id": None,
                "membros_programa": [],
                "membros_projeto": [],
                "acessos_programa": [],
                "acessos_projeto": [],
            }
        return membros[uid]

    for rec in admin_records:
        entry = _get_or_init(rec.user)
        entry["is_admin_cliente"] = True
        entry["membro_cliente_id"] = rec.id

    for rec in prog_records:
        entry = _get_or_init(rec.user)
        prog_item = {
            "id": rec.id,
            "programa_id": rec.programa_id,
            "programa_nome": rec.programa.nome,
        }
        entry["membros_programa"].append(prog_item)
        entry["acessos_programa"].append(prog_item)

    for rec in proj_records:
        entry = _get_or_init(rec.user)
        proj_item = {
            "id": rec.id,
            "projeto_id": rec.projeto_id,
            "projeto_nome": rec.projeto.nome,
        }
        entry["membros_projeto"].append(proj_item)
        entry["acessos_projeto"].append(proj_item)

    return list(membros.values())
