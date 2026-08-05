"""Detecta dinamicamente qual o nível mais profundo (cliente < programa <
projeto < evento) exigido para resolver todos os gaps de um template, dado
o conjunto de CampoDefinicao visíveis a partir da cadeia de ancestrais do
template (cliente/programa/projeto) e os campos nativos (sistema.*)."""

from __future__ import annotations

import operator
from functools import reduce

from django.db.models import Q

from ..enums import NIVEL_ORDEM
from .converters import extract_gap_refs
from .system_fields import SISTEMA_PREFIXO, is_system_referencia


def _visible_definicoes_nivel_map(*, cliente=None, programa=None, projeto=None) -> dict[str, str]:
    from ..models import CampoDefinicao

    conditions = []
    if cliente:
        conditions.append(Q(cliente_id=cliente.id))
    if programa:
        conditions.append(Q(programa_id=programa.id))
    if projeto:
        conditions.append(Q(projeto_id=projeto.id))

    if not conditions:
        return {}

    filtro = reduce(operator.or_, conditions)
    return {
        d.referencia: d.nivel_aplicacao
        for d in CampoDefinicao.objects.filter(filtro)
    }


def scan_required_nivel(
    template_json: dict, *, cliente=None, programa=None, projeto=None
) -> str | None:
    """Retorna o nivel_aplicacao mais profundo referenciado pelos gaps do
    template, ou None se nenhum gap depender de uma variável ligada a nível."""
    refs = extract_gap_refs(template_json)
    nivel_map = _visible_definicoes_nivel_map(
        cliente=cliente, programa=programa, projeto=projeto
    )

    deepest: str | None = None
    for ref in refs:
        if is_system_referencia(ref):
            nivel = ref[len(SISTEMA_PREFIXO) :].split(".", 1)[0]
        else:
            nivel = nivel_map.get(ref)

        if nivel is None or nivel not in NIVEL_ORDEM:
            continue
        if deepest is None or NIVEL_ORDEM[nivel] > NIVEL_ORDEM[deepest]:
            deepest = nivel

    return deepest
