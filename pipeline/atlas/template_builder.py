"""模板迭代构建器: Harris取点 → 局部配准 → 归一化+平均 → 点平均 → STPS校正 → 收敛判断"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.io import read_v3draw, save_nifti
from pipeline.io.writer_v3draw import write_v3draw
from pipeline.preprocess.build_previews import build_previews_from_volume
from pipeline.wrappers.harris_wrapper import run_harris
from pipeline.wrappers.local_registration import run_local_registration
from pipeline.wrappers.stps_wrapper import run_stps
from pipeline.atlas.intensity_normalize import normalize_and_average
from pipeline.atlas.marker_average import average_markers, parse_marker, write_marker
from pipeline.atlas.convergence import compute_convergence_delta, is_converged
from pipeline.atlas.template_version import (
    ensure_version_dir,
    save_build_config,
    save_convergence,
    save_summary,
    latest_version,
    version_dir,
)


# ---------------------------------------------------------------------------
#  单轮迭代
# ---------------------------------------------------------------------------

def run_single_iteration(
    iteration: int,
    project_dir: Path,
    sample_entries: list[dict[str, Any]],
    config: dict[str, Any],
    logger: Any = None,
    progress_fn: Any = None,
) -> dict[str, Any]:
    """执行单轮模板构建迭代 (7步)"""
    prev_version = iteration - 1
    prev_dir = version_dir(project_dir, prev_version)
    prev_template = prev_dir / "template.v3draw"

    if not prev_template.exists():
        raise FileNotFoundError(
            f"Previous template not found: {prev_template}. "
            f"Ensure template_v{prev_version} exists."
        )

    cur_dir = ensure_version_dir(project_dir, iteration)
    work_dir = cur_dir / "_work"
    work_dir.mkdir(parents=True, exist_ok=True)

    # 保存构建参数快照
    save_build_config(cur_dir, {
        "iteration": iteration,
        "n_samples": len(sample_entries),
        "sample_ids": [s["sample_id"] for s in sample_entries],
        "config": config,
    })

    _log(logger, f"=== Iteration {iteration} ===")
    _log(logger, f"  Previous template: {prev_template}")
    _log(logger, f"  Samples: {len(sample_entries)}")

    max_iter = config.get("max_iterations", 3)
    n_samples = len(sample_entries)

    def _step_progress(step: int, total_steps: int, label: str, detail: str = "",
                       sample_done: int = 0, sample_total: int = 0):
        # 每轮 7 步；粗略百分比 = ((iteration-1)*7 + step) / (max_iter*7) * 100
        pct = int(((iteration - 1) * total_steps + step) / (max_iter * total_steps) * 100)
        pct = min(pct, 99)
        _progress(progress_fn, {
            "iteration": iteration,
            "max_iterations": max_iter,
            "step": step,
            "total_steps": total_steps,
            "step_label": label,
            "detail": detail,
            "sample_done": sample_done,
            "sample_total": sample_total,
            "percent": pct,
        })

    # ── Step 1: Harris 取点 ─────────────────────────
    _step_progress(0, 7, "Harris角点检测", "检测模板特征点…")
    _log(logger, "Step 1: Harris corner detection on template")
    landmarks_marker = cur_dir / "template_landmarks.marker"
    harris_result = run_harris(
        input_image=prev_template,
        output_marker=landmarks_marker,
        nms_2d=config.get("harris", {}).get("nms_2d", 15),
        nms_3d=config.get("harris", {}).get("nms_3d", 15),
        max_points=config.get("harris", {}).get("point_count", 50),
    )
    _log(logger, f"  Harris done: {harris_result['n_points']} points")

    if harris_result["n_points"] == 0:
        raise RuntimeError(
            f"Harris detected 0 points on template {prev_template}. "
            "Cannot proceed with local registration."
        )

    # ── Step 2: 局部配准（每个样本）──────────────────
    _step_progress(1, 7, "局部配准", f"0/{n_samples} 样本", 0, n_samples)
    _log(logger, "Step 2: Local registration for each sample")
    local_results = []
    for idx, entry in enumerate(sample_entries):
        sid = entry["sample_id"]
        global_v3draw = Path(entry["global_v3draw"])

        _step_progress(1, 7, "局部配准", f"{idx}/{n_samples} 样本", idx, n_samples)
        _log(logger, f"  [{idx+1}/{len(sample_entries)}] Sample {sid}")

        if not global_v3draw.exists():
            _log(logger, f"    SKIP: global v3draw not found: {global_v3draw}")
            continue

        sample_work_dir = work_dir / sid
        try:
            result = run_local_registration(
                subject_image=global_v3draw,
                template_v3draw=prev_template,
                landmarks=landmarks_marker,
                output_dir=sample_work_dir,
            )
        except Exception as exc:
            _log(logger, f"    FAILED (exception): {exc}")
            continue

        if result["status"] == "completed" and result["registered_image"]:
            local_results.append({
                "sample_id": sid,
                "registered_image": result["registered_image"],
                "sub_marker": result["sub_marker"],
                "tar_marker": result["tar_marker"],
            })
            _log(logger, f"    OK: {result['registered_image']}")
        else:
            _log(logger, f"    FAILED: see {result['log_path']}")

    if not local_results:
        raise RuntimeError("All local registrations failed. Cannot continue iteration.")

    _log(logger, f"  Local registration completed: {len(local_results)}/{len(sample_entries)} succeeded")

    # ── Step 2.5: 确保 local reg 输出与模板同尺寸 ──
    _step_progress(2, 7, "尺寸校正", "重采样配准输出…")
    # (multiscale > 1 时 exe 输出降采样图像，需上采样回原始尺寸)
    prev_vol, _ = read_v3draw(prev_template)
    if prev_vol.ndim == 4:
        prev_vol = prev_vol[0]
    target_shape = prev_vol.shape  # (Z, Y, X)
    del prev_vol

    for r in local_results:
        reg_path = Path(r["registered_image"])
        reg_vol, _ = read_v3draw(reg_path)
        if reg_vol.ndim == 4:
            reg_vol = reg_vol[0]
        if reg_vol.shape != target_shape:
            from scipy.ndimage import zoom
            factors = tuple(t / s for t, s in zip(target_shape, reg_vol.shape))
            _log(logger, f"  Resample {r['sample_id']}: {reg_vol.shape} → {target_shape} (factors={tuple(f'{f:.2f}' for f in factors)})")
            reg_vol = zoom(reg_vol.astype(np.float32), factors, order=3).clip(0, 255).astype(np.uint8)
            write_v3draw(reg_vol, reg_path)

            # 同步缩放 marker 坐标 (x, y, z) ↔ (dim2, dim1, dim0) factors
            scale_xyz = np.array([factors[2], factors[1], factors[0]], dtype=np.float64)
            for key in ("sub_marker", "tar_marker"):
                mp = r.get(key)
                if mp and Path(mp).exists():
                    pts = parse_marker(mp)
                    if len(pts) > 0:
                        pts *= scale_xyz
                        write_marker(pts, mp)
        del reg_vol

    # ── Step 3: 点集平均 ────────────────────────────
    _step_progress(3, 7, "点集平均", "计算标记点均值…")
    _log(logger, "Step 3: Marker averaging")
    sub_marker_paths = [Path(r["sub_marker"]) for r in local_results if r["sub_marker"]]
    tar_marker_paths = [Path(r["tar_marker"]) for r in local_results if r["tar_marker"]]

    sub_avg = average_markers(sub_marker_paths)
    sub_avg_marker = cur_dir / "sub_avg.marker"
    write_marker(sub_avg, sub_avg_marker)
    _log(logger, f"  sub_avg: {len(sub_avg)} points → {sub_avg_marker}")

    # tar_ref = tar_1 (所有 tar_i 应该相同)
    tar_ref = parse_marker(tar_marker_paths[0])
    tar_ref_marker = cur_dir / "tar_ref.marker"
    write_marker(tar_ref, tar_ref_marker)
    _log(logger, f"  tar_ref: {len(tar_ref)} points → {tar_ref_marker}")

    # ── Step 4: 强度归一化 + 体素平均 ──────────────
    _step_progress(4, 7, "强度归一化", "归一化并平均体素…")
    _log(logger, "Step 4: Intensity normalization + voxel average")
    registered_paths = [Path(r["registered_image"]) for r in local_results]

    avg_vol, norm_stats = normalize_and_average(
        volume_paths=registered_paths,
        reader_fn=read_v3draw,
        low_pct=config.get("intensity", {}).get("low_pct", 1.0),
        high_pct=config.get("intensity", {}).get("high_pct", 99.0),
        logger=logger,
    )
    _log(logger, f"  Voxel average shape: {avg_vol.shape}")

    # 保存 M_raw
    m_raw_path = work_dir / "M_raw.v3draw"
    write_v3draw(avg_vol, m_raw_path)
    _log(logger, f"  M_raw saved: {m_raw_path}")

    # ── Step 5: STPS 形状校正 ──────────────────────
    _step_progress(5, 7, "STPS形状校正", "薄板样条变形…")
    _log(logger, "Step 5: STPS shape correction")
    template_v3draw = cur_dir / "template.v3draw"
    stps_result = run_stps(
        subject_image=m_raw_path,
        subject_markers=tar_ref_marker,   # 当前形状 = 模板点
        target_markers=sub_avg_marker,     # 目标形状 = 平均 subject 点
        output_image=template_v3draw,
        df_method=config.get("stps", {}).get("df_method", 1),
        block_size=config.get("stps", {}).get("block_size", 4),
        lambda_val=config.get("stps", {}).get("lambda", 0.2),
    )
    _log(logger, f"  STPS output: {stps_result['status']}")

    # ── NIfTI 转换 + 预览 ─────────────────────────
    template_vol, _ = read_v3draw(template_v3draw)
    if template_vol.ndim == 4:
        template_vol = template_vol[0]
    template_nii = cur_dir / "template.nii.gz"
    save_nifti(template_vol, template_nii)
    _log(logger, f"  NIfTI saved: {template_nii}")

    preview_dir = cur_dir / "preview"
    build_previews_from_volume(template_vol, preview_dir)
    _log(logger, "  Previews generated")

    # ── Step 6: 收敛判断 ──────────────────────────
    _step_progress(6, 7, "收敛判断", "比较相邻迭代标记点偏移…")
    conv_data: dict[str, Any] = {
        "iteration": iteration,
        "n_points": len(sub_avg),
        "n_samples": len(local_results),
    }
    converged = False

    if iteration >= 2:
        prev_sub_avg_path = version_dir(project_dir, iteration - 1) / "sub_avg.marker"
        if prev_sub_avg_path.exists():
            prev_sub_avg = parse_marker(prev_sub_avg_path)
            if len(prev_sub_avg) == len(sub_avg):
                delta = compute_convergence_delta(sub_avg, prev_sub_avg)
                threshold = config.get("convergence_threshold", 0.5)
                converged = is_converged(delta, threshold)
                conv_data["delta"] = delta
                conv_data["threshold"] = threshold
                conv_data["converged"] = converged
                _log(logger, f"  Convergence: delta={delta:.4f}, threshold={threshold}, converged={converged}")
            else:
                _log(logger, f"  Convergence: point count mismatch ({len(prev_sub_avg)} vs {len(sub_avg)}), skip")
        else:
            _log(logger, "  Convergence: no previous sub_avg, skip")
    else:
        _log(logger, "  Convergence: iteration < 2, skip")

    save_convergence(cur_dir, conv_data)

    # ── Step 7: 保存版本摘要 ──────────────────────
    summary = {
        "version": iteration,
        "source": "iteration",
        "n_samples": len(local_results),
        "sample_ids": [r["sample_id"] for r in local_results],
        "template_v3draw": str(template_v3draw),
        "template_nii": str(template_nii),
        "harris_n_points": harris_result["n_points"],
        "converged": converged,
        "norm_stats": norm_stats,
    }
    if "delta" in conv_data:
        summary["convergence_delta"] = conv_data["delta"]

    save_summary(cur_dir, summary)
    _log(logger, f"  Summary saved. Version {iteration} complete.")

    return summary


# ---------------------------------------------------------------------------
#  多轮自动迭代
# ---------------------------------------------------------------------------

def run_template_build(
    project_dir: Path,
    sample_entries: list[dict[str, Any]],
    config: dict[str, Any],
    logger: Any = None,
    progress_fn: Any = None,
) -> dict[str, Any]:
    """运行多轮迭代直到收敛或达到最大轮数"""
    max_iterations = config.get("max_iterations", 3)
    start_iteration = latest_version(project_dir) + 1
    if start_iteration < 1:
        start_iteration = 1

    _log(logger, f"Template build starting from iteration {start_iteration}, max={max_iterations}")

    results = []
    final_version = start_iteration - 1

    for k in range(start_iteration, start_iteration + max_iterations):
        _log(logger, f"\n{'='*60}")
        summary = run_single_iteration(
            iteration=k,
            project_dir=project_dir,
            sample_entries=sample_entries,
            config=config,
            logger=logger,
            progress_fn=progress_fn,
        )
        results.append(summary)
        final_version = k

        if summary.get("converged"):
            _log(logger, f"\nConverged at iteration {k}!")
            break

    return {
        "final_version": final_version,
        "total_iterations": len(results),
        "converged": results[-1].get("converged", False) if results else False,
        "iterations": results,
    }


def _log(logger: Any, msg: str) -> None:
    if logger:
        logger.info(msg)


def _progress(fn: Any, data: dict) -> None:
    """调用进度回调（如果有）"""
    if fn:
        try:
            fn(data)
        except Exception:
            pass
