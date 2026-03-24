"""
task_runner.py — 后台任务执行器

职责：
- 在独立线程中执行耗时任务（global registration 等）
- 写入结构化日志文件
- 完成后更新 task 和 sample 状态
- 统一的异常处理

用法：
    from .task_runner import submit_task
    submit_task("global_registration", task_id, project_id, payload)
"""
from __future__ import annotations

import logging
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .task_service import update_task, task_log_path

logger = logging.getLogger(__name__)

# 注册的任务处理函数
_handlers: dict[str, Callable[..., dict[str, Any]]] = {}


class TaskLogger:
    """
    将日志同时写入文件和 Python logger。
    每个任务一个实例，写入 tasks/{task_id}/task.log
    """

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.log_path.open("a", encoding="utf-8")

    def info(self, msg: str) -> None:
        self._write("INFO", msg)

    def error(self, msg: str) -> None:
        self._write("ERROR", msg)

    def _write(self, level: str, msg: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] [{level}] {msg}\n"
        self._file.write(line)
        self._file.flush()

    def close(self) -> None:
        try:
            self._file.close()
        except Exception:
            pass


def register_handler(task_type: str, handler: Callable[..., dict[str, Any]]) -> None:
    """注册任务类型的处理函数。handler 签名: (payload, task_logger) -> result_dict"""
    _handlers[task_type] = handler


def submit_task(
    task_type: str,
    task_id: str,
    project_id: str,
    payload: dict[str, Any],
) -> None:
    """提交任务到后台线程执行"""
    t = threading.Thread(
        target=_run_task,
        args=(task_type, task_id, project_id, payload),
        name=f"task-{task_type}-{task_id[:8]}",
        daemon=True,
    )
    t.start()


def _run_task(
    task_type: str,
    task_id: str,
    project_id: str,
    payload: dict[str, Any],
) -> None:
    """线程入口：执行任务并管理生命周期"""
    log_path = task_log_path(project_id, task_id)
    tl = TaskLogger(log_path)

    try:
        # 更新状态为 running
        update_task(
            task_id,
            status="running",
            log_file=str(log_path),
            project_id=project_id,
        )
        tl.info(f"Task started: type={task_type}, id={task_id}")
        tl.info(f"Payload: {payload}")

        handler = _handlers.get(task_type)
        if handler is None:
            raise ValueError(f"No handler registered for task type: {task_type}")

        # 执行实际处理
        result = handler(payload, tl)

        # 成功
        update_task(
            task_id,
            status="completed",
            result=result,
            project_id=project_id,
        )
        tl.info(f"Task completed successfully")

    except Exception as e:
        error_msg = str(e)
        tb = traceback.format_exc()
        tl.error(f"Task failed: {error_msg}")
        tl.error(tb)
        logger.error(f"Task {task_id} failed: {error_msg}")
        try:
            update_task(
                task_id,
                status="failed",
                error_message=error_msg,
                result={"error": error_msg, "traceback": tb},
                project_id=project_id,
            )
        except Exception:
            pass
    finally:
        tl.close()
