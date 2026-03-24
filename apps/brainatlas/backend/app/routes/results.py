from fastapi import APIRouter, HTTPException

from ..services.task_service import get_task


router = APIRouter(prefix="/results", tags=["results"])


@router.get("/{task_id}")
def result_detail(task_id: str, project_id: str = "default") -> dict:
    task = get_task(task_id, project_id=project_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    if not task.get("result"):
        raise HTTPException(status_code=404, detail="result not ready")
    return {"task_id": task_id, "task_type": task.get("task_type"), "result": task.get("result")}
