"""
registration.py — 配准路由（兼容旧前端）

端点：
- POST /api/registration         提交全局配准后台任务（前端兼容入口）
- GET  /api/registration/latest   查看最新配准结果

注意：主要入口已统一到 /api/tasks/register/global
这里保留 POST /api/registration 作为前端兼容入口，内部转发到 task 系统。
"""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.sample_service import get_sample
from ..services.task_service import create_task
from ..services.task_runner import submit_task


router = APIRouter(prefix="/registration", tags=["registration"])


class RegistrationRequest(BaseModel):
    project_id: str = "default"
    moving_sample_id: str
    moving_path: str = ""  # 保留兼容，实际从 sample 读取
    fixed_path: str


@router.post("")
def registration(req: RegistrationRequest) -> dict:
    """提交全局配准后台任务（前端兼容入口）"""
    sample = get_sample(req.moving_sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail=f"sample not found: {req.moving_sample_id}")

    if str(sample.get("filename", "")).lower() == "global.v3draw":
        raise HTTPException(status_code=400, detail="moving sample cannot be global.v3draw")

    moving = Path(sample.get("stored_path", ""))
    fixed = Path(req.fixed_path)
    if not moving.exists():
        raise HTTPException(status_code=404, detail=f"moving file not found: {moving}")
    if not fixed.exists():
        raise HTTPException(status_code=404, detail=f"fixed path not found: {req.fixed_path}")

    payload = {
        "moving_sample_id": req.moving_sample_id,
        "project_id": req.project_id,
        "moving_path": str(moving),
        "fixed_path": str(fixed),
    }
    task = create_task(
        task_type="global_registration",
        payload=payload,
        project_id=req.project_id,
    )
    task_id = task["task_id"]
    payload["task_id"] = task_id

    submit_task("global_registration", task_id, req.project_id, payload)

    return {"task_id": task_id, "status": "queued"}


@router.get("/latest")
def latest_registration(project_id: str = "default") -> dict:
    """查看项目级最新配准结果（保留兼容）"""
    from ..services.task_service import list_tasks as _list
    tasks = _list(project_id)
    completed = [
        t for t in tasks
        if t.get("task_type") == "global_registration" and t.get("status") == "completed"
    ]
    if not completed:
        return {"status": "none"}
    latest = completed[0]  # list_tasks 已按 mtime 降序
    return {
        "status": "completed",
        "task_id": latest["task_id"],
        "result": latest.get("result"),
    }
