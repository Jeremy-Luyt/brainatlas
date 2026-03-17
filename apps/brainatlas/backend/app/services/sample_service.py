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


def _samples_dir(project_id: str) -> Path:
    path = project_workspace(project_id) / "samples"
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_sample(project_id: str, original_filename: str, stored_path: Path) -> dict[str, Any]:
    sample_id = uuid4().hex[:12]
    payload: dict[str, Any] = {
        "sample_id": sample_id,
        "project_id": project_id,
        "filename": original_filename,
        "input_format": _suffix_label(original_filename),
        "stored_path": str(stored_path),
        "converted_format": None,
        "image_size": None,
        "prepare_status": "pending",
        "global_registration_status": "idle",
        "output_path": None,
        "log_path": None,
        "preview_paths": {},
        "created_at": _now(),
        "updated_at": _now(),
    }
    write_json(_samples_dir(project_id) / f"{sample_id}.json", payload)
    return payload


def _iter_sample_files() -> list[Path]:
    root = project_root() / "data" / "projects"
    if not root.exists():
        return []
    return list(root.glob("*/samples/*.json"))


def get_sample(sample_id: str) -> dict[str, Any] | None:
    for p in _iter_sample_files():
        if p.stem == sample_id:
            return read_json(p)
    return None


def update_sample(sample_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    for p in _iter_sample_files():
        if p.stem == sample_id:
            data = read_json(p)
            data.update(updates)
            data["updated_at"] = _now()
            write_json(p, data)
            return data
    raise KeyError(sample_id)
