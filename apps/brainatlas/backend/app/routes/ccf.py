"""CCF 脑区查询与 3D 网格接口。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from ..services.ccf_service import (
    CCF_ANNOTATION_NII,
    CCF_REGION_MESH_CACHE,
    ccf_status,
    get_region,
    search_regions,
)
from pipeline.atlas.region_mesh import ensure_region_glb


router = APIRouter(prefix="/ccf", tags=["ccf"])


@router.get("/status")
def ccf_status_endpoint() -> dict:
    return ccf_status()


@router.get("/regions/search")
def search_regions_endpoint(
    q: str = Query(..., min_length=1),
    limit: int = Query(30, ge=1, le=100),
) -> dict:
    try:
        items = search_regions(q, limit=limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"query": q, "count": len(items), "items": items}


@router.get("/regions/{region_id}")
def region_detail_endpoint(region_id: int) -> dict:
    try:
        return get_region(region_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/mesh/{region_id}")
def region_mesh_endpoint(region_id: int):
    if not CCF_ANNOTATION_NII.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"annotation NIfTI missing: {CCF_ANNOTATION_NII}. "
                "Run scripts/download_ccf_resources.py first."
            ),
        )

    try:
        glb = ensure_region_glb(
            CCF_ANNOTATION_NII,
            region_id,
            CCF_REGION_MESH_CACHE,
            target_faces=60_000,
            smooth_iterations=8,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return FileResponse(
        str(glb),
        media_type="model/gltf-binary",
        filename=f"ccf_region_{region_id}.glb",
    )
