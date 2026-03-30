<p align="center">
  <img src="apps/brainatlas/frontend/assets/brainatlas-logo.png" alt="BrainAtlas Logo" width="120" />
</p>

<h1 align="center">BrainAtlas</h1>

<p align="center">
  <strong>小样本动态全脑三维图谱构建与可视化平台</strong><br/>
  <em>Small-Sample Dynamic Whole-Brain 3D Atlas Construction &amp; Visualization</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.2.0-blue?style=flat-square" alt="version" />
  <img src="https://img.shields.io/badge/python-3.13-green?style=flat-square&logo=python&logoColor=white" alt="python" />
  <img src="https://img.shields.io/badge/FastAPI-0.116-009688?style=flat-square&logo=fastapi&logoColor=white" alt="fastapi" />
  <img src="https://img.shields.io/badge/NiiVue-WebGL-orange?style=flat-square" alt="niivue" />
  <img src="https://img.shields.io/badge/SciPy-Harris_3D-8CAAE6?style=flat-square&logo=scipy&logoColor=white" alt="scipy" />
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=flat-square" alt="license" />
</p>

---

## 📖 概述

**BrainAtlas** 是一个面向 fMOST（荧光显微光学层析断层扫描）等大规模神经影像数据的**全脑三维动态图谱**构建平台。与传统静态图谱不同，本平台通过**迭代配准 + 收敛驱动**的流水线，从少量样本中动态构建模板脑图谱，适用于新物种、新模态等无现成图谱可用的场景。

平台覆盖从数据上传、格式转换、预览生成、全局配准、质量控制、T0 模板选择到多轮迭代模板构建的**完整 10 步流水线**，并通过基于 NiiVue 的 WebGL 3D 浏览器进行交互式可视化。

### 核心特性

| 特性 | 说明 |
|------|------|
| 🧠 **V3draw 原生支持** | 直接读写 Vaa3D `.v3draw` 格式，自动转换为 NIfTI |
| 🔬 **六向预览** | 自动生成 XY/XZ/YZ 正交切片 + 三方向最大强度投影 (MIP) |
| 📐 **全局配准** | 集成 C++ 高性能全局配准引擎，仿射对齐到参考模板 |
| 🎯 **7 因子 QC 评分** | 文件完整性 · 图像统计 · 前景体积 · 边界裁剪 · 对称性 · 清晰度 · 综合评分 |
| 🏗️ **动态模板构建** | Harris 角点检测 → 局部配准 → 强度归一化 → Marker 均值 → STPS 形变 → 收敛判定 |
| 🖥️ **3D WebGL 浏览器** | 基于 NiiVue 的多平面/三维渲染查看器 |
| ⚡ **异步任务系统** | 后台线程池执行 + JSON 持久化 + 实时日志轮询 |
| 📂 **多项目管理** | 项目级隔离，支持批量操作 + 流水线状态看板 |

