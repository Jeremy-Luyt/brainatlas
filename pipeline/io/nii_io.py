from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import nibabel as nib


def save_nifti(
    volume: np.ndarray,
    out_path: str | Path,
    spacing: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> None:
    """
    内部统一使用:
        单通道: (Z, Y, X)

    NIfTI 常见保存方向:
        (X, Y, Z)

    所以这里保存前做一次 transpose:
        (Z, Y, X) -> (X, Y, Z)
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if volume.ndim != 3:
        raise ValueError(f"save_nifti 目前只支持 3D 单通道数组，收到 shape={volume.shape}")

    # 内部 (Z, Y, X) -> NIfTI 写出时用 (X, Y, Z)
    data_xyz = np.transpose(volume, (2, 1, 0))

    # spacing 约定为 (sz, sy, sx)
    sz, sy, sx = spacing

    affine = np.array(
        [
            [sx, 0.0, 0.0, 0.0],
            [0.0, sy, 0.0, 0.0],
            [0.0, 0.0, sz, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )

    nii = nib.Nifti1Image(data_xyz, affine)
    nib.save(nii, str(out_path))


def load_nifti(path: str | Path) -> tuple[np.ndarray, dict[str, Any]]:
    """
    读回后重新统一成内部格式:
        (X, Y, Z) -> (Z, Y, X)
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"NIfTI 文件不存在: {path}")

    nii = nib.load(str(path))
    data_xyz = nii.get_fdata(dtype=np.float32)

    # 读回内部统一格式 (Z, Y, X)
    volume = np.transpose(data_xyz, (2, 1, 0))

    zooms = nii.header.get_zooms()[:3]  # (sx, sy, sz)
    sx, sy, sz = zooms

    meta = {
        "path": str(path),
        "shape_out": tuple(volume.shape),
        "dtype": str(volume.dtype),
        "spacing": (float(sz), float(sy), float(sx)),  # 统一回 (sz, sy, sx)
        "min": float(np.min(volume)),
        "max": float(np.max(volume)),
        "mean": float(np.mean(volume)),
    }

    return volume, meta


def inspect_nii(path: str | Path) -> dict[str, Any]:
    """只读取 NIfTI 头元数据，不返回实际数据。"""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"NIfTI 文件不存在: {path}")

    nii = nib.load(str(path))
    zooms = nii.header.get_zooms()[:3]
    sx, sy, sz = zooms
    shape_xyz = nii.shape[:3]

    return {
        "path": str(path),
        "shape": tuple(shape_xyz),
        "spacing": (float(sz), float(sy), float(sx)),
        "dtype": str(nii.get_data_dtype()),
    }
