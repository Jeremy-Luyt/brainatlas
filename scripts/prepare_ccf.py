"""
prepare_ccf.py — 从本地 NRRD 文件准备 CCF 解剖模板数据

功能:
  1. 将 tools/templates/ccf_25um/ 中的 NRRD 文件转换为 NIfTI (.nii.gz)
  2. 从 structure_graph_1.json 构建扁平化脑区索引 (含中文名)
  3. 将所有文件输出到 data/ccf/ 目录供 API 使用

用法:
  python scripts/prepare_ccf.py
  python scripts/prepare_ccf.py --source tools/templates/ccf_25um --dest data/ccf
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import nibabel as nib
import numpy as np

# ── 项目根目录 ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── 主要脑区中文名称映射 (Allen CCF v3 结构 ID → 中文) ──
CHINESE_NAMES: dict[int, str] = {
    # ── 根/大分区 ──
    997: "根",
    8: "基本细胞群和区域",
    567: "大脑",
    688: "大脑皮层",
    695: "皮质板",
    315: "等皮层 (新皮层)",
    698: "皮层下板",
    1089: "海马结构",
    703: "嗅觉区",
    623: "大脑核团",
    477: "纹状体",
    803: "苍白球",
    343: "中间脑",
    # ── 等皮层分区 ──
    184: "额极",
    500: "前扣带区",
    985: "运动前区",
    993: "初级运动区",
    353: "初级体感区",
    329: "体感补充区",
    1057: "后扣带区",
    677: "嗅后区",
    247: "初级视觉区",
    669: "前听区",
    31: "初级听觉区",
    254: "次级视觉区 (外)",
    # ── 海马 ──
    1080: "海马区",
    375: "阿蒙角",
    382: "海马 CA1",
    423: "海马 CA2",
    463: "海马 CA3",
    726: "齿状回",
    502: "海马下脚",
    603: "海马伞",
    909: "内嗅区",
    # ── 丘脑/下丘脑 ──
    549: "丘脑",
    856: "丘脑-多模态联合皮层相关",
    864: "丘脑-感觉运动皮层相关",
    1097: "下丘脑",
    141: "丘脑室周区",
    170: "外侧膝状体 (背侧)",
    178: "外侧膝状体 (腹侧)",
    # ── 中脑 ──
    313: "中脑",
    323: "中脑-运动相关",
    302: "上丘-感觉相关",
    4: "下丘",
    795: "导水管周围灰质",
    374: "黑质-致密部",
    381: "黑质-网状部",
    749: "腹侧被盖区",
    # ── 脑桥/延髓 ──
    771: "后脑",
    1065: "脑桥",
    354: "小脑皮层",
    512: "蚓部",
    528: "小脑半球",
    776: "脑桥核团",
    354: "小脑皮层",
    # ── 小脑 ──
    512: "蚓部",
    528: "小脑半球",
    645: "小脑核团",
    # ── 延髓 ──
    354: "小脑皮层",
    386: "延髓核团",
    # ── 纤维束 ──
    967: "纤维束",
    784: "胼胝体",
    # ── 脑室 ──
    73: "脑室系统",
    # ── 嗅球 ──
    507: "嗅球",
    # ── 杏仁核 ──
    278: "皮质杏仁区",
    23: "前杏仁区",
    131: "基底外侧杏仁核",
    295: "基底内侧杏仁核",
    319: "中央杏仁核",
    # ── 基底核/纹状体 ──
    485: "尾状核-壳核",
    672: "壳核 (尾侧)",
    56: "伏隔核",
    998: "苍白球外侧部",
    1022: "苍白球内侧部",
    # ── 下丘脑核团 ──
    126: "视交叉上核",
    223: "弓状核",
    # ── 脑干核团 ──
    679: "面神经核",
    693: "三叉神经核",
    # ── 边缘系统 ──
    972: "扣带束",
    # ── 白质 ──
    1009: "内囊",
    # 其他常用
    1097: "背侧丘脑",
    864: "腹侧丘脑",
    1044: "哈贝核 (缰核)",
    149: "中央灰质 (导水管周围灰质)",
}


def nrrd_to_nifti(nrrd_path: Path, nii_path: Path) -> None:
    """将 NRRD 转换为 NIfTI 格式。"""
    import nrrd as pynrrd

    data, header = pynrrd.read(str(nrrd_path))
    data = np.asarray(data)

    # Allen CCF 默认 25μm 分辨率 → 0.025mm
    spacing_mm = 0.025
    space_dirs = header.get("space directions")
    if isinstance(space_dirs, (list, tuple)) and len(space_dirs) >= 3:
        try:
            norms = [float(np.linalg.norm(np.asarray(d, dtype=np.float64))) for d in space_dirs[:3]]
            if all(v > 0 for v in norms):
                spacing_mm = norms[0] / 1000.0 if norms[0] > 1 else norms[0]
        except Exception:
            pass

    affine = np.diag([spacing_mm, spacing_mm, spacing_mm, 1.0])
    img = nib.Nifti1Image(data, affine=affine)
    nii_path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(img, str(nii_path))
    print(f"  [nrrd→nii] {nrrd_path.name} → {nii_path.name}  (shape={data.shape}, spacing={spacing_mm:.4f}mm)")


def flatten_tree(node: dict, out: list[dict], depth: int = 0) -> None:
    """递归展开结构树为扁平列表。"""
    region_id = node.get("id")
    chinese = CHINESE_NAMES.get(region_id, "")
    out.append({
        "id": region_id,
        "acronym": node.get("acronym", ""),
        "name": node.get("name", ""),
        "name_zh": chinese,
        "color_hex_triplet": node.get("color_hex_triplet", ""),
        "parent_structure_id": node.get("parent_structure_id"),
        "st_level": node.get("st_level"),
        "depth": depth,
    })
    for child in node.get("children", []):
        flatten_tree(child, out, depth + 1)


def build_regions_index(structure_tree_json: Path, out_json: Path) -> int:
    """构建脑区索引文件，返回区域总数。"""
    payload = json.loads(structure_tree_json.read_text(encoding="utf-8"))
    roots = payload.get("msg", [])
    rows: list[dict] = []
    for root in roots:
        flatten_tree(root, rows)
    rows.sort(key=lambda x: int(x.get("id") or 0))
    out_json.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    n_zh = sum(1 for r in rows if r.get("name_zh"))
    print(f"  [index] {len(rows)} regions ({n_zh} with Chinese names) → {out_json.name}")
    return len(rows)


def collect_unique_labels(annotation_nii: Path) -> set[int]:
    """读取 annotation 体并返回所有出现的标签 ID。"""
    img = nib.load(str(annotation_nii))
    data = np.asarray(img.get_fdata(dtype=np.float32), dtype=np.int64)
    labels = set(np.unique(data).tolist())
    labels.discard(0)
    return labels


def main() -> None:
    parser = argparse.ArgumentParser(description="准备 CCF 解剖模板数据 (NRRD → NIfTI + 脑区索引)")
    parser.add_argument("--source", default=str(PROJECT_ROOT / "tools" / "templates" / "ccf_25um"),
                        help="NRRD 源文件目录")
    parser.add_argument("--dest", default=str(PROJECT_ROOT / "data" / "ccf"),
                        help="输出目录")
    args = parser.parse_args()

    src = Path(args.source)
    dst = Path(args.dest)
    dst.mkdir(parents=True, exist_ok=True)

    print(f"CCF 数据准备")
    print(f"  源目录: {src}")
    print(f"  输出目录: {dst}")
    print()

    # 1. 转换 annotation NRRD → NIfTI
    annotation_nrrd = src / "annotation_25.nrrd"
    annotation_nii = dst / "annotation_25.nii.gz"
    if annotation_nrrd.exists():
        if annotation_nii.exists():
            print(f"  [skip] {annotation_nii.name} 已存在")
        else:
            print("步骤 1/4: 转换 annotation 标注体...")
            nrrd_to_nifti(annotation_nrrd, annotation_nii)
    else:
        print(f"  [warn] {annotation_nrrd} 不存在")

    # 2. 转换 anatomical Nissl NRRD → NIfTI
    anatomical_nrrd = src / "ara_nissl_25.nrrd"
    anatomical_nii = dst / "ara_nissl_25.nii.gz"
    if anatomical_nrrd.exists():
        if anatomical_nii.exists():
            print(f"  [skip] {anatomical_nii.name} 已存在")
        else:
            print("步骤 2/4: 转换 anatomical Nissl 解剖体...")
            nrrd_to_nifti(anatomical_nrrd, anatomical_nii)
    else:
        print(f"  [warn] {anatomical_nrrd} 不存在")

    # 3. 复制/构建结构树
    tree_src = src / "structure_graph_1.json"
    tree_dst = dst / "structure_graph_1.json"
    if tree_src.exists():
        shutil.copy2(tree_src, tree_dst)
        print(f"  [copy] structure_graph_1.json")
    else:
        print(f"  [warn] {tree_src} 不存在")

    # 4. 构建脑区索引
    if tree_dst.exists():
        print("步骤 3/4: 构建脑区索引 (含中文名)...")
        index_path = dst / "ccf_regions_index.json"
        n = build_regions_index(tree_dst, index_path)
    else:
        print("  [skip] 无结构树，跳过索引构建")

    # 5. 验证 annotation 标签覆盖率
    if annotation_nii.exists() and (dst / "ccf_regions_index.json").exists():
        print("步骤 4/4: 验证标注体标签覆盖率...")
        labels = collect_unique_labels(annotation_nii)
        index = json.loads((dst / "ccf_regions_index.json").read_text(encoding="utf-8"))
        index_ids = {r["id"] for r in index}
        covered = labels & index_ids
        missing = labels - index_ids
        print(f"  annotation 标签数: {len(labels)}")
        print(f"  索引覆盖: {len(covered)}/{len(labels)} ({100*len(covered)/max(len(labels),1):.1f}%)")
        if missing:
            print(f"  未覆盖标签 (前 10): {sorted(missing)[:10]}")

    # 6. 创建缓存目录
    cache_dir = dst / "cache" / "region_meshes"
    cache_dir.mkdir(parents=True, exist_ok=True)

    print()
    print("✓ CCF 数据准备完成")
    print(f"  annotation : {annotation_nii}")
    print(f"  anatomical : {anatomical_nii}")
    print(f"  regions    : {dst / 'ccf_regions_index.json'}")
    print(f"  mesh cache : {cache_dir}")


if __name__ == "__main__":
    main()
