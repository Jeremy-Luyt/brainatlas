from pathlib import Path
from typing import Any

from pipeline.io.converter import convert_v3draw_to_nifti
from pipeline.io import read_v3draw
from pipeline.io.nii_io import save_nifti
from pipeline.preprocess.build_previews import build_previews_from_nifti, build_previews_from_volume
from pipeline.preprocess.enhance import apply_enhancements
from .sample_service import get_sample, update_sample, get_sample_dir
from ..utils.paths import data_root


def _to_static_url(path_str: str) -> str:
    src = Path(path_str).resolve()
    try:
        rel = src.relative_to(data_root().resolve()).as_posix()
        return f"/api/static/{rel}"
    except ValueError:
        return ""


def run_prepare(sample_id: str, enhance_options: dict | None = None,
                task_logger: Any = None) -> dict[str, Any]:
    """同步执行预处理（也可由后台任务调用）"""
    sample = get_sample(sample_id)
    if not sample:
        raise ValueError(f"Sample {sample_id} not found")

    project_id = sample.get("project_id", "default")
    sample_dir = get_sample_dir(project_id, sample_id)

    # 1. 找到 raw .v3draw
    input_path = Path(sample["stored_path"])
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # 2. 设置输出目录
    converted_dir = sample_dir / "converted"
    preview_dir = sample_dir / "viewer" / "previews"
    converted_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)

    nii_path = converted_dir / "image.nii.gz"
    meta_path = converted_dir / "image_meta.json"

    # 3. 如果有增强选项，先增强再转换
    if enhance_options and any(
        enhance_options.get(k, {}).get("enabled") for k in
        ("downsample", "destripe", "remove_artifact", "brightness_adapt")
    ):
        if task_logger:
            task_logger.info("Applying enhancement preprocessing...")
        volume, meta = read_v3draw(input_path)
        if volume.ndim == 4:
            volume = volume[0]
        volume = apply_enhancements(volume, enhance_options, logger=task_logger)
        save_nifti(volume, nii_path)
        import json
        meta_safe = {k: v for k, v in meta.items() if k != "dtype_np"}
        meta_safe["enhanced"] = True
        meta_safe["enhance_options"] = enhance_options
        with meta_path.open("w", encoding="utf-8") as f:
            json.dump(meta_safe, f, ensure_ascii=False, indent=2, default=str)
        conv_res = {
            "nii_path": str(nii_path),
            "meta_path": str(meta_path),
            "shape": list(volume.shape),
            "dtype": str(volume.dtype),
            "min": float(volume.min()),
            "max": float(volume.max()),
            "mean": float(volume.mean()),
        }
    else:
        # 标准流程
        conv_res = convert_v3draw_to_nifti(
            v3draw_path=input_path,
            nii_path=nii_path,
            meta_path=meta_path,
            spacing=(1.0, 1.0, 1.0),
        )

    # 4. 生成 6 张 preview 图
    prev_res = build_previews_from_nifti(nii_path, preview_dir)

    # 5. 准备写回 sample JSON 的数据
    nii_url = _to_static_url(str(nii_path))
    preview_urls = {k: _to_static_url(v) for k, v in prev_res["preview_paths"].items()}

    updates = {
        "prepare_status": "completed",
        "converted": {
            "nii_path": str(nii_path),
            "meta_path": str(meta_path),
            "nii_url": nii_url,
        },
        "preview": {
            "preview_urls": preview_urls,
        },
        "stats": {
            "shape": conv_res["shape"],
            "dtype": conv_res["dtype"],
            "min": conv_res["min"],
            "max": conv_res["max"],
            "mean": conv_res["mean"],
        },
    }

    # 6. 更新 sample JSON
    updated_sample = update_sample(sample_id, updates)

    return updated_sample


def run_prepare_task(payload: dict[str, Any], task_logger: Any) -> dict[str, Any]:
    """后台任务处理器（由 task_runner 调用）"""
    sample_id = payload["sample_id"]
    enhance_options = payload.get("enhance_options")
    task_logger.info(f"Starting prepare for sample {sample_id}")
    if enhance_options:
        task_logger.info(f"Enhancement options: {enhance_options}")

    update_sample(sample_id, {"prepare_status": "running"})

    try:
        result = run_prepare(sample_id, enhance_options=enhance_options,
                             task_logger=task_logger)
        task_logger.info(f"Prepare completed: shape={result.get('stats', {}).get('shape')}")
        return {"sample_id": sample_id, "status": "completed"}
    except Exception:
        update_sample(sample_id, {"prepare_status": "failed"})
        raise
