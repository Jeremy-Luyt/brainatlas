"""初始模板脑T0选择: 从QC通过的样本中选取得分最高者"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def select_t0(
    candidates: list[dict[str, Any]],
    project_samples_dir: Path,
    template_v0_dir: Path,
) -> dict[str, Any]:
    """从QC候选列表中选得分最高的样本作为T0, 复制到templates/v0/"""
    if not candidates:
        raise ValueError("No QC candidates available for T0 selection")

    best = candidates[0]
    sample_id = best["sample_id"]
    score = best.get("score", 0)

    # 找到该样本的 global registration 输出
    sample_dir = project_samples_dir / sample_id
    sample_json = sample_dir / "sample.json"
    if not sample_json.exists():
        raise FileNotFoundError(f"sample.json not found: {sample_json}")

    sample = json.loads(sample_json.read_text(encoding="utf-8"))
    global_reg = sample.get("global_registration", {})
    global_v3draw = Path(global_reg.get("global_v3draw_path", ""))

    if not global_v3draw.exists():
        raise FileNotFoundError(f"Global v3draw not found: {global_v3draw}")

    # 创建 template_v0 目录
    template_v0_dir.mkdir(parents=True, exist_ok=True)

    # 复制 global.v3draw → template.v3draw
    template_v3draw = template_v0_dir / "template.v3draw"
    shutil.copy2(global_v3draw, template_v3draw)

    # 复制 global.nii.gz → template.nii.gz (如果存在)
    global_nii = Path(global_reg.get("global_nii_path", ""))
    template_nii = None
    if global_nii.exists():
        template_nii = template_v0_dir / "template.nii.gz"
        shutil.copy2(global_nii, template_nii)

    # 复制 previews (如果存在)
    global_preview_dir = sample_dir / "registration" / "global" / "previews"
    if global_preview_dir.exists():
        preview_dst = template_v0_dir / "preview"
        if preview_dst.exists():
            shutil.rmtree(preview_dst)
        shutil.copytree(global_preview_dir, preview_dst)

    # 写 summary.json
    summary = {
        "version": 0,
        "source": "t0_selection",
        "source_sample_id": sample_id,
        "source_score": score,
        "template_v3draw": str(template_v3draw),
        "template_nii": str(template_nii) if template_nii else "",
    }
    (template_v0_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return summary
