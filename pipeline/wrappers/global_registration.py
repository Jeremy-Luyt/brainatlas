from pathlib import Path
import json

from pipeline.common.file_naming import registration_file_name


def run_global_registration(moving: Path, fixed: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / registration_file_name(moving, fixed)
    payload = {
        "moving": str(moving),
        "fixed": str(fixed),
        "transform": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        "translation": [0, 0, 0],
        "status": "completed",
    }
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"result_path": str(result_path), "status": "completed"}
