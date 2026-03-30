"""收敛判断: delta = ||sub_avg_k - sub_avg_{k-1}||₂ / sqrt(n_points)"""
from __future__ import annotations

import math

import numpy as np


def compute_convergence_delta(
    sub_avg_current: np.ndarray,
    sub_avg_previous: np.ndarray,
) -> float:
    """计算两轮之间的收敛指标"""
    diff = sub_avg_current - sub_avg_previous
    l2_norm = float(np.linalg.norm(diff))
    n_points = len(sub_avg_current)
    return l2_norm / math.sqrt(n_points) if n_points > 0 else float("inf")


def is_converged(delta: float, threshold: float = 0.5) -> bool:
    """检查是否收敛。"""
    return delta < threshold
