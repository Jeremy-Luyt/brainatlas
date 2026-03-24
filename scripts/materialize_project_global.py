from pathlib import Path
from pipeline.io import read_v3draw, save_nifti
from pipeline.preprocess.build_previews import build_previews_from_volume

root = Path(r"E:\workspace\brainatlas\data\projects\default\registration")
v3 = root / "global.v3draw"
nii = root / "global.nii.gz"
pre = root / "previews"

if not v3.exists():
    raise FileNotFoundError(str(v3))

vol, header = read_v3draw(v3)
save_nifti(vol, nii, spacing=header.get("voxel_size", [1.0, 1.0, 1.0]))
build_previews_from_volume(vol, pre)
print("OK", nii)
