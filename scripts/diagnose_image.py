"""诊断 global.v3draw 的维度、通道、数值等信息，与原图对比"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from pipeline.io.reader_v3draw import read_v3draw, read_v3draw_header

DATA = Path(__file__).resolve().parent.parent / "data"
SAMPLE_DIR = DATA / "projects" / "default" / "samples" / "bb3d902cb10d"

# --- 原图 ---
original_path = Path(json.loads((SAMPLE_DIR / "sample.json").read_text("utf-8"))["stored_path"])
print("=" * 60)
print("ORIGINAL:", original_path)
if original_path.exists():
    h = read_v3draw_header(original_path)
    print(f"  Header: {h['width']}x{h['height']}x{h['depth']} C={h['channels']} dtype={h['dtype']}")
    print(f"  File size: {h['file_size']/1024/1024:.1f} MB, data_offset={h['data_offset']}")
    vol, meta = read_v3draw(original_path)
    print(f"  Volume shape: {vol.shape}, ndim={vol.ndim}, dtype={vol.dtype}")
    print(f"  Stats: min={meta['min']}, max={meta['max']}, mean={meta['mean']:.2f}")
else:
    print("  FILE NOT FOUND!")

# --- Global v3draw ---
global_path = SAMPLE_DIR / "registration" / "global" / "global.v3draw"
print("\n" + "=" * 60)
print("GLOBAL:", global_path)
if global_path.exists():
    h = read_v3draw_header(global_path)
    print(f"  Header: {h['width']}x{h['height']}x{h['depth']} C={h['channels']} dtype={h['dtype']}")
    print(f"  File size: {h['file_size']/1024/1024:.1f} MB, data_offset={h['data_offset']}")
    print(f"  Shape raw (X,Y,Z,C): {h['shape_raw']}")
    
    vol_g, meta_g = read_v3draw(global_path)
    print(f"  Volume shape: {vol_g.shape}, ndim={vol_g.ndim}, dtype={vol_g.dtype}")
    print(f"  Stats: min={meta_g['min']}, max={meta_g['max']}, mean={meta_g['mean']:.2f}")
    
    if vol_g.ndim == 4:
        print(f"\n  MULTI-CHANNEL detected ({vol_g.shape[0]} channels):")
        for ch in range(vol_g.shape[0]):
            ch_vol = vol_g[ch]
            print(f"    Ch{ch}: shape={ch_vol.shape}, min={ch_vol.min()}, max={ch_vol.max()}, "
                  f"mean={ch_vol.mean():.2f}, nonzero={np.count_nonzero(ch_vol)}/{ch_vol.size} "
                  f"({np.count_nonzero(ch_vol)/ch_vol.size*100:.1f}%)")
else:
    print("  FILE NOT FOUND!")

# --- 检查 global.nii.gz ---
global_nii = SAMPLE_DIR / "registration" / "global" / "global.nii.gz"
print("\n" + "=" * 60)
print("GLOBAL NII:", global_nii)
if global_nii.exists():
    import nibabel as nib
    nii = nib.load(str(global_nii))
    data = nii.get_fdata()
    print(f"  NIfTI data shape: {data.shape}, dtype={data.dtype}")
    print(f"  Affine:\n{nii.affine}")
    print(f"  Zooms: {nii.header.get_zooms()}")
    print(f"  Stats: min={data.min():.2f}, max={data.max():.2f}, mean={data.mean():.2f}")
    print(f"  NIfTI file size: {global_nii.stat().st_size/1024/1024:.1f} MB")
else:
    print("  FILE NOT FOUND!")

# --- 检查原图 nii.gz ---
orig_nii = SAMPLE_DIR / "converted" / "image.nii.gz"
print("\n" + "=" * 60)
print("ORIGINAL NII:", orig_nii)
if orig_nii.exists():
    import nibabel as nib
    nii2 = nib.load(str(orig_nii))
    data2 = nii2.get_fdata()
    print(f"  NIfTI data shape: {data2.shape}, dtype={data2.dtype}")
    print(f"  Affine:\n{nii2.affine}")
    print(f"  Zooms: {nii2.header.get_zooms()}")
    print(f"  Stats: min={data2.min():.2f}, max={data2.max():.2f}, mean={data2.mean():.2f}")
else:
    print("  FILE NOT FOUND!")

# --- 对比 preview 图片大小 ---
print("\n" + "=" * 60)
print("PREVIEW COMPARISON:")
for name in ["xy", "xz", "yz", "mip_xy", "mip_xz", "mip_yz"]:
    orig_p = SAMPLE_DIR / "viewer" / "previews" / f"{name}.png"
    glob_p = SAMPLE_DIR / "registration" / "global" / "previews" / f"{name}.png"
    orig_size = f"{orig_p.stat().st_size/1024:.1f}KB" if orig_p.exists() else "MISSING"
    glob_size = f"{glob_p.stat().st_size/1024:.1f}KB" if glob_p.exists() else "MISSING"
    
    # 也用 imageio 读一下看看图的尺寸
    if orig_p.exists() and glob_p.exists():
        import imageio.v2 as imageio
        io = imageio.imread(orig_p)
        ig = imageio.imread(glob_p)
        print(f"  {name:8s}: orig={io.shape} {orig_size:>10s}  |  global={ig.shape} {glob_size:>10s}")
    else:
        print(f"  {name:8s}: orig={orig_size}  |  global={glob_size}")

print("\nDONE!")
