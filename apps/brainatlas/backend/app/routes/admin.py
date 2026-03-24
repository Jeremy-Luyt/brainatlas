"""
诊断+恢复 API: 检查 global.v3draw 转换流程，并为历史样本恢复 Global 结果
"""
from pathlib import Path
import traceback
import shutil

from fastapi import APIRouter

from ..services.sample_service import get_sample, update_sample, get_sample_dir, _iter_sample_files
from ..services.registration_service import _to_static_url
from ..utils.paths import data_root, project_workspace

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/diagnose-global")
def diagnose_global(project_id: str = "default") -> dict:
    """诊断 global.v3draw 转换流程"""
    results = {"steps": [], "errors": []}

    # 1. 检查项目级 registration 目录
    reg_root = project_workspace(project_id) / "registration"
    results["reg_root_exists"] = reg_root.exists()
    if not reg_root.exists():
        results["errors"].append("registration directory not found")
        return results

    # 2. 查找所有 global.v3draw
    all_globals = sorted(reg_root.glob("**/global.v3draw"))
    results["global_v3draw_count"] = len(all_globals)
    results["global_v3draw_paths"] = [str(p) for p in all_globals[:5]]

    if not all_globals:
        results["errors"].append("no global.v3draw found")
        return results

    # 3. 尝试读取第一个 global.v3draw 的 header
    target = all_globals[0]
    results["target"] = str(target)
    results["target_size_mb"] = target.stat().st_size / 1024 / 1024

    try:
        from pipeline.io.reader_v3draw import read_v3draw_header
        header = read_v3draw_header(target)
        results["header"] = {
            "width": header["width"],
            "height": header["height"],
            "depth": header["depth"],
            "channels": header["channels"],
            "dtype": header["dtype"],
            "expected_bytes": header["expected_bytes"],
            "actual_bytes": header["actual_bytes"],
            "size_match": header["expected_bytes"] == header["actual_bytes"],
        }
        results["steps"].append("header_read: OK")
    except Exception as e:
        results["errors"].append(f"header_read: {e}")
        results["traceback_header"] = traceback.format_exc()
        return results

    # 4. 尝试完整读取
    try:
        from pipeline.io.reader_v3draw import read_v3draw
        volume, meta = read_v3draw(target)
        results["read_v3draw"] = {
            "shape_out": list(meta.get("shape_out", [])),
            "ndim": volume.ndim,
            "dtype": str(volume.dtype),
            "min": float(meta.get("min", 0)),
            "max": float(meta.get("max", 0)),
        }
        results["steps"].append("read_v3draw: OK")
    except Exception as e:
        results["errors"].append(f"read_v3draw: {e}")
        results["traceback_read"] = traceback.format_exc()
        return results

    # 5. 如果是多通道，取第一个通道
    if volume.ndim == 4:
        results["steps"].append(f"multi-channel detected: {volume.shape}, taking channel 0")
        volume = volume[0]

    # 6. 尝试 save_nifti
    try:
        from pipeline.io.nii_io import save_nifti
        test_out = data_root() / "temp" / "diag_global.nii.gz"
        save_nifti(volume, test_out, spacing=(1.0, 1.0, 1.0))
        results["save_nifti"] = {"path": str(test_out), "size_mb": test_out.stat().st_size / 1024 / 1024}
        results["steps"].append("save_nifti: OK")
        # 清理
        test_out.unlink(missing_ok=True)
    except Exception as e:
        results["errors"].append(f"save_nifti: {e}")
        results["traceback_nifti"] = traceback.format_exc()
        return results

    # 7. 检查样本信息
    samples_with_opwarp = []
    for p in _iter_sample_files():
        try:
            import json
            data = json.loads(p.read_text(encoding="utf-8"))
            if data.get("filename", "").lower() == "op_warp.v3draw":
                samples_with_opwarp.append({
                    "sample_id": data["sample_id"],
                    "status": data.get("global_registration_status", "?"),
                    "stored_path": data.get("stored_path", ""),
                })
        except Exception:
            pass
    results["op_warp_samples"] = len(samples_with_opwarp)
    results["sample_list"] = samples_with_opwarp[:5]

    # 8. 检查 hydrate 流程
    root_log = reg_root / "global_registration.log"
    if root_log.exists():
        try:
            txt = root_log.read_text(encoding="utf-8", errors="ignore")[:2000]
            results["root_log_preview"] = txt
        except Exception as e:
            results["root_log_error"] = str(e)

    results["steps"].append("diagnosis complete")
    return results


