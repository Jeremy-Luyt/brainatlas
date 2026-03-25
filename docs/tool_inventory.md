# BrainAtlas 工具清单 (Tool Inventory)

> 最后更新: 2026-03-25

本文档记录 `tools/` 目录下所有二进制工具、源代码、模板和批处理脚本的用途、调用方式和可用性状态。

---

## 目录

- [1. 全局配准 (Global Registration)](#1-全局配准-global-registration)
  - [1.1 GlobalRegistration_LYT.exe（主用）](#11-globalregistration_lyeexe主用)
  - [1.2 其他全局配准 exe](#12-其他全局配准-exe)
- [2. 局部配准 (Local Registration)](#2-局部配准-local-registration)
  - [2.1 local_registration.exe (local_hhm, 主用)](#21-local_registrationexe-local_hhm-主用)
  - [2.2 win64_bin 中的 local 系列](#22-win64_bin-中的-local-系列)
- [3. 特征点检测 (2.5D Harris)](#3-特征点检测-25d-harris)
- [4. STPS 变形 (Stps_warp_image&point)](#4-stps-变形-stps_warp_imagepoint)
- [5. 模板数据 (Templates)](#5-模板数据-templates)
- [6. 配置文件 (Config)](#6-配置文件-config)
- [7. 批处理脚本 (Batch Scripts)](#7-批处理脚本-batch-scripts)
- [8. 第三方依赖 (3rdparty)](#8-第三方依赖-3rdparty)
- [9. EXE 可用性汇总表](#9-exe-可用性汇总表)

---

## 1. 全局配准 (Global Registration)

### 1.1 GlobalRegistration_LYT.exe（主用）

| 属性 | 值 |
|------|-----|
| **路径** | `tools/bin/global/CPU/release/GlobalRegistration_LYT.exe` |
| **大小** | 0.74 MB |
| **状态** | ✅ **可用** — 当前系统默认调用的全局配准程序 |
| **源码** | `tools/bin/global/CPU/src/main_mBrainAligner_global.cpp` |
| **功能** | 将 subject 脑图像通过 Affine + FFD + Normalization 配准到 target 模板空间。支持 v3draw / nii / nii.gz 格式。 |

#### 命令行接口（新版，由 batch 脚本和 Python wrapper 使用）

```
GlobalRegistration_LYT.exe
  -f <fixed_image_or_template_dir>    目标图像(atlas)路径，可为单个文件或包含 atlas_v3draw/ 的模板目录
  -m <moving_image>                   待配准的 subject 图像 (.v3draw / .nii / .nii.gz)
  -p <registration_methods>           配准方法组合: a=Affine, r=RPM, f=FFD, n=Normalization
                                       示例: "a+f+n" "r+f" "a+f"
  -o <output_dir>                     输出保存目录（末尾加 \）
  -d <threshold>                      像素阈值，低于此值归零 (默认 30; 设 0 禁用)
  -l <padding>                        target 图像各轴 padding 大小，格式 "x+y+z" 或单值
  -s <subject_marker>                 subject 先验标记点文件 (.marker)
  -t <target_marker>                  target 先验标记点文件 (.marker)
```

#### 输入

| 参数 | 必需 | 说明 |
|------|------|------|
| `-f` | ✅ | target 模板目录或文件。给目录时程序自动从 `atlas_v3draw/` 加载标准脑 |
| `-m` | ✅ | subject 待配准图像（v3draw/nii/nii.gz）|
| `-p` | ✅ | 配准方法组合字符串 |
| `-o` | ✅ | 输出目录 |
| `-s` | 推荐 | subject marker (Affine 模式必须) |
| `-t` | 推荐 | target marker (Affine 模式必须) |
| `-d` | 可选 | 阈值 (默认 30) |
| `-l` | 可选 | padding (默认 0) |

#### 输出

程序在 `-o` 指定目录下生成：

| 输出文件 | 说明 |
|----------|------|
| `global.v3draw` | 全局配准后的 subject 图像 |
| `{sample}_FFD.v3draw` | FFD 变形后的图像 |
| `{sample}_FFD_grid.swc` | FFD 变形网格 |
| `{sample}_NORM.v3draw` | 归一化后的图像 |
| `{sample}_to_25um_568.json` | 配准参数记录 |

#### 示例

```bat
GlobalRegistration_LYT.exe ^
  -f E:\templates\25um_568\ ^
  -m E:\data\sample.v3draw ^
  -p a+f+n ^
  -o E:\output\ ^
  -d 0 -l 0+0+0 ^
  -s E:\templates\25um_568\fMOST_space_prior_sub.marker ^
  -t E:\templates\25um_568\fMOST_space_prior_tar.marker
```

#### Python 调用

已封装为 `pipeline/wrappers/global_registration.py` → `run_global_registration(moving, fixed, output_dir)`，自动处理路径、环境变量和输出收集。

---

### 1.2 其他全局配准 exe

这些 exe 使用**旧版命令行接口**（printHelp 接口），与 LYT 版不同：

| 文件 | 位置 | 状态 | 说明 |
|------|------|------|------|
| `GlobalRegistration_zmj.exe` | `global/CPU/release/` | ⚠️ 不可用 | 无参数运行无输出，疑似依赖缺失或为旧版调试 |
| `GlobalRegistration - 副本.exe` | `global/CPU/release/` | ❌ 备份 | 文件名含空格和中文，应为手工备份，不建议使用 |
| `global_registration1.exe` | `global/CPU/release/` | ⚠️ 旧版 | 功能可用，但使用旧版 `-T/-S` 参数接口 |
| `GlobalRegistration.exe` | `win64_bin/` | ⚠️ 旧版 | 同上，旧版接口 |
| `global_registration.exe` | `win64_bin/` | ⚠️ 旧版 | 同上 |
| `global_registration.exe` | `win64_bin/zmj/` | ⚠️ 旧版 | zmj 子目录版本，旧版接口 |

#### 旧版接口（global_registration1.exe / GlobalRegistration.exe 等）

```
Input paras:
  -T  <filename_tar>              target (atlas) 图像完整路径
  -t  <markerFilename_target>     target 标记点文件
  -s  <markerFilename_subject>    subject 标记点文件
  -S  <filename_sub>              subject 图像完整路径
  [-r] <kenelradius>              局部强度归一化半径

Output paras:
  [-a] <filename_sub2tar_affine>  Affine 变换后图像输出路径
  [-o] <filename_sub2tar_global>  全局配准后图像输出路径
  [-x] <output_size_x>            输出 X 尺寸
  [-y] <output_size_y>            输出 Y 尺寸
  [-z] <output_size_z>            输出 Z 尺寸
  [-f] <markerFilename_target>    输出 target marker (全局配准后)
  [-m] <markerFilename_subject>   输出 subject marker (全局配准后)
  [-g] <filename_grid>            SSD 网格文件输出路径
  [-d] <filename_sub2tar_ssd>     SSD 变形图像输出路径
  [-n] <filename_sub2tar_norm>    归一化后图像输出路径
```

> **注意**：旧版需要为每个输出文件单独指定路径（`-a`, `-o`, `-d`, `-n`, `-g` 等），新版只需 `-o` 指定目录。

---

## 2. 局部配准 (Local Registration)

### 2.1 local_registration.exe (local_hhm, 主用)

| 属性 | 值 |
|------|-----|
| **路径** | `tools/bin/local/local_hhm/CPU/release/local_registration.exe` |
| **大小** | 1.46 MB |
| **状态** | ✅ **可用** |
| **源码** | `tools/bin/local/local_hhm/CPU/src/main_local_registration.cpp` |
| **功能** | 基于 STPS (Smooth Thin-Plate Spline) 迭代的局部非刚性配准。输入为全局配准的结果，进一步精细对齐。 |

#### 命令行接口

```
local_registration.exe
  -p <input_parameter_file>       参数配置文件 (.txt)，见 config.txt 说明
  -s <input_subject_image>        全局配准结果图像 (global.v3draw)
  -m <input_segmentation_image>   分割结果图像（可选）
  -g <input_data_dir>             目标模板数据目录 (包含 target image、marker 等)
  -f <finetune_data>              断点续跑数据目录（可选）
  -l <landmarks_file_path>        标记点文件路径 (high/middle/low_landmarks.marker)
  -o <output_save_path>           输出保存目录
```

#### 输入

| 参数 | 必需 | 说明 |
|------|------|------|
| `-p` | ✅ | 配置文件，控制迭代次数、平滑约束、尺度等参数 |
| `-s` | ✅ | subject 图像 — 通常为全局配准输出的 `global.v3draw` |
| `-g` | ✅ | target 数据目录，内含模板脑图像和参考标记点 |
| `-l` | ✅ | landmark 文件，高/中/低级别标记点 |
| `-o` | ✅ | 输出目录 |
| `-m` | 可选 | 分割结果（fMOST 模态下使用） |
| `-f` | 可选 | 从之前中断处恢复 |

#### 输出

| 输出文件 | 说明 |
|----------|------|
| `local_registered_image.v3draw` | 局部配准后的图像 |
| `local_registered_sub.marker` | 变形后的 subject 标记点 |
| `local_registered_tar.marker` | 对应的 target 标记点 |

#### 示例

```bat
local_registration.exe ^
  -p config\config.txt ^
  -s E:\output\global.v3draw ^
  -l E:\templates\25um_568\target_landmarks\high_landmarks.marker ^
  -g E:\templates\25um_568\ ^
  -o E:\output\local\
```

---

### 2.2 win64_bin 中的 local 系列

所有 local 变体使用相同的命令行接口，区别在于内部算法或针对的模态：

| 文件 | 大小 | 状态 | 说明 |
|------|------|------|------|
| `local_registration.exe` | 1.50 MB | ✅ 可用 | 通用局部配准 |
| `local_registrationln2.exe` | 1.50 MB | ✅ 可用 | ln 改进版 v2 |
| `local_registration_2017.exe` | 1.50 MB | ✅ 可用 | 2017 算法版（batch 脚本 test_windowszmj.bat 使用） |
| `local_registration_deep.exe` | 1.57 MB | ✅ 可用 | 深度学习辅助版（体积更大，含额外特征） |
| `local_registration_ln.exe` | 1.46 MB | ✅ 可用 | ln 版本，与 local_hhm 版相同 |
| `local_registration.exe` (zmj) | 1.56 MB | ✅ 可用 | zmj 子目录，较新版 |

> **推荐使用 `local/local_hhm/CPU/release/local_registration.exe`**，它是最新版，拥有完整源码。

---

## 3. 特征点检测 (2.5D Harris)

| 属性 | 值 |
|------|-----|
| **路径** | `tools/bin/win64_bin/2.5D Harris.exe` (也存在于 `win64_bin/zmj/`) |
| **大小** | 0.51 MB |
| **状态** | ✅ **可用** |
| **功能** | 从 3D 脑图像中提取 2.5D Harris 特征角点，用于后续配准的标记点匹配。 |

#### 命令行接口

```
2.5D Harris.exe
  -m  <input_image_path>     输入图像(.raw / .tif / .lsm / .v3draw)
  -o  <corner_save_path>     角点输出保存路径
  -p1 <window_size_2D_NMS>   2D 非极大值抑制窗口大小
  -p2 <window_size_3D_NMS>   3D 非极大值抑制窗口大小
```

#### 输入

| 参数 | 必需 | 说明 |
|------|------|------|
| `-m` | ✅ | 输入 3D 图像文件 |
| `-o` | ✅ | 角点结果保存路径 |
| `-p1` | 可选 | 2D NMS 窗口大小 |
| `-p2` | 可选 | 3D NMS 窗口大小 |

#### 输出

- `.marker` 文件，包含检测到的角点坐标 (x, y, z)

---

## 4. STPS 变形 (Stps_warp_image&point)

| 属性 | 值 |
|------|-----|
| **路径** | `tools/bin/STPS/Stps_warp_image&point/` |
| **状态** | ✅ **已重构** — 源码已优化，加入 getopt switch-case CLI，需 VS2013 编译 |
| **源码** | `main_warp_ssdjba_ctlpts.cpp` + 多个 `.cu` (CUDA) 和 `.cpp` 文件 |
| **项目** | Visual Studio 2013 项目 (`Stps_warp_image.vcxproj`), Release|x64 |
| **功能** | 基于 STPS 控制点的图像和标记点变形。给定 sub/tar marker pair，对图像做 TPS 插值变换。 |

#### 重构变更记录

| 文件 | 变更内容 |
|------|----------|
| `main_warp_ssdjba_ctlpts.cpp` | **完全重写**: 移除 ~500 行注释死代码和硬编码 `G:\` 路径; 加入 `getopt` switch-case CLI 参数解析; 新增 `printHelp()` 帮助函数; 新增 `process_batch_sample()` 批处理函数; 支持单样本 STPS 变形和批处理预处理两种模式; 修复 `downsample3dvol` 中 `dfactor` 内存泄漏; 全文加入中英双语注释 |
| `q_imgwarp_tps_quicksmallmemory.h` | 移除硬编码 `G:\postgraduate\...\basic_memory.cpp` 和 `newmatap.h`/`newmatio.h` 的绝对路径, 改为通过项目 Include 路径解析的相对引用; 所有函数声明加入中英双语算法注释 |
| `q_imgwarp_tps_quicksmallmemory.cpp` | 所有核心函数加入详细中英双语注释: 文件头部算法概述、`q_imgblockwarp` 逐体素变形、`imgwarp_smallmemory` 主流程编排、`q_dfblcokinterp_linear/bspline` DF插值、`compute_df_tps_subsampled_volume` 经典TPS公式注释、`compute_df_stps_subsampled_volume_4bspline` STPS QR分解算法注释、`q_nonrigid_ini_bsplinebasis_3D` B样条基矩阵构建、`linearinterp_regularmesh_3d` 和 `interpolate_coord_linear` 插值函数 |
| `Stps_warp_image.vcxproj` | Release\|x64 配置中 `AdditionalIncludeDirectories` 和 `AdditionalLibraryDirectories` 的 `G:\postgraduate\3rdparty\3rdparty\...` 全部替换为相对路径 `..\..\3rdparty\3rdparty\...` |

#### 源文件清单

| 文件 | 类型 | 功能 |
|------|------|------|
| `main_warp_ssdjba_ctlpts.cpp` | C++ | 主程序：getopt CLI 解析，支持单样本 STPS 变形和批处理预处理 |
| `q_imgwarp_tps_quicksmallmemory.cpp/.h` | C++ | 核心 TPS/STPS 变形算法（快速小内存逐块处理版） |
| `q_interpolate.cpp/.h` | C++ | 3D 图像插值 |
| `q_imresize.cpp` | C++ | 图像缩放 |
| `q_littleQuickWarp_common.h` | C++ | 数据结构定义 (Coord3D_JBA, DisplaceFieldF3D, Vol3DSimple) |
| `aff.cu` | CUDA | 仿射变换 GPU 加速 |
| `chazhi.cu` | CUDA | 插值 GPU 加速 |
| `GETA.cu` / `GET_A_i.cu` / `GET_C.cu` | CUDA | TPS 矩阵求解 GPU 内核 |
| `weiyijisuan.cu` | CUDA | 位移计算 GPU 内核 |
| `extendornormal.cu` | CUDA | 扩展正交化 GPU 加速 |
| `qr.cu` | CUDA | QR 分解 GPU 内核 |
| `XNX4C.cu` | CUDA | 矩阵运算 GPU 内核 |
| `ele.cuh` | CUDA | GPU 元素操作头文件 |
| `stackutil.cpp/.h` | C++ | V3D 图像栈工具 |
| `basic_surf_objs.cpp` | C++ | V3D 基础表面对象 |
| `mg_image_lib.cpp/.h` | C++ | 图像库操作 |
| `mg_utilities.cpp/.h` | C++ | 通用工具函数 |
| `jba_match_landmarks.cpp/.h` | C++ | 标记点匹配 |

#### CLI 接口

```
用法:
  模式1 - 单样本 STPS 变形:
    Stps_warp_image.exe -s <img> -T <tar.marker> -S <sub.marker> -o <output> [选项]

  模式2 - 批处理预处理 (降采样 + NIfTI 导出):
    Stps_warp_image.exe -f <data.txt> -D <data_dir> -O <out_dir> [选项]

输入参数:
  -s <file>    样本图像文件 (v3draw 格式)
  -L <file>    标签图像文件 (v3draw, 可选)
  -T <file>    目标标记文件 (.marker)
  -S <file>    样本标记文件 (.marker)

输出参数:
  -o <file>    输出变形图像文件

批处理参数:
  -f <file>    批处理数据文件 (每行一个样本名)
  -D <dir>     数据根目录
  -O <dir>     输出根目录

选项:
  -r <int>     降采样因子 (默认: 4)
  -b <int>     STPS 变形块大小 (默认: 4)
  -d <int>     DF 插值方法: 0=三线性, 1=B样条 (默认: 1)
  -i <int>     图像插值: 0=双线性, 1=最近邻 (默认: 0)
  -R <W,H,D>   输出尺寸覆盖 (默认: 使用输入尺寸)
  -W           在批处理模式中启用 STPS 变形
  -h           打印帮助信息
```

#### 使用示例

```bash
# 单样本 STPS 变形 (B样条 DF 插值, 双线性图像插值)
Stps_warp_image.exe -s global.v3draw -T tar.marker -S sub.marker -o warped.v3draw

# 单样本, 指定输出尺寸和块大小
Stps_warp_image.exe -s global.v3draw -T tar.marker -S sub.marker -o warped.v3draw -R 568,320,456 -b 8

# 批处理导出 (降采样 + NIfTI导出 + marker文本导出)
Stps_warp_image.exe -f data.txt -D /data/samples -O /output/preprocessed -r 4

# 批处理导出 + STPS 变形
Stps_warp_image.exe -f data.txt -D /data/samples -O /output/warped -r 4 -W
```

#### 核心算法说明

**STPS (Subsampled Thin-Plate Spline) 工作流:**

1. **控制点输入**: 读取 target/subject marker 对 (对应点集)
2. **位移场计算**: 在子采样网格上计算 TPS 或 STPS 位移场
   - **TPS 模式** (`-d 0`): 经典 TPS, 使用 r²log(r) 核, 解 wW = wL⁻¹ × wY
   - **STPS 模式** (`-d 1`): QR 分解控制点矩阵 P, 分离仿射项 d 和非仿射项 c, 正则化参数 λ=0.2 控制平滑度
3. **逐块插值**: 将子采样 DF 插值到全分辨率
   - 三线性: 2×2×2 角点线性插值
   - B样条: 4×4×4 控制网格, 三次 B样条基函数 (Kronecker 积扩展)
4. **逐块变形**: 对每个图像块, 根据 DF 进行体素级变形 (双线性/最近邻插值)

#### 构建依赖

- Visual Studio 2013 (v120 工具集), Release|x64
- Qt 4.8.6 (`qt-4.8.6/msvc2013_64`)
- CUDA 10.0 (nvcc, cudart, cublas, cusolver)
- newmat11 矩阵库 (`3rdparty/v3d_main_jba0/newmat11`)
- NIfTI C 库 (`3rdparty/nifti_clib-master`)
- OpenCV 3.10 (`3rdparty/opencv_vc12_lib`)
- 所有依赖路径已改为相对路径 `../../3rdparty/3rdparty/...`

---

## 5. 模板数据 (Templates)

### 5.1 25um_568 (标准 CCF 模板)

路径: `tools/templates/25um_568/`

| 文件 | 说明 |
|------|------|
| `atlas_v3draw/CCF_u8_xpad.v3draw` | CCF 标准模板（主图像） |
| `atlas_v3draw/CCF_roi.v3draw` | ROI 分区标注 |
| `atlas_v3draw/CCF_contour.v3draw` | 轮廓线 |
| `atlas_v3draw/CCF_mask.v3draw` | 掩膜 |
| `atlas_NIFTI/CCF_u8_xpad.nii.gz` | NIfTI 格式模板 |
| `atlas_NIFTI/CCF_roi.nii.gz` | NIfTI 格式 ROI |
| `atlas_NIFTI/CCF_contour.nii.gz` | NIfTI 格式轮廓 |
| `atlas_NIFTI/CCF_mask.nii.gz` | NIfTI 格式掩膜 |
| `fMOST_space_prior_sub.marker` | Affine 配准用 subject 先验标记点 |
| `fMOST_space_prior_tar.marker` | Affine 配准用 target 先验标记点 |
| `target_landmarks/high_landmarks.marker` | 局部配准用高级别标记点 |
| `target_landmarks/middle_landmarks.marker` | 局部配准用中级别标记点 |
| `target_landmarks/low_landmarks.marker` | 局部配准用低级别标记点 |

### 5.2 fmost (fMOST 专用模板)

路径: `tools/templates/fmost/`

| 文件 | 说明 |
|------|------|
| `atlas_v3draw/CCF_u8_xpad.v3draw` | fMOST 模板 |
| `atlas_v3draw/CCF_roi.v3draw` | ROI |
| `atlas_v3draw/CCF_contour.v3draw` | 轮廓 |
| `fMOST_space_prior_sub.marker` | subject 先验标记点 |
| `fMOST_space_prior_tar.marker` | target 先验标记点 |
| `high_landmarks_fmost.marker` | 高级别标记点 |

---

## 6. 配置文件 (Config)

### 6.1 全局配准配置 (`tools/batch/config.txt`)

此文件用于**局部配准**的参数配置（非全局配准），全局配准通过命令行参数直接控制。

```txt
Select_modal = 2          # 模态: 0=fMOST, 1=其他模态鼠脑, 2=其他物种(如斑马鱼)
max_iteration_number = 2000     # 最大迭代次数
smoothness_constraint_outer_initial = 150   # 外部 STPS 初始平滑约束 (越大越强)
smoothness_constraint_inner_initial = 400   # 内部 STPS 初始平滑约束
smoothness_constraint_outer_end = 20        # 外部退火终止值
smoothness_constraint_inner_end = 40        # 内部退火终止值
kernel_radius = 10        # 特征提取半径
search_radius = 10        # 搜索匹配标记点半径
interval_save = 500       # 每 N 次保存一次结果
interval_region_constraint = 25    # 每 N 次做一次局部约束
interval_global_constraint = 50    # 每 N 次做一次全局约束
multiscale = 1            # 多尺度选择 (1=单尺度, 2=多尺度)
```

### 6.2 局部配准配置 (`tools/bin/local/config/config.txt`)

专用于 local_hhm 局部配准：

```txt
Select_modal = 1          # 其他模态鼠脑
max_iteration_number = 100
smoothness_constraint_outer_initial = 100
smoothness_constraint_inner_initial = 500
smoothness_constraint_outer_end = 50
smoothness_constraint_inner_end = 50
kernel_radius = 10
search_radius = 10
interval_save = 500
interval_region_constraint = 500
interval_global_constraint = 500
multiscale = 2            # 多尺度
```

### 6.3 局部配准 target landmarks (`tools/bin/local/config/target_landmarks/`)

- `high_landmarks.marker` — 高精度标记点
- `middle_landmarks.marker` — 中精度标记点
- `low_landmarks.marker` — 低精度标记点

---

## 7. 批处理脚本 (Batch Scripts)

### 7.1 `tools/batch/run_script_windows_global_ln.bat`

**功能**: 运行全局配准（使用 zmj 版 global_registration.exe + 新版接口）

```bat
..\binary\win64_bin\zmj\global_registration.exe ^
  -f E:\fmost_demo\examples\target_ln\fa\ ^
  -m E:\ln_data\downstrip\cutoff7_radius6_preprocess.v3draw ^
  -p a+f+n ^
  -o E:\ln_data\global_result\ ^
  -d 0 -l 0+0+0 ^
  -s E:\ln_data\marker\cutoff7_radius6_preprocess.marker ^
  -t E:\ln_data\marker\new2.marker
```

### 7.2 `tools/batch/test_windowszmj.bat`

**功能**: 批量运行局部配准（使用 local_registration_2017.exe）

```bat
# 读取 dataf.txt 中的目录列表，逐个运行
..\binary\win64_bin\local_registration_2017.exe ^
  -p config/config.txt ^
  -s <dir>\brain.v3draw ^
  -l E:\fmost_demo\examples\target\25um_568\target_landmarks/high_landmarks.marker ^
  -g E:\fmost_demo\examples\target\25um_568/ ^
  -o <dir>\ccf\ -u 0
```

### 7.3 `tools/bin/local/test_windowsln.bat`

**功能**: 运行局部配准单样本测试

```bat
local_registration.exe ^
  -p E:\...\config\config.txt ^
  -s E:\...\global.v3draw ^
  -l E:\...\target_landmarks\high_landmarks.marker ^
  -g E:\...\target_mouse\25umpad ^
  -o E:\...\output
```

### 7.4 `tools/bin/global/CPU/run_script_windows1.bat`

**功能**: 使用旧版接口运行全局配准

```bat
release\GlobalRegistration.exe ^
  -f D:\Demo\Demo_padding_x4_new_V3\examples\target\25um\ ^
  -m D:\Demo\1\18454_red_mm_RSA_final.v3draw ^
  -p r+f ^
  -o D:\Demo\1\ ^
  -d 1 -l 20
```

---

## 8. 第三方依赖 (3rdparty)

路径: `tools/bin/3rdparty/3rdparty/`

| 目录 | 说明 |
|------|------|
| `eigen-3.4.0/` | 矩阵/线性代数库 |
| `LBFGSpp-master/` | L-BFGS 优化算法 |
| `nifti_clib-master/` | NIfTI C 读写库 |
| `opencv_include/` | OpenCV 头文件 |
| `opencv_vc12_lib/` | OpenCV VC12 编译库 |
| `qt-4.8.6/` | Qt 4.8.6 (msvc2013_64) |
| `v3d_main_basic_c_fun/` | V3D 基础 C 函数 |
| `v3d_main_common_lib/` | V3D 公共库 |
| `v3d_main_common_lib0/` | V3D 公共库 (旧版) |
| `v3d_main_io/` | V3D I/O 模块 |
| `v3d_main_jba/` | V3D JBA (包含 newmat11 矩阵库) |
| `v3d_main_jba0/` | V3D JBA (旧版) |
| `zlib-1.2.11/` | zlib 压缩库 |

**运行时 DLL 依赖**（位于 `win64_bin/`）:

| DLL | 说明 |
|-----|------|
| `opencv_world310.dll` | OpenCV 3.10 |
| `QtCore4.dll` / `QtGui4.dll` | Qt 4.x 核心/GUI |
| `msvcr120.dll` | VS2013 运行时 |
| `zlibwapi.dll` | zlib |

**GPU 版额外依赖**（如使用 GPU 加速）:

`cublas64_*.dll`, `cudart64_*.dll`, `cudnn64_7.dll`, `cusolver64_*.dll`, `torch.dll`, `torch_cuda.dll` 等

---

## 9. EXE 可用性汇总表

| EXE | 路径 | 可用 | 接口版本 | 功能 |
|-----|------|:----:|---------|------|
| **GlobalRegistration_LYT.exe** | `global/CPU/release/` | ✅ | 新版 (`-f -m -p -o`) | 全局配准（主用） |
| global_registration1.exe | `global/CPU/release/` | ⚠️ | 旧版 (`-T -S -t -s`) | 全局配准（旧版） |
| GlobalRegistration_zmj.exe | `global/CPU/release/` | ❌ | — | 运行无输出，不可用 |
| GlobalRegistration - 副本.exe | `global/CPU/release/` | ❌ | 新版 | 备份文件，不建议使用 |
| GlobalRegistration.exe | `win64_bin/` | ⚠️ | 旧版 | 全局配准（旧版） |
| global_registration.exe | `win64_bin/` | ⚠️ | 旧版 | 全局配准（旧版） |
| global_registration.exe | `win64_bin/zmj/` | ⚠️ | 旧版 | 全局配准（旧版） |
| **local_registration.exe** | `local/local_hhm/CPU/release/` | ✅ | 标准 | 局部配准（主用，有源码） |
| local_registration1.exe | `local/local_hhm/CPU/release/` | ✅ | 标准 | 局部配准（旧编译） |
| local_registration.exe | `win64_bin/` | ✅ | 标准 | 局部配准 |
| local_registrationln2.exe | `win64_bin/` | ✅ | 标准 | 局部配准 ln v2 |
| local_registration_2017.exe | `win64_bin/` | ✅ | 标准 | 局部配准 2017 版 |
| local_registration_deep.exe | `win64_bin/` | ✅ | 标准 | 局部配准 + 深度学习 |
| local_registration_ln.exe | `win64_bin/` | ✅ | 标准 | 局部配准 ln 版 |
| local_registration.exe | `win64_bin/zmj/` | ✅ | 标准 | 局部配准 zmj 版 |
| **2.5D Harris.exe** | `win64_bin/` | ✅ | 独立 | 2.5D Harris 角点检测 |
| 2.5D Harris.exe | `win64_bin/zmj/` | ✅ | 独立 | 同上 (zmj 副本) |
| **Stps_warp_image** | `STPS/Stps_warp_image&point/` | ✅ | 已重构, 待编译 | STPS 图像+点变形 (getopt CLI, 双模式, 相对路径) |

---

## 附录：完整配准流水线

```
输入 subject 图像 (.v3draw)
         │
         ▼
 ┌─── 全局配准 ───┐
 │ GlobalRegistration_LYT.exe │
 │ -p a+f+n                   │
 │ 输入: subject + template   │
 │ 输出: global.v3draw        │
 └────────────────────────────┘
         │
         ▼
 ┌─── 局部配准 ───┐
 │ local_registration.exe     │
 │ 输入: global.v3draw        │
 │      + config.txt          │
 │      + landmarks           │
 │ 输出: local_registered_*   │
 └────────────────────────────┘
         │
         ▼
 ┌──── STPS 变形（待编译）────┐
 │ Stps_warp_image.exe        │
 │ 输入: image + sub/tar markers │
 │ 输出: 变形后图像           │
 └────────────────────────────┘
```
