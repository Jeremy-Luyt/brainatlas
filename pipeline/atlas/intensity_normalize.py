"""强度归一化与体素平均"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


def percentile_normalize(
    volume: np.ndarray,
    low_pct: float = 1.0,
    high_pct: float = 99.0,
) -> tuple[np.ndarray, dict[str, float]]:
    """百分位裁剪+拉伸到[0,255], 仅计算前景体素百分位"""
    vol = volume.astype(np.float32)
    fg_mask = vol > 0
    fg_vals = vol[fg_mask]

    if fg_vals.size == 0:
        return np.zeros_like(volume, dtype=np.uint8), {"p_low": 0.0, "p_high": 0.0}

    p_low = float(np.percentile(fg_vals, low_pct))
    p_high = float(np.percentile(fg_vals, high_pct))

    if p_high <= p_low:
        return np.zeros_like(volume, dtype=np.uint8), {"p_low": p_low, "p_high": p_high}

    normalized = np.clip((vol - p_low) / (p_high - p_low), 0.0, 1.0) * 255.0
    # 背景保持为零
    normalized[~fg_mask] = 0.0
    return normalized.astype(np.uint8), {"p_low": p_low, "p_high": p_high}


def voxel_average(volumes: list[np.ndarray], margin: int = 8) -> np.ndarray:
    """距离变换加权体素平均, 边界margin体素内线性衰减消除FOV拼接伪影"""
    from scipy.ndimage import distance_transform_edt

    if not volumes:
        raise ValueError("Empty volume list")

    weight_sum = np.zeros_like(volumes[0], dtype=np.float64)
    value_sum = np.zeros_like(volumes[0], dtype=np.float64)

    for vol in volumes:
        v = vol.astype(np.float64)
        mask = v > 0
        # 距离变换: 每个前景体素到最近背景体素的距离
        dist = distance_transform_edt(mask).astype(np.float64)
        # 线性衰减权重: 边界处 0 → margin 处 1
        w = np.clip(dist / max(margin, 1), 0.0, 1.0)

        value_sum += v * w
        weight_sum += w

    safe_weight = np.maximum(weight_sum, 1e-8)
    avg = value_sum / safe_weight
    avg[weight_sum < 1e-8] = 0.0
    return np.clip(avg, 0, 255).astype(np.uint8)


def normalize_and_average(
    volume_paths: list[Path],
    reader_fn,
    low_pct: float = 1.0,
    high_pct: float = 99.0,
    logger: Any = None,
) -> tuple[np.ndarray, list[dict[str, float]]]:
    """批量读取v3draw并归一化后体素平均"""
    normalized_vols = []
    stats_list = []

    for i, vp in enumerate(volume_paths):
        if logger:
            logger.info(f"  Normalizing [{i+1}/{len(volume_paths)}]: {vp.name}")

        vol, _ = reader_fn(vp)
        # 多通道取第0通道
        if vol.ndim == 4:
            vol = vol[0]

        norm_vol, stats = percentile_normalize(vol, low_pct, high_pct)
        normalized_vols.append(norm_vol)
        stats["file"] = str(vp)
        stats_list.append(stats)

        if logger:
            logger.info(f"    p_low={stats['p_low']:.1f}, p_high={stats['p_high']:.1f}")

    avg = voxel_average(normalized_vols)
    return avg, stats_list
