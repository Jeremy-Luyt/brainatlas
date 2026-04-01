"""后台任务执行器: 独立进程隔离 + 结构化日志 + heartbeat 存活检测

重型任务 (global_registration, template_build) 在独立子进程中运行，
使得 uvicorn --reload 不会杀死正在执行的长时任务。
轻量任务仍在 daemon 线程中执行。

进程间通过 JSON 文件通信: 子进程写 result.json / error.json,
监控线程轮询读取并更新 task_service。
每个运行中的任务通过 heartbeat 文件维持心跳 (每 30 秒更新)，
startup 时据此判断僵尸 vs. 仍存活的任务。
"""
from __future__ import annotations

import json
import logging
import multiprocessing
import os
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .task_service import update_task, task_log_path

logger = logging.getLogger(__name__)

# 注册的任务处理函数
_handlers: dict[str, Callable[..., dict[str, Any]]] = {}

# ---------------------------------------------------------------------------
#  并发控制：重型任务（如配准 exe）同时只允许 1 个执行
# ---------------------------------------------------------------------------
_heavy_semaphore = threading.Semaphore(1)
_HEAVY_TASK_TYPES: set[str] = {"global_registration", "template_build"}

# heartbeat 间隔 (秒)
HEARTBEAT_INTERVAL: int = 30
# 超过此时间无心跳视为僵尸 (秒)
HEARTBEAT_TIMEOUT: int = 120


# ═══════════════════════ Heartbeat ════════════════════════════

def heartbeat_path(project_id: str, task_id: str) -> Path:
    """返回 heartbeat 文件路径"""
    return task_log_path(project_id, task_id).parent / ".heartbeat"


def write_heartbeat(hb_path: Path) -> None:
    """写入当前时间戳到 heartbeat 文件"""
    hb_path.parent.mkdir(parents=True, exist_ok=True)
    hb_path.write_text(str(time.time()), encoding="utf-8")


def read_heartbeat(hb_path: Path) -> float | None:
    """读取 heartbeat 时间戳, 不存在或读取失败返回 None"""
    try:
        if hb_path.exists():
            return float(hb_path.read_text(encoding="utf-8").strip())
    except Exception:
        pass
    return None


def is_task_alive(project_id: str, task_id: str) -> bool:
    """根据 heartbeat 判断任务是否仍在运行"""
    hb = read_heartbeat(heartbeat_path(project_id, task_id))
    if hb is None:
        return False
    return (time.time() - hb) < HEARTBEAT_TIMEOUT


class _HeartbeatThread(threading.Thread):
    """后台线程: 定期更新 heartbeat 文件"""

    def __init__(self, hb_path: Path):
        super().__init__(daemon=True, name="heartbeat")
        self._hb_path = hb_path
        self._stop_event = threading.Event()

    def run(self) -> None:
        while not self._stop_event.is_set():
            write_heartbeat(self._hb_path)
            self._stop_event.wait(HEARTBEAT_INTERVAL)

    def stop(self) -> None:
        self._stop_event.set()


# ═══════════════════════ TaskLogger ═══════════════════════════

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


# ═══════════════════════ 子进程入口 ════════════════════════════

