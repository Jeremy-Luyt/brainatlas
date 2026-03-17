from pathlib import Path
from typing import Any

from fastapi import UploadFile

from .sample_service import create_sample
from ..utils.paths import uploads_root


def save_upload(file: UploadFile, project_id: str = "default") -> dict[str, Any]:
    safe_name = Path(file.filename or "upload.bin").name
    target = uploads_root() / project_id / safe_name
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as f:
        while chunk := file.file.read(1024 * 1024):
            f.write(chunk)
    sample = create_sample(project_id=project_id, original_filename=safe_name, stored_path=target)
    return {
        "project_id": project_id,
        "sample_id": sample["sample_id"],
        "filename": safe_name,
        "saved_path": str(target),
    }
