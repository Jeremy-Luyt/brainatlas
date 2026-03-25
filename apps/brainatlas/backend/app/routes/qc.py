"""
qc.py — QC 路由

端点：
- POST /api/samples/{sample_id}/qc/global          单样本 global QC
- POST /api/projects/{project_id}/qc/global         批量 global QC
- POST /api/samples/{sample_id}/qc/manual-review    人工确认
- GET  /api/projects/{project_id}/template-candidates 模板候选列表
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.qc_service import (
    list_template_candidates,
    run_batch_qc,
    run_sample_qc,
    update_manual_review,
)

router = APIRouter(tags=["qc"])


# ─────────── 单样本 QC ───────────

@router.post("/samples/{sample_id}/qc/global")
def qc_global_single(sample_id: str) -> dict:
    """对单个 sample 运行 global QC，返回 global_qc 结果。"""
    try:
        return run_sample_qc(sample_id)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ─────────── 批量 QC ─────────────

@router.post("/projects/{project_id}/qc/global")
def qc_global_batch(project_id: str) -> dict:
    """对项目下所有已完成 global 的样本批量执行 QC。"""
    return run_batch_qc(project_id)


# ─────────── 人工确认 ─────────────

class ManualReviewRequest(BaseModel):
    status: str
    comment: str = ""


@router.post("/samples/{sample_id}/qc/manual-review")
def qc_manual_review(sample_id: str, req: ManualReviewRequest) -> dict:
    """更新人工确认状态（approved / rejected / needs_check）。"""
    try:
        return update_manual_review(sample_id, req.status, req.comment)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ─────────── 模板候选 ─────────────

@router.get("/projects/{project_id}/template-candidates")
def template_candidates(project_id: str) -> list:
    """返回项目中所有可用于模板构建的样本，按 score 降序。"""
    return list_template_candidates(project_id)
