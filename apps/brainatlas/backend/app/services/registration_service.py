"""
registration_service.py — 配准业务逻辑

职责：
- run_global_registration_task(): 后台任务处理器（由 task_runner 调用）
- _convert_and_preview(): v3draw → nii.gz + 预览图
- _to_static_url(): 绝对路径 → 静态 URL
- hydrate_global_registration(): 从磁盘恢复 sample 的配准结果

设计原则：
- 纯业务函数，不涉及路由/HTTP
- 所有副作用（update_sample）在本模块内完成
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.io import read_v3draw, save_nifti
from pipeline.preprocess.build_previews import build_previews_from_volume
from pipeline.wrappers.global_registration import run_global_registration
from ..services.sample_service import get_sample, get_sample_dir, update_sample
from ..services.qc_service import run_sample_qc
from ..utils.paths import data_root, project_workspace


# ---------------------------------------------------------------------------
#  工具函数
# ---------------------------------------------------------------------------

def _to_static_url(path_str: str) -> str:
    """绝对路径 → /api/static/... URL"""
    src = Path(path_str).resolve()
    try:
        rel = src.relative_to(data_root().resolve()).as_posix()
        return f"/api/static/{rel}"
    except ValueError:
        return ""


def _convert_and_preview(
    v3draw_path: Path,
    output_dir: Path,
    task_logger: Any = None,
) -> tuple[Path, dict[str, str]]:
    """
    读取 v3draw → 保存 nii.gz → 生成 6 张 preview。
    返回 (nii_path, preview_paths_dict)
    """
    if task_logger:
        task_logger.info(f"Reading v3draw: {v3draw_path}")
    volume, header = read_v3draw(v3draw_path)

    # 多通道时取第 0 通道
    if volume.ndim == 4:
        if task_logger:
            task_logger.info(f"Multi-channel detected ({volume.shape[0]}ch), taking ch0")
        volume = volume[0]

    if task_logger:
        task_logger.info(f"Volume shape={volume.shape}, dtype={volume.dtype}")

    nii_path = output_dir / "global.nii.gz"
    save_nifti(volume, nii_path, spacing=(1.0, 1.0, 1.0))
    if task_logger:
        task_logger.info(f"Saved NIfTI: {nii_path} ({nii_path.stat().st_size / 1024 / 1024:.1f} MB)")

    preview_dir = output_dir / "previews"
    preview_paths = build_previews_from_volume(volume, preview_dir)
    if task_logger:
        task_logger.info(f"Generated previews: {list(preview_paths.keys())}")

    return nii_path, preview_paths


def _build_global_reg_data(
    output_dir: Path,
    v3draw_path: Path,
    nii_path: Path,
    preview_paths: dict[str, str],
    task_id: str | None = None,
) -> dict[str, Any]:
    """构建统一的 global_registration 字典"""
    tar_marker = next(iter(sorted(output_dir.glob("*tar*.marker"))), None)
    sub_marker = next(iter(sorted(output_dir.glob("*sub*.marker"))), None)
    return {
        "task_id": task_id or "",
        "output_dir": str(output_dir),
        "global_v3draw_path": str(v3draw_path),
        "global_nii_path": str(nii_path),
        "global_nii_url": _to_static_url(str(nii_path)),
        "tar_marker_path": str(tar_marker) if tar_marker else "",
        "sub_marker_path": str(sub_marker) if sub_marker else "",
        "preview_paths": preview_paths,
        "preview_urls": {k: _to_static_url(v) for k, v in preview_paths.items()},
    }


# ---------------------------------------------------------------------------
#  后台任务处理器（由 task_runner 调用）
# ---------------------------------------------------------------------------

def run_global_registration_task(
    payload: dict[str, Any],
    task_logger: Any,
) -> dict[str, Any]:
    """
    后台线程中执行全局配准。
    payload 需包含: moving_sample_id, project_id, fixed_path
    task_logger: TaskLogger 实例
    """
    moving_sample_id = payload["moving_sample_id"]
    project_id = payload.get("project_id", "default")
    task_id = payload.get("task_id", "")

    sample = get_sample(moving_sample_id)
    if sample is None:
        raise ValueError(f"Sample not found: {moving_sample_id}")

    moving = Path(sample["stored_path"])
    fixed = Path(payload["fixed_path"])

    if not moving.exists():
        raise FileNotFoundError(f"Moving file not found: {moving}")
    if not fixed.exists():
        raise FileNotFoundError(f"Fixed file not found: {fixed}")

    # 输出目录：sample-scoped
    output_dir = get_sample_dir(project_id, moving_sample_id) / "registration" / "global"
    output_dir.mkdir(parents=True, exist_ok=True)

    task_logger.info(f"Starting global registration")
    task_logger.info(f"  moving: {moving}")
    task_logger.info(f"  fixed:  {fixed}")
    task_logger.info(f"  output: {output_dir}")

    # 1. 更新 sample 状态为 running
    update_sample(moving_sample_id, {
        "global_registration_status": "running",
    })

    # 2. 调用 exe
    task_logger.info("Calling GlobalRegistration_LYT.exe ...")
    result = run_global_registration(moving=moving, fixed=fixed, output_dir=output_dir)
    task_logger.info(f"Exe finished. Output: {result.get('binary_output_path', '')}")

    # 3. v3draw → nii.gz + preview
    global_v3draw = Path(result["binary_output_path"])
    if not global_v3draw.exists():
        raise FileNotFoundError(f"global.v3draw not found at {global_v3draw}")

    nii_path, preview_paths = _convert_and_preview(global_v3draw, output_dir, task_logger)

    # 4. 构建结果数据
    global_reg_data = _build_global_reg_data(
        output_dir, global_v3draw, nii_path, preview_paths, task_id,
    )

    # 5. 更新 sample
    update_sample(moving_sample_id, {
        "global_registration_status": "completed",
        "global_registration": global_reg_data,
    })
    task_logger.info(f"Sample {moving_sample_id} updated: global_registration_status=completed")
    task_logger.info(f"  global_nii_url = {global_reg_data['global_nii_url']}")

    # 6. 自动运行 QC
    import sys
    print(f"[registration_service] step 6: auto QC for {moving_sample_id}", file=sys.stderr, flush=True)
    task_logger.info("--- Step 6: auto QC begin ---")
    qc_info = None
    try:
        task_logger.info("Running auto QC ...")
        qc_result = run_sample_qc(moving_sample_id)
        qc_info = {"score": qc_result.get("score"), "qc_level": qc_result.get("qc_level")}
        task_logger.info(f"QC done: score={qc_result.get('score')}, level={qc_result.get('qc_level')}")
    except Exception as qc_exc:
        task_logger.error(f"Auto QC failed: {qc_exc}")
        import traceback
        task_logger.error(traceback.format_exc())

    return {
        "sample_id": moving_sample_id,
        "global_nii_url": global_reg_data["global_nii_url"],
        "output_dir": str(output_dir),
        "qc": qc_info,
    }


# ---------------------------------------------------------------------------
#  Hydrate: 从磁盘恢复已有的配准结果
# ---------------------------------------------------------------------------

def hydrate_global_registration(sample_id: str) -> dict[str, Any] | None:
    """
    检查 sample 目录下是否已有 global.v3draw，
    如果有 → 自动转换 nii.gz + preview → 更新 sample.json
    """
    sample = get_sample(sample_id)
    if not sample:
        return None

    # 已完成且有 URL → 直接返回
    existing = sample.get("global_registration", {})
    if (sample.get("global_registration_status") == "completed"
            and existing.get("global_nii_url")
            and Path(existing.get("global_nii_path", "")).exists()):
        return sample

    project_id = sample.get("project_id", "default")
    global_dir = get_sample_dir(project_id, sample_id) / "registration" / "global"
    global_v3draw = global_dir / "global.v3draw"

    if not global_v3draw.exists():
        return sample

    # 有 v3draw 但没有 nii.gz → 自动转换
    global_nii = global_dir / "global.nii.gz"
    if not global_nii.exists():
        nii_path, preview_paths = _convert_and_preview(global_v3draw, global_dir)
    else:
        nii_path = global_nii
        preview_dir = global_dir / "previews"
        if preview_dir.exists() and list(preview_dir.glob("*.png")):
            preview_paths = {p.stem: str(p) for p in sorted(preview_dir.glob("*.png"))}
        else:
            _, preview_paths = _convert_and_preview(global_v3draw, global_dir)

    global_reg_data = _build_global_reg_data(global_dir, global_v3draw, nii_path, preview_paths)

    return update_sample(sample_id, {
        "global_registration_status": "completed",
        "global_registration": global_reg_data,
    })
