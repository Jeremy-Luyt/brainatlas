"""将 CCF 解剖标注映射到自建模板空间

流程:
  1. 加载 CCF 参考体 (nissl) 与自建模板体
  2. 通过质心对齐 + 缩放估计仿射变换 (参考空间 → 模板空间)
  3. 使用最近邻插值将标注体映射到模板空间
  4. 统计每个脑区在模板中的体素分布
  5. 输出: 映射标注 NIfTI + 脑区统计 JSON

设计说明:
  - 标注体 (annotation) 中的像素值为整数脑区 ID, 配准时必须使用
    最近邻插值 (order=0) 以保持标签完整性
  - 仿射变换基于前景质心对齐, CCF 与模板分辨率可不同
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import nibabel as nib
import numpy as np
from scipy.ndimage import affine_transform, binary_erosion, gaussian_filter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  仿射变换估计
# ---------------------------------------------------------------------------

def _foreground_mask(vol: np.ndarray, threshold_pct: float = 5.0) -> np.ndarray:
    """Otsu-like 前景 mask: > threshold_pct 百分位作为前景。"""
    thr = np.percentile(vol[vol > 0], threshold_pct) if np.any(vol > 0) else 0
    return vol > thr


def _center_of_mass(vol: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    """计算体数据的前景质心 (Z, Y, X) 体素坐标。"""
    if mask is None:
        mask = vol > 0
    coords = np.argwhere(mask).astype(np.float64)
    if len(coords) == 0:
        return np.array(vol.shape, dtype=np.float64) / 2.0
    weights = vol[mask].astype(np.float64)
    total = weights.sum()
    if total < 1e-8:
        return coords.mean(axis=0)
    return (coords * weights[:, None]).sum(axis=0) / total


def _bounding_box(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """返回前景的 (min_corner, max_corner) 体素坐标。"""
    coords = np.argwhere(mask)
    if len(coords) == 0:
        return np.zeros(3), np.array(mask.shape, dtype=np.float64)
    return coords.min(axis=0).astype(np.float64), coords.max(axis=0).astype(np.float64)


def estimate_affine_transform(
    ref_volume: np.ndarray,
    ref_spacing: tuple[float, float, float],
    tgt_volume: np.ndarray,
    tgt_spacing: tuple[float, float, float],
) -> np.ndarray:
    """估计从参考空间到模板空间的 4×4 仿射矩阵。

    策略: 质心对齐 + 各向异性缩放 (基于包围盒比例)。
    输入/输出均为体素坐标。

    Args:
        ref_volume: CCF 参考体 (Z, Y, X)
        ref_spacing: 参考体体素间距 (sz, sy, sx) mm
        tgt_volume: 自建模板体 (Z, Y, X)
        tgt_spacing: 模板体素间距 (sz, sy, sx) mm

    Returns:
        4×4 仿射矩阵 M, 使得 tgt_voxel = M @ ref_voxel (齐次坐标)
    """
    ref_sp = np.array(ref_spacing, dtype=np.float64)
    tgt_sp = np.array(tgt_spacing, dtype=np.float64)

    ref_mask = _foreground_mask(ref_volume)
    tgt_mask = _foreground_mask(tgt_volume)

    ref_com = _center_of_mass(ref_volume, ref_mask)
    tgt_com = _center_of_mass(tgt_volume, tgt_mask)

    # 物理尺度的包围盒
    ref_mn, ref_mx = _bounding_box(ref_mask)
    tgt_mn, tgt_mx = _bounding_box(tgt_mask)

    ref_extent = (ref_mx - ref_mn) * ref_sp
    tgt_extent = (tgt_mx - tgt_mn) * tgt_sp

    # 各轴缩放 = (模板物理范围 / 参考物理范围) * (参考体素 / 模板体素)
    safe_ref = np.where(ref_extent > 1e-6, ref_extent, 1.0)
    scale = (tgt_extent / safe_ref) * (ref_sp / tgt_sp)
    scale = np.clip(scale, 0.5, 2.0)  # 限制缩放范围

    # 变换 = 平移到原点 → 缩放 → 平移到目标质心
    # tgt_voxel = scale * (ref_voxel - ref_com) + tgt_com
    # => tgt_voxel = scale * ref_voxel + (tgt_com - scale * ref_com)
    M = np.eye(4)
    M[0, 0], M[1, 1], M[2, 2] = scale
    M[:3, 3] = tgt_com - scale * ref_com

    logger.info(
        "Affine: scale=%s, ref_com=%s, tgt_com=%s",
        np.round(scale, 4), np.round(ref_com, 1), np.round(tgt_com, 1),
    )
    return M


# ---------------------------------------------------------------------------
#  标注映射
# ---------------------------------------------------------------------------

def map_annotation(
    annotation_volume: np.ndarray,
    affine_matrix: np.ndarray,
    target_shape: tuple[int, int, int],
) -> np.ndarray:
    """使用最近邻插值将标注体映射到模板空间。

    scipy.ndimage.affine_transform 的 matrix 参数是 *逆映射*:
    对于输出每个体素 out_voxel, 计算 src_voxel = inv(M) @ out_voxel,
    然后从源体采样。

    Args:
        annotation_volume: CCF 标注体 (int64/uint32), shape (Z, Y, X)
        affine_matrix: 4×4, ref_voxel → tgt_voxel
        target_shape: 输出体尺寸 (Z, Y, X)

    Returns:
        映射后的标注体 (int64)
    """
    M_inv = np.linalg.inv(affine_matrix)
    A = M_inv[:3, :3]
    b = M_inv[:3, 3]

    mapped = affine_transform(
        annotation_volume.astype(np.float64),
        A,
        offset=b,
        output_shape=target_shape,
        order=0,  # 最近邻: 保持离散标签
        mode="constant",
        cval=0.0,
    )
    return mapped.astype(np.int64)


def map_reference_image(
    ref_volume: np.ndarray,
    affine_matrix: np.ndarray,
    target_shape: tuple[int, int, int],
) -> np.ndarray:
    """用三线性插值将参考体映射到模板空间 (用于视觉对比)。"""
    M_inv = np.linalg.inv(affine_matrix)
    mapped = affine_transform(
        ref_volume.astype(np.float64),
        M_inv[:3, :3],
        offset=M_inv[:3, 3],
        output_shape=target_shape,
        order=3,
        mode="constant",
        cval=0.0,
    )
    return mapped.astype(np.float32)


# ---------------------------------------------------------------------------
#  边界提取 (用于叠加轮廓)
# ---------------------------------------------------------------------------

def extract_region_boundaries(mapped_annotation: np.ndarray) -> np.ndarray:
    """从映射标注中提取脑区边界体素 (用于前端叠加显示)。

    Returns:
        uint8 体 — 边界处 = 255, 其余 = 0
    """
    # 腐蚀 mask 并取差集
    mask = mapped_annotation > 0
    eroded = binary_erosion(mask, iterations=1)
    boundary = (mask & ~eroded).astype(np.uint8) * 255

    # 同时检测相邻体素标签不同处
    for axis in range(3):
        diff = np.diff(mapped_annotation, axis=axis) != 0
        slices_src = [slice(None)] * 3
        slices_src[axis] = slice(1, None)
        boundary[tuple(slices_src)] = np.maximum(
            boundary[tuple(slices_src)], diff.astype(np.uint8) * 255
        )
    return boundary


# ---------------------------------------------------------------------------
#  脑区统计
# ---------------------------------------------------------------------------

def compute_region_statistics(
    mapped_annotation: np.ndarray,
    regions_index: list[dict],
    voxel_vol_mm3: float,
) -> list[dict]:
    """计算映射后标注体中每个脑区的统计信息。

    Returns:
        list[dict], 每个脑区含 id, acronym, name, name_zh, voxel_count,
        volume_mm3, centroid_voxel
    """
    region_lookup = {int(r["id"]): r for r in regions_index}
    unique_ids, counts = np.unique(mapped_annotation, return_counts=True)

    stats = []
    for label_id, count in zip(unique_ids, counts):
        label_id = int(label_id)
        if label_id == 0:
            continue
        region = region_lookup.get(label_id, {})
        # 计算质心
        coords = np.argwhere(mapped_annotation == label_id)
        centroid = coords.mean(axis=0).tolist() if len(coords) > 0 else [0, 0, 0]

        stats.append({
            "id": label_id,
            "acronym": region.get("acronym", ""),
            "name": region.get("name", ""),
            "name_zh": region.get("name_zh", ""),
            "color_hex_triplet": region.get("color_hex_triplet", ""),
            "parent_structure_id": region.get("parent_structure_id"),
            "depth": region.get("depth", 0),
            "voxel_count": int(count),
            "volume_mm3": round(float(count) * voxel_vol_mm3, 4),
            "centroid_voxel": [round(c, 1) for c in centroid],
        })

    stats.sort(key=lambda x: x["voxel_count"], reverse=True)
    return stats


# ---------------------------------------------------------------------------
#  主流程
# ---------------------------------------------------------------------------

def run_anatomy_mapping(
    ccf_annotation_nii: str | Path,
    ccf_nissl_nii: str | Path,
    template_nii: str | Path,
    output_dir: str | Path,
    regions_index_json: str | Path,
    *,
    logger_fn=None,
) -> dict[str, Any]:
    """完整的解剖图谱映射流程。

    Args:
        ccf_annotation_nii: CCF 标注体 NIfTI (annotation_25.nii.gz)
        ccf_nissl_nii: CCF Nissl 参考体 NIfTI (ara_nissl_25.nii.gz)
        template_nii: 自建模板 NIfTI (template.nii.gz)
        output_dir: 输出目录
        regions_index_json: 脑区索引 JSON (ccf_regions_index.json)

    Returns:
        dict 含: mapped_annotation_path, mapped_nissl_path, boundary_path,
                 region_stats_path, n_regions, summary
    """
    def _log(msg):
        if logger_fn:
            logger_fn(msg)
        logger.info(msg)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    _log("=== 解剖图谱映射 ===")

    # 1. 加载输入
    _log("Step 1: 加载输入数据...")
    ann_img = nib.load(str(ccf_annotation_nii))
    ann_data = np.asarray(ann_img.get_fdata(dtype=np.float32), dtype=np.int64)
    ann_spacing = tuple(np.abs(np.diag(ann_img.affine[:3, :3])))

    nissl_img = nib.load(str(ccf_nissl_nii))
    nissl_data = nissl_img.get_fdata(dtype=np.float32)
    nissl_spacing = tuple(np.abs(np.diag(nissl_img.affine[:3, :3])))

    tpl_img = nib.load(str(template_nii))
    tpl_data = tpl_img.get_fdata(dtype=np.float32)
    tpl_spacing = tuple(np.abs(np.diag(tpl_img.affine[:3, :3])))
    tpl_shape = tpl_data.shape[:3]

    _log(f"  CCF annotation: shape={ann_data.shape}, spacing={ann_spacing}")
    _log(f"  CCF nissl:      shape={nissl_data.shape}, spacing={nissl_spacing}")
    _log(f"  Template:       shape={tpl_shape}, spacing={tpl_spacing}")

    # 2. 估计仿射变换
    _log("Step 2: 估计仿射变换 (质心对齐 + 包围盒缩放)...")
    affine_M = estimate_affine_transform(nissl_data, nissl_spacing, tpl_data, tpl_spacing)
    _log(f"  缩放: diag={np.diag(affine_M[:3,:3]).round(4).tolist()}")
    _log(f"  平移: {affine_M[:3,3].round(1).tolist()}")

    # 3. 映射标注体
    _log("Step 3: 映射标注体 (最近邻插值)...")
    mapped_ann = map_annotation(ann_data, affine_M, tpl_shape)
    n_labels = len(np.unique(mapped_ann)) - (1 if 0 in mapped_ann else 0)
    _log(f"  映射完成: {n_labels} 个脑区标签")

    # 4. 映射参考体 (用于视觉对检)
    _log("Step 4: 映射 Nissl 参考体 (三线性插值)...")
    mapped_nissl = map_reference_image(nissl_data, affine_M, tpl_shape)
    _log(f"  Nissl 映射完成")

    # 5. 提取边界
    _log("Step 5: 提取脑区边界...")
    boundary = extract_region_boundaries(mapped_ann)
    n_boundary = int(np.count_nonzero(boundary))
    _log(f"  边界体素: {n_boundary}")

    # 6. 保存输出
    _log("Step 6: 保存输出...")

    # 映射标注
    mapped_ann_path = output_dir / "mapped_annotation.nii.gz"
    ann_nii = nib.Nifti1Image(mapped_ann.astype(np.int32), tpl_img.affine)
    nib.save(ann_nii, str(mapped_ann_path))
    _log(f"  标注体: {mapped_ann_path.name}")

    # 映射 Nissl
    mapped_nissl_path = output_dir / "mapped_nissl.nii.gz"
    nissl_nii = nib.Nifti1Image(mapped_nissl, tpl_img.affine)
    nib.save(nissl_nii, str(mapped_nissl_path))
    _log(f"  Nissl:  {mapped_nissl_path.name}")

    # 边界
    boundary_path = output_dir / "annotation_boundary.nii.gz"
    bnd_nii = nib.Nifti1Image(boundary, tpl_img.affine)
    nib.save(bnd_nii, str(boundary_path))
    _log(f"  边界:  {boundary_path.name}")

    # 仿射矩阵
    affine_path = output_dir / "ccf_to_template_affine.json"
    affine_path.write_text(json.dumps({
        "matrix": affine_M.tolist(),
        "ref_spacing": list(nissl_spacing),
        "tgt_spacing": list(tpl_spacing),
        "ref_shape": list(nissl_data.shape),
        "tgt_shape": list(tpl_shape),
    }, indent=2), encoding="utf-8")

    # 7. 脑区统计
    _log("Step 7: 计算脑区统计...")
    regions_index = json.loads(Path(regions_index_json).read_text(encoding="utf-8"))
    voxel_vol = float(np.prod(tpl_spacing))
    stats = compute_region_statistics(mapped_ann, regions_index, voxel_vol)

    stats_path = output_dir / "region_stats.json"
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"  脑区统计: {len(stats)} 个脑区 → {stats_path.name}")

    # 8. 保存映射摘要
    summary = {
        "ccf_annotation": str(ccf_annotation_nii),
        "ccf_nissl": str(ccf_nissl_nii),
        "template": str(template_nii),
        "mapped_annotation": str(mapped_ann_path),
        "mapped_nissl": str(mapped_nissl_path),
        "boundary": str(boundary_path),
        "affine_matrix": str(affine_path),
        "region_stats": str(stats_path),
        "n_regions": n_labels,
        "n_boundary_voxels": n_boundary,
        "tpl_shape": list(tpl_shape),
        "tpl_spacing": [float(s) for s in tpl_spacing],
    }
    summary_path = output_dir / "anatomy_mapping_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    _log(f"\n✓ 解剖图谱映射完成 → {output_dir}")
    return {
        "mapped_annotation_path": str(mapped_ann_path),
        "mapped_nissl_path": str(mapped_nissl_path),
        "boundary_path": str(boundary_path),
        "region_stats_path": str(stats_path),
        "n_regions": n_labels,
        "summary": summary,
    }