---

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (HTML5)                          │
│  ┌──────────────┐  ┌──────────────────────┐  ┌──────────────┐  │
│  │  Upload Page  │  │   NiiVue 3D Viewer   │  │   Monitor    │  │
│  │  拖拽上传     │  │  多平面/3D渲染/切片   │  │  任务监控     │  │
│  │  QC 排行榜    │  │  原图/配准结果切换     │  │  实时日志     │  │
│  │  T0 选择弹窗  │  │  颜色映射/亮度对比度   │  │  进度面板     │  │
│  └──────┬───────┘  └──────────┬───────────┘  └──────┬───────┘  │
├─────────┼─────────────────────┼─────────────────────┼──────────┤
│         ▼         FastAPI Backend (40+ Endpoints)    ▼          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                     Routes (14 files)                    │    │
│  │  upload│samples│batch│tasks│registration│qc│template│…   │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   Services (12 files)                    │    │
│  │  task_runner│registration│prepare│template│qc│batch│…    │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │             Pipeline (21 Pure-Function Modules)          │    │
│  │  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │    │
│  │  │   I/O    │ │Preprocess│ │  Atlas    │ │  Wrappers  │  │    │
│  │  │v3draw R/W│ │previews  │ │builder   │ │global_reg  │  │    │
│  │  │converter │ │enhance   │ │harris    │ │local_reg   │  │    │
│  │  │nii_io   │ │          │ │QC/版本   │ │stps        │  │    │
│  │  └─────────┘ └──────────┘ └──────────┘ └────────────┘  │    │
│  └─────────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────┤
│                        Data Layer                                │
│  data/projects/{project_id}/                                    │
│    ├── project.json            # 项目索引                       │
│    ├── samples/{sample_id}/    # 样本 (v3draw + nii + preview)  │
│    ├── tasks/{task_id}/        # 任务 JSON + 日志               │
│    └── templates/v{k}/         # 模板版本 (v0=T0, v1, v2…)     │
└─────────────────────────────────────────────────────────────────┘
```

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **前端** | HTML5 + CSS3 + Vanilla JS + [NiiVue](https://github.com/niivue/niivue) | WebGL 三维渲染，无框架依赖 |
| **后端** | [FastAPI](https://fastapi.tiangolo.com/) 0.116 + Uvicorn | Python 3.13，异步 HTTP + 静态文件服务 |
| **任务系统** | `ThreadPoolExecutor` + JSON 文件持久化 | 后台执行 + 实时日志 + 自动恢复 |
| **角点检测** | 纯 Python (SciPy / NumPy) | 2.5D Harris：逐层 2D 检测 + 3D NMS |
| **配准引擎** | C++ exe (Vaa3D 生态) | 全局仿射 + 局部非刚性 (B-spline + STPS) |
| **形变场** | STPS (Scattered Thin-Plate Spline) | C++17 现代化实现，支持块插值 |
| **数据格式** | V3draw · NIfTI (.nii.gz) · Marker · PNG | 全链路格式支持 |
| **图像处理** | NumPy 2.4 · NiBabel 5.4 · SciPy · Pillow | percentile 归一化 + MIP 投影 |

---

## 🔄 完整流水线 (10 步)

```
 ❶          ❷           ❸           ❹          ❺           ❻
Upload → Convert → Preview → Global  → QC    → Select
.v3draw   NIfTI    6×PNG    Register   Score    T0

                                                  ↓

                    ❼           ❽           ❾           ❿
                  Harris → Local    → STPS   → Converge?
                  corners  Register   Deform   ──YES──▶ Done ✅
                  (.marker) (.v3draw)  (.v3draw)  │
                                                  NO
                                                  ↓
                                              Iterate ↩
