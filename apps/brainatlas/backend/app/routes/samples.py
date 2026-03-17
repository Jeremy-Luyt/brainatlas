from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..services.prepare_service import prepare_preview
from ..services.sample_service import get_sample, update_sample
from ..services.task_service import create_task, update_task
from ..utils.paths import data_root, project_workspace


router = APIRouter(prefix="/samples", tags=["samples"])


def _to_static_url(path_str: str) -> str:
    src = Path(path_str).resolve()
    rel = src.relative_to(data_root().resolve()).as_posix()
    return f"/api/static/{rel}"


@router.get("/{sample_id}")
def sample_detail(sample_id: str) -> dict:
    sample = get_sample(sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail="sample not found")
    return sample


@router.post("/{sample_id}/prepare")
def prepare_sample(sample_id: str) -> dict:
    sample = get_sample(sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail="sample not found")
    input_path = Path(sample["stored_path"])
    if not input_path.exists():
        raise HTTPException(status_code=404, detail="sample file not found")
    task = create_task(task_type="sample_prepare", payload={"sample_id": sample_id})
    update_task(task["task_id"], "running")
    output_dir = project_workspace(sample["project_id"]) / "previews" / sample_id
    prep_result = prepare_preview(input_path=input_path, output_dir=output_dir)
    preview_paths = prep_result.get("preview_paths", {})
    api_preview_paths = {k: _to_static_url(v) for k, v in preview_paths.items()}
    updated = update_sample(
        sample_id,
        {
            "converted_format": "nii.gz",
            "image_size": f'{prep_result.get("size_bytes", 0)} bytes',
            "prepare_status": "completed",
            "preview_paths": api_preview_paths,
            "output_path": str(output_dir),
            "log_path": str(output_dir / "prepare.log"),
        },
    )
    return update_task(task["task_id"], "completed", result={"sample": updated})
