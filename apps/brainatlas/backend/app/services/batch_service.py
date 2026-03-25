"""
batch_service.py — 批量任务提交服务

职责：
- 批量提交 sample_prepare 任务（用于文件夹索引后的一键预处理）
- 批量提交 global_registration 任务（用于一键全局配准）
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .project_service import list_sample_summaries
from .sample_service import get_sample
from .task_runner import submit_task
from .task_service import create_task


def submit_prepare_for_project(
    project_id: str = "default",
    only_statuses: set[str] | None = None,
) -> dict[str, Any]:
    """
    为项目内样本批量提交预处理任务。

    默认仅处理 indexed/pending/failed，跳过 running/completed。
    """
    statuses = only_statuses or {"indexed", "pending", "failed"}
    samples = list_sample_summaries(project_id)

    started: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []

    for s in samples:
        sid = s.get("sample_id")
        st = s.get("prepare_status", "pending")
        if sid is None:
            continue
        if st not in statuses:
            skipped.append({"sample_id": sid, "reason": f"prepare_status={st}"})
            continue

        payload = {"sample_id": sid, "project_id": project_id}
        task = create_task(
            task_type="sample_prepare",
            payload=payload,
            project_id=project_id,
        )
        task_id = task["task_id"]
        payload["task_id"] = task_id
        submit_task("sample_prepare", task_id, project_id, payload)
        started.append({"sample_id": sid, "task_id": task_id})

    return {
        "project_id": project_id,
        "total_samples": len(samples),
        "started": len(started),
        "skipped": len(skipped),
        "started_tasks": started,
        "skipped_samples": skipped,
    }


def submit_global_for_project(
    project_id: str,
    fixed_path: str,
    only_prepare_statuses: set[str] | None = None,
) -> dict[str, Any]:
    """
    为项目内样本批量提交全局配准任务。

    规则：
    - prepare_status 必须在 only_prepare_statuses（默认 completed）
    - 跳过 global_registration_status=running
    - 跳过 global.v3draw 本身
    """
    prepare_ok = only_prepare_statuses or {"completed"}
    samples = list_sample_summaries(project_id)

    fixed = Path(fixed_path)
    if not fixed.exists():
        raise FileNotFoundError(f"fixed path not found: {fixed_path}")

    started: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []

    for s in samples:
        sid = s.get("sample_id")
        if sid is None:
            continue

        sample = get_sample(sid)
        if sample is None:
            skipped.append({"sample_id": sid, "reason": "sample not found"})
            continue

        prepare_status = sample.get("prepare_status", "pending")
        global_status = sample.get("global_registration_status", "idle")
        filename = str(sample.get("filename", "")).lower()
        moving_path = Path(sample.get("stored_path", ""))

        if prepare_status not in prepare_ok:
            skipped.append({"sample_id": sid, "reason": f"prepare_status={prepare_status}"})
            continue
        if global_status == "running":
            skipped.append({"sample_id": sid, "reason": "global task is already running"})
            continue
        if filename == "global.v3draw":
            skipped.append({"sample_id": sid, "reason": "moving cannot be global.v3draw"})
            continue
        if not moving_path.exists():
            skipped.append({"sample_id": sid, "reason": f"moving file missing: {moving_path}"})
            continue

        payload = {
            "project_id": project_id,
            "moving_sample_id": sid,
            "moving_path": str(moving_path),
            "fixed_path": str(fixed),
        }
        task = create_task(
            task_type="global_registration",
            payload=payload,
            project_id=project_id,
        )
        task_id = task["task_id"]
        payload["task_id"] = task_id
        submit_task("global_registration", task_id, project_id, payload)
        started.append({"sample_id": sid, "task_id": task_id})

    return {
        "project_id": project_id,
        "fixed_path": str(fixed),
        "total_samples": len(samples),
        "started": len(started),
        "skipped": len(skipped),
        "started_tasks": started,
        "skipped_samples": skipped,
    }
