from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..services.prepare_service import run_prepare
from ..services.sample_service import get_sample, update_sample
from ..services.task_service import create_task, update_task


router = APIRouter(prefix="/samples", tags=["samples"])


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

    task = create_task(task_type="sample_prepare", payload={"sample_id": sample_id})
    update_task(task["task_id"], "running")

    try:
        updated_sample = run_prepare(sample_id)
        return update_task(task["task_id"], "completed", result={"sample": updated_sample})
    except Exception as e:
        update_task(task["task_id"], "failed", result={"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))
