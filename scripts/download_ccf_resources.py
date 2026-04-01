"""下载 CCF 解剖模板 / 注释体 / 结构树，并生成本地脑区索引。"""
from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

import nibabel as nib
import numpy as np


BASE = "https://download.alleninstitute.org/informatics-archive/current-release/mouse_ccf"
DEFAULT_RES = 25
DEFAULT_CCF_YEAR = "ccf_2017"
STRUCTURE_TREE_URL = "http://api.brain-map.org/api/v2/structure_graph_download/1.json"


def _download(url: str, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        print(f"[skip] {dst.name} already exists")
        return
    print(f"[download] {url}")
    urllib.request.urlretrieve(url, dst)
    print(f"[saved] {dst}")


def _nrrd_to_nifti(nrrd_path: Path, nii_path: Path) -> None:
    import nrrd

    data, header = nrrd.read(str(nrrd_path))
    data = np.asarray(data)

    # Allen CCF 分辨率是 um，转换为 mm。
    spacing_mm = 0.025
    space_dirs = header.get("space directions")
    if isinstance(space_dirs, (list, tuple)) and len(space_dirs) >= 3:
        try:
            norms = []
            for d in space_dirs[:3]:
                arr = np.asarray(d, dtype=np.float64)
                norms.append(float(np.linalg.norm(arr)))
            if all(v > 0 for v in norms):
                spacing_mm = norms[0] / 1000.0 if norms[0] > 1 else norms[0]
        except Exception:
            pass

    affine = np.diag([spacing_mm, spacing_mm, spacing_mm, 1.0])
    img = nib.Nifti1Image(data, affine=affine)
    nii_path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(img, str(nii_path))
    print(f"[converted] {nrrd_path.name} -> {nii_path.name}")


def _flatten_tree(node: dict, out: list[dict]) -> None:
    out.append(
        {
            "id": node.get("id"),
            "acronym": node.get("acronym", ""),
            "name": node.get("name", ""),
            "name_zh": "",
            "color_hex_triplet": node.get("color_hex_triplet", ""),
            "parent_structure_id": node.get("parent_structure_id"),
            "st_level": node.get("st_level"),
        }
    )
    for child in node.get("children", []):
        _flatten_tree(child, out)


def _build_regions_index(structure_tree_json: Path, out_json: Path) -> None:
    payload = json.loads(structure_tree_json.read_text(encoding="utf-8"))
    roots = payload.get("msg", [])
    rows: list[dict] = []
    for root in roots:
        _flatten_tree(root, rows)
    rows.sort(key=lambda x: int(x.get("id") or 0))
    out_json.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[index] {out_json} ({len(rows)} regions)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resolution", type=int, default=DEFAULT_RES, choices=[10, 25, 50, 100])
    parser.add_argument("--ccf-year", default=DEFAULT_CCF_YEAR)
    parser.add_argument("--out-dir", default="tools/templates/ccf_25um")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    res = int(args.resolution)
    year = str(args.ccf_year)

    annotation_nrrd_url = f"{BASE}/annotation/{year}/annotation_{res}.nrrd"
    anatomical_nrrd_url = f"{BASE}/ara_nissl/ara_nissl_{res}.nrrd"

    annotation_nrrd = out_dir / f"annotation_{res}.nrrd"
    anatomical_nrrd = out_dir / f"ara_nissl_{res}.nrrd"
    structure_tree_json = out_dir / "structure_graph_1.json"

    _download(annotation_nrrd_url, annotation_nrrd)
    _download(anatomical_nrrd_url, anatomical_nrrd)
    _download(STRUCTURE_TREE_URL, structure_tree_json)

    try:
        _nrrd_to_nifti(annotation_nrrd, out_dir / f"annotation_{res}.nii.gz")
        _nrrd_to_nifti(anatomical_nrrd, out_dir / f"ara_nissl_{res}.nii.gz")
    except Exception as exc:
        print(f"[warn] NRRD->NIfTI convert failed: {exc}")
        print("[hint] pip install pynrrd")

    _build_regions_index(structure_tree_json, out_dir / "ccf_regions_index.json")
    print("[done] CCF resources prepared.")


if __name__ == "__main__":
    main()
