from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.registration_service import run_registration
from ..services.sample_service import get_sample, update_sample
from ..services.task_service import create_task, get_task, list_tasks, update_task
from ..utils.paths import project_workspace


router = APIRouter(prefix="/tasks", tags=["tasks"])


class GlobalRegisterRequest(BaseModel):
    project_id: str = "default"
    moving_sample_id: str
    fixed_sample_id: str


@router.get("")
def tasks() -> list[dict]:
    return list_tasks()


@router.get("/{task_id}")
def task_detail(task_id: str) -> dict:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@router.post("/register/global")
def register_global(req: GlobalRegisterRequest) -> dict:
    moving_sample = get_sample(req.moving_sample_id)
    fixed_sample = get_sample(req.fixed_sample_id)
    if moving_sample is None or fixed_sample is None:
        raise HTTPException(status_code=404, detail="sample not found")
    moving_path = Path(moving_sample["stored_path"])
    fixed_path = Path(fixed_sample["stored_path"])
    if not moving_path.exists() or not fixed_path.exists():
        raise HTTPException(status_code=404, detail="sample file not found")
    task = create_task(task_type="global_registration", payload=req.model_dump())
    update_task(task["task_id"], "running")
    output_dir = project_workspace(req.project_id) / "registration" / task["task_id"]
    result = run_registration(moving=moving_path, fixed=fixed_path, output_dir=output_dir)
    update_sample(req.moving_sample_id, {"global_registration_status": "completed", "output_path": str(output_dir)})
    update_sample(req.fixed_sample_id, {"global_registration_status": "completed", "output_path": str(output_dir)})
    return update_task(task["task_id"], "completed", result=result)
