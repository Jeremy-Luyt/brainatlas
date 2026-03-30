"""写出 Vaa3D .v3draw 格式文件"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

VAA3D_MAGIC = b"raw_image_stack_by_hpeng"


def _dtype_to_code(dt: np.dtype) -> int:
    if dt == np.uint8:
        return 1
    if dt == np.uint16:
        return 2
    if dt == np.float32:
        return 4
    raise ValueError(f"Unsupported dtype for v3draw: {dt}")


def write_v3draw(volume: np.ndarray, path: str | Path) -> None:
    """将numpy数组写为v3draw格式, 支持3D(Z,Y,X)或4D(C,Z,Y,X)"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if volume.ndim == 3:
        c, z, y, x = 1, volume.shape[0], volume.shape[1], volume.shape[2]
        data = volume.reshape((1, z, y, x))
    elif volume.ndim == 4:
        c, z, y, x = volume.shape
        data = volume
    else:
        raise ValueError(f"Expected 3D or 4D array, got shape {volume.shape}")

    dtype_code = _dtype_to_code(data.dtype)

    with open(path, "wb") as f:
        f.write(VAA3D_MAGIC)
        f.write(b"L")  # little endian
        f.write(struct.pack("<H", dtype_code))
        f.write(struct.pack("<I", x))
        f.write(struct.pack("<I", y))
        f.write(struct.pack("<I", z))
        f.write(struct.pack("<I", c))
        # 写入数据: Vaa3D 期望 (C, Z, Y, X) 排列
        f.write(data.tobytes())
