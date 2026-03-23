from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.prepare_service import run_prepare
from ..utils.paths import project_workspace


router = APIRouter(prefix="/prepare", tags=["prepare"])


class PrepareRequest(BaseModel):
    sample_id: str


@router.post("")
def prepare(req: PrepareRequest) -> dict:
    try:
        return run_prepare(req.sample_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
