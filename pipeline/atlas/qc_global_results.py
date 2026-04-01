"""全局配准质量评估: 可扩展 plugin 评分体系

每个 QC 维度注册为 (name, weight, checker_fn) 三元组。
checker_fn 签名: (data, mask, qc, global_dir) -> (ok: bool, score: float)
可通过 register_qc_checker() 新增自定义评分维度。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import numpy as np
import nibabel as nib

try:
    from scipy.ndimage import label as ndimage_label
except ImportError:          # pragma: no cover
    ndimage_label = None     # 退化：跳过最大连通域过滤

# ─────────────────────── 常量 & 权重 ──────────────────────────

QC_VERSION = "v0.2"

LEVEL_THRESHOLDS = {"excellent": 0.85, "good": 0.70, "review": 0.55}

# QC checker 类型: (data, mask, qc_dict, global_dir) -> (ok, score)
QcChecker = Callable[[np.ndarray | None, np.ndarray | None, dict, Path], tuple[bool, float]]

# 内部注册表: [(name, weight, checker_fn), ...]
_checkers: list[tuple[str, float, QcChecker]] = []


def register_qc_checker(name: str, weight: float, checker: QcChecker) -> None:
    """注册一个 QC 评分维度。可在模块外部调用以扩展评分体系。"""
    _checkers.append((name, weight, checker))


def list_qc_checkers() -> list[tuple[str, float]]:
    """列出当前所有已注册的 QC 维度及权重。"""
    return [(name, w) for name, w, _ in _checkers]


# ═══════════════════════ 主入口 ═══════════════════════════════

def run_global_qc(
    global_dir: Path,
    sample_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """对单个sample的registration/global/目录运行完整QC"""
    qc: dict[str, Any] = {"qc_version": QC_VERSION, "status": "running"}

    try:
        # ── 加载 global.nii.gz ───────────────────
        nii_path = global_dir / "global.nii.gz"
        data: np.ndarray | None = None
        mask: np.ndarray | None = None

        if nii_path.exists():
            data = nib.load(str(nii_path)).get_fdata(dtype=np.float32)
            # 预计算前景 mask (供多个 checker 复用)
            if data.size > 0:
                thresh = _otsu_threshold(data)
                mask = _largest_cc(data > thresh)

        # ── 执行所有已注册的 checker ─────────────
        subscores: dict[str, float] = {}
        total_weight = sum(w for _, w, _ in _checkers)
        if total_weight <= 0:
            total_weight = 1.0

        for name, weight, checker_fn in _checkers:
            try:
                ok, score = checker_fn(data, mask, qc, global_dir)
                qc[f"{name}_ok"] = ok
                subscores[name] = round(score, 4)
            except Exception as exc:
                qc[f"{name}_ok"] = False
                qc[f"{name}_error"] = str(exc)
                subscores[name] = 0.0

        # ── 综合评分 ─────────────────────────────
        weighted_score = sum(
            subscores.get(name, 0.0) * (w / total_weight)
            for name, w, _ in _checkers
        )
        score = round(weighted_score, 4)

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
            "subscores":           subscores,
            "score":               score,
            "qc_level":            level,
            "usable_for_template": usable,
            "status":              "completed",
        })

    except Exception as exc:
        qc["status"] = "error"
        qc["error"] = str(exc)
        if "subscores" not in qc:
            qc["subscores"] = {}
            qc["score"] = 0.0
            qc["qc_level"] = "reject"
            qc["usable_for_template"] = False

    # ── 初始化人工确认 ────────────────────────────
    qc.setdefault("manual_review", {
        "status": "pending",
        "comment": "",
        "updated_at": None,
    })
    return qc


# ═══════════════════ A: 文件完整性 ════════════════════════════

def _check_files(
    data: np.ndarray | None,
    mask: np.ndarray | None,
    qc: dict,
    global_dir: Path,
) -> tuple[bool, float]:
    d = global_dir
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
    qc["files_ok"] = critical
    return critical, round(score, 4)


# ═══════════════════ B: 图像统计 ══════════════════════════════

def _check_stats(
    data: np.ndarray | None,
    mask: np.ndarray | None,
    qc: dict,
    global_dir: Path,
) -> tuple[bool, float]:
    if data is None or data.size == 0:
        return False, 0.0
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


def _check_foreground(
    data: np.ndarray | None,
    mask: np.ndarray | None,
    qc: dict,
    global_dir: Path,
) -> tuple[bool, float]:
    if data is None or data.size == 0:
        qc["foreground_voxels"] = 0
        qc["foreground_ratio"] = 0.0
        return False, 0.0

    if mask is None:
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
    return ok, round(sc, 4)


# ═══════════════════ D: 边界裁剪 ══════════════════════════════

def _check_boundary(
    data: np.ndarray | None,
    mask: np.ndarray | None,
    qc: dict,
    global_dir: Path,
) -> tuple[bool, float]:
    if mask is None:
        qc["boundary_touch_ratio"] = {k: 0.0 for k in ("x0", "x1", "y0", "y1", "z0", "z1")}
        return True, 1.0
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

def _check_symmetry(
    data: np.ndarray | None,
    mask: np.ndarray | None,
    qc: dict,
    global_dir: Path,
) -> tuple[bool, float]:
    if data is None or data.size == 0:
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

def _check_sharpness(
    data: np.ndarray | None,
    mask: np.ndarray | None,
    qc: dict,
    global_dir: Path,
) -> tuple[bool, float]:
    if data is None or data.size < 1000:
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


# ═══════════════════ G: 地标重投影误差 ════════════════════════

def _parse_marker_file(path: Path) -> np.ndarray:
    """解析 Vaa3D .marker 文件，返回 (N, 3) 坐标数组。"""
    coords = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(",")
        if len(parts) >= 3:
            try:
                coords.append([float(parts[0]), float(parts[1]), float(parts[2])])
            except ValueError:
                continue
    return np.array(coords, dtype=np.float64) if coords else np.empty((0, 3), dtype=np.float64)


def _check_landmark_reprojection(
    data: np.ndarray | None,
    mask: np.ndarray | None,
    qc: dict,
    global_dir: Path,
) -> tuple[bool, float]:
    """计算 sub/tar marker 之间的平均欧氏距离作为配准质量指标。"""
    tar_files = sorted(global_dir.glob("*tar*.marker"))
    sub_files = sorted(global_dir.glob("*sub*.marker"))

    if not tar_files or not sub_files:
        qc["landmark_error"] = None
        qc["landmark_note"] = "marker files not found"
        return True, 0.5   # 无法判断，中性分

    tar_pts = _parse_marker_file(tar_files[0])
    sub_pts = _parse_marker_file(sub_files[0])

    n = min(len(tar_pts), len(sub_pts))
    if n == 0:
        qc["landmark_error"] = None
        qc["landmark_note"] = "no valid landmark coordinates"
        return True, 0.5

    dists = np.linalg.norm(tar_pts[:n] - sub_pts[:n], axis=1)
    mean_err = float(np.mean(dists))
    max_err = float(np.max(dists))

    qc["landmark_mean_error"] = round(mean_err, 4)
    qc["landmark_max_error"] = round(max_err, 4)
    qc["landmark_count"] = n

    # 分数映射: 误差越小越好 (单位: 体素)
    if mean_err < 3.0:
        sc = 1.0
    elif mean_err < 8.0:
        sc = 0.8
    elif mean_err < 15.0:
        sc = 0.5
    elif mean_err < 30.0:
        sc = 0.3
    else:
        sc = 0.1

    return mean_err < 15.0, round(sc, 4)


# ═══════════════════ 注册所有内置 checker ═════════════════════

register_qc_checker("files",    0.15, _check_files)
register_qc_checker("stats",    0.10, _check_stats)
register_qc_checker("volume",   0.15, _check_foreground)
register_qc_checker("boundary", 0.15, _check_boundary)
register_qc_checker("symmetry", 0.15, _check_symmetry)
register_qc_checker("sharpness",0.15, _check_sharpness)
register_qc_checker("landmark", 0.15, _check_landmark_reprojection)
