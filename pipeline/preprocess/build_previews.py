from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import imageio.v2 as imageio

from pipeline.io.nii_io import load_nifti


def normalize_to_uint8(img: np.ndarray, p_low: float = 1.0, p_high: float = 99.0) -> np.ndarray:
    """
    用 percentile 做鲁棒归一化，避免整张图过黑或被极端值拉坏
    """
    img = img.astype(np.float32)

    low = np.percentile(img, p_low)
    high = np.percentile(img, p_high)

    if high <= low:
        return np.zeros_like(img, dtype=np.uint8)

    img = np.clip(img, low, high)
    img = (img - low) / (high - low)
    img = img * 255.0
    return img.astype(np.uint8)


def build_previews_from_volume(volume: np.ndarray, out_dir: str | Path) -> dict[str, str]:
    """
    volume: (Z, Y, X)
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if volume.ndim != 3:
        raise ValueError(f"build_previews_from_volume 只支持 3D 单通道数组，收到 shape={volume.shape}")

    z_mid = volume.shape[0] // 2
    y_mid = volume.shape[1] // 2
    x_mid = volume.shape[2] // 2

    # 正交切片
    xy = volume[z_mid, :, :]
    xz = volume[:, y_mid, :]
    yz = volume[:, :, x_mid]

    # MIP
    mip_xy = volume.max(axis=0)
    mip_xz = volume.max(axis=1)
    mip_yz = volume.max(axis=2)

    images = {
        "xy": normalize_to_uint8(xy),
        "xz": normalize_to_uint8(xz),
        "yz": normalize_to_uint8(yz),
        "mip_xy": normalize_to_uint8(mip_xy),
        "mip_xz": normalize_to_uint8(mip_xz),
        "mip_yz": normalize_to_uint8(mip_yz),
    }

    result = {}
    for name, img in images.items():
        path = out_dir / f"{name}.png"
        imageio.imwrite(path, img)
        result[name] = str(path)

    return result


def build_previews_from_nifti(nii_path: str | Path, out_dir: str | Path) -> dict[str, Any]:
    volume, meta = load_nifti(nii_path)
    preview_paths = build_previews_from_volume(volume, out_dir)

    return {
        "shape_out": meta["shape_out"],
        "dtype": meta["dtype"],
        "spacing": meta["spacing"],
        "preview_paths": preview_paths,
    }
