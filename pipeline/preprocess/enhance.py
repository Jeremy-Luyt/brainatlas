"""增强预处理: 降采样/去条纹/去伪影/亮度自适应, 所有步骤由配置驱动"""
from __future__ import annotations

from typing import Any

import numpy as np

try:
    from scipy.ndimage import uniform_filter, median_filter
    from scipy.fft import fft, ifft
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


# ---------------------------------------------------------------------------
#  1. 降采样
# ---------------------------------------------------------------------------

def downsample(
    volume: np.ndarray,
    factors: tuple[int, int, int] = (2, 2, 2),
) -> np.ndarray:
    """简单步进降采样"""
    fz, fy, fx = factors
    return volume[::fz, ::fy, ::fx].copy()


# ---------------------------------------------------------------------------
#  2. 去条纹
# ---------------------------------------------------------------------------

def destripe(
    volume: np.ndarray,
    sigma: float = 3.0,
) -> np.ndarray:
    """沿Z轴去条纹: 对每个(y,x)位置的Z剖面做高通滤波"""
    if not HAS_SCIPY:
        return volume

    result = volume.astype(np.float32)
    z_len = result.shape[0]

    # 生成高斯低通核
    freqs = np.fft.fftfreq(z_len)
    gaussian_lp = np.exp(-0.5 * (freqs / (sigma / z_len)) ** 2)

    for y in range(result.shape[1]):
        for x in range(result.shape[2]):
            col = result[:, y, x]
            ft = np.fft.fft(col)
            # 减去低频 (条纹) 分量，保留 DC
            stripe = np.real(np.fft.ifft(ft * gaussian_lp)) - col.mean()
            result[:, y, x] = col - stripe

    return np.clip(result, 0, np.iinfo(volume.dtype).max if np.issubdtype(volume.dtype, np.integer) else result.max()).astype(volume.dtype)


# ---------------------------------------------------------------------------
#  3. 去伪影
# ---------------------------------------------------------------------------

def remove_artifact(
    volume: np.ndarray,
    low_pct: float = 0.5,
    high_pct: float = 99.5,
) -> np.ndarray:
    """百分位截断去伪影"""
    vol = volume.astype(np.float32)
    p_low = np.percentile(vol, low_pct)
    p_high = np.percentile(vol, high_pct)
    clipped = np.clip(vol, p_low, p_high)
    # 重新映射回原始范围
    if p_high > p_low:
        if np.issubdtype(volume.dtype, np.integer):
            max_val = np.iinfo(volume.dtype).max
            clipped = (clipped - p_low) / (p_high - p_low) * max_val
        return clipped.astype(volume.dtype)
    return volume


# ---------------------------------------------------------------------------
#  4. 亮度自适应 (简化 CLAHE)
# ---------------------------------------------------------------------------

def brightness_adapt(
    volume: np.ndarray,
    block_size: int = 64,
    clip_limit: float = 3.0,
) -> np.ndarray:
    """简化的 3D 分块局部均值归一化"""
    if not HAS_SCIPY:
        return volume

    vol = volume.astype(np.float32)
    local_mean = uniform_filter(vol, size=block_size)
    local_mean = np.maximum(local_mean, 1.0)  # 避免除零

    # 局部对比度增强
    enhanced = vol / local_mean * vol.mean()
    enhanced = np.clip(enhanced, 0, clip_limit * vol.mean())

    if np.issubdtype(volume.dtype, np.integer):
        max_val = np.iinfo(volume.dtype).max
        enhanced = np.clip(enhanced, 0, max_val)

    return enhanced.astype(volume.dtype)


# ---------------------------------------------------------------------------
#  统一入口
# ---------------------------------------------------------------------------

def apply_enhancements(
    volume: np.ndarray,
    options: dict[str, Any],
    logger: Any = None,
) -> np.ndarray:
    """按配置依次应用预处理增强步骤"""
    result = volume

    # 按固定顺序执行
    steps = [
        ("downsample", _apply_downsample),
        ("destripe", _apply_destripe),
        ("remove_artifact", _apply_artifact),
        ("brightness_adapt", _apply_brightness),
    ]

    for name, fn in steps:
        step_opts = options.get(name, {})
        if not step_opts.get("enabled", False):
            continue
        if logger:
            logger.info(f"  Applying {name}...")
        result = fn(result, step_opts)
        if logger:
            logger.info(f"    Done. shape={result.shape}, dtype={result.dtype}")

    return result


def _apply_downsample(vol: np.ndarray, opts: dict) -> np.ndarray:
    factors = tuple(opts.get("factors", [2, 2, 2]))
    return downsample(vol, factors)


def _apply_destripe(vol: np.ndarray, opts: dict) -> np.ndarray:
    return destripe(vol, sigma=opts.get("sigma", 3.0))


def _apply_artifact(vol: np.ndarray, opts: dict) -> np.ndarray:
    return remove_artifact(
        vol,
        low_pct=opts.get("low_pct", 0.5),
        high_pct=opts.get("high_pct", 99.5),
    )


def _apply_brightness(vol: np.ndarray, opts: dict) -> np.ndarray:
    return brightness_adapt(
        vol,
        block_size=opts.get("block_size", 64),
        clip_limit=opts.get("clip_limit", 3.0),
    )
