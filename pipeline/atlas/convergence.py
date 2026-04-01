"""
收敛判断: 基于平均形变场模长 (Magnitude of Average Deformation Field)

在第 k 轮迭代中, 将 N 个样本配准到当前模板 T_k, 得到一组形变场.
平均形变场:
    ϕ̄_k(x) = (1/N) Σ_{i=1}^{N} ϕ_i(x)

在标记点框架下, 对每个特征点 j:
    ϕ̄(x_j) = sub_avg_j − tar_ref_j
    (平均 subject 标记点 − 模板参考点)

收敛指标 (平均形变位移模长):
    δ_k = (1/M) Σ_{j=1}^{M} ‖ϕ̄_k(x_j)‖₂

当 δ_k < ε 时模板已收敛至样本群体几何中心.
"""
from __future__ import annotations

import math

import numpy as np


# ── 默认收敛阈值 (体素) ──────────────────────────────
DEFAULT_THRESHOLD: float = 0.01


def compute_deformation_field_delta(
    sub_avg: np.ndarray,
    tar_ref: np.ndarray,
) -> float:
    """
    计算平均形变场模长 δ_k.

    δ_k = (1/M) Σ_{j=1}^{M} ‖sub_avg_j − tar_ref_j‖₂

    Parameters
    ----------
    sub_avg : (M, 3) 所有样本 subject 标记点的算术平均
    tar_ref : (M, 3) 当前模板的参考特征点 (Harris 检测点)

    Returns
    -------
    float  平均形变位移模长 (单位: 体素)
    """
    sub_avg = np.asarray(sub_avg, dtype=np.float64)
    tar_ref = np.asarray(tar_ref, dtype=np.float64)

    if sub_avg.shape != tar_ref.shape:
        raise ValueError(
            f"形状不匹配: sub_avg {sub_avg.shape} vs tar_ref {tar_ref.shape}"
        )
    m = len(sub_avg)
    if m == 0:
        return float("inf")

    displacements = sub_avg - tar_ref          # (M, 3)
    magnitudes = np.linalg.norm(displacements, axis=1)  # (M,) 欧几里得范数
    return float(np.mean(magnitudes))


def is_converged(delta: float, threshold: float = DEFAULT_THRESHOLD) -> bool:
    """当 δ_k < ε 时判定为收敛."""
    return delta < threshold


# ── 向后兼容: 保留旧接口供外部脚本调用 ──────────────
def compute_convergence_delta(
    sub_avg_current: np.ndarray,
    sub_avg_previous: np.ndarray,
) -> float:
    """[兼容] 旧版两轮间标记点漂移量 (已弃用, 请使用 compute_deformation_field_delta)"""
    diff = sub_avg_current - sub_avg_previous
    l2_norm = float(np.linalg.norm(diff))
    n_points = len(sub_avg_current)
    return l2_norm / math.sqrt(n_points) if n_points > 0 else float("inf")
