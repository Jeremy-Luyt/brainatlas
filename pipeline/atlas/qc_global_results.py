"""
qc_global_results.py — Global 配准质量评估算法

对 global registration 输出进行多维度 QC：
  A. 文件完整性   B. 图像统计    C. 前景体积与占比
  D. 边界裁剪     E. 对称性      F. 清晰度 / 结构信息
  G. 综合评分

设计原则：
  - 仅使用 numpy / nibabel / scipy（轻量经典方法）
  - 所有指标可解释、可审计
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import nibabel as nib

try:
    from scipy.ndimage import label as ndimage_label
except ImportError:          # pragma: no cover
    ndimage_label = None     # 退化：跳过最大连通域过滤

# ─────────────────────── 常量 & 权重 ──────────────────────────

QC_VERSION = "v0.1"

WEIGHTS: dict[str, float] = {
    "files":     0.20,
    "stats":     0.15,
    "volume":    0.20,
    "boundary":  0.15,
    "symmetry":  0.15,
    "sharpness": 0.15,
}

LEVEL_THRESHOLDS = {"excellent": 0.85, "good": 0.70, "review": 0.55}


# ═══════════════════════ 主入口 ═══════════════════════════════

def run_global_qc(
    global_dir: Path,
    sample_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    对单个 sample 的 ``registration/global`` 目录运行完整 QC.

    Parameters
    ----------
    global_dir : Path
        ``<sample>/registration/global/`` 目录
    sample_meta : dict, optional
        sample.json 内容（可选，用于交叉验证）

    Returns
    -------
    dict  ─ 完整 global_qc 结构，可直接写入 sample.json
    """
    qc: dict[str, Any] = {"qc_version": QC_VERSION, "status": "running"}

    try:
        # ── A. 文件完整性 ────────────────────────
        files_ok, files_score = _check_files(global_dir)
        qc["files_ok"] = files_ok

        # ── 加载 global.nii.gz ───────────────────
        nii_path = global_dir / "global.nii.gz"
        if not nii_path.exists():
            _fill_empty_image(qc)
            qc["files_ok"] = False
            _finalize(qc, files_score)
            return qc

        data: np.ndarray = nib.load(str(nii_path)).get_fdata(dtype=np.float32)

        # ── B. 图像统计 ─────────────────────────
        stats_ok, stats_score = _check_stats(data, qc)

        # ── C. 前景体积 ─────────────────────────
        volume_ok, volume_score, mask = _check_foreground(data, qc)

        # ── D. 边界裁剪 ─────────────────────────
        boundary_ok, boundary_score = _check_boundary(mask, qc)

        # ── E. 对称性 ───────────────────────────
        symmetry_ok, symmetry_score = _check_symmetry(data, qc)

        # ── F. 清晰度 ───────────────────────────
        sharpness_ok, sharpness_score = _check_sharpness(data, qc)

        qc.update({
            "stats_ok":     stats_ok,
            "volume_ok":    volume_ok,
            "boundary_ok":  boundary_ok,
            "symmetry_ok":  symmetry_ok,
            "sharpness_ok": sharpness_ok,
        })

        # ── G. 综合评分 ─────────────────────────
        _finalize(qc, files_score, stats_score, volume_score,
                  boundary_score, symmetry_score, sharpness_score)

    except Exception as exc:
        qc["status"] = "error"
        qc["error"] = str(exc)
        if "subscores" not in qc:
            _fill_empty_image(qc)
            _finalize(qc, 0.0)

    # ── H. 初始化人工确认 ────────────────────────
    qc.setdefault("manual_review", {
        "status": "pending",
        "comment": "",
        "updated_at": None,
    })
    return qc


# ═══════════════════ A: 文件完整性 ════════════════════════════

def _check_files(d: Path) -> tuple[bool, float]:
    checks = [
        (d / "global.v3draw").exists(),
        (d / "global.nii.gz").exists(),
        bool(list(d.glob("*tar*.marker"))),
        bool(list(d.glob("*sub*.marker"))),
        (d / "previews").exists() and bool(list((d / "previews").glob("*.png"))),
        (d / "global_registration.log").exists() or bool(list(d.glob("*.json"))),
    ]
    critical = checks[0] and checks[1]
    score = sum(checks) / len(checks)
    return critical, round(score, 4)


# ═══════════════════ B: 图像统计 ══════════════════════════════

