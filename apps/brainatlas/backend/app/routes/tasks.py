"""
tasks.py — 统一任务管理路由

端点：
- POST /api/tasks/register/global   提交全局配准后台任务
- GET  /api/tasks                    列出所有任务
- GET  /api/tasks/{task_id}          获取任务详情
- GET  /api/tasks/{task_id}/log      获取任务日志
"""
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from ..services.sample_service import get_sample
from ..services.task_service import (
    create_task,
    get_task,
    list_tasks,
    task_log_path,
)
from ..services.task_runner import submit_task


router = APIRouter(prefix="/tasks", tags=["tasks"])


# ---------------------------------------------------------------------------
#  请求模型
# ---------------------------------------------------------------------------

class GlobalRegisterRequest(BaseModel):
    project_id: str = "default"
    moving_sample_id: str
    fixed_path: str  # atlas 模板路径或 fixed 样本路径


# ---------------------------------------------------------------------------
#  POST /api/tasks/register/global — 提交全局配准（立即返回 task_id）
# ---------------------------------------------------------------------------

@router.post("/register/global")
def register_global(req: GlobalRegisterRequest) -> dict:
    sample = get_sample(req.moving_sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail=f"sample not found: {req.moving_sample_id}")

    moving_path = Path(sample.get("stored_path", ""))
    if not moving_path.exists():
        raise HTTPException(status_code=404, detail=f"moving file not found: {moving_path}")

    fixed_path = Path(req.fixed_path)
    if not fixed_path.exists():
        raise HTTPException(status_code=404, detail=f"fixed path not found: {req.fixed_path}")

    # 创建任务
    payload = {
        **req.model_dump(),
        "moving_path": str(moving_path),
    }
    task = create_task(
        task_type="global_registration",
        payload=payload,
        project_id=req.project_id,
    )
    task_id = task["task_id"]
    payload["task_id"] = task_id

    # 提交后台执行
    submit_task("global_registration", task_id, req.project_id, payload)

    return {
        "task_id": task_id,
        "status": "queued",
        "message": "Global registration task submitted",
    }


# ---------------------------------------------------------------------------
#  GET /api/tasks — 列出任务
# ---------------------------------------------------------------------------

@router.get("")
def tasks_list(
    project_id: str = Query("default"),
    status: str | None = Query(None),
) -> list[dict]:
    all_tasks = list_tasks(project_id)
    if status:
        all_tasks = [t for t in all_tasks if t.get("status") == status]
    # 返回摘要信息，不含完整 result
    summaries = []
    for t in all_tasks:
        summaries.append({
            "task_id": t["task_id"],
            "task_type": t.get("task_type"),
            "status": t.get("status"),
            "created_at": t.get("created_at"),
            "started_at": t.get("started_at"),
            "finished_at": t.get("finished_at"),
            "error_message": t.get("error_message"),
            "progress": t.get("progress"),
        })
    return summaries


# ---------------------------------------------------------------------------
#  GET /api/tasks/{task_id} — 任务详情
# ---------------------------------------------------------------------------

@router.get("/{task_id}")
def task_detail(task_id: str, project_id: str = Query("default")) -> dict:
    task = get_task(task_id, project_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


# ---------------------------------------------------------------------------
#  GET /api/tasks/{task_id}/log — 任务日志
# ---------------------------------------------------------------------------

@router.get("/{task_id}/log")
def task_log(
    task_id: str,
    project_id: str = Query("default"),
    tail: int = Query(0, description="只返回最后 N 行，0 表示全部"),
) -> PlainTextResponse:
    log_path = task_log_path(project_id, task_id)
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="log not found")
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e))
    if tail > 0:
        lines = text.splitlines()
        text = "\n".join(lines[-tail:])
    return PlainTextResponse(text)