```

| 步骤 | 模块 | 输入 | 输出 | 说明 |
|------|------|------|------|------|
| ❶ 上传 | `upload_service` | `.v3draw` 文件 | `sample.json` | 拖拽上传 / 文件夹批量扫描 |
| ❷ 转换 | `converter` | V3draw | `.nii.gz` + 元数据 | 自动字节序检测，支持多通道 |
| ❸ 预览 | `build_previews` | NIfTI 体数据 | 6 × PNG | XY/XZ/YZ 切片 + 三向 MIP |
| ❹ 全局配准 | `global_registration` | 原始体 + Atlas 模板 | 配准后 V3draw + NIfTI | C++ 仿射对齐引擎 |
| ❺ QC 评分 | `qc_global_results` | 配准体 | 0–1 分数 + 等级 | 7 因子加权评分模型 |
| ❻ T0 选择 | `template_selector` | QC 排行榜 | `templates/v0/` | 交互式 Top-3 候选弹窗 |
| ❼ Harris 角点 | `harris_wrapper` | 当前模板 | `.marker` 控制点 | 2.5D Harris (SciPy)，3D NMS |
| ❽ 局部配准 | `local_registration` | 样本 + 模板 + 控制点 | 配准后样本 | C++ 非刚性配准 (B-spline) |
| ❾ STPS 形变 | `stps_wrapper` | 模板 + 对应标记 | 更新后模板 | Scattered TPS 形变场 |
| ❿ 收敛判定 | `convergence` | 前后模板 | 收敛/继续 | L2 体素差阈值 (默认 0.5) |

---

## 📂 项目结构

```
brainatlas/
├── apps/brainatlas/
│   ├── backend/app/
│   │   ├── main.py                      # FastAPI 入口 + 启动清理
│   │   ├── routes/                      # 路由层 (14 个文件, 40+ 端点)
│   │   │   ├── health.py                #   GET  /api/health
│   │   │   ├── upload.py                #   POST /api/upload
│   │   │   ├── samples.py               #   GET|POST|DELETE /api/samples/{id}
│   │   │   ├── batch.py                 #   POST /api/batch/prepare|register
│   │   │   ├── tasks.py                 #   POST /api/tasks/register/global
│   │   │   ├── qc.py                    #   POST /api/samples/{id}/qc/global
│   │   │   ├── template.py              #   POST /api/template/select-t0|build
│   │   │   ├── projects.py              #   GET  /api/projects/{id}
│   │   │   ├── session.py               #   POST /api/session/cleanup
│   │   │   └── ...                      #   scan, prepare, registration, results, admin
│   │   ├── services/                    # 业务逻辑层 (12 个文件)
│   │   │   ├── task_runner.py           #   ThreadPoolExecutor + TaskLogger
│   │   │   ├── task_service.py          #   任务生命周期 (JSON 持久化)
│   │   │   ├── registration_service.py  #   全局配准 handler
│   │   │   ├── template_service.py      #   T0 选择 + 模板构建 handler
│   │   │   ├── qc_service.py            #   7 因子 QC 评分
│   │   │   ├── batch_service.py         #   批量预处理 / 批量配准
│   │   │   └── ...                      #   upload, prepare, sample, project, scan, session
│   │   └── utils/                       # paths.py, json_io.py
│   └── frontend/
│       ├── upload/upload.html           # 数据上传 + QC 排行榜 + T0 选择
│       ├── viewer/viewer.html           # NiiVue 3D 浏览器
│       ├── monitor/monitor.html         # 任务监控面板
│       └── assets/                      # 静态资源 (CSS / JS / NiiVue)
├── pipeline/                            # 纯函数管线 (21 个模块, 无 FastAPI 依赖)
│   ├── io/                              # I/O 层
│   │   ├── reader_v3draw.py             #   V3draw 解析 (支持 LE/BE, uint8/16/f32)
│   │   ├── writer_v3draw.py             #   V3draw 写出
│   │   ├── converter.py                 #   V3draw → NIfTI 转换
│   │   └── nii_io.py                    #   NIfTI 读写
│   ├── preprocess/                      # 预处理
│   │   ├── build_previews.py            #   六向预览 (切片 + MIP)
│   │   └── enhance.py                   #   图像增强
│   ├── atlas/                           # 模板构建核心 (7 个模块)
│   │   ├── template_builder.py          #   迭代编排器
│   │   ├── template_selector.py         #   T0 选择
│   │   ├── template_version.py          #   版本管理 (v0, v1, v2…)
│   │   ├── qc_global_results.py         #   7 因子 QC 评分
│   │   ├── convergence.py               #   收敛判定 (L2 norm)
│   │   ├── intensity_normalize.py       #   百分位归一化 + 体素均值
│   │   └── marker_average.py            #   标记点均值计算
│   ├── wrappers/                        # 外部工具封装
│   │   ├── global_registration.py       #   C++ 全局配准
│   │   ├── local_registration.py        #   C++ 局部配准
│   │   ├── harris_wrapper.py            #   2.5D Harris (纯 Python/SciPy)
│   │   └── stps_wrapper.py              #   STPS 形变场
│   └── common/                          # 公共工具
│       └── file_naming.py               #   统一文件命名规范
├── tools/
│   ├── bin/                             # 外部 C++ 二进制
│   │   ├── global/CPU/                  #   全局配准引擎
│   │   ├── local/local_hhm/CPU/         #   局部配准引擎
│   │   ├── STPS/                        #   STPS 原始版本
│   │   ├── win64_bin/                   #   辅助 DLL
│   │   └── 3rdparty/                    #   Qt 4.8.6 等第三方库
│   ├── src_modern/stps/                 #   STPS C++17 现代化源码
│   └── templates/                       # Atlas 参考模板
│       ├── 25um_568/                    #   25μm 568nm (atlas_v3draw + landmarks)
│       └── fmost/                       #   fMOST 模板
├── config/
│   ├── paths.yaml                       # 路径配置
│   └── demo.yaml                        # 运行时 + 模板构建参数
├── data/                                # 运行时数据 (gitignored)
├── scripts/                             # 独立脚本 (诊断 / 恢复 / 调试)
├── tests/                               # 7 个测试模块
├── docs/
│   ├── design.md                        # 统一架构设计文档 (20 节)
│   └── tool_inventory.md                # 工具清单
└── requirements.txt                     # 11 个依赖
```

---

## 🚀 快速开始

### 环境要求

- **Python** ≥ 3.11（推荐 3.13）
- **Windows** x64（配准引擎为 Windows 原生 exe）
- **Git**

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/Jeremy-Luyt/brainatlas.git
cd brainatlas

# 2. 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # Linux/macOS

# 3. 安装依赖
pip install -r requirements.txt
```

