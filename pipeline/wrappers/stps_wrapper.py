"""
STPS exe封装, 调用stps.exe进行薄板样条形状校正

模板构建中的参数方向:
  subject_markers(-S) = tar_ref, target_markers(-T) = sub_avg, subject_image(-s) = M_raw
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _exe_path() -> Path:
    exe = _repo_root() / "tools" / "src_modern" / "stps" / "build" / "bin" / "stps.exe"
    if not exe.exists():
        raise FileNotFoundError(f"STPS exe not found: {exe}")
    return exe


def run_stps(
    subject_image: str | Path,
    subject_markers: str | Path,
    target_markers: str | Path,
    output_image: str | Path,
    df_method: int = 1,
    block_size: int = 4,
    lambda_val: float = 0.2,
    timeout: int = 1800,
) -> dict:
    """运行STPS形状校正"""
    subject_image = Path(subject_image)
    subject_markers = Path(subject_markers)
    target_markers = Path(target_markers)
    output_image = Path(output_image)

    if not subject_image.exists():
        raise FileNotFoundError(f"Subject image not found: {subject_image}")
    if not subject_markers.exists():
        raise FileNotFoundError(f"Subject markers not found: {subject_markers}")
    if not target_markers.exists():
        raise FileNotFoundError(f"Target markers not found: {target_markers}")

    output_image.parent.mkdir(parents=True, exist_ok=True)

    exe = _exe_path()
    cmd = [
        str(exe),
        "-s", str(subject_image.resolve()),
        "-S", str(subject_markers.resolve()),
        "-T", str(target_markers.resolve()),
        "-o", str(output_image.resolve()),
        "-d", str(df_method),
        "-b", str(block_size),
        "--lambda", str(lambda_val),
    ]

    env = os.environ.copy()

    log_path = output_image.parent / "stps.log"

    with open(log_path, "w", encoding="utf-8") as log_fh:
        process = subprocess.run(
            cmd,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=str(exe.parent),
            timeout=timeout,
        )

    if process.returncode != 0 and not output_image.exists():
        raise RuntimeError(
            f"STPS exe failed (code {process.returncode}). "
            f"Log: {log_path}"
        )

    return {
        "output_image": str(output_image),
        "log_path": str(log_path),
        "return_code": process.returncode,
        "status": "completed" if output_image.exists() else "failed",
    }
