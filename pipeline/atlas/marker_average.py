"""标记点解析、写出与平均"""
from __future__ import annotations

from pathlib import Path

import numpy as np


def parse_marker(path: str | Path) -> np.ndarray:
    """
    解析 Vaa3D .marker 文件，返回 (N, 3) float 数组 [x, y, z]。
    跳过 # 开头的注释行。
    """
    path = Path(path)
    points = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(",")
        if len(parts) < 3:
            continue
        try:
            x, y, z = float(parts[0]), float(parts[1]), float(parts[2])
            points.append([x, y, z])
        except ValueError:
            continue
    return np.array(points, dtype=np.float64)


def write_marker(points: np.ndarray, path: str | Path) -> None:
    """
    将 (N, 3) 坐标数组写为 Vaa3D .marker 格式。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["##x,y,z,radius,shape,name,comment, color_r,color_g,color_b"]
    for row in points:
        x, y, z = row[0], row[1], row[2]
        lines.append(f"{x:.3f}, {y:.3f}, {z:.3f}, 0, 1, , , 255,0,0")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def average_markers(marker_paths: list[str | Path]) -> np.ndarray:
    """
    按索引平均多组标记点。

    所有 marker 文件必须包含相同数量的点（由局部配准保证）。
    返回 (N, 3) 平均坐标。
    """
    if not marker_paths:
        raise ValueError("Empty marker path list")

    all_pts = []
    n_expected = None
    for mp in marker_paths:
        pts = parse_marker(mp)
        if n_expected is None:
            n_expected = len(pts)
        elif len(pts) != n_expected:
            raise ValueError(
                f"Marker point count mismatch: expected {n_expected}, "
                f"got {len(pts)} in {mp}"
            )
        all_pts.append(pts)

    stacked = np.stack(all_pts, axis=0)  # (M, N, 3)
    return stacked.mean(axis=0)  # (N, 3)
