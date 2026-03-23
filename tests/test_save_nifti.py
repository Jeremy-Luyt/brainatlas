from pathlib import Path
import numpy as np

from pipeline.io.reader_v3draw import read_v3draw
from pipeline.io.nii_io import save_nifti, load_nifti

v3draw_path = r"data\demo_inputs\test.v3draw"
nii_path = r"data\temp\test_output.nii.gz"

volume, meta = read_v3draw(v3draw_path)

print("===== ORIGINAL =====")
print("shape =", volume.shape)
print("dtype =", volume.dtype)
print("min =", volume.min())
print("max =", volume.max())
print("mean =", volume.mean())

save_nifti(volume, nii_path, spacing=(1.0, 1.0, 1.0))

print("\nNIfTI saved to:", nii_path)
print("exists =", Path(nii_path).exists())

volume2, meta2 = load_nifti(nii_path)

print("\n===== LOADED BACK =====")
print("shape =", volume2.shape)
print("dtype =", volume2.dtype)
print("min =", volume2.min())
print("max =", volume2.max())
print("mean =", volume2.mean())
print("spacing =", meta2["spacing"])

# 基本一致性检查
print("\n===== CHECK =====")
print("same shape =", volume.shape == volume2.shape)

diff = np.abs(volume.astype(np.float32) - volume2.astype(np.float32))
print("mean abs diff =", float(diff.mean()))
print("max abs diff =", float(diff.max()))
