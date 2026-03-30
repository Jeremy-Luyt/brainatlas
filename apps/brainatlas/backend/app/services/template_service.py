"""模板构建业务逻辑"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline.atlas.template_selector import select_t0
from pipeline.atlas.template_version import (
    list_versions,
    version_dir,
    latest_version,
)
from pipeline.atlas.template_builder import run_template_build
from ..services.qc_service import list_template_candidates
from ..services.sample_service import get_sample, get_sample_dir
from ..services.task_service import update_task
from ..utils.paths import project_workspace


# ---------------------------------------------------------------------------
#  T0 选择
# ---------------------------------------------------------------------------

def select_and_save_t0(project_id: str, sample_id: str | None = None) -> dict[str, Any]:
    """
    选择样本作为 T0，保存到 templates/v0/。
    如果指定 sample_id 则使用该样本，否则自动选最高分。
    """
    candidates = list_template_candidates(project_id)
    if not candidates:
        raise ValueError(f"No usable candidates for T0 in project {project_id}")

    if sample_id:
        # 用户指定了样本
        chosen = [c for c in candidates if c["sample_id"] == sample_id]
        if not chosen:
            raise ValueError(f"Sample {sample_id} is not a valid T0 candidate")
        candidates = chosen + [c for c in candidates if c["sample_id"] != sample_id]

    pw = project_workspace(project_id)
    samples_dir = pw / "samples"
    v0_dir = version_dir(pw, 0)

    result = select_t0(candidates, samples_dir, v0_dir)
    return result


# ---------------------------------------------------------------------------
#  版本列表
# ---------------------------------------------------------------------------

def list_template_versions_for_project(project_id: str) -> list[dict[str, Any]]:
    """列出项目中所有模板版本。"""
    pw = project_workspace(project_id)
    return list_versions(pw)


# ---------------------------------------------------------------------------
#  后台任务处理器
# ---------------------------------------------------------------------------

def run_template_build_task(
    payload: dict[str, Any],
    task_logger: Any,
) -> dict[str, Any]:
    """
    后台线程执行模板构建。

    payload 需包含:
      - project_id: str
      - max_iterations: int (可选, 默认 3)
      - max_samples: int (可选, 默认 3)
      - convergence_threshold: float (可选, 默认 0.5)
    """
    project_id = payload.get("project_id", "default")
    max_iterations = payload.get("max_iterations", 3)
    max_samples = payload.get("max_samples", 3)
    convergence_threshold = payload.get("convergence_threshold", 0.5)

    pw = project_workspace(project_id)

    task_logger.info(f"Template build task for project={project_id}")

    # 1. 确保 T0 存在
    v0_dir = version_dir(pw, 0)
    if not (v0_dir / "template.v3draw").exists():
        task_logger.info("T0 not found, selecting from QC candidates...")
        t0_result = select_and_save_t0(project_id)
        task_logger.info(f"T0 selected: sample={t0_result.get('source_sample_id')}, score={t0_result.get('source_score')}")
    else:
        task_logger.info("T0 already exists, skipping selection")

    # 2. 收集参与构建的样本
    candidates = list_template_candidates(project_id)
    sample_entries = []
    for c in candidates[:max_samples]:
        sid = c["sample_id"]
        sample = get_sample(sid)
        if sample is None:
            continue
        global_reg = sample.get("global_registration", {})
        global_v3draw = global_reg.get("global_v3draw_path", "")
        if global_v3draw and Path(global_v3draw).exists():
            sample_entries.append({
                "sample_id": sid,
                "global_v3draw": global_v3draw,
            })

    if not sample_entries:
        raise ValueError("No valid samples found for template building")

    task_logger.info(f"Building with {len(sample_entries)} samples: {[s['sample_id'] for s in sample_entries]}")

    # 3. 构建配置
    config = {
        "max_iterations": max_iterations,
        "convergence_threshold": convergence_threshold,
        "harris": {
            "nms_2d": payload.get("harris_nms_2d", 15),
            "nms_3d": payload.get("harris_nms_3d", 15),
            "point_count": payload.get("harris_point_count", 50),
        },
        "stps": {
            "df_method": payload.get("stps_df_method", 1),
            "block_size": payload.get("stps_block_size", 4),
            "lambda": payload.get("stps_lambda", 0.2),
        },
        "intensity": {
            "low_pct": payload.get("intensity_low_pct", 1.0),
            "high_pct": payload.get("intensity_high_pct", 99.0),
        },
    }

    # 4. 运行迭代构建
    task_id = payload.get("task_id")

    def _on_progress(data: dict):
        if task_id:
            update_task(task_id, progress=data, project_id=project_id)

    result = run_template_build(
        project_dir=pw,
        sample_entries=sample_entries,
        config=config,
        logger=task_logger,
        progress_fn=_on_progress,
    )

    task_logger.info(f"Template build complete: final_version=v{result['final_version']}, converged={result['converged']}")

    return {
        "project_id": project_id,
        "final_version": result["final_version"],
        "total_iterations": result["total_iterations"],
        "converged": result["converged"],
    }
