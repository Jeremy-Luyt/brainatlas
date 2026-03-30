"""
局部配准exe封装, 调用local_registration_LYT.exe

输出: local_registered_image.v3draw, local_registered_sub/tar.marker
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _exe_path() -> Path:
    exe = (
        _repo_root()
        / "tools" / "bin" / "local" / "local_hhm"
        / "CPU" / "release" / "local_registration_LYT.exe"
    )
    if not exe.exists():
        raise FileNotFoundError(f"Local registration exe not found: {exe}")
    return exe


def _default_config_path() -> Path:
    return _repo_root() / "tools" / "bin" / "local" / "config" / "config.txt"


def _runtime_path_entries(exe: Path) -> list[str]:
    root = _repo_root()
    entries = [
        str(exe.parent),
        str(root / "tools" / "bin" / "win64_bin"),
        str(root / "tools" / "bin" / "3rdparty" / "3rdparty" / "qt-4.8.6" / "msvc2013_64" / "bin"),
    ]
    return [p for p in entries if Path(p).exists()]


def _prepare_template_dir(template_v3draw: Path, work_dir: Path) -> Path:
    """
    local_registration_LYT.exe -g 需要一个目录，其中包含模板图像。

    Select_modal=2 (通用模式) 要求目录下有 Target_image.v3draw。
    返回可作为 -g 参数的目录路径。
    """
    temp_template = work_dir / "_template_pkg"
    temp_template.mkdir(parents=True, exist_ok=True)

    dst = temp_template / "Target_image.v3draw"
    if not dst.exists():
        shutil.copy2(template_v3draw, dst)

    return temp_template


def run_local_registration(
    subject_image: str | Path,
    template_v3draw: str | Path,
    landmarks: str | Path,
    output_dir: str | Path,
    config_path: str | Path | None = None,
    segmentation: str | Path | None = None,
    finetune_dir: str | Path | None = None,
    timeout: int = 3600,
) -> dict:
    """运行局部配准"""
    subject_image = Path(subject_image)
    template_v3draw = Path(template_v3draw)
    landmarks = Path(landmarks)
    output_dir = Path(output_dir)

    if not subject_image.exists():
        raise FileNotFoundError(f"Subject image not found: {subject_image}")
    if not template_v3draw.exists():
        raise FileNotFoundError(f"Template v3draw not found: {template_v3draw}")
    if not landmarks.exists():
        raise FileNotFoundError(f"Landmarks marker not found: {landmarks}")

    output_dir.mkdir(parents=True, exist_ok=True)

    config = Path(config_path) if config_path else _default_config_path()
    if not config.exists():
        raise FileNotFoundError(f"Config file not found: {config}")

    # 准备模板目录结构（exe 需要 atlas_v3draw/ 子目录）
    template_dir = _prepare_template_dir(template_v3draw, output_dir)

    exe = _exe_path()
    cmd = [
        str(exe),
        "-p", str(config.resolve()),
        "-s", str(subject_image.resolve()),
        "-g", str(template_dir.resolve()) + os.sep,
        "-l", str(landmarks.resolve()),
        "-o", str(output_dir.resolve()) + os.sep,
    ]

    if segmentation:
        seg_path = Path(segmentation)
        if seg_path.exists():
            cmd.extend(["-m", str(seg_path.resolve())])

    if finetune_dir:
        ft_path = Path(finetune_dir)
        if ft_path.exists():
            cmd.extend(["-f", str(ft_path.resolve()) + os.sep])

    env = os.environ.copy()
    path_entries = _runtime_path_entries(exe)
    env["PATH"] = os.pathsep.join(path_entries + [env.get("PATH", "")])

    log_path = output_dir / "local_registration.log"

    with open(log_path, "w", encoding="utf-8") as log_fh:
        process = subprocess.run(
            cmd,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=str(exe.parent),
            timeout=timeout,
        )

    # 收集输出文件
    registered_image = _find_output(output_dir, "local_registered_image", ".v3draw")
    sub_marker = _find_output(output_dir, "local_registered_sub", ".marker")
    tar_marker = _find_output(output_dir, "local_registered_tar", ".marker")

    if process.returncode != 0 and registered_image is None:
        raise RuntimeError(
            f"Local registration failed (code {process.returncode}). "
            f"Log: {log_path}"
        )

    return {
        "registered_image": str(registered_image) if registered_image else "",
        "sub_marker": str(sub_marker) if sub_marker else "",
        "tar_marker": str(tar_marker) if tar_marker else "",
        "log_path": str(log_path),
        "return_code": process.returncode,
        "status": "completed" if registered_image else "failed",
    }


def _find_output(output_dir: Path, stem_prefix: str, suffix: str) -> Path | None:
    """在 output_dir 中查找匹配的输出文件。"""
    # 精确匹配
    exact = output_dir / f"{stem_prefix}{suffix}"
    if exact.exists():
        return exact
    # 模糊匹配
    candidates = sorted(output_dir.glob(f"{stem_prefix}*{suffix}"))
    return candidates[0] if candidates else None
