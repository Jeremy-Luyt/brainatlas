"""
task_service.py — 任务元数据管理（持久化到 JSON）

职责：
- 创建/更新/查询任务
- 任务状态持久化到 data/projects/{project_id}/tasks/{task_id}/task.json
- 每个任务拥有独立的日志文件 task.log
- 线程安全
"""
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from ..utils.json_io import read_json, write_json
from ..utils.paths import project_workspace

_lock = Lock()

# 内存缓存：加速读取，持久化仍以 JSON 文件为准
_cache: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _task_dir(project_id: str, task_id: str) -> Path:
    d = project_workspace(project_id) / "tasks" / task_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _task_json_path(project_id: str, task_id: str) -> Path:
    return _task_dir(project_id, task_id) / "task.json"


def task_log_path(project_id: str, task_id: str) -> Path:
    """返回任务日志文件路径（供 task_runner 写入）"""
    return _task_dir(project_id, task_id) / "task.log"


def _persist(task: dict[str, Any]) -> None:
    """将任务写入 JSON 文件 + 更新内存缓存"""
    project_id = task.get("project_id", "default")
    task_id = task["task_id"]
    path = _task_json_path(project_id, task_id)
    write_json(path, task)
    _cache[task_id] = dict(task)


def create_task(
    task_type: str,
    payload: dict[str, Any],
    project_id: str = "default",
) -> dict[str, Any]:
    """创建新任务，立即持久化，返回 task 字典"""
    task_id = str(uuid4())
    task: dict[str, Any] = {
        "task_id": task_id,
        "project_id": project_id,
        "task_type": task_type,
        "status": "queued",
        "progress": None,
        "error_message": None,
        "created_at": _now(),
        "updated_at": _now(),
        "started_at": None,
        "finished_at": None,
        "payload": payload,
        "result": None,
        "log_file": None,  # 由 task_runner 填充
    }
    with _lock:
        _persist(task)
    return dict(task)


def update_task(
    task_id: str,
    *,
    status: str | None = None,
    result: dict[str, Any] | None = None,
    error_message: str | None = None,
    progress: str | None = None,
    log_file: str | None = None,
    project_id: str = "default",
) -> dict[str, Any]:
    """更新任务字段并持久化"""
    with _lock:
        task = _load_task(task_id, project_id)
        if task is None:
            raise KeyError(f"task not found: {task_id}")
        if status is not None:
            task["status"] = status
            if status == "running" and task.get("started_at") is None:
                task["started_at"] = _now()
            if status in ("completed", "failed", "cancelled"):
                task["finished_at"] = _now()
        if result is not None:
            task["result"] = result
        if error_message is not None:
            task["error_message"] = error_message
        if progress is not None:
            task["progress"] = progress
        if log_file is not None:
            task["log_file"] = log_file
        task["updated_at"] = _now()
        _persist(task)
        return dict(task)


def get_task(task_id: str, project_id: str = "default") -> dict[str, Any] | None:
    """获取单个任务"""
    with _lock:
        return _load_task(task_id, project_id)


def list_tasks(project_id: str = "default") -> list[dict[str, Any]]:
    """列出项目下所有任务（从文件系统扫描）"""
    tasks_root = project_workspace(project_id) / "tasks"
    if not tasks_root.exists():
        return []
    result = []
    for task_json in sorted(tasks_root.glob("*/task.json"),
                            key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            task = read_json(task_json)
            _cache[task["task_id"]] = task
            result.append(task)
        except Exception:
            continue
    return result


def list_tasks_by_status(
    project_id: str = "default",
    status: str | None = None,
) -> list[dict[str, Any]]:
    """按状态过滤任务列表"""
    all_tasks = list_tasks(project_id)
    if status is None:
        return all_tasks
    return [t for t in all_tasks if t.get("status") == status]


def _load_task(task_id: str, project_id: str = "default") -> dict[str, Any] | None:
    """从缓存或文件加载任务（内部方法，调用方需持有 _lock）"""
    if task_id in _cache:
        return dict(_cache[task_id])
    path = _task_json_path(project_id, task_id)
    if path.exists():
        try:
            task = read_json(path)
            _cache[task_id] = task
            return dict(task)
        except Exception:
            return None
    return None