def _check_stats(data: np.ndarray, qc: dict) -> tuple[bool, float]:
    mn = float(np.min(data))
    mx = float(np.max(data))
    mean = float(np.mean(data))
    std = float(np.std(data))

    is_empty = data.size == 0 or (mx - mn < 1e-8 and mx < 1e-8)
    rng = mx - mn if mx > mn else 1.0
    is_nearly_black = (not is_empty) and (mean < 0.005 * rng)
    is_nearly_white = (not is_empty) and (mx > 0) and (mean > 0.99 * mx)

    qc.update({
        "shape": list(data.shape),
        "dtype": str(data.dtype),
        "min": round(mn, 4),
        "max": round(mx, 4),
        "mean": round(mean, 4),
    })

    ok = not is_empty and not is_nearly_black and not is_nearly_white
    if is_empty:
        score = 0.0
    elif is_nearly_black:
        score = 0.1
    elif is_nearly_white:
        score = 0.3
    elif std < 1e-3:
        score = 0.2
    else:
        score = 1.0
    return ok, round(score, 4)


# ═══════════════════ C: 前景体积 ══════════════════════════════

def _otsu_threshold(data: np.ndarray, n_bins: int = 256) -> float:
    """向量化 Otsu 阈值。"""
    flat = data.ravel().astype(np.float64)
    mn, mx = float(flat.min()), float(flat.max())
    if mx - mn < 1e-8:
        return mn

    hist, edges = np.histogram(flat, bins=n_bins, range=(mn, mx))
    centers = (edges[:-1] + edges[1:]) / 2.0
    total = float(hist.sum())
    total_mean = float(np.dot(hist, centers))

    cum_w = np.cumsum(hist).astype(np.float64)
    cum_m = np.cumsum(hist * centers)
    w_fg = total - cum_w
    valid = (cum_w > 0) & (w_fg > 0)

    m_bg = np.where(valid, cum_m / cum_w, 0.0)
    m_fg = np.where(valid, (total_mean - cum_m) / w_fg, 0.0)
    var_b = np.where(valid, cum_w * w_fg * (m_bg - m_fg) ** 2, 0.0)
    return float(centers[int(np.argmax(var_b))])


def _largest_cc(mask: np.ndarray) -> np.ndarray:
    if ndimage_label is None:
        return mask
    labeled, n = ndimage_label(mask)
    if n == 0:
        return mask
    sizes = np.bincount(labeled.ravel())
    sizes[0] = 0
    return (labeled == int(np.argmax(sizes)))


def _check_foreground(data: np.ndarray, qc: dict) -> tuple[bool, float, np.ndarray]:
    thresh = _otsu_threshold(data)
    mask = _largest_cc(data > thresh)

    total = int(data.size)
    fg = int(mask.sum())
    ratio = fg / total if total > 0 else 0.0

    qc["foreground_voxels"] = fg
    qc["foreground_ratio"] = round(ratio, 6)

    ok = 0.02 <= ratio <= 0.70
    if ratio < 0.01:
        sc = 0.0
    elif ratio < 0.05:
        sc = 0.3
    elif ratio <= 0.60:
        sc = 1.0
    elif ratio <= 0.70:
        sc = 0.7
    else:
        sc = 0.3
    return ok, round(sc, 4), mask


# ═══════════════════ D: 边界裁剪 ══════════════════════════════

def _check_boundary(mask: np.ndarray, qc: dict) -> tuple[bool, float]:
    fg = int(mask.sum())
    if fg == 0:
        touch = {k: 0.0 for k in ("x0", "x1", "y0", "y1", "z0", "z1")}
        qc["boundary_touch_ratio"] = touch
        return True, 1.0

    touch = {
        "x0": float(mask[0, :, :].sum()) / fg,
        "x1": float(mask[-1, :, :].sum()) / fg,
        "y0": float(mask[:, 0, :].sum()) / fg,
        "y1": float(mask[:, -1, :].sum()) / fg,
        "z0": float(mask[:, :, 0].sum()) / fg,
        "z1": float(mask[:, :, -1].sum()) / fg,
    }
    touch = {k: round(v, 6) for k, v in touch.items()}
    qc["boundary_touch_ratio"] = touch

    mx = max(touch.values())
    ok = mx < 0.05
    if mx < 0.02:
        sc = 1.0
    elif mx < 0.05:
        sc = 0.85
    elif mx < 0.10:
        sc = 0.6
    elif mx < 0.20:
        sc = 0.3
    else:
        sc = 0.1
    return ok, round(sc, 4)


