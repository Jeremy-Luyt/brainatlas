"""
batch.py — 批量操作路由

端点：
- POST /api/batch/prepare
- POST /api/batch/register/global
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.batch_service import submit_global_for_project, submit_prepare_for_project


router = APIRouter(prefix="/batch", tags=["batch"])


class BatchPrepareRequest(BaseModel):
    project_id: str = "default"


class BatchGlobalRequest(BaseModel):
    project_id: str = "default"
    fixed_path: str


@router.post("/prepare")
def batch_prepare(req: BatchPrepareRequest) -> dict:
    """一键为当前项目提交所有待处理样本的预处理任务。"""
    return submit_prepare_for_project(project_id=req.project_id)


@router.post("/register/global")
def batch_register_global(req: BatchGlobalRequest) -> dict:
    """一键为当前项目提交全局配准任务。"""
    try:
        return submit_global_for_project(
            project_id=req.project_id,
            fixed_path=req.fixed_path,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
