from pathlib import Path


def read_v3draw_header(path: str | Path) -> dict:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(str(file_path))
    size = file_path.stat().st_size
    with file_path.open("rb") as f:
        magic = f.read(24)
    return {
        "path": str(file_path),
        "size_bytes": size,
        "magic_ascii": magic.decode("ascii", errors="ignore").strip("\x00"),
    }
