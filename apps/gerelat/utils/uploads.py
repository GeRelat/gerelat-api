import uuid


def asset_upload_to(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    suffix = f".{ext}" if ext else ""
    return f"assets/{uuid.uuid4()}{suffix}"
