from pathlib import Path
import json
import os
import subprocess

from pipeline.common.file_naming import registration_file_name


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_template_root(fixed: Path) -> Path:
    if fixed.is_dir() and (fixed / "atlas_v3draw").exists():
        return fixed
    default_template = _repo_root() / "tools" / "templates" / "25um_568"
    if (default_template / "atlas_v3draw").exists():
        return default_template
    fallback_template = _repo_root() / "tools" / "templates" / "fmost"
    if (fallback_template / "atlas_v3draw").exists():
        return fallback_template
    raise FileNotFoundError("No atlas template directory found under tools/templates")


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


def run_global_registration(moving: Path, fixed: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    if not moving.exists():
        raise FileNotFoundError(str(moving))
    template_root = _resolve_template_root(fixed)
    exe = _exe_path()
    cmd = [
        str(exe),
        "-f",
        str(template_root) + os.sep,
        "-m",
        str(moving),
        "-p",
        "r",
        "-o",
        str(output_dir),
        "-d",
        "0",
        "-l",
        "0",
    ]
    env = os.environ.copy()
    path_entries = _runtime_path_entries(exe)
    env["PATH"] = os.pathsep.join(path_entries + [env.get("PATH", "")])
    process = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(exe.parent))
    log_path = output_dir / "global_registration.log"
    log_path.write_text((process.stdout or "") + "\n" + (process.stderr or ""), encoding="utf-8")
    if process.returncode != 0:
        raise RuntimeError(f"GlobalRegistration_LYT.exe failed with code {process.returncode}. log={log_path}")
    output_candidates = sorted(output_dir.glob("global*"))
    output_path = output_candidates[0] if output_candidates else output_dir / "global.v3draw"
    result_path = output_dir / registration_file_name(moving, fixed)
    payload = {
        "moving": str(moving),
        "fixed": str(fixed),
        "template_root": str(template_root),
        "command": cmd,
        "binary_output_path": str(output_path),
        "log_path": str(log_path),
        "return_code": process.returncode,
        "status": "completed",
    }
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"result_path": str(result_path), "binary_output_path": str(output_path), "log_path": str(log_path), "status": "completed"}
