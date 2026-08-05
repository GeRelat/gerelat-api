"""Constrói o dicionário plano {referencia: valor} usado por
`converters.replace_placeholders`, combinando campos nativos do sistema
(system_fields) com os valores customizados (CampoValor) visíveis para a
cadeia de instâncias (cliente/programa/projeto/evento) informada.
"""

from __future__ import annotations

import operator
from functools import reduce
from typing import Any

from django.db.models import Q

from .system_fields import resolve_system_variables


def _resolve_chain(
    *,
    cliente_id: int | None = None,
    programa_id: int | None = None,
    projeto_id: int | None = None,
    evento_id: int | None = None,
):
    from ..models import Cliente, Evento, Programa, Projeto

    evento = None
    projeto = None
    programa = None
    cliente = None

    if evento_id:
        evento = Evento.objects.select_related(
            "projeto__programa__cliente"
        ).get(id=evento_id)
        projeto = evento.projeto
    elif projeto_id:
        projeto = Projeto.objects.select_related("programa__cliente").get(
            id=projeto_id
        )

    if projeto:
        programa = projeto.programa
    elif programa_id:
        programa = Programa.objects.select_related("cliente").get(id=programa_id)

    if programa:
        cliente = programa.cliente
    elif cliente_id:
        cliente = Cliente.objects.get(id=cliente_id)

    return cliente, programa, projeto, evento


def build_variables_context(
    *,
    cliente_id: int | None = None,
    programa_id: int | None = None,
    projeto_id: int | None = None,
    evento_id: int | None = None,
) -> dict[str, Any]:
    from ..models import CampoValor

    cliente, programa, projeto, evento = _resolve_chain(
        cliente_id=cliente_id,
        programa_id=programa_id,
        projeto_id=projeto_id,
        evento_id=evento_id,
    )

    context = resolve_system_variables(
        cliente=cliente, programa=programa, projeto=projeto, evento=evento
    )

    conditions = []
    if cliente:
        conditions.append(Q(cliente_id=cliente.id))
    if programa:
        conditions.append(Q(programa_id=programa.id))
    if projeto:
        conditions.append(Q(projeto_id=projeto.id))
    if evento:
        conditions.append(Q(evento_id=evento.id))

    if conditions:
        filtro = reduce(operator.or_, conditions)
        campo_valores = CampoValor.objects.filter(filtro).select_related("definicao")
        context.update({cv.definicao.referencia: cv.valor for cv in campo_valores})

    return context
