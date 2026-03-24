from pathlib import Path
import json
import os
import shutil
import subprocess

from pipeline.common.file_naming import registration_file_name


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_template_root(fixed: Path) -> Path:
    if fixed.is_file():
        # assume fixed is atlas_v3draw/some.v3draw, return parent.parent
        return fixed.parent.parent
    if fixed.is_dir() and (fixed / "atlas_v3draw").exists():
        return fixed
    default_template = _repo_root() / "tools" / "templates" / "25um_568"
    if (default_template / "atlas_v3draw").exists():
        return default_template
    fallback_template = _repo_root() / "tools" / "templates" / "fmost"
    if (fallback_template / "atlas_v3draw").exists():
        return fallback_template
    raise FileNotFoundError("No atlas template directory found under tools/templates")


def _resolve_fixed_arg(fixed: Path, template_root: Path) -> str:
    if fixed.is_file():
        return str(fixed.resolve())
    # GlobalRegistration_LYT.exe expects template package directory when using atlas bundle.
    return str(template_root.resolve()) + os.sep


def _exe_path() -> Path:
    exe = _repo_root() / "tools" / "bin" / "global" / "CPU" / "release" / "GlobalRegistration_LYT.exe"
    if not exe.exists():
        raise FileNotFoundError(str(exe))
    return exe


def _runtime_path_entries(exe: Path) -> list[str]:
    root = _repo_root()
    entries = [
        str(exe.parent),
        str(root / "tools" / "bin" / "win64_bin"),
        str(root / "tools" / "bin" / "3rdparty" / "3rdparty" / "qt-4.8.6" / "msvc2013_64" / "bin"),
    ]
    return [p for p in entries if Path(p).exists()]


def _collect_outputs(output_dir: Path, moving: Path) -> Path:
    direct_candidates = sorted(output_dir.glob("global*.v3draw"))
    if direct_candidates:
        return direct_candidates[0]

    parent = output_dir.parent
    moving_stem = moving.stem
    fallback_patterns = [
        "global*.v3draw",
        f"{moving_stem}*.v3draw",
        f"{moving_stem}*.marker",
        f"{moving_stem}*.swc",
        "global_registration.log",
    ]
    moved_global: Path | None = None
    for pattern in fallback_patterns:
        for src in sorted(parent.glob(pattern)):
            if src.is_dir() or src.parent == output_dir:
                continue
            dest = output_dir / src.name
            if not dest.exists():
                shutil.copy2(src, dest)
            if src.name.startswith("global") and src.suffix.lower() == ".v3draw":
                moved_global = dest

    if moved_global:
        return moved_global
    return output_dir / "global.v3draw"


def _decode_output(buf: bytes | None) -> str:
    if not buf:
        return ""
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return buf.decode(enc)
        except UnicodeDecodeError:
            continue
    return buf.decode("utf-8", errors="replace")


def run_global_registration(moving: str | Path, fixed: str | Path, output_dir: str | Path, subject_marker: str | Path = None, target_marker: str | Path = None) -> dict:
    moving = Path(moving)
    fixed = Path(fixed)
    output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    if not moving.exists():
        raise FileNotFoundError(str(moving))
    template_root = _resolve_template_root(fixed)
    fixed_arg = _resolve_fixed_arg(fixed, template_root)
    exe = _exe_path()
    cmd = [
        str(exe),
        "-f", fixed_arg,
        "-m", str(moving.resolve()),
        "-p", "a+f+n",
        "-o", str(output_dir.resolve()) + os.sep,
        "-d", "0",
        "-l", "0+0+0",
    ]
    # Note: markers are required for affine registration
    subject_marker_path = None
    target_marker_path = None
    if subject_marker:
        subject_marker_path = Path(subject_marker).resolve()
        cmd.extend(["-s", str(subject_marker_path)])
    else:
        default_subject = template_root / "fMOST_space_prior_sub.marker"
        if default_subject.exists():
            subject_marker_path = default_subject.resolve()
            cmd.extend(["-s", str(subject_marker_path)])

    if target_marker:
        target_marker_path = Path(target_marker).resolve()
        cmd.extend(["-t", str(target_marker_path)])
    else:
        default_target = template_root / "fMOST_space_prior_tar.marker"
        if default_target.exists():
            target_marker_path = default_target.resolve()
            cmd.extend(["-t", str(target_marker_path)])

    env = os.environ.copy()
    path_entries = _runtime_path_entries(exe)
    env["PATH"] = os.pathsep.join(path_entries + [env.get("PATH", "")])
    log_path = output_dir / "global_registration.log"
    print(f"DEBUG CMD: {cmd}")
    output_path = _collect_outputs(output_dir, moving)
    process = subprocess.run(cmd, capture_output=True, text=False, env=env, cwd=str(exe.parent))
    stdout_text = _decode_output(process.stdout)
    stderr_text = _decode_output(process.stderr)
    merged_log = (stdout_text or "") + "\n" + (stderr_text or "")
    log_path.write_text(merged_log, encoding="utf-8")

    has_output = output_path.exists()
    success_by_log = "Program exit success" in merged_log
    if process.returncode != 0 and not has_output and not success_by_log:
        raise RuntimeError(f"GlobalRegistration_LYT.exe failed with code {process.returncode}. log={log_path}")

    result_path = output_dir / registration_file_name(moving, fixed)
    payload = {
        "moving": str(moving),
        "fixed": str(fixed),
        "fixed_arg": fixed_arg,
        "template_root": str(template_root),
        "command": cmd,
        "binary_output_path": str(output_path),
        "log_path": str(log_path),
        "return_code": process.returncode,
        "status": "completed",
        "subject_marker_path": str(subject_marker_path) if subject_marker_path else "",
        "target_marker_path": str(target_marker_path) if target_marker_path else "",
    }
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "result_path": str(result_path),
        "binary_output_path": str(output_path),
        "log_path": str(log_path),
        "subject_marker_path": str(subject_marker_path) if subject_marker_path else "",
        "target_marker_path": str(target_marker_path) if target_marker_path else "",
        "status": "completed",
    }
