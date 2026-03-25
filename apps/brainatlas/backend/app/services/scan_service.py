"""
scan_service.py — 文件夹扫描 + 懒加载索引

设计原则：
- 用户给定文件夹路径，扫描出所有支持的脑影像文件
- 只创建 sample 索引（sample.json），**不读取**文件内容
- 状态设为 "indexed"：仅知道文件路径，未进行任何 I/O
- 后续用到哪个脑，才按需触发 prepare（转换 + 预览）
- 这样数十乃至上百个脑文件也不会占内存
"""
from pathlib import Path
from typing import Any

from .sample_service import create_sample, get_sample


# 支持的文件扩展名
_SUPPORTED_SUFFIXES = {
    ".v3draw", ".nii", ".tif", ".tiff", ".mhd", ".mha", ".nrrd",
}


def _is_supported(path: Path) -> bool:
    """判断文件是否为支持的脑影像格式"""
    name = path.name.lower()
    # 特殊处理 .nii.gz
    if name.endswith(".nii.gz"):
        return True
    return path.suffix.lower() in _SUPPORTED_SUFFIXES


def scan_folder(folder_path: str, project_id: str = "default",
                recursive: bool = True) -> dict[str, Any]:
    """
    扫描指定文件夹，为每个脑影像文件创建 sample 索引。

    返回:
        {
            "folder": str,
            "project_id": str,
            "total_found": int,        # 发现的文件数
            "newly_indexed": int,       # 新创建的样本数
            "already_existed": int,     # 之前已存在的（按路径去重）
            "samples": [               # 新索引的样本列表
                {"sample_id": ..., "filename": ..., "stored_path": ...},
            ]
        }
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        raise ValueError(f"路径不存在或不是文件夹: {folder_path}")

    # 收集所有支持的文件
    if recursive:
        candidates = [p for p in folder.rglob("*") if p.is_file() and _is_supported(p)]
    else:
        candidates = [p for p in folder.iterdir() if p.is_file() and _is_supported(p)]

    # 按文件名排序，保持稳定顺序
    candidates.sort(key=lambda p: p.name.lower())

    # 检查哪些路径已经被索引过（避免重复创建 sample）
    from .sample_service import _iter_sample_files
    from ..utils.json_io import read_json

    existing_paths: set[str] = set()
    for sample_json in _iter_sample_files():
        data = read_json(sample_json)
        sp = data.get("stored_path", "")
        if sp:
            existing_paths.add(str(Path(sp).resolve()))

    newly_indexed = []
    already_existed = 0

    for file_path in candidates:
        resolved = str(file_path.resolve())
        if resolved in existing_paths:
            already_existed += 1
            continue

        # 创建 sample 索引，状态为 indexed（懒加载，尚未读取内容）
        sample = create_sample(
            project_id=project_id,
            original_filename=file_path.name,
            stored_path=file_path,
        )
        # 覆盖 prepare_status 为 indexed（区别于 upload 后的 pending）
        from .sample_service import update_sample
        update_sample(sample["sample_id"], {"prepare_status": "indexed"})

        newly_indexed.append({
            "sample_id": sample["sample_id"],
            "filename": file_path.name,
            "stored_path": str(file_path),
            "size_mb": round(file_path.stat().st_size / 1024 / 1024, 2),
        })
        existing_paths.add(resolved)

    return {
        "folder": str(folder),
        "project_id": project_id,
        "total_found": len(candidates),
        "newly_indexed": len(newly_indexed),
        "already_existed": already_existed,
        "samples": newly_indexed,
    }
