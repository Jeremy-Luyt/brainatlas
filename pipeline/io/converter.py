from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from pipeline.io.reader_v3draw import read_v3draw
from pipeline.io.nii_io import save_nifti


def _make_json_safe(meta: dict[str, Any]) -> dict[str, Any]:
    """
    把 meta 里不适合直接写 json 的对象转成普通类型
    """
    safe = {}
    for k, v in meta.items():
        if k == "dtype_np":
            continue
        if isinstance(v, Path):
            safe[k] = str(v)
        elif isinstance(v, tuple):
            safe[k] = list(v)
        else:
            safe[k] = v
    return safe


def convert_v3draw_to_nifti(
    v3draw_path: str | Path,
    nii_path: str | Path,
    meta_path: str | Path,
    spacing: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> dict[str, Any]:
    """
    读取 .v3draw -> 保存 .nii.gz -> 写 meta.json
    """
    v3draw_path = Path(v3draw_path)
    nii_path = Path(nii_path)
    meta_path = Path(meta_path)

    nii_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.parent.mkdir(parents=True, exist_ok=True)

    volume, meta = read_v3draw(v3draw_path)

    save_nifti(volume, nii_path, spacing=spacing)

    meta_out = _make_json_safe(meta)
    meta_out["input_path"] = str(v3draw_path)
    meta_out["output_nii_path"] = str(nii_path)
    meta_out["spacing"] = list(spacing)

    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(meta_out, f, ensure_ascii=False, indent=2)

    return {
        "nii_path": str(nii_path),
        "meta_path": str(meta_path),
        "shape": list(volume.shape),
        "dtype": str(volume.dtype),
        "min": float(volume.min()),
        "max": float(volume.max()),
        "mean": float(volume.mean()),
    }
