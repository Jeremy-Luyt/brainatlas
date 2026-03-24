from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..utils.json_io import read_json, write_json
from ..utils.paths import project_root, project_workspace


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _suffix_label(file_name: str) -> str:
    lower = file_name.lower()
    if lower.endswith(".v3draw"):
        return "v3draw"
    if lower.endswith(".nii.gz"):
        return "nii.gz"
    if lower.endswith(".nii"):
        return "nii"
    if lower.endswith(".tiff"):
        return "tiff"
    if lower.endswith(".tif"):
        return "tif"
    if lower.endswith(".mhd"):
        return "mhd"
    if lower.endswith(".mha"):
        return "mha"
    if lower.endswith(".nrrd"):
        return "nrrd"
    return "unknown"


def _sample_dir(project_id: str, sample_id: str) -> Path:
    path = project_workspace(project_id) / "samples" / sample_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_sample(project_id: str, original_filename: str, stored_path: Path, sample_id: str | None = None) -> dict[str, Any]:
    sample_id = sample_id or uuid4().hex[:12]
    sample_dir = _sample_dir(project_id, sample_id)
    payload: dict[str, Any] = {
        "sample_id": sample_id,
        "project_id": project_id,
        "filename": original_filename,
        "input_format": _suffix_label(original_filename),
        "stored_path": str(stored_path),
        "converted": {},
        "preview": {},
        "stats": {},
        "prepare_status": "pending",
        "global_registration_status": "idle",
        "created_at": _now(),
        "updated_at": _now(),
    }
    write_json(sample_dir / "sample.json", payload)
    return payload


def _iter_sample_files() -> list[Path]:
    root = project_root() / "data" / "projects"
    if not root.exists():
        return []
    return list(root.glob("*/samples/*/sample.json"))


def get_sample(sample_id: str) -> dict[str, Any] | None:
    for p in _iter_sample_files():
        if p.parent.name == sample_id:
            return read_json(p)
    return None


def update_sample(sample_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    for p in _iter_sample_files():
        if p.parent.name == sample_id:
            data = read_json(p)
            data.update(updates)
            data["updated_at"] = _now()
            write_json(p, data)
            return data
    raise KeyError(sample_id)


def get_sample_dir(project_id: str, sample_id: str) -> Path:
    return _sample_dir(project_id, sample_id)
