from __future__ import annotations

import re
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import quote

from django.core.files.storage import default_storage
from django.utils.text import slugify
from docxtpl import DocxTemplate


def build_docx_filename_and_content_disposition(
    nome: str,
    *,
    fallback: str = "template",
) -> str:
    raw_name = nome or fallback
    safe = slugify(str(raw_name)) or fallback
    sanitized = re.sub(r'[\x00-\x1f\\/"\']+', " ", str(raw_name))
    sanitized = re.sub(r"\s+", " ", sanitized).strip()[:80] or safe

    content_disp = (
        f'attachment; filename="{sanitized}.docx"; '
        f"filename*=UTF-8''{quote(str(raw_name))}.docx"
    )
    return content_disp


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
