"""
独立脚本：诊断 global.v3draw 并为样本恢复 Global 结果
不依赖 FastAPI 服务器，直接操作文件系统
用法: python scripts/recover_global.py [sample_id]
"""
import sys, json, shutil, traceback
from pathlib import Path

# 设置路径
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

DATA_ROOT = REPO / "data"
PROJECT_ROOT = DATA_ROOT / "projects" / "default"
REG_ROOT = PROJECT_ROOT / "registration"
SAMPLES_ROOT = PROJECT_ROOT / "samples"

def to_static_url(path_str):
    src = Path(path_str).resolve()
    try:
        rel = src.relative_to(DATA_ROOT.resolve()).as_posix()
        return f"/api/static/{rel}"
    except ValueError:
        return ""

def diagnose():
    print("=" * 60)
    print("DIAGNOSE: global.v3draw 转换流程")
    print("=" * 60)

    if not REG_ROOT.exists():
        print(f"ERROR: {REG_ROOT} does not exist")
        return

    all_globals = sorted(REG_ROOT.glob("**/global.v3draw"), key=lambda p: p.stat().st_mtime, reverse=True)
    print(f"Found {len(all_globals)} global.v3draw files")
    for g in all_globals[:3]:
        print(f"  {g} ({g.stat().st_size / 1024 / 1024:.1f} MB)")

    if not all_globals:
        return

    target = all_globals[0]
    print(f"\nTesting: {target}")

    # Header
    try:
        from pipeline.io.reader_v3draw import read_v3draw_header
        h = read_v3draw_header(target)
        print(f"  Header: {h['width']}x{h['height']}x{h['depth']}x{h['channels']} dtype={h['dtype']}")
        print(f"  Size match: expected={h['expected_bytes']} actual={h['actual_bytes']} match={h['expected_bytes']==h['actual_bytes']}")
    except Exception as e:
        print(f"  Header FAILED: {e}")
        return

    # Full read
    try:
        from pipeline.io.reader_v3draw import read_v3draw
        volume, meta = read_v3draw(target)
        print(f"  Read OK: shape={volume.shape} ndim={volume.ndim} dtype={volume.dtype}")
    except Exception as e:
        print(f"  Read FAILED: {e}")
        traceback.print_exc()
        return

    # Handle multi-channel
    if volume.ndim == 4:
        print(f"  >>> MULTI-CHANNEL detected! shape={volume.shape}, taking channel 0")
        volume = volume[0]
        print(f"  >>> After squeeze: shape={volume.shape}")

    # Save NIfTI
    try:
        from pipeline.io.nii_io import save_nifti
        test_out = DATA_ROOT / "temp" / "diag_global.nii.gz"
        save_nifti(volume, test_out, spacing=(1.0, 1.0, 1.0))
        print(f"  save_nifti OK: {test_out} ({test_out.stat().st_size / 1024 / 1024:.1f} MB)")
        test_out.unlink(missing_ok=True)
    except Exception as e:
        print(f"  save_nifti FAILED: {e}")
        traceback.print_exc()
        return

    # Previews
    try:
        from pipeline.preprocess.build_previews import build_previews_from_volume
        pdir = DATA_ROOT / "temp" / "diag_previews"
        pdir.mkdir(parents=True, exist_ok=True)
        previews = build_previews_from_volume(volume, pdir)
        print(f"  Previews OK: {list(previews.keys())}")
        shutil.rmtree(pdir, ignore_errors=True)
    except Exception as e:
        print(f"  Previews FAILED: {e}")
        traceback.print_exc()
        return

    print("\n=== ALL CONVERSION STEPS OK ===")


def recover(sample_id):
    print("=" * 60)
    print(f"RECOVER: sample {sample_id}")
    print("=" * 60)

    sample_dir = SAMPLES_ROOT / sample_id
    sample_json = sample_dir / "sample.json"
    if not sample_json.exists():
        print(f"ERROR: {sample_json} not found")
        return

    sample = json.loads(sample_json.read_text(encoding="utf-8"))
    print(f"  Filename: {sample.get('filename')}")
    print(f"  Status: {sample.get('global_registration_status')}")

    # Find latest global.v3draw
    all_globals = sorted(REG_ROOT.glob("**/global.v3draw"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not all_globals:
        print("ERROR: no global.v3draw found")
        return

    src_v3draw = all_globals[0]
    src_dir = src_v3draw.parent
    print(f"  Source: {src_v3draw}")

    # Create sample-scoped output
    sample_global_dir = sample_dir / "registration" / "global"
    sample_global_dir.mkdir(parents=True, exist_ok=True)

    # Copy files
    for pattern in ["global*.v3draw", "*.marker", "global_registration.log",
                     "op_warp_RPM*.v3draw", "op_warp_RPM*.marker", "op_warp_sub*.marker"]:
        for src in src_dir.glob(pattern):
            if src.is_file():
                dst = sample_global_dir / src.name
                if not dst.exists():
                    print(f"  Copying {src.name}...")
                    shutil.copy2(src, dst)

    global_v3draw = sample_global_dir / "global.v3draw"
    if not global_v3draw.exists():
        print(f"ERROR: {global_v3draw} not found after copy")
        return

    # Read
    from pipeline.io.reader_v3draw import read_v3draw
    volume, header = read_v3draw(global_v3draw)
    print(f"  Read: shape={volume.shape} ndim={volume.ndim}")

    if volume.ndim == 4:
        print(f"  Multi-channel, taking channel 0")
        volume = volume[0]

    # Save NIfTI
    from pipeline.io.nii_io import save_nifti
    global_nii = sample_global_dir / "global.nii.gz"
    save_nifti(volume, global_nii, spacing=(1.0, 1.0, 1.0))
    print(f"  NIfTI: {global_nii} ({global_nii.stat().st_size / 1024 / 1024:.1f} MB)")

    # Previews
    from pipeline.preprocess.build_previews import build_previews_from_volume
    preview_dir = sample_global_dir / "previews"
    preview_paths = build_previews_from_volume(volume, preview_dir)
    print(f"  Previews: {list(preview_paths.keys())}")

    # Update sample.json
    global_reg_data = {
        "output_dir": str(sample_global_dir),
        "global_v3draw_path": str(global_v3draw),
        "global_nii_path": str(global_nii),
        "global_nii_url": to_static_url(str(global_nii)),
        "preview_paths": preview_paths,
        "preview_urls": {k: to_static_url(v) for k, v in preview_paths.items()},
    }
    sample["global_registration_status"] = "completed"
    sample["global_registration"] = global_reg_data

    sample_json.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  DONE! sample.json updated")
    print(f"  global_nii_url = {global_reg_data['global_nii_url']}")
    print(f"  preview_urls = {global_reg_data['preview_urls']}")


if __name__ == "__main__":
    diagnose()
    print()

    if len(sys.argv) > 1:
        sid = sys.argv[1]
        recover(sid)
    else:
        # 找一个 op_warp.v3draw 的样本自动恢复
        for s in sorted(SAMPLES_ROOT.iterdir()):
            sj = s / "sample.json"
            if sj.exists():
                data = json.loads(sj.read_text(encoding="utf-8"))
                if data.get("filename", "").lower() == "op_warp.v3draw" and data.get("global_registration_status") == "idle":
                    print(f"Auto-recovering first idle op_warp sample: {data['sample_id']}")
                    recover(data["sample_id"])
                    break
