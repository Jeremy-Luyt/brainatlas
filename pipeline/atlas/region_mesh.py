"""CCF 标注体按脑区导出 GLB。"""
from __future__ import annotations

from pathlib import Path

import nibabel as nib
import numpy as np
from skimage.measure import marching_cubes
import trimesh


def _region_glb_path(out_dir: Path, region_id: int) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"region_{region_id}.glb"


def build_region_glb(
    annotation_nii: Path,
    region_id: int,
    out_dir: Path,
    *,
    target_faces: int = 80_000,
    smooth_iterations: int = 10,
) -> Path:
    """从 annotation.nii.gz 中提取单个脑区并导出 GLB。"""
    img = nib.load(str(annotation_nii))
    data = np.asarray(img.get_fdata(dtype=np.float32), dtype=np.int64)

    mask = (data == int(region_id)).astype(np.uint8)
    if int(mask.sum()) == 0:
        raise ValueError(f"region id {region_id} not found in annotation volume")

    # 对二值 mask 取 0.5 等值面。
    voxel_sizes = np.abs(np.diag(img.affine[:3, :3]))
    voxel_sizes = np.where(voxel_sizes > 0, voxel_sizes, 1.0)
    verts, faces, normals, _ = marching_cubes(mask, level=0.5, spacing=tuple(voxel_sizes))
    mesh = trimesh.Trimesh(vertices=verts, faces=faces, vertex_normals=normals)
    mesh.vertices -= mesh.center_mass

    if smooth_iterations > 0:
        trimesh.smoothing.filter_taubin(mesh, iterations=smooth_iterations)

    if len(mesh.faces) > target_faces:
        try:
            mesh = mesh.simplify_quadric_decimation(face_count=target_faces)
        except Exception:
            # 在无 fast-simplification 时保留原 mesh。
            pass

    mesh.fix_normals()
    out_path = _region_glb_path(out_dir, region_id)
    mesh.export(str(out_path), file_type="glb")
    return out_path


def ensure_region_glb(
    annotation_nii: Path,
    region_id: int,
    out_dir: Path,
    **kwargs,
) -> Path:
    """按需生成脑区 GLB（有缓存时直接复用）。"""
    out_path = _region_glb_path(out_dir, region_id)
    if out_path.exists() and out_path.stat().st_mtime >= annotation_nii.stat().st_mtime:
        return out_path
    return build_region_glb(annotation_nii, region_id, out_dir, **kwargs)
