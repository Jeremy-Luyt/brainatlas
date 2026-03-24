import mimetypes

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .routes.health import router as health_router
from .routes.prepare import router as prepare_router
from .routes.projects import router as projects_router
from .routes.registration import router as registration_router
from .routes.results import router as results_router
from .routes.samples import router as samples_router
from .routes.tasks import router as tasks_router
from .routes.upload import router as upload_router
from .utils.paths import data_root

# 修正 Windows 上 .gz 的 MIME 类型，确保 NiiVue 能识别体数据
mimetypes.add_type("application/gzip", ".gz")
mimetypes.add_type("application/octet-stream", ".nii")

app = FastAPI(title="BrainAtlas API", version="0.2.0")

# ---------- 路由注册 ----------
app.include_router(health_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
app.include_router(prepare_router, prefix="/api")
app.include_router(projects_router, prefix="/api")
app.include_router(registration_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")
app.include_router(samples_router, prefix="/api")
app.include_router(results_router, prefix="/api")

# ---------- 注册后台任务处理器 ----------
from .services.task_runner import register_handler  # noqa: E402
from .services.registration_service import run_global_registration_task  # noqa: E402
from .services.prepare_service import run_prepare_task  # noqa: E402

register_handler("global_registration", run_global_registration_task)
register_handler("sample_prepare", run_prepare_task)

_frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
_upload_file = _frontend_dir / "upload" / "index.html"
if not _upload_file.exists():
    _upload_file = _frontend_dir / "upload" / "upload.html"
_viewer_file = _frontend_dir / "viewer" / "index.html"
if not _viewer_file.exists():
    _viewer_file = _frontend_dir / "viewer" / "viewer.html"
app.mount("/assets", StaticFiles(directory=str(_frontend_dir / "assets")), name="assets")
app.mount("/static", StaticFiles(directory=str(_frontend_dir / "assets")), name="static")
app.mount("/api/static", StaticFiles(directory=str(data_root())), name="api-static")


@app.get("/upload", include_in_schema=False)
def upload_page() -> FileResponse:
    return FileResponse(_upload_file)


@app.get("/viewer", include_in_schema=False)
def viewer_page() -> FileResponse:
    return FileResponse(_viewer_file)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/upload")
