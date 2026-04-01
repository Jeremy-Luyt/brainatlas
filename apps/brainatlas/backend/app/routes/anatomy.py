"""解剖图谱路由 — 映射触发 / 脑区检索 / 切片叠加

端点:
  POST /api/anatomy/map                  触发 CCF → 模板映射
  GET  /api/anatomy/status               获取映射状态
  GET  /api/anatomy/regions/search       脑区检索 (中/英/缩写)
  GET  /api/anatomy/regions/{region_id}  单个脑区详情
  GET  /api/anatomy/regions/tree         脑区层级树
  GET  /api/anatomy/slice/{axis}/{index} 标注叠加切片 PNG
"""
from __future__ import annotations

import io
from pathlib import Path

import nibabel as nib
import numpy as np
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from ..services.anatomy_service import (
    get_mapping_status,
    get_mapped_region_stats,
    get_region_detail,
    run_anatomy_mapping_task,
    search_mapped_regions,
    _anatomy_dir,
)
from ..services.ccf_service import (
    CCF_REGIONS_INDEX,
    load_regions_index,
    search_regions as ccf_search_regions,
)
from ..services.task_runner import submit_task
from ..services.task_service import create_task
from ..utils.paths import project_workspace
from pipeline.atlas.template_version import latest_version


router = APIRouter(prefix="/anatomy", tags=["anatomy"])


# ---------------------------------------------------------------------------
#  映射触发 & 状态
# ---------------------------------------------------------------------------

class _MapRequest:
    pass


@router.post("/map")
def trigger_anatomy_mapping(
    project_id: str = "default",
    version: int | None = None,
) -> dict:
    """触发解剖标注映射 (后台任务)。version 留空自动选最新模板。"""
    pw = project_workspace(project_id)
    if version is None:
        version = latest_version(pw)
        if version < 0:
            raise HTTPException(400, "No template version found. Build template first.")

    template_nii = pw / "templates" / f"v{version}" / "template.nii.gz"
    if not template_nii.exists():
        raise HTTPException(404, f"template.nii.gz not found for v{version}")

    payload = {"project_id": project_id, "version": version}
    task = create_task(
        task_type="anatomy_mapping",
        payload=payload,
        project_id=project_id,
    )
    task_id = task["task_id"]
    payload["task_id"] = task_id
    submit_task("anatomy_mapping", task_id, project_id, payload)
    return {"status": "submitted", "task_id": task_id, "version": version}


@router.get("/status")
def anatomy_status(
    project_id: str = "default",
    version: int | None = None,
) -> dict:
    """获取解剖映射状态。"""
    pw = project_workspace(project_id)
    if version is None:
        version = latest_version(pw)
        if version < 0:
            return {"status": "no_template"}
    return get_mapping_status(project_id, version)


# ---------------------------------------------------------------------------
#  脑区检索
# ---------------------------------------------------------------------------

@router.get("/regions/search")
def search_regions_endpoint(
    q: str = Query("", min_length=0),
    project_id: str = "default",
    version: int | None = None,
    limit: int = Query(30, ge=1, le=200),
    source: str = Query("mapped", regex="^(mapped|ccf)$"),
) -> dict:
    """搜索脑区。source=mapped 从模板映射结果搜 (含体积), source=ccf 从 CCF 原索引搜。"""
    if source == "ccf":
        try:
            items = ccf_search_regions(q, limit=limit) if q else load_regions_index()[:limit]
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc))
        return {"query": q, "source": "ccf", "count": len(items), "items": items}

    pw = project_workspace(project_id)
    if version is None:
        version = latest_version(pw)
    if version < 0:
        raise HTTPException(400, "No template version found.")

    try:
        items = search_mapped_regions(project_id, version, q, limit=limit)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    return {
        "query": q,
        "source": "mapped",
        "version": version,
        "count": len(items),
        "items": items,
    }


@router.get("/regions/tree")
def region_tree(
    project_id: str = "default",
    version: int | None = None,
) -> dict:
    """返回脑区层级树 (用于前端树形展示)。"""
    pw = project_workspace(project_id)
    if version is None:
        version = latest_version(pw)
    if version < 0:
        raise HTTPException(400, "No template version found.")

    try:
        stats = get_mapped_region_stats(project_id, version)
    except FileNotFoundError:
        # 回退到 CCF 原索引
        try:
            stats = load_regions_index()
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc))

    # 构建 id → node 映射
    lookup = {r["id"]: {**r, "children": []} for r in stats}
    roots = []
    for r in stats:
        pid = r.get("parent_structure_id")
        if pid and pid in lookup:
            lookup[pid]["children"].append(lookup[r["id"]])
        else:
            roots.append(lookup[r["id"]])

    return {"version": version, "count": len(stats), "tree": roots}


