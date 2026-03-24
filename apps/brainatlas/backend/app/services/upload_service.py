from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile

from .sample_service import create_sample
from ..utils.paths import project_workspace


def save_upload(file: UploadFile, project_id: str = "default") -> dict[str, Any]:
    safe_name = Path(file.filename or "upload.bin").name
    sample_id = uuid4().hex[:12]
    target = project_workspace(project_id) / "samples" / sample_id / "raw" / safe_name
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as f:
        while chunk := file.file.read(1024 * 1024):
            f.write(chunk)
    sample = create_sample(project_id=project_id, original_filename=safe_name, stored_path=target, sample_id=sample_id)
    return {
        "project_id": project_id,
        "sample_id": sample["sample_id"],
        "filename": safe_name,
        "saved_path": str(target),
    }
