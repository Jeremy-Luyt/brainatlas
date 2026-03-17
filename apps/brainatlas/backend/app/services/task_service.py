from datetime import datetime, timezone
from threading import Lock
from typing import Any
from uuid import uuid4


_lock = Lock()
_tasks: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_task(task_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    task_id = str(uuid4())
    task = {
        "task_id": task_id,
        "task_type": task_type,
        "status": "queued",
        "created_at": _now(),
        "updated_at": _now(),
        "payload": payload,
        "result": None,
    }
    with _lock:
        _tasks[task_id] = task
    return task


def update_task(task_id: str, status: str, result: dict[str, Any] | None = None) -> dict[str, Any]:
    with _lock:
        if task_id not in _tasks:
            raise KeyError(task_id)
        _tasks[task_id]["status"] = status
        _tasks[task_id]["updated_at"] = _now()
        if result is not None:
            _tasks[task_id]["result"] = result
        return dict(_tasks[task_id])


def get_task(task_id: str) -> dict[str, Any] | None:
    with _lock:
        task = _tasks.get(task_id)
        return dict(task) if task else None


def list_tasks() -> list[dict[str, Any]]:
    with _lock:
        return [dict(v) for v in _tasks.values()]
