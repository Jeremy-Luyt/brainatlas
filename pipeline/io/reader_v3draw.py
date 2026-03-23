from __future__ import annotations

from pathlib import Path
import struct
from typing import Any

import numpy as np


VAA3D_MAGIC = b"raw_image_stack_by_hpeng"


def _read_exact(f, n: int) -> bytes:
    data = f.read(n)
    if len(data) != n:
        raise ValueError(f"读取失败：期望 {n} 字节，实际只读到 {len(data)} 字节")
    return data


def _dtype_from_code(code: int, endian: str) -> np.dtype:
    """
    Vaa3D / v3draw 常见数据类型编码：
    1 -> uint8
    2 -> uint16
    4 -> float32

    endian:
        '<' 小端
        '>' 大端
    """
    if code == 1:
        return np.dtype(np.uint8)
    if code == 2:
        return np.dtype(endian + "u2")
    if code == 4:
        return np.dtype(endian + "f4")
    raise ValueError(f"不支持的数据类型编码: {code}")


def _parse_header(path: str | Path) -> dict[str, Any]:
    path = Path(path)

    with path.open("rb") as f:
        # 1) 读 magic
        magic = _read_exact(f, len(VAA3D_MAGIC))

        if magic != VAA3D_MAGIC:
            raise ValueError(
                f"文件头 magic 不匹配，读取到的是 {magic!r}，不是标准 Vaa3D raw/v3draw"
            )

        # 2) 读 endian 标记：一般是 'L' 或 'B'
        endian_flag = _read_exact(f, 1)
        if endian_flag == b"L":
            endian = "<"
            endian_name = "little"
        elif endian_flag == b"B":
            endian = ">"
            endian_name = "big"
        else:
            raise ValueError(f"未知字节序标记: {endian_flag!r}")

        # 3) 读 datatype code（2 字节 unsigned short）
        dtype_code = struct.unpack(endian + "H", _read_exact(f, 2))[0]
        dtype = _dtype_from_code(dtype_code, endian)

        # 4) 读四个维度：X, Y, Z, C（每个 4 字节 unsigned int）
        x = struct.unpack(endian + "I", _read_exact(f, 4))[0]
        y = struct.unpack(endian + "I", _read_exact(f, 4))[0]
        z = struct.unpack(endian + "I", _read_exact(f, 4))[0]
        c = struct.unpack(endian + "I", _read_exact(f, 4))[0]

        data_offset = f.tell()

    file_size = path.stat().st_size
    expected_elems = x * y * z * c
    expected_bytes = expected_elems * dtype.itemsize
    actual_bytes = file_size - data_offset

    return {
        "magic": magic.decode("ascii", errors="replace"),
        "endian_flag": endian_flag.decode("ascii", errors="replace"),
        "endian": endian_name,
        "dtype_code": dtype_code,
        "dtype": str(dtype),
        "dtype_np": dtype,
        "width": x,
        "height": y,
        "depth": z,
        "channels": c,
        "shape_raw": (x, y, z, c),
        "data_offset": data_offset,
        "file_size": file_size,
        "expected_elems": expected_elems,
        "expected_bytes": expected_bytes,
        "actual_bytes": actual_bytes,
    }


def read_v3draw(path: str | Path) -> tuple[np.ndarray, dict[str, Any]]:
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    meta = _parse_header(path)

    if meta["expected_bytes"] != meta["actual_bytes"]:
        raise ValueError(
            "文件大小与 header 推断的数据区大小不一致："
            f" expected_bytes={meta['expected_bytes']}, "
            f" actual_bytes={meta['actual_bytes']}"
        )

    dtype: np.dtype = meta["dtype_np"]
    x = meta["width"]
    y = meta["height"]
    z = meta["depth"]
    c = meta["channels"]
    data_offset = meta["data_offset"]

    # 直接读取 payload
    data = np.fromfile(path, dtype=dtype, offset=data_offset)

    if data.size != x * y * z * c:
        raise ValueError(
            f"读取数据元素数量不对：expected={x*y*z*c}, actual={data.size}"
        )

    # Vaa3D 常见理解下，原始维度是 X, Y, Z, C
    # 先 reshape 成 (C, Z, Y, X)，方便后续 Python 图像处理
    volume = data.reshape((c, z, y, x))

    # 单通道时直接返回 (Z, Y, X)
    if c == 1:
        volume = volume[0]

    meta["shape_out"] = tuple(volume.shape)

    # 这几个统计量非常重要，用于验证“真的读进去了”
    meta["min"] = float(np.min(volume))
    meta["max"] = float(np.max(volume))
    meta["mean"] = float(np.mean(volume))

    # dtype_np 不能直接写 json，后面通常去掉
    return volume, meta
