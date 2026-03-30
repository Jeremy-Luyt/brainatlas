"""
diagnose2 — 检查样本非零区域重叠情况
当部分样本有值、部分样本为零时, 简单平均会产生 N/3 跳变伪影
"""
import sys
sys.path.insert(0, ".")
import numpy as np
from pathlib import Path
from pipeline.io import read_v3draw

work_dir = Path("data/projects/default/templates/v3/_work")

sample_dirs = sorted([d for d in work_dir.iterdir() if d.is_dir() and not d.name.startswith("_")])
print(f"样本数: {len(sample_dirs)}")

masks = []
vols = []
for sd in sample_dirs:
    lr = sd / "local_registered_image.v3draw"
    vol, _ = read_v3draw(lr)
    if vol.ndim == 4:
        vol = vol[0]
    vols.append(vol.astype(np.float32))
    masks.append(vol > 0)
    print(f"  {sd.name}: 非零体素 {(vol > 0).sum():,} / {vol.size:,}")

# 重叠分析
n = len(masks)
coverage = np.zeros(masks[0].shape, dtype=np.int32)
for m in masks:
    coverage += m.astype(np.int32)

total_voxels = coverage.size
for c in range(n + 1):
    count = (coverage == c).sum()
    pct = count / total_voxels * 100
    print(f"\n覆盖数={c}: {count:,} 体素 ({pct:.1f}%)")

# 这是关键: 覆盖数=1或2 的区域在3样本平均时会产生伪影
partial = ((coverage > 0) & (coverage < n))
print(f"\n*** 部分覆盖区域 (0<coverage<{n}): {partial.sum():,} 体素 ({partial.sum()/total_voxels*100:.1f}%)")
full = (coverage == n)
print(f"*** 完全覆盖区域 (coverage=={n}): {full.sum():,} 体素 ({full.sum()/total_voxels*100:.1f}%)")

# 检查当前 normalize_and_average 的效果
# 重新做一次平均: 简单方法 vs 加权方法
from pipeline.atlas.intensity_normalize import percentile_normalize

normed = []
for i, v in enumerate(vols):
    nv, stats = percentile_normalize(v, low_pct=1.0, high_pct=99.0)
    normed.append(nv.astype(np.float64))
    print(f"\n  样本{i} 归一化后: min={nv.min()}, max={nv.max()}, mean={nv.mean():.2f}")
    print(f"    p_low={stats['p_low']:.2f}, p_high={stats['p_high']:.2f}")
    # 检查归一化是否把0变成了非零
    orig_zero = (vols[i] == 0).sum()
    norm_zero = (nv == 0).sum()
    print(f"    原始零值: {orig_zero:,}, 归一化后零值: {norm_zero:,}")

# 简单平均 (当前实现)
simple_avg = np.zeros_like(normed[0])
for nv in normed:
    simple_avg += nv
simple_avg /= n

# 加权平均 (除以覆盖数)
weighted_avg = np.zeros_like(normed[0])
for nv in normed:
    weighted_avg += nv
# 只在有覆盖的地方除以覆盖数
cover_f = coverage.astype(np.float64)
cover_f[cover_f == 0] = 1  # 避免除零
weighted_avg /= cover_f

# 比较在部分覆盖区域的差异
simple_partial_vals = simple_avg[partial]
weighted_partial_vals = weighted_avg[partial]
print(f"\n部分覆盖区域 — 简单平均: mean={simple_partial_vals.mean():.2f}, std={simple_partial_vals.std():.2f}")
print(f"部分覆盖区域 — 加权平均: mean={weighted_partial_vals.mean():.2f}, std={weighted_partial_vals.std():.2f}")

# 检查边界处的跳变: 在z方向做示例
z_mid = coverage.shape[0] // 2
y_mid = coverage.shape[1] // 2
# 沿 x 方向扫描一条线
coverage_line = coverage[z_mid, y_mid, :]
simple_line = simple_avg[z_mid, y_mid, :]
weighted_line = weighted_avg[z_mid, y_mid, :]

# 找到 coverage 变化点
changes = np.where(np.diff(coverage_line) != 0)[0]
if len(changes) > 0:
    print(f"\nZ={z_mid}, Y={y_mid} 处 X方向 coverage 变化点数: {len(changes)}")
    for ci in changes[:5]:
        print(f"  X={ci}: coverage {coverage_line[ci]}->{coverage_line[ci+1]}, "
              f"simple {simple_line[ci]:.1f}->{simple_line[ci+1]:.1f}, "
              f"weighted {weighted_line[ci]:.1f}->{weighted_line[ci+1]:.1f}")

print("\n结论:")
print(f"  当前使用简单求和/N平均, 部分覆盖区域占比 {partial.sum()/total_voxels*100:.1f}%")
print(f"  这些区域的强度会因为部分样本贡献0而被拉低, 产生边界伪影")
print(f"  建议: 使用 coverage 加权平均 (除以实际贡献样本数)")
