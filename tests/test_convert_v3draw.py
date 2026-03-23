from pathlib import Path
import json

from pipeline.io.converter import convert_v3draw_to_nifti

v3draw_path = r"data\demo_inputs\test.v3draw"
nii_path = r"data\temp\converted\test_output.nii.gz"
meta_path = r"data\temp\converted\test_output_meta.json"

result = convert_v3draw_to_nifti(
    v3draw_path=v3draw_path,
    nii_path=nii_path,
    meta_path=meta_path,
    spacing=(1.0, 1.0, 1.0),
)

print("===== CONVERT RESULT =====")
print(result)

print("\nfiles exist:")
print("nii exists =", Path(nii_path).exists())
print("meta exists =", Path(meta_path).exists())

with open(meta_path, "r", encoding="utf-8") as f:
    meta = json.load(f)

print("\n===== META JSON =====")
print("shape_out =", meta.get("shape_out"))
print("dtype =", meta.get("dtype"))
print("min =", meta.get("min"))
print("max =", meta.get("max"))
print("mean =", meta.get("mean"))
