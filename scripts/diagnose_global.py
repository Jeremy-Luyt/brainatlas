"""诊断 global.v3draw 文件能否被 read_v3draw / save_nifti 正常处理"""
import sys, traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.io.reader_v3draw import read_v3draw, read_v3draw_header

# 找到一个 global.v3draw
reg_root = Path(r"E:\workspace\brainatlas\data\projects\default\registration")
global_files = sorted(reg_root.glob("**/global.v3draw"))

print(f"Found {len(global_files)} global.v3draw files")
if not global_files:
    sys.exit(1)

target = global_files[0]
print(f"\n--- Testing: {target} ({target.stat().st_size / 1024 / 1024:.1f} MB) ---")

# Step 1: header only
try:
    header = read_v3draw_header(target)
    print(f"Header OK: shape_raw={header['shape_raw']}, dtype={header['dtype']}, channels={header['channels']}")
    print(f"  expected_bytes={header['expected_bytes']}, actual_bytes={header['actual_bytes']}")
    print(f"  match={header['expected_bytes'] == header['actual_bytes']}")
except Exception as e:
    print(f"Header FAILED: {e}")
    traceback.print_exc()
    sys.exit(1)

# Step 2: full read
try:
    volume, meta = read_v3draw(target)
    print(f"read_v3draw OK: shape_out={meta['shape_out']}, ndim={volume.ndim}, dtype={volume.dtype}")
    print(f"  min={meta['min']:.2f}, max={meta['max']:.2f}, mean={meta['mean']:.2f}")
except Exception as e:
    print(f"read_v3draw FAILED: {e}")
    traceback.print_exc()
    sys.exit(1)

# Step 3: save nifti
try:
    from pipeline.io.nii_io import save_nifti
    out = Path(r"E:\workspace\brainatlas\data\temp\test_global.nii.gz")
    save_nifti(volume, out, spacing=(1.0, 1.0, 1.0))
    print(f"save_nifti OK: {out} ({out.stat().st_size / 1024 / 1024:.1f} MB)")
except Exception as e:
    print(f"save_nifti FAILED: {e}")
    traceback.print_exc()
    sys.exit(1)

# Step 4: build previews
try:
    from pipeline.preprocess.build_previews import build_previews_from_volume
    pdir = Path(r"E:\workspace\brainatlas\data\temp\test_previews")
    previews = build_previews_from_volume(volume, pdir)
    print(f"build_previews OK: {list(previews.keys())}")
except Exception as e:
    print(f"build_previews FAILED: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n=== ALL OK ===")
