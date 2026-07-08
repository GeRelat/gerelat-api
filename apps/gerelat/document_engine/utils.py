from __future__ import annotations

import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

from django.core.files.storage import default_storage
from docxtpl import DocxTemplate


def extract_text_from_value(value: Any) -> str:
    if not isinstance(value, dict):
        return ""

    content = value.get("content")
    if not isinstance(content, list):
        return ""

    texts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_content = block.get("content")
        if not isinstance(block_content, list):
            continue
        for node in block_content:
            if not isinstance(node, dict):
                continue
            if node.get("type") != "text":
                continue
            text = node.get("text")
            if isinstance(text, str):
                texts.append(text)

    return " ".join(texts).strip()


def build_render_context(raw_context: dict[str, Any]) -> dict[str, str]:
    return {key: extract_text_from_value(value) for key, value in raw_context.items()}


def render_docx_from_template(
    template_path: str,
    context: dict[str, str],
) -> BytesIO:
    with default_storage.open(template_path, "rb") as source:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            local_template_path = tmpdir_path / "template.docx"
            local_template_path.write_bytes(source.read())

            doc = DocxTemplate(str(local_template_path))
            doc.render(context)

            output_buffer = BytesIO()
            doc.save(output_buffer)
            output_buffer.seek(0)

    return output_buffer
