"""
projects.py — 项目管理路由

端点：
- GET /api/projects/{project_id}   获取项目概览（样本索引 + 任务索引 + 模板索引）
"""
from fastapi import APIRouter

from ..services.project_service import (
    get_or_create_project,
    list_sample_summaries,
    list_template_summaries,
)
from ..services.task_service import list_tasks


router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/{project_id}")
def project_detail(project_id: str) -> dict:
    """
    返回项目概览。
    - project: 项目基本信息
    - samples: 样本索引（仅摘要，不含大体数据）
    - templates: 模板索引（骨架）
    - tasks: 最近任务列表
    """
    project = get_or_create_project(project_id)
    samples = list_sample_summaries(project_id)
    templates = list_template_summaries(project_id)

    # 任务只返回摘要
    all_tasks = list_tasks(project_id)
    task_summaries = [
        {
            "task_id": t["task_id"],
            "task_type": t.get("task_type"),
            "status": t.get("status"),
            "created_at": t.get("created_at"),
            "finished_at": t.get("finished_at"),
            "error_message": t.get("error_message"),
        }
        for t in all_tasks[:50]  # 最多返回50条
    ]

    return {
        "project": project,
        "samples": samples,
        "sample_count": len(samples),
        "templates": templates,
        "template_count": len(templates),
        "tasks": task_summaries,
        "task_count": len(all_tasks),
    }


@router.get("/{project_id}/pipeline-status")
def pipeline_status(project_id: str) -> dict:
    """返回项目级别的流水线进度统计。"""
    samples = list_sample_summaries(project_id)
    total = len(samples)
    prep_done = sum(1 for s in samples if s.get("prepare_status") == "completed")
    reg_done = sum(1 for s in samples if s.get("global_registration_status") == "completed")
    reg_running = sum(1 for s in samples if s.get("global_registration_status") == "running")
    qc_done = sum(1 for s in samples if s.get("global_qc_score") is not None)
    usable = sum(1 for s in samples if s.get("global_qc_level") in ("excellent", "good"))

    return {
        "total": total,
        "steps": {
            "upload":       {"done": total, "total": total},
            "prepare":      {"done": prep_done, "total": total},
            "registration": {"done": reg_done, "running": reg_running, "total": total},
            "qc":           {"done": qc_done, "total": reg_done},
            "template":     {"done": usable, "total": qc_done},
        },
        "samples": samples,
    }
