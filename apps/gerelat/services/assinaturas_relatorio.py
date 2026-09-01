"""Resolve os signatários de um relatório para o bloco de assinaturas do .docx.

Um relatório pode usar as assinaturas configuradas no template
(`AssinaturaTemplate`) ou uma seleção feita na hora da geração. O resultado é uma
lista de dicts `{nome, cargo, nome_equipe}` que é congelada em
`Relatorio.metadados["sistema.assinaturas"]` e renderizada por
`document_engine.renderer._render_assinaturas`.
"""

from __future__ import annotations

from ..models import AssinaturaTemplate, EquipePrograma, EquipeProjeto


def _linha_programa(equipe: EquipePrograma) -> dict:
    return {"nome": equipe.nome, "cargo": equipe.cargo, "nome_equipe": ""}


def _linha_projeto(equipe: EquipeProjeto) -> dict:
    return {
        "nome": equipe.nome,
        "cargo": equipe.cargo,
        "nome_equipe": equipe.nome_equipe,
    }


def resolver_assinaturas(
    template_id: int,
    assinaturas_override: list[dict] | None = None,
) -> list[dict]:
    """Lista `[{nome, cargo, nome_equipe}]` na ordem de exibição.

    `assinaturas_override`: lista de `{"equipe_programa": id}` /
    `{"equipe_projeto": id}` — quando informada, resolve esses ids na ordem dada
    (ids inexistentes são ignorados). Sem override, usa as `AssinaturaTemplate`
    do template, ordenadas por id.
    """
    if assinaturas_override:
        prog_ids = [
            item["equipe_programa"]
            for item in assinaturas_override
            if item.get("equipe_programa")
        ]
        proj_ids = [
            item["equipe_projeto"]
            for item in assinaturas_override
            if item.get("equipe_projeto")
        ]
        prog = {e.id: e for e in EquipePrograma.objects.filter(id__in=prog_ids)}
        proj = {e.id: e for e in EquipeProjeto.objects.filter(id__in=proj_ids)}

        linhas: list[dict] = []
        for item in assinaturas_override:
            pid = item.get("equipe_programa")
            jid = item.get("equipe_projeto")
            if pid and pid in prog:
                linhas.append(_linha_programa(prog[pid]))
            elif jid and jid in proj:
                linhas.append(_linha_projeto(proj[jid]))
        return linhas

    linhas = []
    for assinatura in (
        AssinaturaTemplate.objects.filter(template_id=template_id)
        .select_related("equipe_programa", "equipe_projeto")
        .order_by("id")
    ):
        if assinatura.equipe_programa_id:
            linhas.append(_linha_programa(assinatura.equipe_programa))
        elif assinatura.equipe_projeto_id:
            linhas.append(_linha_projeto(assinatura.equipe_projeto))
    return linhas
