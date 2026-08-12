"""Service de gestão de acessos hierárquicos.

Centraliza toda a lógica de transição de estado de acesso (adicionar/remover/sincronizar)
para facilitar testes isolados e evitar duplicação de regras entre views.
"""

from django.db import transaction
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.gerelat.models import (
    MembroCliente,
    MembroPrograma,
    MembroProjeto,
    Programa,
    Projeto,
)


class ConflitoDeAcessoError(Exception):
    """Usuário já tem acesso via nível superior; ação exige confirmação explícita."""

    pass


def adicionar_membro_projeto(user, projeto, forcar_rebaixamento=False):
    """
    Concede acesso de Membro Projeto. Se o usuário já é Membro Programa
    do Programa pai, isso é um REBAIXAMENTO e precisa de confirmação.
    """
    ja_tem_acesso_via_programa = MembroPrograma.objects.filter(
        user=user, programa=projeto.programa
    ).exists()

    if ja_tem_acesso_via_programa and not forcar_rebaixamento:
        raise ConflitoDeAcessoError(
            "Usuário já tem acesso a este Projeto via Membro Programa. "
            "Confirme o rebaixamento para restringir o acesso apenas a este Projeto."
        )

    if ja_tem_acesso_via_programa and forcar_rebaixamento:
        MembroPrograma.objects.filter(user=user, programa=projeto.programa).delete()

    membro, _ = MembroProjeto.objects.get_or_create(user=user, projeto=projeto)
    return membro


def adicionar_membro_programa(user, programa):
    """
    Concede acesso de Membro Programa. Isso é uma PROMOÇÃO em relação a
    qualquer MembroProjeto existente dentro do Programa — remove os registros
    redundantes automaticamente, sem precisar de confirmação.
    """
    MembroProjeto.objects.filter(user=user, projeto__programa=programa).delete()
    membro, _ = MembroPrograma.objects.get_or_create(user=user, programa=programa)
    return membro


@transaction.atomic
def remover_usuario_do_cliente(cliente, user_id, solicitante):
    """
    Remove TODOS os acessos de um usuário neste cliente:
      - Deleta MembroCliente (admin) se existir
      - Deleta MembroPrograma de todos os programas deste cliente
      - Deleta MembroProjeto de todos os projetos deste cliente

    Args:
        cliente: instância de Cliente
        user_id: ID do usuário a ser removido
        solicitante: User que está fazendo a remoção (para validação)

    Raises:
        DRFValidationError: se o solicitante tentar se remover sendo o último admin
    """
    # Prevenir remoção do último admin pelo próprio admin
    if str(solicitante.id) == str(user_id):
        remaining_admins = MembroCliente.objects.filter(cliente=cliente).count()
        if (
            remaining_admins <= 1
            and MembroCliente.objects.filter(cliente=cliente, user_id=user_id).exists()
        ):
            raise DRFValidationError(
                "Você não pode se remover: é o último administrador deste cliente."
            )

    MembroCliente.objects.filter(user_id=user_id, cliente=cliente).delete()
    MembroPrograma.objects.filter(user_id=user_id, programa__cliente=cliente).delete()
    MembroProjeto.objects.filter(
        user_id=user_id, projeto__programa__cliente=cliente
    ).delete()


@transaction.atomic
def sincronizar_acessos_cliente(
    cliente,
    usuario_alvo,
    e_admin_cliente,
    programas_ids,
    projetos_ids,
    promovido_por,
):
    """
    Substitui integralmente o conjunto de acessos de um usuário dentro de um Cliente.
    Centraliza a regra de sincronização usada por aprovar() e atualizar_permissoes().

    Args:
        cliente: instância de Cliente
        usuario_alvo: User que terá permissões atualizadas
        e_admin_cliente: bool - se True, concede MembroCliente e remove demais acessos
        programas_ids: list[int] - IDs de programas a conceder acesso
        projetos_ids: list[int] - IDs de projetos a conceder acesso
        promovido_por: User que está fazendo a mudança

    Raises:
        DRFValidationError: se IDs não pertencerem ao cliente
    """
    # Validar que programas pertencem ao cliente
    if programas_ids:
        count = Programa.objects.filter(id__in=programas_ids, cliente=cliente).count()
        if count != len(programas_ids):
            raise DRFValidationError(
                "Um ou mais programas não pertencem a este cliente."
            )

    # Validar que projetos pertencem ao cliente
    if projetos_ids:
        count = Projeto.objects.filter(
            id__in=projetos_ids, programa__cliente=cliente
        ).count()
        if count != len(projetos_ids):
            raise DRFValidationError(
                "Um ou mais projetos não pertencem a este cliente."
            )

    if e_admin_cliente:
        # Conceder admin, remover membros de programa/projeto
        MembroCliente.objects.get_or_create(
            user=usuario_alvo,
            cliente=cliente,
            defaults={"promovido_por": promovido_por},
        )
        MembroPrograma.objects.filter(
            user=usuario_alvo, programa__cliente=cliente
        ).delete()
        MembroProjeto.objects.filter(
            user=usuario_alvo, projeto__programa__cliente=cliente
        ).delete()
    else:
        # Remover admin se existia
        MembroCliente.objects.filter(user=usuario_alvo, cliente=cliente).delete()

        # Sincronizar programas: remover os que não estão na lista
        MembroPrograma.objects.filter(
            user=usuario_alvo, programa__cliente=cliente
        ).exclude(programa_id__in=programas_ids).delete()

        # Adicionar os novos programas
        for prog_id in programas_ids:
            programa = Programa.objects.get(id=prog_id, cliente=cliente)
            adicionar_membro_programa(usuario_alvo, programa)

        # Sincronizar projetos: remover os que não estão na lista e não são
        # cobertos por programa adicionado
        MembroProjeto.objects.filter(
            user=usuario_alvo, projeto__programa__cliente=cliente
        ).exclude(projeto_id__in=projetos_ids).delete()

        # Adicionar os novos projetos (pular se programa já foi adicionado)
        for proj_id in projetos_ids:
            projeto = Projeto.objects.get(id=proj_id, programa__cliente=cliente)
            # Se o programa do projeto já foi adicionado, pular (já tem acesso via programa)
            if projeto.programa_id not in programas_ids:
                adicionar_membro_projeto(usuario_alvo, projeto)
