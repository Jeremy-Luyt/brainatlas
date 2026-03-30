"""
verify_fix — 在现有 v3 数据上模拟修复后的 averaging 效果
对比修复前/后的部分覆盖区域强度
"""
import sys
sys.path.insert(0, ".")
import numpy as np
from pathlib import Path
from pipeline.io import read_v3draw
from pipeline.atlas.intensity_normalize import percentile_normalize, voxel_average

work_dir = Path("data/projects/default/templates/v3/_work")
sample_dirs = sorted([d for d in work_dir.iterdir() if d.is_dir() and not d.name.startswith("_")])

print("=" * 60)
print("修复验证 — 对比旧/新 averaging 效果")
print("=" * 60)

vols = []
for sd in sample_dirs:
    lr = sd / "local_registered_image.v3draw"
    vol, _ = read_v3draw(lr)
    if vol.ndim == 4:
        vol = vol[0]
    vols.append(vol)

# 计算覆盖图
coverage = np.zeros(vols[0].shape, dtype=np.int32)
for v in vols:
    coverage += (v > 0).astype(np.int32)

n = len(vols)
partial = ((coverage > 0) & (coverage < n))
full_cover = (coverage == n)

# --- 旧方法: /N 简单平均 + 全图百分位 ---
old_normed = []
for v in vols:
    vol_f = v.astype(np.float32)
    p_low = float(np.percentile(vol_f, 1.0))
    p_high = float(np.percentile(vol_f, 99.0))
    if p_high > p_low:
        norm = np.clip((vol_f - p_low) / (p_high - p_low), 0.0, 1.0) * 255.0
    else:
        norm = np.zeros_like(vol_f)
    old_normed.append(norm.astype(np.uint8))

old_acc = np.zeros(vols[0].shape, dtype=np.float64)
for nv in old_normed:
    old_acc += nv.astype(np.float64)
old_avg = np.clip(old_acc / n, 0, 255).astype(np.uint8)

# --- 新方法: 修复后的 percentile_normalize + voxel_average ---
new_normed = []
for v in vols:
    nv, stats = percentile_normalize(v, 1.0, 99.0)
    new_normed.append(nv)
    
new_avg = voxel_average(new_normed)

# --- 对比 ---
print(f"\n部分覆盖区域 ({partial.sum():,} 体素):")
old_partial = old_avg[partial].astype(float)
new_partial = new_avg[partial].astype(float)
print(f"  旧方法 (/N 平均): mean={old_partial.mean():.2f}, std={old_partial.std():.2f}")
print(f"  新方法 (覆盖加权): mean={new_partial.mean():.2f}, std={new_partial.std():.2f}")
print(f"  强度提升比例: {new_partial.mean() / max(old_partial.mean(), 1e-6):.2f}x")

print(f"\n完全覆盖区域 ({full_cover.sum():,} 体素):")
old_full = old_avg[full_cover].astype(float)
new_full = new_avg[full_cover].astype(float)
print(f"  旧方法: mean={old_full.mean():.2f}, std={old_full.std():.2f}")
print(f"  新方法: mean={new_full.mean():.2f}, std={new_full.std():.2f}")

# 检查边界跳变改善
z_mid = coverage.shape[0] // 2
y_mid = coverage.shape[1] // 2
coverage_line = coverage[z_mid, y_mid, :]
old_line = old_avg[z_mid, y_mid, :].astype(float)
new_line = new_avg[z_mid, y_mid, :].astype(float)

# 计算 coverage 跳变处的强度跳变幅度
changes = np.where(np.diff(coverage_line) != 0)[0]
old_jumps = []
new_jumps = []
for ci in changes:
    old_jumps.append(abs(old_line[ci+1] - old_line[ci]))
    new_jumps.append(abs(new_line[ci+1] - new_line[ci]))

if old_jumps:
    print(f"\n边界跳变 (Z={z_mid}, Y={y_mid}, {len(changes)} 个变化点):")
    print(f"  旧方法平均跳变: {np.mean(old_jumps):.2f}")
    print(f"  新方法平均跳变: {np.mean(new_jumps):.2f}")

# 整体统计
print(f"\n整体:")
print(f"  旧方法: shape={old_avg.shape}, range=[{old_avg.min()},{old_avg.max()}], mean={old_avg.mean():.2f}")
print(f"  新方法: shape={new_avg.shape}, range=[{new_avg.min()},{new_avg.max()}], mean={new_avg.mean():.2f}")

print("\n✓ 验证完成")
