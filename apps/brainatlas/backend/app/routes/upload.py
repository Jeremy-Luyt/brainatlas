from fastapi import APIRouter, File, UploadFile

from ..services.upload_service import save_upload


router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("")
def upload_file(file: UploadFile = File(...), project_id: str = "default") -> dict:
    return save_upload(file=file, project_id=project_id)
