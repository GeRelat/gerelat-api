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
        try:
            evento = Evento.objects.select_related(
                "projeto__programa__cliente",
            ).get(id=evento_id)
            if evento.projeto:
                projeto = evento.projeto
                programa = projeto.programa
                cliente = programa.cliente
        except Evento.DoesNotExist:
            evento = None

    if not projeto and projeto_id:
        try:
            projeto = Projeto.objects.select_related("programa__cliente").get(
                id=projeto_id
            )
            if not programa:
                programa = projeto.programa
            if not cliente:
                cliente = programa.cliente
        except Projeto.DoesNotExist:
            pass

    if not programa and programa_id:
        try:
            programa = Programa.objects.select_related("cliente").get(id=programa_id)
            if not cliente:
                cliente = programa.cliente
        except Programa.DoesNotExist:
            pass

    if not cliente and cliente_id:
        try:
            cliente = Cliente.objects.get(id=cliente_id)
        except Cliente.DoesNotExist:
            pass

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

    # Logomarcas do cabeçalho do relatório, congeladas aqui para sobreviverem em
    # Relatorio.metadados (o snapshot que o download consome — Relatorio não tem
    # FK de escopo). Prefixo reservado 'sistema.' evita colisão com
    # CampoDefinicao.referencia (ver models.CampoDefinicao.clean).
    context["sistema.cabecalho.logo_cliente_asset_id"] = (
        cliente.logomarca_id if cliente else None
    )
    context["sistema.cabecalho.logo_parceira_asset_id"] = (
        projeto.logomarca_id if projeto else None
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

        def _sort_key(cv):
            d = cv.definicao
            if d.cliente_id:
                return 1
            if d.programa_id:
                return 2
            if d.projeto_id:
                return 3
            return 4

        campo_valores_ordenados = sorted(campo_valores, key=_sort_key)

        for cv in campo_valores_ordenados:
            ref = cv.definicao.referencia
            d = cv.definicao
            if d.cliente_id:
                clean_ref = ref.removeprefix("cliente.")
                context[f"cliente.{clean_ref}"] = cv.valor
                context[clean_ref] = cv.valor
            elif d.programa_id:
                clean_ref = ref.removeprefix("programa.")
                context[f"programa.{clean_ref}"] = cv.valor
                context[clean_ref] = cv.valor
            elif d.projeto_id:
                clean_ref = ref.removeprefix("projeto.")
                context[f"projeto.{clean_ref}"] = cv.valor
                context[clean_ref] = cv.valor
            else:
                clean_ref = ref.removeprefix("evento.")
                context[f"evento.{clean_ref}"] = cv.valor
                context[clean_ref] = cv.valor

    return context
