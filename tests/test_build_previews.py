from pathlib import Path

from pipeline.preprocess.build_previews import build_previews_from_nifti

nii_path = r"data\temp\converted\test_output.nii.gz"
out_dir = r"data\temp\previews"

result = build_previews_from_nifti(nii_path, out_dir)

print("===== PREVIEW RESULT =====")
print("shape_out =", result["shape_out"])
print("dtype =", result["dtype"])
print("spacing =", result["spacing"])

print("\npreview files:")
for k, v in result["preview_paths"].items():
    print(k, "->", v, "| exists =", Path(v).exists())
    