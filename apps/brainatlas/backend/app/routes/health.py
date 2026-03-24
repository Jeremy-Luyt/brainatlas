"""
health.py — 健康检查路由

端点：
- GET /api/health    基础健康检查
"""
from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.2.0"}
