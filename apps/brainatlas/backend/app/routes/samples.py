"""
samples.py — 样本管理路由

端点：
- GET  /api/samples/{sample_id}          获取样本详情（含 hydrate）
- POST /api/samples/{sample_id}/prepare  触发预处理（后台任务）
"""
from fastapi import APIRouter, HTTPException

from ..services.registration_service import hydrate_global_registration
from ..services.sample_service import get_sample
from ..services.task_service import create_task
from ..services.task_runner import submit_task


router = APIRouter(prefix="/samples", tags=["samples"])


@router.get("/{sample_id}")
def sample_detail(sample_id: str) -> dict:
    """返回样本详情，自动 hydrate 已有的 global 结果"""
    # 先尝试 hydrate
    try:
        sample = hydrate_global_registration(sample_id)
    except Exception as e:
        print(f"WARN hydrate({sample_id}): {e}")
        sample = None

    if sample is None:
        sample = get_sample(sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail="sample not found")

    return sample


@router.post("/{sample_id}/prepare")
def prepare_sample(sample_id: str, project_id: str = "default") -> dict:
    """提交预处理后台任务（立即返回 task_id）"""
    sample = get_sample(sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail="sample not found")

    payload = {"sample_id": sample_id, "project_id": project_id}
    task = create_task(
        task_type="sample_prepare",
        payload=payload,
        project_id=project_id,
    )
    task_id = task["task_id"]
    payload["task_id"] = task_id

    submit_task("sample_prepare", task_id, project_id, payload)

    return {"task_id": task_id, "status": "queued"}