def _subprocess_entry(
    handler_module: str,
    handler_qualname: str,
    payload: dict[str, Any],
    log_path_str: str,
    result_path_str: str,
    error_path_str: str,
    hb_path_str: str,
) -> None:
    """
    在独立子进程中执行 handler。
    通过 JSON 文件返回结果/错误，通过 heartbeat 文件报告存活。
    """
    import importlib

    log_path = Path(log_path_str)
    result_path = Path(result_path_str)
    error_path = Path(error_path_str)
    hb_path = Path(hb_path_str)

    tl = TaskLogger(log_path)
    hb = _HeartbeatThread(hb_path)
    hb.start()

    try:
        # 动态导入 handler
        mod = importlib.import_module(handler_module)
        handler_fn = getattr(mod, handler_qualname)

        tl.info(f"Subprocess started (pid={os.getpid()})")
        tl.info(f"Payload: {payload}")

        result = handler_fn(payload, tl)

        result_path.write_text(
            json.dumps(result, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        tl.info("Task completed successfully")

    except Exception as e:
        error_msg = str(e)
        tb = traceback.format_exc()
        tl.error(f"Task failed: {error_msg}")
        tl.error(tb)
        error_path.write_text(
            json.dumps({"error": error_msg, "traceback": tb}, ensure_ascii=False),
            encoding="utf-8",
        )
    finally:
        hb.stop()
        tl.close()


# ═══════════════════════ 提交 & 执行 ══════════════════════════

def submit_task(
    task_type: str,
    task_id: str,
    project_id: str,
    payload: dict[str, Any],
) -> None:
    """提交任务: 重型任务走子进程, 轻量任务走线程"""
    if task_type in _HEAVY_TASK_TYPES:
        t = threading.Thread(
            target=_run_task_in_process,
            args=(task_type, task_id, project_id, payload),
            name=f"task-monitor-{task_id[:8]}",
            daemon=True,
        )
    else:
        t = threading.Thread(
            target=_run_task_in_thread,
            args=(task_type, task_id, project_id, payload),
            name=f"task-{task_type}-{task_id[:8]}",
            daemon=True,
        )
    t.start()


def _run_task_in_process(
    task_type: str,
    task_id: str,
    project_id: str,
    payload: dict[str, Any],
) -> None:
    """
    监控线程: 启动子进程执行重型任务, 轮询等待完成。
    uvicorn --reload 只会杀死本守护线程, 子进程不受影响。
    """
    log_path = task_log_path(project_id, task_id)
    task_dir = log_path.parent
    result_path = task_dir / "result.json"
    error_path = task_dir / "error.json"
    hb_path = heartbeat_path(project_id, task_id)

    # 清除上次残留
    for p in (result_path, error_path):
        if p.exists():
            p.unlink()

    try:
        # 串行控制: 重型任务排队
        update_task(
            task_id,
            status="queued",
            progress="waiting",
            log_file=str(log_path),
            project_id=project_id,
        )
        _heavy_semaphore.acquire()

        update_task(
            task_id,
            status="running",
            progress="running",
            project_id=project_id,
        )

        # 获取 handler 的模块/名称供子进程导入
        handler = _handlers.get(task_type)
        if handler is None:
            raise ValueError(f"No handler registered for task type: {task_type}")

        handler_module = handler.__module__
        handler_qualname = handler.__qualname__

        # 启动独立子进程
        proc = multiprocessing.Process(
            target=_subprocess_entry,
            args=(
                handler_module,
                handler_qualname,
                payload,
                str(log_path),
                str(result_path),
                str(error_path),
                str(hb_path),
            ),
            name=f"task-{task_type}-{task_id[:8]}",
            daemon=False,  # 非守护进程: uvicorn 重启不会杀它
        )
        proc.start()
        logger.info(
            f"Heavy task {task_id[:8]} started in subprocess pid={proc.pid}"
        )

        # 轮询等待子进程完成 (同时维护信号量)
        while proc.is_alive():
            proc.join(timeout=5.0)

        # 子进程结束, 读取结果
        if result_path.exists():
            result = json.loads(result_path.read_text(encoding="utf-8"))
            update_task(
                task_id,
                status="completed",
                result=result,
                project_id=project_id,
            )
        elif error_path.exists():
            err = json.loads(error_path.read_text(encoding="utf-8"))
            update_task(
                task_id,
                status="failed",
                error_message=err.get("error", "unknown error"),
                result=err,
                project_id=project_id,
            )
        else:
            # 子进程异常退出, 无输出文件
            update_task(
                task_id,
                status="failed",
                error_message=f"subprocess exited with code {proc.exitcode}, no output",
                project_id=project_id,
            )

    except Exception as e:
        error_msg = str(e)
        tb = traceback.format_exc()
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
        _heavy_semaphore.release()


def _run_task_in_thread(
    task_type: str,
    task_id: str,
    project_id: str,
    payload: dict[str, Any],
) -> None:
    """线程入口: 轻量任务在当前进程 daemon 线程中执行"""
    log_path = task_log_path(project_id, task_id)
    tl = TaskLogger(log_path)
    hb = _HeartbeatThread(heartbeat_path(project_id, task_id))
    hb.start()

    try:
        update_task(
            task_id,
            status="running",
            progress="running",
            log_file=str(log_path),
            project_id=project_id,
        )
        tl.info(f"Task started: type={task_type}, id={task_id}")
        tl.info(f"Payload: {payload}")

        handler = _handlers.get(task_type)
        if handler is None:
            raise ValueError(f"No handler registered for task type: {task_type}")

        result = handler(payload, tl)

        update_task(
            task_id,
            status="completed",
            result=result,
            project_id=project_id,
        )
        tl.info("Task completed successfully")

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
        hb.stop()
        tl.close()