# ═══════════════════ E: 对称性 ════════════════════════════════

def _check_symmetry(data: np.ndarray, qc: dict) -> tuple[bool, float]:
    if data.size == 0:
        qc["symmetry_score"] = 0.0
        return False, 0.0

    # 降采样（每 2 取 1）以加速
    ds = data[::2, ::2, ::2].astype(np.float64)
    flipped = np.flip(ds, axis=0)  # X 轴翻转 (左右对称)

    a = ds.ravel()
    b = flipped.ravel()
    a_c = a - a.mean()
    b_c = b - b.mean()
    denom = float(np.sqrt(np.dot(a_c, a_c) * np.dot(b_c, b_c)))
    corr = max(0.0, float(np.dot(a_c, b_c)) / denom) if denom > 1e-8 else 0.0

    qc["symmetry_score"] = round(corr, 4)
    return corr > 0.5, round(corr, 4)


# ═══════════════════ F: 清晰度 ════════════════════════════════

def _check_sharpness(data: np.ndarray, qc: dict) -> tuple[bool, float]:
    if data.size < 1000:
        qc["sharpness_score"] = 0.0
        return False, 0.0

    # 中心 1/3 裁切
    slices = tuple(slice(d // 3, 2 * d // 3) for d in data.shape)
    center = data[slices].astype(np.float64)

    # 3D Laplacian 方差
    lap = np.zeros_like(center)
    lap[1:-1] += center[2:]  + center[:-2]  - 2 * center[1:-1]
    lap[:, 1:-1] += center[:, 2:]  + center[:, :-2]  - 2 * center[:, 1:-1]
    lap[:, :, 1:-1] += center[:, :, 2:] + center[:, :, :-2] - 2 * center[:, :, 1:-1]

    lap_var = float(np.var(lap))
    i_range = float(data.max() - data.min())
    if i_range < 1e-8:
        qc["sharpness_score"] = 0.0
        return False, 0.0

    normalized = lap_var / (i_range ** 2)
    score = round(min(1.0, max(0.0, normalized / 0.05)), 4)

    qc["sharpness_score"] = score
    return score > 0.3, score


# ═══════════════════ G: 综合评分 ══════════════════════════════

def _finalize(
    qc: dict,
    files_s: float = 0.0,
    stats_s: float = 0.0,
    volume_s: float = 0.0,
    boundary_s: float = 0.0,
    symmetry_s: float = 0.0,
    sharpness_s: float = 0.0,
) -> None:
    subs = {
        "files":     files_s,
        "stats":     stats_s,
        "volume":    volume_s,
        "boundary":  boundary_s,
        "symmetry":  symmetry_s,
        "sharpness": sharpness_s,
    }
    score = round(sum(subs[k] * WEIGHTS[k] for k in WEIGHTS), 4)

    if score >= LEVEL_THRESHOLDS["excellent"]:
        level = "excellent"
    elif score >= LEVEL_THRESHOLDS["good"]:
        level = "good"
    elif score >= LEVEL_THRESHOLDS["review"]:
        level = "review"
    else:
        level = "reject"

    files_ok = qc.get("files_ok", False)
    fg_ratio = qc.get("foreground_ratio", 0.0)
    usable = files_ok and (0.02 <= fg_ratio <= 0.70) and score >= 0.55

    qc.update({
        "subscores":           subs,
        "score":               score,
        "qc_level":            level,
        "usable_for_template": usable,
        "status":              "completed",
    })


# ──────── 辅助：nii.gz 缺失时填充空结果 ────────

def _fill_empty_image(qc: dict) -> None:
    qc.update({
        "shape": [], "dtype": "", "min": 0.0, "max": 0.0, "mean": 0.0,
        "stats_ok": False, "volume_ok": False, "boundary_ok": False,
        "symmetry_ok": False, "sharpness_ok": False,
        "foreground_voxels": 0, "foreground_ratio": 0.0,
        "boundary_touch_ratio": {k: 0.0 for k in ("x0", "x1", "y0", "y1", "z0", "z1")},
        "symmetry_score": 0.0, "sharpness_score": 0.0,
    })
