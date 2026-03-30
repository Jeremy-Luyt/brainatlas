"""
diagnose_template_artifacts.py — 诊断模板构建伪影

分析:
1. 各样本 local registration 输出的尺寸和值域
2. resample 前后对比
3. 归一化参数
4. 逐体素平均结果
5. STPS 前后对比
"""
import sys
sys.path.insert(0, ".")

import numpy as np
from pathlib import Path
from pipeline.io import read_v3draw

project_dir = Path("data/projects/default")
templates_dir = project_dir / "templates"

print("=" * 60)
print("模板伪影诊断")
print("=" * 60)

# 检查各版本
for ver_dir in sorted(templates_dir.iterdir()):
    if not ver_dir.is_dir() or not ver_dir.name.startswith("v"):
        continue
    v = ver_dir.name
    print(f"\n{'─' * 50}")
    print(f"版本: {v}")
    
    # 模板体数据
    tpl = ver_dir / "template.v3draw"
    if tpl.exists():
        vol, hdr = read_v3draw(tpl)
        if vol.ndim == 4:
            vol = vol[0]
        print(f"  template.v3draw: shape={vol.shape}, dtype={vol.dtype}")
        print(f"    min={vol.min()}, max={vol.max()}, mean={vol.mean():.2f}, std={vol.std():.2f}")
        # 检查零值比例
        zero_pct = (vol == 0).sum() / vol.size * 100
        print(f"    零值体素比例: {zero_pct:.1f}%")
        # 检查是否有大面积全黑区域（边界伪影）
        # 按每个 slice 统计零值
        z_slices_zero = [(vol[z] == 0).sum() / vol[z].size * 100 for z in range(vol.shape[0])]
        n_mostly_black = sum(1 for p in z_slices_zero if p > 90)
        print(f"    Z方向 >90%黑色切片数: {n_mostly_black}/{vol.shape[0]}")
        y_slices_zero = [(vol[:, y] == 0).sum() / vol[:, y].size * 100 for y in range(vol.shape[1])]
        n_y_black = sum(1 for p in y_slices_zero if p > 90)
        print(f"    Y方向 >90%黑色切片数: {n_y_black}/{vol.shape[1]}")
    else:
        print(f"  template.v3draw: 不存在")
    
    # 工作目录分析
    work_dir = ver_dir / "_work"
    if not work_dir.exists():
        continue
    
    # M_raw（归一化+平均后、STPS前）
    m_raw = work_dir / "M_raw.v3draw"
    if m_raw.exists():
        mvol, _ = read_v3draw(m_raw)
        if mvol.ndim == 4:
            mvol = mvol[0]
        print(f"\n  M_raw: shape={mvol.shape}, dtype={mvol.dtype}")
        print(f"    min={mvol.min()}, max={mvol.max()}, mean={mvol.mean():.2f}, std={mvol.std():.2f}")
        zero_pct = (mvol == 0).sum() / mvol.size * 100
        print(f"    零值体素比例: {zero_pct:.1f}%")
    
    # 各样本 local registration 输出
    sample_dirs = [d for d in work_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]
    if sample_dirs:
        print(f"\n  样本 local reg 输出 ({len(sample_dirs)} 个样本):")
        for sd in sorted(sample_dirs):
            lr = sd / "local_registered_image.v3draw"
            if not lr.exists():
                print(f"    {sd.name}: 无输出文件")
                continue
            svol, _ = read_v3draw(lr)
            if svol.ndim == 4:
                svol = svol[0]
            zero_pct = (svol == 0).sum() / svol.size * 100
            print(f"    {sd.name}: shape={svol.shape}, range=[{svol.min()},{svol.max()}], "
                  f"mean={svol.mean():.2f}, zero={zero_pct:.1f}%")
            
            # 检查样本之间的重叠: 非零区域
            nonzero_mask = svol > 0
            # 检查边界切片
            z_first_nz = -1
            z_last_nz = -1
            for z in range(svol.shape[0]):
                if svol[z].max() > 0:
                    if z_first_nz < 0:
                        z_first_nz = z
                    z_last_nz = z
            print(f"      Z非零范围: [{z_first_nz}, {z_last_nz}] / {svol.shape[0]}")

print("\n" + "=" * 60)
print("诊断完成")
