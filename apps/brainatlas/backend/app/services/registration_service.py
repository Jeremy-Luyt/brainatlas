from pathlib import Path

from pipeline.wrappers.global_registration import run_global_registration


def run_registration(moving: Path, fixed: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    return run_global_registration(moving=moving, fixed=fixed, output_dir=output_dir)
