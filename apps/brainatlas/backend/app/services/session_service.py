"""
session_service.py — 会话清理服务

目标：
- 清理当次上传样本与任务产物
- 下次启动后从干净状态重新开始
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ..utils.paths import data_root, project_workspace


def _safe_rmtree(path: Path) -> bool:
    if not path.exists():
        return False
    shutil.rmtree(path, ignore_errors=True)
    return True


def cleanup_project_session(project_id: str = "default") -> dict[str, Any]:
    """清理项目目录（samples/tasks 等产物）。"""
    target = project_workspace(project_id)
    removed = _safe_rmtree(target)
    return {"path": str(target), "removed": removed}


def cleanup_temp_session() -> list[dict[str, Any]]:
    """清理临时目录中的上传/转换/预览缓存。"""
    temp = data_root() / "temp"
    targets = [
        temp / "uploads",
        temp / "converted",
        temp / "previews",
    ]
    results: list[dict[str, Any]] = []
    for t in targets:
        removed = _safe_rmtree(t)
        results.append({"path": str(t), "removed": removed})
    return results


def cleanup_current_session(project_id: str = "default", *, include_project: bool = False) -> dict[str, Any]:
    """清理当前会话数据。默认仅清理临时缓存，保留项目数据。"""
    proj: dict[str, Any] = {"path": "", "removed": False}
    if include_project:
        proj = cleanup_project_session(project_id)
    tmp = cleanup_temp_session()
    return {
        "project": proj,
        "temp": tmp,
    }
