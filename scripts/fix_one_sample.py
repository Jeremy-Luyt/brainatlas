"""最简脚本：为 bb3d902cb10d 恢复 Global 结果"""
import sys, json, shutil
from pathlib import Path
sys.path.insert(0, r"E:\workspace\brainatlas")

# 配置
SAMPLE_ID = "bb3d902cb10d"
SRC = Path(r"E:\workspace\brainatlas\data\projects\default\registration\2207eba3-b60e-402a-b98a-510554ca14ef\global.v3draw")
DST_DIR = Path(r"E:\workspace\brainatlas\data\projects\default\samples") / SAMPLE_ID / "registration" / "global"
SAMPLE_JSON = Path(r"E:\workspace\brainatlas\data\projects\default\samples") / SAMPLE_ID / "sample.json"
DATA_ROOT = Path(r"E:\workspace\brainatlas\data")

print("Step 0: setup")
DST_DIR.mkdir(parents=True, exist_ok=True)

# Copy v3draw
dst_v3draw = DST_DIR / "global.v3draw"
if not dst_v3draw.exists():
    print(f"Copying {SRC} -> {dst_v3draw}")
    shutil.copy2(SRC, dst_v3draw)
else:
    print(f"Already exists: {dst_v3draw}")

# Read
print("Step 1: reading v3draw...")
from pipeline.io.reader_v3draw import read_v3draw
vol, meta = read_v3draw(dst_v3draw)
print(f"  shape={vol.shape}, ndim={vol.ndim}, dtype={vol.dtype}")

if vol.ndim == 4:
    print(f"  Multi-channel! Taking ch0")
    vol = vol[0]
    print(f"  New shape={vol.shape}")

# Save nii.gz
print("Step 2: saving nii.gz...")
from pipeline.io.nii_io import save_nifti
nii_path = DST_DIR / "global.nii.gz"
save_nifti(vol, nii_path, spacing=(1.0, 1.0, 1.0))
print(f"  OK: {nii_path} ({nii_path.stat().st_size / 1024 / 1024:.1f} MB)")

# Previews
print("Step 3: generating previews...")
from pipeline.preprocess.build_previews import build_previews_from_volume
preview_dir = DST_DIR / "previews"
preview_paths = build_previews_from_volume(vol, preview_dir)
print(f"  OK: {list(preview_paths.keys())}")

# URL helper
def to_url(p):
    return "/api/static/" + Path(p).resolve().relative_to(DATA_ROOT.resolve()).as_posix()

# Update sample.json
print("Step 4: updating sample.json...")
sample = json.loads(SAMPLE_JSON.read_text(encoding="utf-8"))
sample["global_registration_status"] = "completed"
sample["global_registration"] = {
    "output_dir": str(DST_DIR),
    "global_v3draw_path": str(dst_v3draw),
    "global_nii_path": str(nii_path),
    "global_nii_url": to_url(str(nii_path)),
    "preview_paths": preview_paths,
    "preview_urls": {k: to_url(v) for k, v in preview_paths.items()},
}
SAMPLE_JSON.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"  global_nii_url = {sample['global_registration']['global_nii_url']}")
print(f"  preview_urls = {sample['global_registration']['preview_urls']}")
print("\nDONE!")
