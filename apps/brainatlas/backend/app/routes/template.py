"""
template.py — 模板构建路由

端点：
- POST /api/template/select-t0      选择初始模板 T0
- POST /api/template/build           启动模板迭代构建
- GET  /api/template/versions        列出所有模板版本
- GET  /api/template/versions/{ver}  获取某版本详情
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.template_service import (
    select_and_save_t0,
    list_template_versions_for_project,
    run_template_build_task,
)
from ..services.task_runner import submit_task
from ..services.task_service import create_task
from ..utils.paths import project_workspace
from pipeline.atlas.template_version import version_dir, load_summary


router = APIRouter(prefix="/template", tags=["template"])


class SelectT0Request(BaseModel):
    project_id: str = "default"
    sample_id: str | None = None


class TemplateBuildRequest(BaseModel):
    project_id: str = "default"
    max_iterations: int = 3
    max_samples: int = 3
    convergence_threshold: float = 0.5


@router.post("/select-t0")
def select_t0_endpoint(req: SelectT0Request) -> dict:
    """选择样本作为初始模板 T0。可指定 sample_id，不传则自动选最高分。"""
    try:
        result = select_and_save_t0(req.project_id, sample_id=req.sample_id)
        return {"status": "ok", "template_v0": result}
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/build")
def start_template_build(req: TemplateBuildRequest) -> dict:
    """启动模板迭代构建后台任务。"""
    payload = {
        "project_id": req.project_id,
        "max_iterations": req.max_iterations,
        "max_samples": req.max_samples,
        "convergence_threshold": req.convergence_threshold,
    }
    task = create_task(
        task_type="template_build",
        payload=payload,
        project_id=req.project_id,
    )
    task_id = task["task_id"]
    payload["task_id"] = task_id
    submit_task("template_build", task_id, req.project_id, payload)
    return {"status": "submitted", "task_id": task_id}


@router.get("/versions")
def get_template_versions(project_id: str = "default") -> dict:
    """列出项目的所有模板版本。"""
    versions = list_template_versions_for_project(project_id)
    return {"project_id": project_id, "versions": versions}


@router.get("/versions/{version}")
def get_template_version_detail(version: int, project_id: str = "default") -> dict:
    """获取指定版本的详细信息。"""
    pw = project_workspace(project_id)
    ver_dir = version_dir(pw, version)
    if not ver_dir.exists():
        raise HTTPException(status_code=404, detail=f"Version v{version} not found")

    summary = load_summary(ver_dir) or {}
    summary["version"] = version

    # 附加收敛信息
    conv_path = ver_dir / "convergence.json"
    if conv_path.exists():
        summary["convergence"] = json.loads(conv_path.read_text(encoding="utf-8"))

    # 附加 NIfTI URL
    from ..utils.paths import data_root
    template_nii = ver_dir / "template.nii.gz"
    if template_nii.exists():
        try:
            rel = template_nii.resolve().relative_to(data_root().resolve()).as_posix()
            summary["template_nii_url"] = f"/api/static/{rel}"
        except ValueError:
            pass

    # 附加预览图 base URL
    preview_dir = ver_dir / "preview"
    if preview_dir.exists():
        try:
            rel = preview_dir.resolve().relative_to(data_root().resolve()).as_posix()
            summary["preview_base_url"] = f"/api/static/{rel}"
        except ValueError:
            pass

    return summary
