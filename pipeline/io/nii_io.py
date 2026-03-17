from pathlib import Path


def inspect_nii(path: str | Path) -> dict:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(str(file_path))
    return {
        "path": str(file_path),
        "suffixes": file_path.suffixes,
        "size_bytes": file_path.stat().st_size,
    }
