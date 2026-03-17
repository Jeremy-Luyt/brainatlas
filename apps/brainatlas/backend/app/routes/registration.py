from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.registration_service import run_registration
from ..services.task_service import create_task, update_task
from ..utils.paths import project_workspace


router = APIRouter(prefix="/registration", tags=["registration"])


class RegistrationRequest(BaseModel):
    project_id: str = "default"
    moving_path: str
    fixed_path: str


@router.post("")
def registration(req: RegistrationRequest) -> dict:
    moving = Path(req.moving_path)
    fixed = Path(req.fixed_path)
    if not moving.exists() or not fixed.exists():
        raise HTTPException(status_code=404, detail="moving_path or fixed_path not found")
    task = create_task(task_type="registration", payload=req.model_dump())
    update_task(task["task_id"], "running")
    result = run_registration(moving=moving, fixed=fixed, output_dir=project_workspace(req.project_id) / "registration")
    return update_task(task["task_id"], "completed", result=result)
