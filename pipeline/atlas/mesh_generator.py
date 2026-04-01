"""NIfTI → GLB 网格生成器

将体数据通过 Marching Cubes 提取等值面，经 Taubin 平滑 + 四面体简化后
导出为 GLB (Binary glTF) 文件，供前端 Three.js 加载。
"""
from __future__ import annotations

import logging
from pathlib import Path

import nibabel as nib
import numpy as np
from skimage.measure import marching_cubes
import trimesh

logger = logging.getLogger(__name__)


def _otsu(data: np.ndarray, n_bins: int = 256) -> float:
    """快速 Otsu 阈值。"""
    flat = data.ravel().astype(np.float64)
    mn, mx = float(flat.min()), float(flat.max())
    if mx - mn < 1e-8:
        return mn
    hist, edges = np.histogram(flat, bins=n_bins, range=(mn, mx))
    centers = (edges[:-1] + edges[1:]) / 2.0
    total = float(hist.sum())
    total_mean = float(np.dot(hist, centers))
    cum_w = np.cumsum(hist).astype(np.float64)
    cum_m = np.cumsum(hist * centers)
    w_fg = total - cum_w
    valid = (cum_w > 0) & (w_fg > 0)
    m_bg = np.where(valid, cum_m / cum_w, 0.0)
    m_fg = np.where(valid, (total_mean - cum_m) / w_fg, 0.0)
    var_b = np.where(valid, cum_w * w_fg * (m_bg - m_fg) ** 2, 0.0)
    return float(centers[int(np.argmax(var_b))])


def nifti_to_glb(
    nii_path: Path,
    out_path: Path | None = None,
    *,
    iso_level: float | None = None,
    target_faces: int = 100_000,
    smooth_iterations: int = 30,
    step_size: int = 1,
) -> Path:
    """NIfTI → GLB 完整管线。

    Args:
        nii_path: .nii.gz 文件路径
        out_path: 输出 GLB 路径，默认同目录同名 .glb
        iso_level: 等值面阈值，None 则自动 Otsu
        target_faces: 简化后目标面数
        smooth_iterations: Taubin 平滑迭代次数
        step_size: marching cubes 步长 (1=全精度, 2=降采样)

    Returns:
        GLB 文件路径
    """
    if out_path is None:
        out_path = nii_path.with_suffix(".glb")

    # 加载体数据
    img = nib.load(str(nii_path))
    data = img.get_fdata(dtype=np.float32)
    affine = img.affine
    voxel_sizes = np.abs(np.diag(affine[:3, :3]))
    logger.info("Loaded %s, shape=%s, voxel=%.2f×%.2f×%.2f",
                nii_path.name, data.shape, *voxel_sizes)

    # 阈值
    if iso_level is None:
        iso_level = _otsu(data)
    logger.info("Iso level=%.2f", iso_level)

    # Marching Cubes
    verts, faces, normals, _ = marching_cubes(
        data, level=iso_level, spacing=tuple(voxel_sizes), step_size=step_size
    )
    logger.info("Marching cubes: %d verts, %d faces", len(verts), len(faces))

    # 构建 trimesh
    mesh = trimesh.Trimesh(vertices=verts, faces=faces, vertex_normals=normals)

    # 居中
    mesh.vertices -= mesh.center_mass

    # Taubin 平滑 (交替正/负 lambda，保持体积)
    if smooth_iterations > 0:
        trimesh.smoothing.filter_taubin(mesh, iterations=smooth_iterations)
        logger.info("Taubin smooth: %d iterations", smooth_iterations)

    # 简化 (quadric decimation, 需要 fast-simplification)
    if len(mesh.faces) > target_faces:
        try:
            mesh = mesh.simplify_quadric_decimation(face_count=target_faces)
            logger.info("Simplified to %d faces", len(mesh.faces))
        except Exception as exc:
            logger.warning("Simplification skipped: %s", exc)

    # 重新计算法线
    mesh.fix_normals()

    # 导出 GLB
    out_path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(str(out_path), file_type="glb")
    size_kb = out_path.stat().st_size / 1024
    logger.info("Exported %s (%.0f KB, %d verts, %d faces)",
                out_path.name, size_kb, len(mesh.vertices), len(mesh.faces))

    return out_path


def _glb_path_for(nii_path: Path) -> Path:
    """处理 .nii.gz 双后缀：template.nii.gz → template.glb"""
    name = nii_path.name
    if name.endswith(".nii.gz"):
        return nii_path.parent / (name[:-7] + ".glb")
    return nii_path.with_suffix(".glb")


def ensure_glb(nii_path: Path, **kwargs) -> Path:
    """如果 GLB 缓存不存在或 NIfTI 更新了，则重新生成。"""
    glb_path = _glb_path_for(nii_path)
    if glb_path.exists():
        if glb_path.stat().st_mtime >= nii_path.stat().st_mtime:
            return glb_path
        logger.info("GLB stale, regenerating")
    return nifti_to_glb(nii_path, glb_path, **kwargs)
