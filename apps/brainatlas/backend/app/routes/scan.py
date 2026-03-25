"""
scan.py — 文件夹扫描路由

端点：
- POST /api/scan    扫描文件夹，懒加载索引脑影像
- GET  /api/scan/formats  返回支持的文件格式列表
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.scan_service import scan_folder

router = APIRouter(prefix="/scan", tags=["scan"])


class ScanRequest(BaseModel):
    folder_path: str
    project_id: str = "default"
    recursive: bool = True


@router.post("")
def scan(req: ScanRequest) -> dict:
    try:
        return scan_folder(req.folder_path, req.project_id, req.recursive)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError:
        raise HTTPException(status_code=403, detail="无权访问该文件夹")


@router.get("/formats")
def supported_formats() -> dict:
    return {
        "formats": [
            {"ext": ".v3draw", "label": "Vaa3D 体数据"},
            {"ext": ".nii / .nii.gz", "label": "NIfTI 体数据"},
            {"ext": ".tif / .tiff", "label": "TIFF 切片栈"},
            {"ext": ".mhd / .mha", "label": "MetaImage 体数据"},
            {"ext": ".nrrd", "label": "NRRD 体数据"},
        ]
    }
