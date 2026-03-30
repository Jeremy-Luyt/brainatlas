"""纯 Python 2.5D Harris角点检测, 输出Vaa3D .marker格式"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy import ndimage


def _harris_response_2d(img_slice: np.ndarray, sigma: float = 1.5, k: float = 0.04) -> np.ndarray:
    """计算单个 2D 切片的 Harris 角点响应。"""
    img = img_slice.astype(np.float64)
    Ix = ndimage.sobel(img, axis=1).astype(np.float64)
    Iy = ndimage.sobel(img, axis=0).astype(np.float64)

    Ixx = ndimage.gaussian_filter(Ix * Ix, sigma)
    Iyy = ndimage.gaussian_filter(Iy * Iy, sigma)
    Ixy = ndimage.gaussian_filter(Ix * Iy, sigma)

    det = Ixx * Iyy - Ixy * Ixy
    trace = Ixx + Iyy
    return det - k * trace * trace


def _harris_response_3d(volume: np.ndarray, sigma: float = 1.5) -> np.ndarray:
    """
    2.5D Harris: 逐 z-slice 计算 2D Harris 响应，
    再沿 z 轴做 Gaussian 平滑以融合相邻层信息。
    """
    z, y, x = volume.shape
    response = np.zeros_like(volume, dtype=np.float64)
    for zi in range(z):
        response[zi] = _harris_response_2d(volume[zi], sigma=sigma)
    # 沿 z 轴平滑以融合相邻层
    response = ndimage.gaussian_filter1d(response, sigma=max(sigma * 0.5, 0.5), axis=0)
    return response


def _nms_3d(response: np.ndarray, window_2d: int, window_3d: int,
            threshold_ratio: float = 0.01) -> list[tuple[int, int, int, float]]:
    """
    3D 非极大值抑制。
    返回 [(x, y, z, score), ...] 按 score 降序。
    """
    # 用 maximum_filter 做 3D NMS
    half_z = max(window_3d // 2, 1)
    half_xy = max(window_2d // 2, 1)
    footprint_size = (2 * half_z + 1, 2 * half_xy + 1, 2 * half_xy + 1)
    local_max = ndimage.maximum_filter(response, size=footprint_size)
    is_peak = (response == local_max)

    # 阈值: 只保留响应值大于最大响应的 threshold_ratio 的点
    threshold = response.max() * threshold_ratio
    is_peak &= (response > threshold)

    # 排除边界
    margin = max(half_xy, half_z)
    is_peak[:margin, :, :] = False
    is_peak[-margin:, :, :] = False
    is_peak[:, :margin, :] = False
    is_peak[:, -margin:, :] = False
    is_peak[:, :, :margin] = False
    is_peak[:, :, -margin:] = False

    coords = np.argwhere(is_peak)  # (N, 3) → (z, y, x)
    scores = response[is_peak]

    # 按 score 降序
    order = np.argsort(-scores)
    coords = coords[order]
    scores = scores[order]

    return [(int(c[2]), int(c[1]), int(c[0]), float(s))
            for c, s in zip(coords, scores)]


def _write_marker(points: list[tuple[int, int, int, float]], path: Path) -> None:
    """写出 Vaa3D .marker 格式 (1-indexed x, y, z)。"""
    lines = ["##x,y,z,radius,shape,name,comment, color_r,color_g,color_b"]
    for i, (x, y, z, score) in enumerate(points):
        # Vaa3D marker 是 1-indexed
        lines.append(f"{x+1},{y+1},{z+1},0,1,pt{i+1},{score:.2f},255,0,0")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_harris(
    input_image: str | Path,
    output_marker: str | Path,
    nms_2d: int = 15,
    nms_3d: int = 15,
    max_points: int = 200,
    timeout: int = 600,
) -> dict:
    """运行2.5D Harris角点检测"""
    from pipeline.io import read_v3draw

    input_image = Path(input_image)
    output_marker = Path(output_marker)

    if not input_image.exists():
        raise FileNotFoundError(f"Input image not found: {input_image}")

    output_marker.parent.mkdir(parents=True, exist_ok=True)

    log_path = output_marker.parent / "harris.log"
    log_lines: list[str] = []

    def _log(msg: str) -> None:
        log_lines.append(msg)

    _log(f"Input: {input_image}")
    _log(f"NMS 2D: {nms_2d}, 3D: {nms_3d}, max_points: {max_points}")

    # 读取图像
    volume, meta = read_v3draw(input_image)
    _log(f"Volume shape: {volume.shape}, dtype: {volume.dtype}")

    # 如果多通道只取第一通道
    if volume.ndim == 4:
        volume = volume[0]
    _log(f"Processing shape (Z,Y,X): {volume.shape}")

    # 下采样以加速 (如果体积很大)
    downsample = 1
    total_voxels = volume.shape[0] * volume.shape[1] * volume.shape[2]
    if total_voxels > 200_000_000:
        downsample = 2
        volume = volume[::2, ::2, ::2]
        _log(f"Downsampled 2x → {volume.shape}")

    # 计算 2.5D Harris 响应
    _log("Computing 2.5D Harris response...")
    response = _harris_response_3d(volume)
    _log(f"Response range: [{response.min():.2f}, {response.max():.2f}]")

    # 3D NMS
    _log("Running 3D NMS...")
    adjusted_2d = max(nms_2d // downsample, 3)
    adjusted_3d = max(nms_3d // downsample, 3)
    points = _nms_3d(response, adjusted_2d, adjusted_3d)
    _log(f"Detected {len(points)} corners before max_points filter")

    # 截取 max_points
    points = points[:max_points]

    # 恢复原始坐标 (如果有下采样)
    if downsample > 1:
        points = [(x * downsample, y * downsample, z * downsample, s)
                  for x, y, z, s in points]

    _log(f"Final: {len(points)} corners")

    # 写出 marker
    _write_marker(points, output_marker)
    _log(f"Written to: {output_marker}")

    # 写 log
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    return {
        "output_marker": str(output_marker),
        "log_path": str(log_path),
        "n_points": len(points),
        "return_code": 0,
        "status": "completed",
    }
