"""mesh.py — GLB 网格生成 & 分发

端点：
- GET /api/mesh/template/{version}             模板 GLB
- GET /api/mesh/sample/{sample_id}/global      样本 global 配准 GLB
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..utils.paths import project_workspace, data_root
from pipeline.atlas.template_version import version_dir
from pipeline.atlas.mesh_generator import ensure_glb

router = APIRouter(prefix="/mesh", tags=["mesh"])


@router.get("/template/{version}")
def template_mesh(version: int, project_id: str = "default"):
    """返回模板版本的 GLB 网格（按需生成 + 缓存）。"""
    pw = project_workspace(project_id)
    ver = version_dir(pw, version)
    nii = ver / "template.nii.gz"
    if not nii.exists():
        raise HTTPException(404, f"template.nii.gz not found for v{version}")
    glb = ensure_glb(nii, target_faces=150_000, smooth_iterations=40)
    return FileResponse(str(glb), media_type="model/gltf-binary",
                        filename=f"template_v{version}.glb")


@router.get("/sample/{sample_id}/global")
def sample_global_mesh(sample_id: str, project_id: str = "default"):
    """返回样本 global 配准结果的 GLB 网格。"""
    pw = project_workspace(project_id)
    nii = pw / "samples" / sample_id / "registration" / "global" / "global.nii.gz"
    if not nii.exists():
        raise HTTPException(404, f"global.nii.gz not found for sample {sample_id}")
    glb = ensure_glb(nii, target_faces=100_000, smooth_iterations=30)
    return FileResponse(str(glb), media_type="model/gltf-binary",
                        filename=f"{sample_id}_global.glb")
