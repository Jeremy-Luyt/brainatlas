"""
降采样模块: 各向异性缩放匹配目标模板体素尺度

fMOST 鼠脑原始数据尺寸约 40k×30k×10k 体素, 直接用于三维非线性配准
在计算与存储上均不现实. 为匹配目标 CCFv3 模板 (25 μm) 的体素尺度,
对所有 fMOST 图像执行各向异性缩放 (默认 X×Y×Z = 64×64×16),
使其在空间尺寸上与参考模板大致一致.

提供两种降采样策略:
  1) stride - 简单步进取样, 速度极快, 适合粗预览
  2) block_mean - 块均值降采样, 抗混叠, 适合正式配准流程
"""
from __future__ import annotations

from typing import Literal

import numpy as np


def downsample(
    volume: np.ndarray,
    factors: tuple[int, int, int] = (16, 64, 64),
    method: Literal["stride", "block_mean"] = "block_mean",
) -> np.ndarray:
    """
    各向异性降采样.

    Parameters
    ----------
    volume : (Z, Y, X) uint8/uint16/float32
        输入三维图像.
    factors : (fz, fy, fx)
        沿 Z/Y/X 轴的降采样倍数.  fMOST→CCFv3 典型值: (16, 64, 64).
    method : "stride" | "block_mean"
        "stride"     - 简单步进取样, 速度最快
        "block_mean" - 块均值, 抗混叠, 推荐用于正式配准

    Returns
    -------
    np.ndarray  降采样后的图像, dtype 与输入一致 (block_mean 时四舍五入到整型).
    """
    fz, fy, fx = factors

    if method == "stride":
        return _downsample_stride(volume, fz, fy, fx)
    elif method == "block_mean":
        return _downsample_block_mean(volume, fz, fy, fx)
    else:
        raise ValueError(f"不支持的降采样方法: {method}")


# ---------------------------------------------------------------------------
# 策略 1: 步进取样
# ---------------------------------------------------------------------------

def _downsample_stride(
    vol: np.ndarray, fz: int, fy: int, fx: int,
) -> np.ndarray:
    return vol[::fz, ::fy, ::fx].copy()


# ---------------------------------------------------------------------------
# 策略 2: 块均值降采样 (抗混叠)
# ---------------------------------------------------------------------------

def _downsample_block_mean(
    vol: np.ndarray, fz: int, fy: int, fx: int,
) -> np.ndarray:
    """
    将体素划分为 (fz, fy, fx) 大小的块, 取均值.
    尾部不足一块的部分截断.
    """
    orig_dtype = vol.dtype
    z, y, x = vol.shape

    # 截断到整数块
    nz = (z // fz) * fz
    ny = (y // fy) * fy
    nx = (x // fx) * fx
    cropped = vol[:nz, :ny, :nx]

    # reshape + mean
    out_z, out_y, out_x = nz // fz, ny // fy, nx // fx
    reshaped = cropped.reshape(out_z, fz, out_y, fy, out_x, fx)
    mean_vol = reshaped.astype(np.float64).mean(axis=(1, 3, 5))

    if np.issubdtype(orig_dtype, np.integer):
        return np.clip(np.round(mean_vol), 0, np.iinfo(orig_dtype).max).astype(orig_dtype)
    return mean_vol.astype(orig_dtype)
