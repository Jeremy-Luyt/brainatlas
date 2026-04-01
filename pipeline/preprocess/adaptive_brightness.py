"""
亮度自适应模块: 3D 局部对比度增强 (CLAHE 思想)

对于部分成像数据, 由于成像方式或数据类型转换等原因, 常出现脑区间
亮度对比度差异显著的情况 (如小脑区域异常偏暗而皮层区域过亮).

本模块借鉴 Fiji 中局部亮度自适应算法 (CLAHE) 的思想, 对三维图像
强度分布进行自动校正:
  1) 将图像划分为重叠的三维块 (block)
  2) 对每个块内的直方图独立进行限幅均衡化
  3) 通过三线性插值融合相邻块的映射函数, 消除块边界伪影

该方法使不同脑区之间的对比度处于适宜范围, 增强解剖边界与
内部结构特征, 从而提升后续相似性度量和特征点提取的稳定性.
"""
from __future__ import annotations

from typing import Any

import numpy as np


def adaptive_brightness(
    volume: np.ndarray,
    block_size: int = 64,
    clip_limit: float = 3.0,
    n_bins: int = 256,
) -> np.ndarray:
    """
    3D CLAHE (Contrast Limited Adaptive Histogram Equalization).

    Parameters
    ----------
    volume : (Z, Y, X) uint8
        输入三维图像, 目前仅支持 uint8.
    block_size : int
        分块大小 (各轴相同). 块越小局部增强效果越强.
    clip_limit : float
        直方图裁剪限幅 (>1). 越大允许的对比度增强越强.
        典型值 2.0~4.0, 设得太大会放大噪声.
    n_bins : int
        直方图 bin 数量.

    Returns
    -------
    np.ndarray (Z, Y, X) uint8
    """
    orig_dtype = volume.dtype
    vol = volume.astype(np.float32)

    nz, ny, nx = vol.shape

    # 计算网格: 每轴的块数 (至少 1)
    gz = max(nz // block_size, 1)
    gy = max(ny // block_size, 1)
    gx = max(nx // block_size, 1)

    # 实际块尺寸 (适配图像尺寸)
    bz = nz / gz
    by = ny / gy
    bx = nx / gx

    # 为每个网格节点计算限幅直方图映射表
    # 映射表 shape: (gz, gy, gx, n_bins) -> 映射后的值
    lut = np.zeros((gz, gy, gx, n_bins), dtype=np.float32)

    for iz in range(gz):
        z0 = int(round(iz * bz))
        z1 = int(round((iz + 1) * bz))
        z1 = min(z1, nz)
        for iy in range(gy):
            y0 = int(round(iy * by))
            y1 = int(round((iy + 1) * by))
            y1 = min(y1, ny)
            for ix in range(gx):
                x0 = int(round(ix * bx))
                x1 = int(round((ix + 1) * bx))
                x1 = min(x1, nx)

                block = vol[z0:z1, y0:y1, x0:x1]
                lut[iz, iy, ix] = _clip_histogram_equalize(
                    block, n_bins, clip_limit,
                )

    # 三线性插值融合
    result = _interpolate_3d(vol, lut, gz, gy, gx, bz, by, bx, n_bins)

    if np.issubdtype(orig_dtype, np.integer):
        max_val = np.iinfo(orig_dtype).max
        return np.clip(np.round(result), 0, max_val).astype(orig_dtype)
    return result.astype(orig_dtype)


def _clip_histogram_equalize(
    block: np.ndarray,
    n_bins: int,
    clip_limit: float,
) -> np.ndarray:
    """
    对一个块计算限幅均衡化的查找表 (LUT).

    Returns
    -------
    np.ndarray (n_bins,) - 输入灰度 → 均衡化后灰度的映射
    """
    n_pixels = block.size
    if n_pixels == 0:
        return np.arange(n_bins, dtype=np.float32)

    # 直方图
    hist, _ = np.histogram(block.ravel(), bins=n_bins, range=(0, 255))
    hist = hist.astype(np.float64)

    # 限幅: 超出部分均匀重新分配
    if clip_limit > 0:
        limit = max(1, int(clip_limit * n_pixels / n_bins))
        excess = 0
        for i in range(n_bins):
            if hist[i] > limit:
                excess += hist[i] - limit
                hist[i] = limit
        # 均匀分配
        per_bin = excess / n_bins
        hist += per_bin

    # 累积分布函数
    cdf = hist.cumsum()
    cdf_min = cdf[cdf > 0].min() if np.any(cdf > 0) else 0
    denom = max(n_pixels - cdf_min, 1)
    lut = (cdf - cdf_min) / denom * 255.0
    lut = np.clip(lut, 0, 255)

    return lut.astype(np.float32)


def _interpolate_3d(
    vol: np.ndarray,
    lut: np.ndarray,
    gz: int, gy: int, gx: int,
    bz: float, by: float, bx: float,
    n_bins: int,
) -> np.ndarray:
    """
    三线性插值融合各块的 LUT 映射.

    对每个体素, 根据其在网格中的位置找到周围 8 个块的 LUT,
    按距离做三线性插值, 消除块边界突变.
    """
    nz, ny, nx = vol.shape
    result = np.empty_like(vol, dtype=np.float32)

    # 预计算每个体素在网格中的坐标
    z_coords = np.arange(nz, dtype=np.float64)
    y_coords = np.arange(ny, dtype=np.float64)
    x_coords = np.arange(nx, dtype=np.float64)

    # 网格坐标 (浮点), 块中心位置
    gz_pos = z_coords / bz - 0.5
    gy_pos = y_coords / by - 0.5
    gx_pos = x_coords / bx - 0.5

    gz_floor = np.clip(np.floor(gz_pos).astype(int), 0, gz - 1)
    gy_floor = np.clip(np.floor(gy_pos).astype(int), 0, gy - 1)
    gx_floor = np.clip(np.floor(gx_pos).astype(int), 0, gx - 1)

    gz_ceil = np.clip(gz_floor + 1, 0, gz - 1)
    gy_ceil = np.clip(gy_floor + 1, 0, gy - 1)
    gx_ceil = np.clip(gx_floor + 1, 0, gx - 1)

    # 插值权重
    wz = np.clip(gz_pos - gz_floor, 0, 1).astype(np.float32)
    wy = np.clip(gy_pos - gy_floor, 0, 1).astype(np.float32)
    wx = np.clip(gx_pos - gx_floor, 0, 1).astype(np.float32)

    # 逐切片处理 (避免全量 8 份 LUT 占用过多内存)
    for z_idx in range(nz):
        iz0, iz1 = gz_floor[z_idx], gz_ceil[z_idx]
        az = wz[z_idx]

        slice_data = vol[z_idx]  # (Y, X)
        # 量化到 bin 索引
        bins = np.clip(slice_data.astype(int), 0, n_bins - 1)

        out_slice = np.zeros_like(slice_data, dtype=np.float32)

        for iy_idx in range(ny):
            jy0, jy1 = gy_floor[iy_idx], gy_ceil[iy_idx]
            ay = wy[iy_idx]

            row_bins = bins[iy_idx]  # (X,)
            kx0 = gx_floor  # (X,)
            kx1 = gx_ceil   # (X,)
            ax = wx           # (X,)

            # 8 个角的 LUT 查表
            v000 = lut[iz0, jy0, kx0, row_bins]
            v001 = lut[iz0, jy0, kx1, row_bins]
            v010 = lut[iz0, jy1, kx0, row_bins]
            v011 = lut[iz0, jy1, kx1, row_bins]
            v100 = lut[iz1, jy0, kx0, row_bins]
            v101 = lut[iz1, jy0, kx1, row_bins]
            v110 = lut[iz1, jy1, kx0, row_bins]
            v111 = lut[iz1, jy1, kx1, row_bins]

            # 三线性插值
            c00 = v000 * (1 - ax) + v001 * ax
            c01 = v010 * (1 - ax) + v011 * ax
            c10 = v100 * (1 - ax) + v101 * ax
            c11 = v110 * (1 - ax) + v111 * ax

            c0 = c00 * (1 - ay) + c01 * ay
            c1 = c10 * (1 - ay) + c11 * ay

            out_slice[iy_idx] = c0 * (1 - az) + c1 * az

        result[z_idx] = out_slice

    return result