### 启动服务

```bash
# 设置 PYTHONPATH 并启动开发服务器（自动热重载）
$env:PYTHONPATH='.'   # PowerShell
python -m uvicorn apps.brainatlas.backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

打开浏览器访问：

| 页面 | 地址 | 说明 |
|------|------|------|
| **数据上传** | http://localhost:8000/upload | 拖拽上传、批量扫描、QC 排行、T0 选择 |
| **3D 浏览器** | http://localhost:8000/viewer | NiiVue 多平面/3D 渲染 |
| **任务监控** | http://localhost:8000/monitor | 实时日志、进度追踪 |
| **API 文档** | http://localhost:8000/docs | Swagger UI 自动生成 |

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `BRAINATLAS_AUTO_CLEAN_SESSION_ON_START` | `1` | 启动时自动清理上次会话数据；设为 `0` 保留 |

---

## 🎯 QC 质量评分

每个全局配准完成的样本将经历 **7 因子自动 QC 评分**：

| 因子 | 检测内容 | 权重 |
|------|----------|------|
| 文件完整性 | 配准产物文件是否齐全 | 基础门槛 |
| 图像统计 | min/max/mean 值合理性 | 0.10 |
| 前景体积 | 非零体素占比是否在合理范围 | 0.20 |
| 边界裁剪 | 边界面非零像素比例 | 0.15 |
| 对称性 | 左右半球 NCC 相关系数 | 0.20 |
| 清晰度 | Laplacian 方差 (结构信息量) | 0.20 |
| **综合评分** | 加权求和 → 0.0 ~ 1.0 | — |

**等级划分**：`excellent` ≥ 0.85 · `good` ≥ 0.70 · `review` ≥ 0.55 · `poor` < 0.55

QC 排行榜显示在上传页面右侧面板，用户可从可视化排名中**交互式选择 T0 初始模板**。

---

## 📡 API 参考

### 核心端点 (40+)

<details>
<summary><b>展开完整端点列表</b></summary>

| Method | Path | 说明 |
|--------|------|------|
| **基础** | | |
| `GET` | `/api/health` | 健康检查，返回版本号 |
| `POST` | `/api/upload` | 上传文件 (multipart/form-data) |
| `POST` | `/api/scan` | 扫描文件夹中的可用格式 |
| **样本管理** | | |
| `GET` | `/api/samples/{id}` | 获取样本详情 (自动 hydrate 配准结果) |
| `POST` | `/api/samples/{id}/prepare` | 异步预处理 → 返回 task_id |
| `DELETE` | `/api/samples/{id}` | 删除样本及全部产物 |
| **批量操作** | | |
| `POST` | `/api/batch/prepare` | 批量预处理所有未处理样本 |
| `POST` | `/api/batch/register/global` | 批量提交全局配准 |
| **任务系统** | | |
| `POST` | `/api/tasks/register/global` | 提交单个全局配准任务 |
| `GET` | `/api/tasks` | 任务列表 (支持 `?status=` / `?project_id=`) |
| `GET` | `/api/tasks/{id}` | 任务详情 |
| `GET` | `/api/tasks/{id}/log` | 任务日志 (支持 `?tail=N`) |
| **QC 评分** | | |
| `POST` | `/api/samples/{id}/qc/global` | 单样本 QC 评分 |
| `POST` | `/api/projects/{pid}/qc/global` | 项目级批量 QC |
| `POST` | `/api/samples/{id}/qc/manual-review` | 人工审核标记 |
| `GET` | `/api/projects/{pid}/template-candidates` | 模板候选列表 (按 QC 降序) |
| **模板构建** | | |
| `POST` | `/api/template/select-t0` | 选择 T0 (支持指定 sample_id) |
| `POST` | `/api/template/build` | 启动迭代模板构建后台任务 |
| `GET` | `/api/template/versions` | 列出所有模板版本 |
| **项目** | | |
| `GET` | `/api/projects/{pid}` | 项目概览 + 样本/任务索引 |
| `GET` | `/api/projects/{pid}/pipeline-status` | 流水线进度统计 |
| `POST` | `/api/session/cleanup` | 清理会话数据 |

</details>

### 示例请求

```bash
# 上传文件
curl -X POST http://localhost:8000/api/upload \
  -F "file=@brain_sample.v3draw" \
  -F "project_id=default"

