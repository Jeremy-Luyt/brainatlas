from pathlib import Path
import shutil


def copy_as_nifti(input_path: str | Path, output_path: str | Path) -> dict:
    src = Path(input_path)
    dst = Path(output_path)
    if not src.exists():
        raise FileNotFoundError(str(src))
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return {"input_path": str(src), "output_path": str(dst)}
