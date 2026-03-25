"""
session.py — 会话管理路由

端点：
- POST /api/session/cleanup
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from ..services.session_service import cleanup_current_session


router = APIRouter(prefix="/session", tags=["session"])


@router.post("/cleanup")
def cleanup(project_id: str = Query("default")) -> dict:
    """清理当前会话上传数据和产物。"""
    return cleanup_current_session(project_id)
