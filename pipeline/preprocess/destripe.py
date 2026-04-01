"""
去条纹模块: 对数空间频域陷波滤波

fMOST 图像中经常出现由刀切痕迹和荧光漂白等因素引起的条纹噪声,
若不加处理会在频域上引入明显的周期性伪影, 严重干扰图像纹理与配准精度.

本模块将条纹伪影建模为乘法周期性噪声, 设计对数空间下的频率陷波
滤波器以实现高质量去条纹. 具体步骤:

  1) 提取一个包含最大前景脑区的二维冠状切片, 执行 FFT 获取频域谱图
  2) 根据频谱确定条纹噪声对应的频率分布, 构造高斯型陷波滤波器
  3) 对全脑图像执行对数变换, 将乘法噪声转化为加法噪声
  4) 逐片 (沿冠状面) 变换到频域, 应用高斯陷波滤波器
  5) 逆 FFT + 反对数变换, 还原至原始强度空间
"""
from __future__ import annotations

from typing import Any

import numpy as np


def destripe(
    volume: np.ndarray,
    orientation: str = "coronal",
    bandwidth: float = 2.0,
    notch_freq: float | None = None,
    threshold_ratio: float = 5.0,
    log_offset: float = 1.0,
) -> np.ndarray:
    """
    对数空间频域陷波去条纹.

    Parameters
    ----------
    volume : (Z, Y, X) uint8/uint16/float32
        输入三维图像.
    orientation : "coronal" | "sagittal" | "axial"
        条纹所在平面的方向. fMOST 刀切条纹通常出现在冠状面(coronal).
        "coronal"  - 沿 Z 轴逐片处理 (每片 = Y×X)
        "sagittal" - 沿 X 轴逐片处理
        "axial"    - 沿 Y 轴逐片处理
    bandwidth : float
        陷波滤波器的高斯带宽 (像素频率单位), 控制滤除范围宽度.
    notch_freq : float | None
        手动指定条纹频率 (归一化, 0~0.5). 为 None 时自动检测.
    threshold_ratio : float
        自动检测时, 频谱峰值 / 中位数 > 此比值则判定为条纹频率.
    log_offset : float
        对数变换偏移量 log(I + offset), 防止 log(0).

    Returns
    -------
    np.ndarray  去条纹后的图像, dtype 与输入一致.
    """
    orig_dtype = volume.dtype
    vol = volume.astype(np.float64)

    # ── Step 1: 检测条纹频率 ──────────────────────────
    if notch_freq is None:
        ref_slice = _select_reference_slice(vol, orientation)
        notch_freq = _detect_stripe_frequency(ref_slice, threshold_ratio)

    if notch_freq is None or notch_freq <= 0:
        # 未检测到明显条纹, 直接返回
        return volume

    # ── Step 2: 构造陷波滤波器 ────────────────────────
    # 滤波器在逐片处理时根据切片尺寸动态构造

    # ── Step 3~5: 对数空间 → 频域滤波 → 反变换 ──────
    result = _apply_notch_filter_3d(
        vol, orientation, notch_freq, bandwidth, log_offset,
    )

    if np.issubdtype(orig_dtype, np.integer):
        max_val = np.iinfo(orig_dtype).max
        return np.clip(np.round(result), 0, max_val).astype(orig_dtype)
    return result.astype(orig_dtype)


# ---------------------------------------------------------------------------
#  参考切片选择
# ---------------------------------------------------------------------------

