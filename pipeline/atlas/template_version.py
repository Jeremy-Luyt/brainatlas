"""模板版本管理: templates/v{k}/ 目录结构"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def template_base_dir(project_dir: Path) -> Path:
    """返回项目的 templates 根目录。"""
    return project_dir / "templates"


def version_dir(project_dir: Path, version: int) -> Path:
    """返回指定版本目录: templates/v{k}/"""
    return template_base_dir(project_dir) / f"v{version}"


def latest_version(project_dir: Path) -> int:
    """返回最新已完成版本号（含 template.v3draw），无版本时返回 -1。"""
    base = template_base_dir(project_dir)
    if not base.exists():
        return -1
    versions = []
    for d in base.iterdir():
        if d.is_dir() and d.name.startswith("v"):
            try:
                v = int(d.name[1:])
            except ValueError:
                continue
            # 只计入实际包含 template.v3draw 的版本
            if (d / "template.v3draw").exists():
                versions.append(v)
    return max(versions) if versions else -1


def ensure_version_dir(project_dir: Path, version: int) -> Path:
    """创建并返回版本目录。"""
    d = version_dir(project_dir, version)
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_build_config(ver_dir: Path, config: dict[str, Any]) -> Path:
    """保存构建参数快照。"""
    p = ver_dir / "build_config.json"
    p.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def save_convergence(ver_dir: Path, data: dict[str, Any]) -> Path:
    """保存收敛指标。"""
    p = ver_dir / "convergence.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def save_summary(ver_dir: Path, summary: dict[str, Any]) -> Path:
    """保存版本摘要。"""
    summary.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    p = ver_dir / "summary.json"
    p.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def load_summary(ver_dir: Path) -> dict[str, Any] | None:
    """加载版本摘要。"""
    p = ver_dir / "summary.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def list_versions(project_dir: Path) -> list[dict[str, Any]]:
    """列出所有版本的摘要信息。"""
    base = template_base_dir(project_dir)
    if not base.exists():
        return []
    result = []
    for d in sorted(base.iterdir()):
        if not d.is_dir() or not d.name.startswith("v"):
            continue
        try:
            ver = int(d.name[1:])
        except ValueError:
            continue
        summary = load_summary(d) or {"version": ver}
        summary["version"] = ver
        summary["dir"] = str(d)
        result.append(summary)
    result.sort(key=lambda x: x["version"])
    return result
