import mimetypes
import os
                                                                                                                                                   
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .routes.health import router as health_router
from .routes.batch import router as batch_router
from .routes.prepare import router as prepare_router
from .routes.projects import router as projects_router
from .routes.qc import router as qc_router
from .routes.registration import router as registration_router
from .routes.results import router as results_router
from .routes.samples import router as samples_router
from .routes.scan import router as scan_router
from .routes.session import router as session_router
from .routes.tasks import router as tasks_router
from .routes.template import router as template_router
from .routes.upload import router as upload_router
from .routes.mesh import router as mesh_router
from .routes.ccf import router as ccf_router
from .routes.anatomy import router as anatomy_router
from .services.session_service import cleanup_current_session
from .services.task_service import list_tasks, update_task
from .services.task_runner import is_task_alive
from .utils.paths import data_root

# 修正 Windows 上 .gz 的 MIME 类型，确保 NiiVue 能识别体数据
mimetypes.add_type("application/gzip", ".gz")
mimetypes.add_type("application/octet-stream", ".nii")

app = FastAPI(title="BrainAtlas API", version="0.2.0")

# ---------- 路由注册 ----------
app.include_router(health_router, prefix="/api")
app.include_router(batch_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
app.include_router(prepare_router, prefix="/api")
app.include_router(projects_router, prefix="/api")
app.include_router(qc_router, prefix="/api")
app.include_router(registration_router, prefix="/api")
app.include_router(scan_router, prefix="/api")
app.include_router(session_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")
app.include_router(samples_router, prefix="/api")
app.include_router(results_router, prefix="/api")
app.include_router(template_router, prefix="/api")
app.include_router(mesh_router, prefix="/api")
app.include_router(ccf_router, prefix="/api")
app.include_router(anatomy_router, prefix="/api")


@app.on_event("startup")
def startup_cleanup() -> None:
    """
    启动时清理上次会话数据（默认开启）。
    可通过 BRAINATLAS_AUTO_CLEAN_SESSION_ON_START=0 关闭。
    使用标记文件防止 --reload 热重载时反复清理。
    """
    # 总是清理僵尸任务（根据 heartbeat 判断: 有心跳的任务保留, 无心跳的标记失败）
    try:
        for t in list_tasks("default"):
            if t.get("status") in ("running", "queued"):
                tid = t["task_id"]
                if is_task_alive("default", tid):
                    print(f"[startup] task {tid[:8]} still alive (heartbeat ok), keeping")
                else:
                    update_task(
                        tid,
                        status="failed",
                        error_message="server restarted, task aborted (no heartbeat)",
                        project_id="default",
                    )
                    print(f"[startup] zombie task {tid[:8]} marked failed")
        print("[startup] zombie task check done")
    except Exception as exc:
        print(f"[startup] zombie task cleanup failed: {exc}")

    auto_clean = os.getenv("BRAINATLAS_AUTO_CLEAN_SESSION_ON_START", "1")
    if auto_clean not in {"1", "true", "TRUE", "yes", "YES"}:
        return

    # 防止 --reload 热重载时重复清理：使用标记文件 + 父进程 PID
    # (uvicorn --reload 会复用同一父进程, 真正重启时父进程 PID 不同)
    sentinel = data_root() / "temp" / ".startup_cleaned"
    ppid = str(os.getppid())
    if sentinel.exists():
        old_ppid = sentinel.read_text(encoding="utf-8").strip()
        if old_ppid == ppid:
            print(f"[startup] skip cleanup (same reloader ppid={ppid})")
            return
        print(f"[startup] new session detected (old ppid={old_ppid}, cur ppid={ppid})")

    try:
        cleanup_current_session("default", include_project=True)
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text(ppid, encoding="utf-8")
        print(f"[startup] session cleanup completed for project=default (ppid={ppid})")
    except Exception as exc:
        print(f"[startup] session cleanup failed: {exc}")

# ---------- 注册后台任务处理器 ----------
from .services.task_runner import register_handler  # noqa: E402
from .services.registration_service import run_global_registration_task  # noqa: E402
from .services.prepare_service import run_prepare_task  # noqa: E402
from .services.template_service import run_template_build_task  # noqa: E402

from .services.anatomy_service import run_anatomy_mapping_task  # noqa: E402

register_handler("global_registration", run_global_registration_task)
register_handler("sample_prepare", run_prepare_task)
register_handler("template_build", run_template_build_task)
register_handler("anatomy_mapping", run_anatomy_mapping_task)

_frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
_upload_file = _frontend_dir / "upload" / "index.html"
if not _upload_file.exists():
    _upload_file = _frontend_dir / "upload" / "upload.html"
_viewer_file = _frontend_dir / "viewer" / "index.html"
if not _viewer_file.exists():
    _viewer_file = _frontend_dir / "viewer" / "viewer.html"
_monitor_file = _frontend_dir / "monitor" / "index.html"
if not _monitor_file.exists():
    _monitor_file = _frontend_dir / "monitor" / "monitor.html"
_atlas_file = _frontend_dir / "atlas" / "index.html"
if not _atlas_file.exists():
    _atlas_file = _frontend_dir / "atlas" / "atlas.html"
app.mount("/assets", StaticFiles(directory=str(_frontend_dir / "assets")), name="assets")
app.mount("/static", StaticFiles(directory=str(_frontend_dir / "assets")), name="static")
app.mount("/api/static", StaticFiles(directory=str(data_root())), name="api-static")


@app.get("/upload", include_in_schema=False)
def upload_page() -> FileResponse:
    return FileResponse(_upload_file)


@app.get("/monitor", include_in_schema=False)
def monitor_page() -> FileResponse:
    return FileResponse(str(_monitor_file))


@app.get("/viewer", include_in_schema=False)
def viewer_page() -> FileResponse:
    return FileResponse(_viewer_file)


@app.get("/atlas", include_in_schema=False)
def atlas_page() -> FileResponse:
    return FileResponse(str(_atlas_file))


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/upload")