# 批量全局配准
curl -X POST http://localhost:8000/api/batch/register/global \
  -H "Content-Type: application/json" \
  -d '{"project_id":"default"}'

# 交互式选择 T0
curl -X POST http://localhost:8000/api/template/select-t0 \
  -H "Content-Type: application/json" \
  -d '{"project_id":"default","sample_id":"a1b2c3d4e5f6"}'

# 启动模板构建
curl -X POST http://localhost:8000/api/template/build \
  -H "Content-Type: application/json" \
  -d '{"project_id":"default","max_iterations":3,"convergence_threshold":0.5}'

# 查看任务日志（最后 50 行）
curl "http://localhost:8000/api/tasks/{task_id}/log?tail=50"
```

---

## ⚡ 任务系统

BrainAtlas 采用自研的异步任务系统，支持后台执行耗时操作。

```
[HTTP 请求] → Routes → task_service.create_task()
                            ↓
                  task_runner.submit_task()
                            ↓
                   ThreadPoolExecutor (后台线程)
                            ↓
                  handler(payload, task_logger)
                      ↓              ↓
           update_task(status)   task_logger.info()
                  ↓                    ↓
            task.json (持久化)    task.log (实时日志)
```

### 任务生命周期

```
queued → running → completed ✅
                 → failed ❌
```

### 已注册 Handler

| task_type | Handler | 说明 |
|-----------|---------|------|
| `global_registration` | `run_global_registration_task` | 全局仿射配准 (C++ exe) |
| `sample_prepare` | `run_prepare_task` | 格式转换 + 预览生成 + QC |
| `template_build` | `run_template_build_task` | 迭代模板构建 (多步流水线) |

### 特性

- **持久化存储**：每个任务独立目录，包含 `task.json` + `task.log`
- **Handler 注册**：通过 `register_handler(task_type, fn)` 动态注册
- **实时日志**：`TaskLogger` 写入带时间戳的结构化日志，前端轮询展示
- **僵尸任务恢复**：服务重启时自动将残留 `running`/`queued` 任务标记为 `failed`
- **会话清理**：基于父进程 PID 的哨兵机制，区分热重载与真正重启

---

## 🧬 数据管线 (Pipeline)

Pipeline 层为**纯函数设计**，不依赖 FastAPI，可作为独立库使用。

### V3draw 读写

```python
from pipeline.io.reader_v3draw import read_v3draw
from pipeline.io.writer_v3draw import write_v3draw

volume, meta = read_v3draw("brain.v3draw")
# volume: ndarray (Z, Y, X) 或 (C, Z, Y, X)
# meta: dict {shape, dtype, channels, byte_order, …}

write_v3draw("output.v3draw", volume)
```

支持 Vaa3D 格式特性：
- Magic: `raw_image_stack_by_hpeng`
- 字节序：Little/Big Endian 自动检测
- 数据类型：uint8 / uint16 / float32
- 多通道自动处理

### Harris 角点检测 (纯 Python)

```python
from pipeline.wrappers.harris_wrapper import run_harris

result = run_harris(
    input_image="template.v3draw",
    output_marker="landmarks.marker",
    nms_2d=15, nms_3d=15, max_points=50,
)
# → {"marker_path": "...", "point_count": 50, "status": "completed"}
```

2.5D Harris 算法：逐 Z 层计算 2D Harris 响应 → 堆叠为 3D 响应场 → 3D 非极大值抑制 → 输出 Vaa3D `.marker` 格式。

### 模板构建

```python
from pipeline.atlas.template_builder import run_template_build

