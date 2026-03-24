"""
project_service.py — 项目级管理服务

职责：
- 获取/创建项目元数据（project.json）
- 返回项目下的样本索引（懒加载，仅返回摘要）
- 返回项目下的任务索引
- 返回项目下的模板索引（骨架）
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..utils.json_io import read_json, write_json
from ..utils.paths import project_workspace


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_or_create_project(project_id: str) -> dict[str, Any]:
    """获取项目元数据，不存在则创建"""
    project_dir = project_workspace(project_id)
    project_json = project_dir / "project.json"

    if project_json.exists():
        return read_json(project_json)

    # 首次创建
    project = {
        "project_id": project_id,
        "name": project_id,
        "description": "",
        "created_at": _now(),
        "updated_at": _now(),
    }
    write_json(project_json, project)
    return project


def update_project(project_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """更新项目元数据"""
    project_dir = project_workspace(project_id)
    project_json = project_dir / "project.json"
    data = get_or_create_project(project_id)
    data.update(updates)
    data["updated_at"] = _now()
    write_json(project_json, data)
    return data


def list_sample_summaries(project_id: str) -> list[dict[str, Any]]:
    """
    返回项目下所有样本的摘要信息（懒加载，不读取体数据）。
    只返回索引所需字段：sample_id, filename, prepare_status, global_registration_status, stats.shape
    """
    samples_dir = project_workspace(project_id) / "samples"
    if not samples_dir.exists():
        return []

    summaries = []
    for sample_json in sorted(samples_dir.glob("*/sample.json")):
        try:
            data = read_json(sample_json)
            summaries.append({
                "sample_id": data.get("sample_id", sample_json.parent.name),
                "filename": data.get("filename", ""),
                "input_format": data.get("input_format", ""),
                "prepare_status": data.get("prepare_status", "pending"),
                "global_registration_status": data.get("global_registration_status", "idle"),
                "shape": data.get("stats", {}).get("shape"),
                "created_at": data.get("created_at"),
            })
        except Exception:
            continue

    return summaries


def list_template_summaries(project_id: str) -> list[dict[str, Any]]:
    """返回项目下所有模板的摘要（骨架，当前返回空列表）"""
    templates_dir = project_workspace(project_id) / "templates"
    if not templates_dir.exists():
        return []

    summaries = []
    for template_json in sorted(templates_dir.glob("*/template.json")):
        try:
            data = read_json(template_json)
            summaries.append({
                "template_id": data.get("template_id", template_json.parent.name),
                "name": data.get("name", ""),
                "status": data.get("status", "idle"),
                "created_at": data.get("created_at"),
            })
        except Exception:
            continue

    return summaries
