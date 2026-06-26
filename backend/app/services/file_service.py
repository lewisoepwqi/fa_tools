from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from app.core.config import get_settings


def detect_file_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix not in {"csv", "xlsx", "xls"}:
        raise ValueError(f"Unsupported file type: {suffix}")
    return suffix


def save_uploaded_file(filename: str, content: bytes) -> dict[str, str | int]:
    settings = get_settings()
    file_id = str(uuid.uuid4())
    file_type = detect_file_type(filename)
    digest = hashlib.sha256(content).hexdigest()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    storage_key = f"{file_id}.{file_type}"
    (upload_dir / storage_key).write_bytes(content)

    return {
        "id": file_id,
        "original_filename": filename,
        "file_type": file_type,
        "file_size": len(content),
        "sha256": digest,
        "storage_key": storage_key,
        "status": "pending",
    }
