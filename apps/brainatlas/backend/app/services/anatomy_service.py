"""解剖图谱映射服务 — 将 CCF 标注映射到自建模板空间"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline.atlas.anatomy_mapper import run_anatomy_mapping
from ..services.ccf_service import (
    CCF_ANNOTATION_NII,
    CCF_ANATOMICAL_NII,
    CCF_REGIONS_INDEX,
    load_regions_index,
)
from ..services.task_service import update_task
from ..utils.paths import project_workspace


def _anatomy_dir(project_id: str, version: int) -> Path:
    """返回解剖映射输出目录。"""
    pw = project_workspace(project_id)
    return pw / "templates" / f"v{version}" / "anatomy"


def get_mapping_status(project_id: str, version: int) -> dict:
    """获取指定模板版本的解剖映射状态。"""
    d = _anatomy_dir(project_id, version)
    summary_path = d / "anatomy_mapping_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        return {"status": "completed", "version": version, **summary}
    return {"status": "not_started", "version": version}


def get_mapped_region_stats(project_id: str, version: int) -> list[dict]:
    """获取映射后的脑区统计列表。"""
    d = _anatomy_dir(project_id, version)
    stats_path = d / "region_stats.json"
    if not stats_path.exists():
        raise FileNotFoundError(
            f"Region stats not found for v{version}. "
            "Run anatomy mapping first."
        )
    return json.loads(stats_path.read_text(encoding="utf-8"))


def search_mapped_regions(
    project_id: str,
    version: int,
    query: str,
    limit: int = 30,
) -> list[dict]:
    """在映射后的脑区统计中搜索 (支持中英文 + 缩写)。"""
    stats = get_mapped_region_stats(project_id, version)
    q = (query or "").strip().lower()
    if not q:
        return stats[:limit]

    out = []
    for row in stats:
        name = str(row.get("name", "")).lower()
        acronym = str(row.get("acronym", "")).lower()
        name_zh = str(row.get("name_zh", "")).lower()
        region_id = str(row.get("id", ""))
        if q in name or q in acronym or q in name_zh or q == region_id:
            out.append(row)
            if len(out) >= limit:
                break
    return out


def get_region_detail(
    project_id: str,
    version: int,
    region_id: int,
) -> dict:
    """获取单个脑区在模板中的详细信息。"""
    stats = get_mapped_region_stats(project_id, version)
    for row in stats:
        if int(row.get("id", -1)) == region_id:
            # 附加子区域信息
            children = [
                r for r in stats
                if r.get("parent_structure_id") == region_id
            ]
            row["children"] = children
            row["children_count"] = len(children)
            return row
    raise KeyError(f"Region {region_id} not found in mapped stats for v{version}")


def run_anatomy_mapping_task(
    payload: dict[str, Any],
    task_logger: Any,
) -> dict[str, Any]:
    """后台任务: 将 CCF 解剖标注映射到模板空间。"""
    project_id = payload.get("project_id", "default")
    version = payload.get("version")
    task_id = payload.get("task_id")

    pw = project_workspace(project_id)

    # 确定模板版本
    if version is None:
        from pipeline.atlas.template_version import latest_version
        version = latest_version(pw)
        if version < 0:
            raise ValueError("No template version found. Build template first.")

    template_nii = pw / "templates" / f"v{version}" / "template.nii.gz"
    if not template_nii.exists():
        raise FileNotFoundError(f"Template NIfTI not found: {template_nii}")

    if not CCF_ANNOTATION_NII.exists():
        raise FileNotFoundError(
            f"CCF annotation not found: {CCF_ANNOTATION_NII}. "
            "Run scripts/prepare_ccf.py first."
        )
    if not CCF_ANATOMICAL_NII.exists():
        raise FileNotFoundError(
            f"CCF nissl not found: {CCF_ANATOMICAL_NII}. "
            "Run scripts/prepare_ccf.py first."
        )

    output_dir = _anatomy_dir(project_id, version)
    task_logger.info(f"Anatomy mapping: project={project_id}, version=v{version}")

    def _progress(data):
        if task_id:
            update_task(task_id, progress=data, project_id=project_id)

    result = run_anatomy_mapping(
        ccf_annotation_nii=CCF_ANNOTATION_NII,
        ccf_nissl_nii=CCF_ANATOMICAL_NII,
        template_nii=template_nii,
        output_dir=output_dir,
        regions_index_json=CCF_REGIONS_INDEX,
        logger_fn=task_logger.info,
    )

    return {
        "project_id": project_id,
        "version": version,
        "n_regions": result["n_regions"],
        "output_dir": str(output_dir),
    }
