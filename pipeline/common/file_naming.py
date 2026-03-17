from pathlib import Path
import re


def sanitize_stem(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", name.strip())
    return cleaned.strip("._") or "untitled"


def preview_file_name(source: Path) -> str:
    return f"{sanitize_stem(source.stem)}_preview.txt"


def registration_file_name(moving: Path, fixed: Path) -> str:
    return f"{sanitize_stem(moving.stem)}_to_{sanitize_stem(fixed.stem)}.json"