def _select_reference_slice(
    vol: np.ndarray,
    orientation: str,
) -> np.ndarray:
    """选取前景面积最大的二维切片作为频谱分析参考."""
    if orientation == "coronal":
        axis = 0  # 沿 Z
    elif orientation == "axial":
        axis = 1  # 沿 Y
    elif orientation == "sagittal":
        axis = 2  # 沿 X
    else:
        axis = 0

    n_slices = vol.shape[axis]

    # 采样检查 (避免遍历全部切片)
    step = max(n_slices // 20, 1)
    best_idx = 0
    best_fg = 0

    for i in range(0, n_slices, step):
        slc = _get_slice(vol, axis, i)
        fg_count = int(np.count_nonzero(slc > 0))
        if fg_count > best_fg:
            best_fg = fg_count
            best_idx = i

    # 在最佳位置附近精搜
    lo = max(0, best_idx - step)
    hi = min(n_slices, best_idx + step + 1)
    for i in range(lo, hi):
        slc = _get_slice(vol, axis, i)
        fg_count = int(np.count_nonzero(slc > 0))
        if fg_count > best_fg:
            best_fg = fg_count
            best_idx = i

    return _get_slice(vol, axis, best_idx)


def _get_slice(vol: np.ndarray, axis: int, idx: int) -> np.ndarray:
    if axis == 0:
        return vol[idx, :, :]
    elif axis == 1:
        return vol[:, idx, :]
    else:
        return vol[:, :, idx]


# ---------------------------------------------------------------------------
#  条纹频率自动检测
# ---------------------------------------------------------------------------

def _detect_stripe_frequency(
    ref_slice: np.ndarray,
    threshold_ratio: float,
) -> float | None:
    """
    分析参考切片的频谱, 检测条纹对应的周期性峰.

    条纹通常沿一个方向呈周期性, 在该方向的频谱上表现为
    DC 分量以外的离散峰值.

    Returns
    -------
    float | None  归一化条纹频率 (0~0.5), 未检测到返回 None.
    """
    h, w = ref_slice.shape
    if h < 8 or w < 8:
        return None

    # 对参考切片做 2D FFT
    f = np.fft.fft2(ref_slice)
    f_shift = np.fft.fftshift(f)
    magnitude = np.abs(f_shift)

    # 分析垂直方向频谱 (条纹通常水平 → 垂直频率有峰)
    cy, cx = h // 2, w // 2
    # 取中心列的垂直剖面 (排除 DC 附近)
    vert_profile = magnitude[:, cx]
    dc_margin = max(h // 20, 3)

    # 上半部分 (正频率)
    upper = vert_profile[dc_margin:cy]
    if len(upper) < 4:
        return None

    median_val = np.median(upper)
    if median_val <= 0:
        return None

    # 找最大峰
    peak_idx = np.argmax(upper)
    peak_val = upper[peak_idx]

    if peak_val / median_val > threshold_ratio:
        # 归一化频率
        freq = (peak_idx + dc_margin) / h
        return float(freq)

    return None


# ---------------------------------------------------------------------------
#  高斯陷波滤波器构造
# ---------------------------------------------------------------------------

def _build_notch_filter_2d(
    height: int,
    width: int,
    notch_freq: float,
    bandwidth: float,
) -> np.ndarray:
    """
    构造二维高斯型陷波滤波器 (对称).

    在 notch_freq 及其共轭位置放置高斯凹陷:
        H(u,v) = 1 - G(u - u0) - G(u + u0)
    其中 G 为高斯函数, u0 为陷波中心频率.
    """
    rows = np.arange(height, dtype=np.float64)
    cols = np.arange(width, dtype=np.float64)

    # 频率坐标 (中心化)
    cy, cx = height / 2.0, width / 2.0
    u = rows - cy
    v = cols - cx
    U, V = np.meshgrid(u, v, indexing="ij")

    # 陷波中心位置 (像素频率)
    u0 = notch_freq * height

    # 正频率陷波
    d1_sq = (U - u0) ** 2 + V ** 2
    # 负频率陷波 (共轭对称)
    d2_sq = (U + u0) ** 2 + V ** 2

    sigma_sq = bandwidth ** 2
    h_notch = 1.0 - np.exp(-d1_sq / (2 * sigma_sq)) - np.exp(-d2_sq / (2 * sigma_sq))
    h_notch = np.clip(h_notch, 0.0, 1.0)

    return h_notch


# ---------------------------------------------------------------------------
#  3D 逐片频域滤波 (对数空间)
# ---------------------------------------------------------------------------

def _apply_notch_filter_3d(
    vol: np.ndarray,
    orientation: str,
    notch_freq: float,
    bandwidth: float,
    log_offset: float,
) -> np.ndarray:
    """
    在对数空间逐片应用陷波滤波.

    Step 3: log(I + offset)   → 乘法噪声转加法
    Step 4: FFT → 陷波滤波
    Step 5: iFFT → exp() - offset  → 还原
    """
    result = vol.copy()

    if orientation == "coronal":
        axis = 0
    elif orientation == "axial":
        axis = 1
    elif orientation == "sagittal":
        axis = 2
    else:
        axis = 0

    n_slices = vol.shape[axis]

    # 预构造滤波器 (所有同方向切片尺寸相同)
    if axis == 0:
        h, w = vol.shape[1], vol.shape[2]
    elif axis == 1:
        h, w = vol.shape[0], vol.shape[2]
    else:
        h, w = vol.shape[0], vol.shape[1]

    notch_filter = _build_notch_filter_2d(h, w, notch_freq, bandwidth)

    for i in range(n_slices):
        slc = _get_slice(vol, axis, i).copy()

        # Step 3: 对数变换
        slc_log = np.log(slc + log_offset)

        # Step 4: FFT + 陷波滤波
        f = np.fft.fft2(slc_log)
        f_shift = np.fft.fftshift(f)
        f_filtered = f_shift * notch_filter
        f_ishift = np.fft.ifftshift(f_filtered)

        # Step 5: iFFT + 反对数变换
        slc_filtered = np.real(np.fft.ifft2(f_ishift))
        slc_restored = np.exp(slc_filtered) - log_offset
        slc_restored = np.maximum(slc_restored, 0.0)

        # 写回
        if axis == 0:
            result[i, :, :] = slc_restored
        elif axis == 1:
            result[:, i, :] = slc_restored
        else:
            result[:, :, i] = slc_restored

    return result
