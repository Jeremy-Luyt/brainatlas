"""
为所有样本恢复 Global 配准结果。
在新服务器启动后执行此脚本。
用法: python scripts/recover_all_samples.py
"""
import sys
import json
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.io import read_v3draw, save_nifti
from pipeline.preprocess.build_previews import build_previews_from_volume

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"
REG_ROOT = DATA_ROOT / "projects" / "default" / "registration"
SAMPLES_ROOT = DATA_ROOT / "projects" / "default" / "samples"


def to_url(p: str) -> str:
    return "/api/static/" + Path(p).resolve().relative_to(DATA_ROOT.resolve()).as_posix()


def main():
    print("=" * 60)
    print("  Recover Global Registration for ALL samples")
    print("=" * 60)

    # 找到最新的 global.v3draw
    all_globals = sorted(
        REG_ROOT.glob("**/global.v3draw"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    print(f"\nFound {len(all_globals)} global.v3draw files in registration/")
    if not all_globals:
        print("ERROR: No global.v3draw found! Nothing to recover.")
        return

    src = all_globals[0]
    print(f"  Using latest: {src}")
    print(f"  Size: {src.stat().st_size / 1024 / 1024:.1f} MB")

    # 读取一次, 复用给所有样本
    print("\nReading global.v3draw...")
    volume, meta = read_v3draw(src)
    print(f"  shape={volume.shape}, ndim={volume.ndim}, dtype={volume.dtype}")
    if volume.ndim == 4:
        print(f"  Multi-channel detected, taking channel 0")
        volume = volume[0]
        print(f"  New shape={volume.shape}")

    # 遍历所有样本目录
    sample_dirs = sorted([d for d in SAMPLES_ROOT.iterdir() if d.is_dir()])
    print(f"\nFound {len(sample_dirs)} sample directories")

    fixed = 0
    skipped = 0
    errors = 0

    for sd in sample_dirs:
        sample_json = sd / "sample.json"
        if not sample_json.exists():
            continue

        sample_id = sd.name
        try:
            sample = json.loads(sample_json.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  SKIP {sample_id}: can't read sample.json: {e}")
            skipped += 1
            continue

        # 检查是否已有完整的 global 数据
        existing = sample.get("global_registration", {})
        if (
            sample.get("global_registration_status") == "completed"
            and existing.get("global_nii_url")
            and Path(existing.get("global_nii_path", "")).exists()
        ):
            print(f"  SKIP {sample_id}: already has valid Global data")
            skipped += 1
            continue

        print(f"  Processing {sample_id}...")

        try:
            # 创建目标目录
            global_dir = sd / "registration" / "global"
            global_dir.mkdir(parents=True, exist_ok=True)

            # 复制 global.v3draw
            dst_v3draw = global_dir / "global.v3draw"
            if not dst_v3draw.exists():
                shutil.copy2(src, dst_v3draw)
                print(f"    Copied global.v3draw")

            # 生成 global.nii.gz
            dst_nii = global_dir / "global.nii.gz"
            if not dst_nii.exists():
                save_nifti(volume, dst_nii, spacing=(1.0, 1.0, 1.0))
                print(f"    Created global.nii.gz ({dst_nii.stat().st_size / 1024 / 1024:.1f} MB)")
            else:
                print(f"    global.nii.gz already exists")

            # 生成预览
            preview_dir = global_dir / "previews"
            if not preview_dir.exists() or not list(preview_dir.glob("*.png")):
                preview_paths = build_previews_from_volume(volume, preview_dir)
                print(f"    Created previews: {list(preview_paths.keys())}")
            else:
                preview_paths = {p.stem: str(p) for p in sorted(preview_dir.glob("*.png"))}
                print(f"    Previews already exist: {list(preview_paths.keys())}")

            # 更新 sample.json
            global_reg_data = {
                "output_dir": str(global_dir),
                "global_v3draw_path": str(dst_v3draw),
                "global_nii_path": str(dst_nii),
                "global_nii_url": to_url(str(dst_nii)),
                "preview_paths": preview_paths,
                "preview_urls": {k: to_url(v) for k, v in preview_paths.items()},
            }
            sample["global_registration_status"] = "completed"
            sample["global_registration"] = global_reg_data
            sample_json.write_text(
                json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"    Updated sample.json ✓")
            print(f"    nii_url = {global_reg_data['global_nii_url']}")
            fixed += 1

        except Exception as e:
            print(f"    ERROR: {e}")
            errors += 1

    print(f"\n{'=' * 60}")
    print(f"  Results: {fixed} fixed, {skipped} skipped, {errors} errors")
    print(f"  Total samples: {len(sample_dirs)}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
