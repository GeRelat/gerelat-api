from __future__ import annotations

import re
from urllib.parse import quote

from django.utils.text import slugify


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
