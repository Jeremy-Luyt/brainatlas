"""
qc_service.py — Global QC 业务逻辑

职责：
- 对单个 sample 运行 global QC 并写回 sample.json
- 批量 QC（按项目）
- 人工确认更新（approved / rejected / needs_check）
- 模板候选筛选（按 score 降序）
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pipeline.atlas.qc_global_results import run_global_qc
from .sample_service import get_sample, update_sample, get_sample_dir
from .project_service import list_sample_summaries


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ──────────────────────── 单样本 QC ──────────────────────────

def run_sample_qc(sample_id: str) -> dict[str, Any]:
    """对单个 sample 运行 global QC，结果写回 sample.json 并返回 global_qc。"""
    sample = get_sample(sample_id)
    if sample is None:
        raise ValueError(f"Sample not found: {sample_id}")

    if sample.get("global_registration_status") != "completed":
        raise ValueError(
            f"Sample {sample_id} global registration not completed "
            f"(status={sample.get('global_registration_status')})"
        )

    project_id = sample.get("project_id", "default")
    global_dir = get_sample_dir(project_id, sample_id) / "registration" / "global"

    if not global_dir.exists():
        raise FileNotFoundError(f"Global registration directory not found: {global_dir}")

    qc_result = run_global_qc(global_dir, sample_meta=sample)

    # 保留已有的非 pending 人工确认
    existing_review = (sample.get("global_qc") or {}).get("manual_review")
    if existing_review and existing_review.get("status") != "pending":
        qc_result["manual_review"] = existing_review

    updated = update_sample(sample_id, {"global_qc": qc_result})
    return updated.get("global_qc", qc_result)


# ──────────────────────── 批量 QC ────────────────────────────

def run_batch_qc(project_id: str) -> dict[str, Any]:
    """对项目下所有 ``global_registration_status=completed`` 的样本批量执行 QC。"""
    summaries = list_sample_summaries(project_id)
    candidates = [s for s in summaries if s.get("global_registration_status") == "completed"]

    total = len(candidates)
    succeeded = 0
    failed_count = 0
    usable_count = 0
    results: list[dict[str, Any]] = []

    for s in candidates:
        sid = s["sample_id"]
        try:
            qc = run_sample_qc(sid)
            succeeded += 1
            if qc.get("usable_for_template"):
                usable_count += 1
            results.append({
                "sample_id": sid,
                "score": qc.get("score"),
                "qc_level": qc.get("qc_level"),
                "error": None,
            })
        except Exception as exc:
            failed_count += 1
            results.append({
                "sample_id": sid,
                "score": None,
                "qc_level": None,
                "error": str(exc),
            })

    return {
        "total": total,
        "succeeded": succeeded,
        "failed": failed_count,
        "usable_for_template_count": usable_count,
        "results": results,
    }


# ──────────────────────── 人工确认 ────────────────────────────

def update_manual_review(
    sample_id: str,
    status: str,
    comment: str = "",
) -> dict[str, Any]:
    """更新 sample.json 中 global_qc.manual_review，返回更新后的 global_qc。"""
    valid = {"pending", "approved", "rejected", "needs_check"}
    if status not in valid:
        raise ValueError(f"Invalid status: {status}. Must be one of {valid}")

    sample = get_sample(sample_id)
    if sample is None:
        raise ValueError(f"Sample not found: {sample_id}")

    qc = sample.get("global_qc")
    if qc is None:
        raise ValueError(f"Sample {sample_id} has no global_qc. Run QC first.")

    qc["manual_review"] = {
        "status": status,
        "comment": comment,
        "updated_at": _now(),
    }

    # rejected → 强制不可用于模板
    if status == "rejected":
        qc["usable_for_template"] = False

    updated = update_sample(sample_id, {"global_qc": qc})
    return updated.get("global_qc", qc)


# ──────────────────────── 模板候选 ────────────────────────────

def list_template_candidates(project_id: str) -> list[dict[str, Any]]:
    """返回项目中所有 usable_for_template=true 的样本，按 score 降序。"""
    summaries = list_sample_summaries(project_id)

    candidates: list[dict[str, Any]] = []
    for s in summaries:
        sid = s["sample_id"]
        sample = get_sample(sid)
        if sample is None:
            continue
        qc = sample.get("global_qc") or {}
        if not qc.get("usable_for_template"):
            continue
        review = qc.get("manual_review") or {}
        if review.get("status") == "rejected":
            continue
        candidates.append({
            "sample_id": sid,
            "filename": sample.get("filename", ""),
            "score": qc.get("score", 0),
            "qc_level": qc.get("qc_level", ""),
            "manual_review_status": review.get("status", "pending"),
        })

    candidates.sort(key=lambda c: c.get("score", 0), reverse=True)
    return candidates