@router.get("/regions/{region_id}")
def region_detail_endpoint(
    region_id: int,
    project_id: str = "default",
    version: int | None = None,
) -> dict:
    """获取单个脑区详情 (含体积、质心、子区域)。"""
    pw = project_workspace(project_id)
    if version is None:
        version = latest_version(pw)
    if version < 0:
        raise HTTPException(400, "No template version found.")

    try:
        return get_region_detail(project_id, version, region_id)
    except (FileNotFoundError, KeyError) as exc:
        raise HTTPException(404, str(exc))


# ---------------------------------------------------------------------------
#  切片叠加 (PNG)
# ---------------------------------------------------------------------------

@router.get("/slice/{axis}/{index}")
def annotation_slice(
    axis: str,
    index: int,
    project_id: str = "default",
    version: int | None = None,
    region_id: int | None = None,
    alpha: float = Query(0.4, ge=0.0, le=1.0),
) -> Response:
    """返回模板 + 标注叠加的 PNG 切片。

    axis: axial / coronal / sagittal
    index: 切片序号
    region_id: 可选, 仅高亮指定脑区
    """
    pw = project_workspace(project_id)
    if version is None:
        version = latest_version(pw)
    if version < 0:
        raise HTTPException(400, "No template version.")

    ver_dir = pw / "templates" / f"v{version}"
    tpl_nii = ver_dir / "template.nii.gz"
    ann_dir = ver_dir / "anatomy"
    ann_nii = ann_dir / "mapped_annotation.nii.gz"

    if not tpl_nii.exists():
        raise HTTPException(404, "Template NIfTI not found")
    if not ann_nii.exists():
        raise HTTPException(404, "Mapped annotation not found. Run anatomy mapping first.")

    tpl_img = nib.load(str(tpl_nii))
    tpl_data = tpl_img.get_fdata(dtype=np.float32)
    ann_img = nib.load(str(ann_nii))
    ann_data = np.asarray(ann_img.get_fdata(dtype=np.float32), dtype=np.int64)

    axis_map = {"axial": 2, "coronal": 1, "sagittal": 0}
    ax = axis_map.get(axis.lower())
    if ax is None:
        raise HTTPException(400, f"Unknown axis: {axis}. Use axial/coronal/sagittal")
    if index < 0 or index >= tpl_data.shape[ax]:
        raise HTTPException(400, f"Index {index} out of range [0, {tpl_data.shape[ax] - 1}]")

    slicing = [slice(None)] * 3
    slicing[ax] = index
    tpl_slice = tpl_data[tuple(slicing)]
    ann_slice = ann_data[tuple(slicing)]

    # 归一化模板切片到 0–255
    mn, mx = float(tpl_slice.min()), float(tpl_slice.max())
    if mx - mn > 1e-8:
        tpl_norm = ((tpl_slice - mn) / (mx - mn) * 255).astype(np.uint8)
    else:
        tpl_norm = np.zeros_like(tpl_slice, dtype=np.uint8)

    # 转 RGB
    rgb = np.stack([tpl_norm, tpl_norm, tpl_norm], axis=-1)

    # 叠加标注颜色
    if region_id is not None:
        mask = ann_slice == region_id
    else:
        mask = ann_slice > 0

    if np.any(mask):
        # 加载颜色映射
        color_map = _load_color_map()
        if region_id is not None:
            color = color_map.get(region_id, (78, 205, 196))
            overlay = np.zeros_like(rgb)
            overlay[mask] = color
        else:
            overlay = np.zeros_like(rgb)
            for rid in np.unique(ann_slice[mask]):
                rid = int(rid)
                rmask = ann_slice == rid
                overlay[rmask] = color_map.get(rid, (78, 205, 196))

        rgb = (rgb.astype(np.float32) * (1 - alpha) + overlay.astype(np.float32) * alpha).clip(0, 255).astype(np.uint8)

    # 编码 PNG
    from PIL import Image
    img = Image.fromarray(rgb)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


_cached_color_map: dict[int, tuple[int, int, int]] | None = None


def _load_color_map() -> dict[int, tuple[int, int, int]]:
    """从 CCF 索引加载 region_id → (R, G, B) 颜色映射。"""
    global _cached_color_map
    if _cached_color_map is not None:
        return _cached_color_map

    _cached_color_map = {}
    if not CCF_REGIONS_INDEX.exists():
        return _cached_color_map

    import json
    regions = json.loads(CCF_REGIONS_INDEX.read_text(encoding="utf-8"))
    for r in regions:
        hex_str = r.get("color_hex_triplet", "")
        if hex_str and len(hex_str) == 6:
            try:
                _cached_color_map[r["id"]] = (
                    int(hex_str[0:2], 16),
                    int(hex_str[2:4], 16),
                    int(hex_str[4:6], 16),
                )
            except ValueError:
                pass
    return _cached_color_map
