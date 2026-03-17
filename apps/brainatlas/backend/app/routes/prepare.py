from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.prepare_service import prepare_preview
from ..utils.paths import project_workspace


router = APIRouter(prefix="/prepare", tags=["prepare"])


class PrepareRequest(BaseModel):
    project_id: str = "default"
    input_path: str


@router.post("")
def prepare(req: PrepareRequest) -> dict:
    input_path = Path(req.input_path)
    if not input_path.exists():
        raise HTTPException(status_code=404, detail="input_path not found")
    output_dir = project_workspace(req.project_id) / "previews"
    return prepare_preview(input_path=input_path, output_dir=output_dir)