result = run_template_build(
    project_dir=Path("data/projects/default"),
    sample_entries=[{"sample_id": "abc", "global_v3draw": "path/to/abc.v3draw"}, ...],
    config={"max_iterations": 3, "convergence_threshold": 0.5, ...},
    logger=my_logger,
)
# → {"final_version": 2, "total_iterations": 2, "converged": True}
```

每次迭代执行：Harris 角点 → 局部配准 → Marker 均值 → 强度归一化 → STPS 形变 → 收敛检查。

---

## ⚙️ 配置

### 路径配置 (`config/paths.yaml`)

```yaml
data_root: data                    # 数据根目录
projects_dir: data/projects        # 项目存储目录
temp_dir: data/temp                # 临时文件目录
uploads_dir: data/temp/uploads     # 上传暂存目录
```

### 运行时 + 模板构建 (`config/demo.yaml`)

```yaml
server:
  host: 127.0.0.1
  port: 8000

template_build:
  enabled: true
  max_iterations: 3
  convergence_threshold: 0.5

landmarks:
  extractor: harris
  point_count: 50             # Harris 选取的控制点数量
  nms_2d: 15                  # 2D 非极大值抑制窗口
  nms_3d: 15                  # 3D 非极大值抑制窗口

intensity_normalize:
  method: percentile
  low_percentile: 1           # p1 下截断
  high_percentile: 99         # p99 上截断

stps:
  exe: tools/src_modern/stps/build/bin/stps.exe
  df_method: 1                # 形变场方法
  block_size: 4               # 块插值大小
  lambda: 0.2                 # 平滑约束
```

---

## 🧪 测试

```bash
# 运行全部测试
python -m pytest tests/ -v

# 运行单个测试
python -m pytest tests/test_reader_v3draw.py -v
```

| 测试文件 | 覆盖范围 |
|----------|----------|
| `test_reader_v3draw.py` | V3draw 格式解析与数据校验 |
| `test_convert_v3draw.py` | V3draw → NIfTI 转换链路 |
| `test_save_nifti.py` | NIfTI 输出文件验证 |
| `test_build_previews.py` | 六向预览图生成 |
| `test_global_registration.py` | 全局配准工作流 |
| `test_prepare_integration.py` | 预处理完整链路 |
| `test_atlas_dir.py` | Atlas 模板目录校验 |

---

## 🗺️ 路线图

- [x] V3draw 格式读写 + NIfTI 转换
- [x] 六向预览图自动生成 (切片 + MIP)
- [x] 全局配准 (C++ 仿射引擎)
- [x] NiiVue WebGL 3D 浏览器
- [x] 异步任务系统 (ThreadPoolExecutor + JSON)
- [x] 实时任务日志 (浏览器内轮询)
- [x] 多项目管理 + 批量操作
- [x] 7 因子自动 QC 评分
- [x] 交互式 T0 模板选择 (Top-3 弹窗)
- [x] Harris 角点检测 (纯 Python/SciPy)
- [x] 局部配准集成 (C++ B-spline)
- [x] STPS 形变场 (C++17)
- [x] 迭代模板构建流水线 (收敛驱动)
- [x] 强度归一化 + Marker 均值
- [x] 样本删除功能
- [x] 任务监控面板 (Monitor)
- [ ] WebSocket 实时日志推送
- [ ] 多用户权限管理
- [ ] GPU 加速配准

---

## 📊 项目规模

| 指标 | 数量 |
|------|------|
| API 端点 | 40+ |
| 路由文件 | 14 |
| 服务模块 | 12 |
| Pipeline 模块 | 21 |
| 前端页面 | 3 (Upload / Viewer / Monitor) |
| 测试模块 | 7 |
| 后台 Handler | 3 (prepare / registration / template_build) |
| Atlas 模板 | 2 (25μm_568 / fMOST) |
| 依赖包 | 11 |

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

```bash
# Fork 后克隆
git clone https://github.com/<your-username>/brainatlas.git

# 创建特性分支
git checkout -b feature/your-feature

# 提交并推送
git commit -m "feat: add your feature"
git push origin feature/your-feature
```

---

## 📄 License

MIT License — 详见 [LICENSE](LICENSE) 文件

---

<p align="center">
  <sub>Built with ❤️ for neuroscience research</sub>
</p>