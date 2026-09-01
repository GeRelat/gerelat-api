"""Detecta dinamicamente qual o nível mais profundo (cliente < programa <
projeto < evento) exigido para resolver todos os gaps de um template, dado
o conjunto de CampoDefinicao visíveis a partir da cadeia de ancestrais do
template (cliente/programa/projeto) e os campos nativos (sistema.*)."""

from __future__ import annotations

import operator
from functools import reduce

from django.db.models import Q

from ..enums import NIVEL_ORDEM, CampoTipo
from .converters import extract_gap_refs
from .system_fields import SISTEMA_PREFIXO, is_system_referencia


def _visible_definicoes(*, cliente=None, programa=None, projeto=None):
    """QuerySet de CampoDefinicao visíveis a partir da cadeia de ancestrais."""
    from ..models import CampoDefinicao

    conditions = []
    if cliente:
        conditions.append(Q(cliente_id=cliente.id))
    if programa:
        conditions.append(Q(programa_id=programa.id))
    if projeto:
        conditions.append(Q(projeto_id=projeto.id))

    if not conditions:
        return CampoDefinicao.objects.none()

    return CampoDefinicao.objects.filter(reduce(operator.or_, conditions))


def _chaves_da_definicao(d) -> list[str]:
    """Todas as variantes de chave sob as quais uma definição pode ser
    referenciada (crua, com prefixo de escopo, e sem prefixo) — espelha o que
    `build_variables_context` grava no contexto de renderização."""
    chaves = [d.referencia]
    if d.cliente_id:
        clean_ref = d.referencia.removeprefix("cliente.")
        chaves += [f"cliente.{clean_ref}", clean_ref]
    elif d.programa_id:
        clean_ref = d.referencia.removeprefix("programa.")
        chaves += [f"programa.{clean_ref}", clean_ref]
    elif d.projeto_id:
        clean_ref = d.referencia.removeprefix("projeto.")
        chaves += [f"projeto.{clean_ref}", clean_ref]
    return chaves


def _richtext_docs_por_ref(definicoes, refs) -> dict[str, dict]:
    """Mapa {ref: documento} dos valores das variáveis richtext citadas em
    `refs`, para que `extract_gap_refs` possa descer para dentro deles.

    Sobre-aproximação deliberada e no lado seguro: reúne o conteúdo de TODOS
    os valores de cada definição richtext (um relatório pode ter qualquer
    alvo). Se qualquer valor de `texto_padrao` cita `sistema.evento.nome`, todo
    template que use `texto_padrao` passa a exigir um evento."""
    from ..models import CampoValor

    ref_para_def: dict[str, object] = {}
    for d in definicoes:
        if d.tipo != CampoTipo.RICHTEXT:
            continue
        for chave in _chaves_da_definicao(d):
            ref_para_def[chave] = d

    citadas = {ref_para_def[r].id: ref_para_def[r] for r in refs if r in ref_para_def}
    if not citadas:
        return {}

    por_def: dict[int, dict] = {}
    for def_id, valor in CampoValor.objects.filter(
        definicao_id__in=citadas
    ).values_list("definicao_id", "valor"):
        if isinstance(valor, dict) and valor.get("type") == "doc":
            acc = por_def.setdefault(def_id, {"type": "doc", "content": []})
            acc["content"].extend(valor.get("content", []))

    docs_por_ref: dict[str, dict] = {}
    for def_id, d in citadas.items():
        doc = por_def.get(def_id)
        if doc:
            for chave in _chaves_da_definicao(d):
                docs_por_ref[chave] = doc
    return docs_por_ref


def scan_required_nivel(
    template_json: dict, *, cliente=None, programa=None, projeto=None
) -> str | None:
    """Retorna o nivel_aplicacao mais profundo referenciado pelos gaps do
    template (inclusive os usados transitivamente por valores de variáveis
    richtext), ou None se nenhum gap depender de uma variável ligada a nível."""
    definicoes = list(
        _visible_definicoes(cliente=cliente, programa=programa, projeto=projeto)
    )

    nivel_map: dict[str, str] = {}
    for d in definicoes:
        for chave in _chaves_da_definicao(d):
            nivel_map[chave] = d.nivel_aplicacao

    refs_diretos = extract_gap_refs(template_json)
    docs_por_ref = _richtext_docs_por_ref(definicoes, refs_diretos)
    refs = (
        extract_gap_refs(template_json, docs_por_ref)
        if docs_por_ref
        else refs_diretos
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
