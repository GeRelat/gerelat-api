from typing import Any

from django.core.exceptions import ValidationError

from ..enums import CampoTipo


def _raise_schema_error(message: str) -> None:
    raise ValidationError(message)


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _raise_schema_error(f"{label} deve ser um objeto JSON.")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        _raise_schema_error(f"{label} deve ser uma lista.")
    return value


def _require_str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _raise_schema_error(f"{label} deve ser um texto.")
    return value


def _validate_prosemirror_node(node: Any) -> None:
    if not isinstance(node, dict):
        _raise_schema_error("Estrutura ProseMirror inválida.")
    node_type = node.get("type")
    if not isinstance(node_type, str) or not node_type.strip():
        _raise_schema_error("Estrutura ProseMirror inválida.")

    if node_type == "text":
        text_value = node.get("text")
        if not isinstance(text_value, str):
            _raise_schema_error("Estrutura ProseMirror inválida.")
        if "content" in node:
            _raise_schema_error("Estrutura ProseMirror inválida.")
        return

    if "attrs" in node and not isinstance(node["attrs"], dict):
        _raise_schema_error("Estrutura ProseMirror inválida.")

    if "content" in node:
        content = _require_list(node["content"], "content")
        for child in content:
            _validate_prosemirror_node(child)


def validate_text(value: Any) -> None:
    data = _require_dict(value, "Texto")
    if data.get("type") != "doc":
        _raise_schema_error("Texto deve possuir type='doc'.")

    content = _require_list(data.get("content"), "content")
    if not content:
        _raise_schema_error("Texto deve conter ao menos um parágrafo.")

    for block in content:
        if not isinstance(block, dict) or block.get("type") != "paragraph":
            _raise_schema_error("Texto deve conter apenas parágrafos.")
        block_content = _require_list(block.get("content"), "content")
        if not block_content:
            _raise_schema_error("Parágrafo deve conter texto.")
        for node in block_content:
            if not isinstance(node, dict) or node.get("type") != "text":
                _raise_schema_error("Texto deve conter apenas nós de texto.")
            _require_str(node.get("text"), "text")


def validate_richtext(value: Any) -> None:
    data = _require_dict(value, "Texto rico")
    if data.get("type") != "doc":
        _raise_schema_error("Texto rico deve possuir type='doc'.")

    content = _require_list(data.get("content"), "content")
    for node in content:
        _validate_prosemirror_node(node)


def validate_table(value: Any) -> None:
    data = _require_dict(value, "Tabela")
    if "columns" not in data or "rows" not in data:
        _raise_schema_error("Tabela deve possuir columns e rows.")

    columns = _require_list(data.get("columns"), "columns")
    rows = _require_list(data.get("rows"), "rows")

    if not columns:
        _raise_schema_error("Tabela deve possuir ao menos uma coluna.")
    if not rows:
        _raise_schema_error("Tabela deve possuir ao menos uma linha.")

    column_keys: list[str] = []
    for column in columns:
        if not isinstance(column, dict):
            _raise_schema_error("Colunas devem ser objetos JSON.")
        key = _require_str(column.get("key"), "key")
        label = _require_str(column.get("label"), "label")
        column_keys.append(key)
        if not label:
            _raise_schema_error("Colunas devem possuir label.")

    expected_keys = set(column_keys)
    for row in rows:
        if not isinstance(row, dict):
            _raise_schema_error("Linhas devem ser objetos JSON.")
        row_keys = set(row.keys())
        if row_keys != expected_keys:
            _raise_schema_error("Linhas devem conter exatamente as chaves das colunas.")


def validate_image(value: Any) -> None:
    data = _require_dict(value, "Imagem")
    if "asset_id" not in data:
        _raise_schema_error("Imagem deve possuir asset_id.")

    asset_id = data.get("asset_id")
    if not isinstance(asset_id, int) or asset_id <= 0:
        _raise_schema_error("asset_id inválido.")

    for dimension in ("width_mm", "height_mm"):
        if dimension not in data:
            continue
        dimension_value = data.get(dimension)
        if dimension_value is None:
            continue
        if not isinstance(dimension_value, (int, float)) or dimension_value <= 0:
            _raise_schema_error("Dimensão inválida.")

    if "caption" in data and data["caption"] is not None:
        _require_str(data.get("caption"), "caption")


def validate_prosemirror_doc(value: Any) -> Any:
    """Valida que `value` é um documento ProseMirror raiz (dict com type='doc').

    Levanta `ValidationError` do Django que o DRF converte automaticamente
    nas camadas de serializer. Retorna `value` para uso em validate_<field>.
    """
    if not isinstance(value, dict) or value.get("type") != "doc":
        _raise_schema_error(
            "modelo_json deve ser um documento ProseMirror válido com type='doc'."
        )
    return value


def validate_document_value(tipo: str, value: Any) -> None:
    if tipo not in CampoTipo.values:
        _raise_schema_error("Tipo de campo inválido.")

    if tipo == CampoTipo.TEXT:
        validate_text(value)
    elif tipo == CampoTipo.RICHTEXT:
        validate_richtext(value)
    elif tipo == CampoTipo.TABLE:
        validate_table(value)
    elif tipo == CampoTipo.IMAGE:
        validate_image(value)
