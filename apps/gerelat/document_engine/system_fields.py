"""Registro de campos nativos das entidades (Cliente/Programa/Projeto/Evento)
que são automaticamente expostos como variáveis de gap, sem precisar de
cadastro manual em CampoDefinicao.

Convenção de referencia: "sistema.<nivel>.<campo>" (ex. "sistema.projeto.parceira").
Esse prefixo é reservado e não pode ser usado por CampoDefinicao.referencia.
"""

from __future__ import annotations

from typing import Any

from ..enums import CampoTipo

SISTEMA_PREFIXO = "sistema."

# Whitelist de campos "de negócio" por nível (exclui ids, FKs, timestamps de
# auditoria e campos de lock).
SYSTEM_FIELDS: dict[str, list[str]] = {
    "cliente": ["nome", "cnpj", "nome_contato", "email_contato", "fone_contato"],
    "programa": ["nome", "lei_criacao", "convenio_dados"],
    "projeto": ["nome", "parceira", "sigla"],
    "evento": ["nome", "local", "endereco", "data", "objetivo"],
}


def system_referencia(nivel: str, campo: str) -> str:
    return f"{SISTEMA_PREFIXO}{nivel}.{campo}"


def is_system_referencia(referencia: str) -> bool:
    return referencia.startswith(SISTEMA_PREFIXO)


def get_system_fields_for_level(nivel: str) -> list[tuple[str, str, str]]:
    """Retorna trios (referencia, tipo, descricao) para popular autocomplete."""
    return [
        (system_referencia(nivel, campo), CampoTipo.TEXT, campo)
        for campo in SYSTEM_FIELDS.get(nivel, [])
    ]


def _field_value(instance: Any, campo: str) -> Any:
    value = getattr(instance, campo, None)
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def resolve_system_variables(
    *,
    cliente=None,
    programa=None,
    projeto=None,
    evento=None,
) -> dict[str, Any]:
    """Constrói {referencia: valor} para os campos nativos das instâncias informadas."""
    instances = {
        "cliente": cliente,
        "programa": programa,
        "projeto": projeto,
        "evento": evento,
    }
    context: dict[str, Any] = {}
    for nivel, instance in instances.items():
        if instance is None:
            continue
        for campo in SYSTEM_FIELDS.get(nivel, []):
            context[system_referencia(nivel, campo)] = _field_value(instance, campo)
    return context