@router.post("/recover-global")
def recover_global(sample_id: str, project_id: str = "default") -> dict:
    """为指定样本恢复 Global 配准结果"""
    results = {"steps": [], "errors": []}

    sample = get_sample(sample_id)
    if not sample:
        return {"error": f"sample {sample_id} not found"}

    results["sample_id"] = sample_id
    results["filename"] = sample.get("filename")

    # 找到最新的 global.v3draw
    reg_root = project_workspace(project_id) / "registration"
    all_globals = sorted(reg_root.glob("**/global.v3draw"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not all_globals:
        return {"error": "no global.v3draw found in registration directory"}

    src_v3draw = all_globals[0]
    results["source_v3draw"] = str(src_v3draw)

    # 创建 sample-scoped 输出目录
    sample_global_dir = get_sample_dir(project_id, sample_id) / "registration" / "global"
    sample_global_dir.mkdir(parents=True, exist_ok=True)

    # 复制 v3draw 和相关文件
    try:
        src_dir = src_v3draw.parent
        for pattern in ["global*.v3draw", "*.marker", "global_registration.log"]:
            for src in src_dir.glob(pattern):
                if src.is_file():
                    dst = sample_global_dir / src.name
                    if not dst.exists():
                        shutil.copy2(src, dst)
                        results["steps"].append(f"copied {src.name}")
    except Exception as e:
        results["errors"].append(f"copy: {e}")

    # 读取 v3draw
    global_v3draw = sample_global_dir / "global.v3draw"
    try:
        from pipeline.io.reader_v3draw import read_v3draw
        volume, header = read_v3draw(global_v3draw)
        results["steps"].append(f"read_v3draw OK: shape={volume.shape}, ndim={volume.ndim}")

        # 处理多通道
        if volume.ndim == 4:
            results["steps"].append(f"multi-channel {volume.shape}, taking channel 0")
            volume = volume[0]
    except Exception as e:
        results["errors"].append(f"read_v3draw: {e}")
        results["traceback"] = traceback.format_exc()
        return results

    # 转换 nii.gz
    global_nii = sample_global_dir / "global.nii.gz"
    try:
        from pipeline.io.nii_io import save_nifti
        save_nifti(volume, global_nii, spacing=(1.0, 1.0, 1.0))
        results["steps"].append(f"save_nifti OK: {global_nii.stat().st_size / 1024 / 1024:.1f} MB")
    except Exception as e:
        results["errors"].append(f"save_nifti: {e}")
        results["traceback"] = traceback.format_exc()
        return results

    # 生成预览
    preview_paths = {}
    try:
        from pipeline.preprocess.build_previews import build_previews_from_volume
        preview_dir = sample_global_dir / "previews"
        preview_paths = build_previews_from_volume(volume, preview_dir)
        results["steps"].append(f"previews OK: {list(preview_paths.keys())}")
    except Exception as e:
        results["errors"].append(f"previews: {e}")

    # 更新 sample.json
    try:
        global_reg_data = {
            "output_dir": str(sample_global_dir),
            "global_v3draw_path": str(global_v3draw),
            "global_nii_path": str(global_nii),
            "global_nii_url": _to_static_url(str(global_nii)),
            "preview_paths": preview_paths,
            "preview_urls": {k: _to_static_url(v) for k, v in preview_paths.items()},
        }
        updated = update_sample(sample_id, {
            "global_registration_status": "completed",
            "global_registration": global_reg_data,
        })
        results["steps"].append("sample.json updated")
        results["global_nii_url"] = global_reg_data["global_nii_url"]
        results["preview_urls"] = global_reg_data["preview_urls"]
    except Exception as e:
        results["errors"].append(f"update_sample: {e}")

    return results
