"""CCF 资源读取与脑区检索。"""
from __future__ import annotations

import json
from pathlib import Path

from ..utils.paths import data_root


CCF_ROOT = data_root() / "ccf"
CCF_REGIONS_INDEX = CCF_ROOT / "ccf_regions_index.json"
CCF_STRUCTURE_TREE = CCF_ROOT / "structure_graph_1.json"
CCF_ANNOTATION_NII = CCF_ROOT / "annotation_25.nii.gz"
CCF_ANATOMICAL_NII = CCF_ROOT / "ara_nissl_25.nii.gz"
CCF_REGION_MESH_CACHE = CCF_ROOT / "cache" / "region_meshes"


def ccf_status() -> dict:
    return {
        "ccf_root": str(CCF_ROOT),
        "annotation_nii": CCF_ANNOTATION_NII.exists(),
        "anatomical_nii": CCF_ANATOMICAL_NII.exists(),
        "regions_index": CCF_REGIONS_INDEX.exists(),
        "structure_tree": CCF_STRUCTURE_TREE.exists(),
    }


def load_regions_index() -> list[dict]:
    if not CCF_REGIONS_INDEX.exists():
        raise FileNotFoundError(
            f"regions index missing: {CCF_REGIONS_INDEX}. Run scripts/download_ccf_resources.py first."
        )
    return json.loads(CCF_REGIONS_INDEX.read_text(encoding="utf-8"))


def search_regions(query: str, limit: int = 30) -> list[dict]:
    q = (query or "").strip().lower()
    if not q:
        return []

    rows = load_regions_index()
    out: list[dict] = []
    for row in rows:
        name = str(row.get("name", "")).lower()
        acronym = str(row.get("acronym", "")).lower()
        name_zh = str(row.get("name_zh", "")).lower()
        if q in name or q in acronym or (name_zh and q in name_zh):
            out.append(row)
            if len(out) >= max(1, min(limit, 100)):
                break
    return out


def get_region(region_id: int) -> dict:
    rows = load_regions_index()
    for row in rows:
        if int(row.get("id", -1)) == int(region_id):
            return row
    raise KeyError(f"region id {region_id} not found")
