<p align="center">
  <img src="apps/brainatlas/frontend/assets/brainatlas-logo.png" alt="BrainAtlas Logo" width="120" />
</p>

<h1 align="center">BrainAtlas</h1>

<p align="center">
  <strong>基于 Web 的全脑三维图谱构建与浏览平台</strong><br/>
  <em>A web-based whole-brain 3D atlas construction and visualization platform</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.2.0-blue?style=flat-square" alt="version" />
  <img src="https://img.shields.io/badge/python-3.13-green?style=flat-square&logo=python&logoColor=white" alt="python" />
  <img src="https://img.shields.io/badge/FastAPI-0.116-009688?style=flat-square&logo=fastapi&logoColor=white" alt="fastapi" />
  <img src="https://img.shields.io/badge/NiiVue-WebGL-orange?style=flat-square" alt="niivue" />
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=flat-square" alt="license" />
</p>

---

## 📖 概述

**BrainAtlas** 是一个面向 fMOST（荧光显微光学层析断层扫描）等大规模神经影像数据的全脑三维图谱构建平台。平台提供了从数据上传、格式转换、预览生成到全局配准的完整流水线，并通过基于 NiiVue 的 WebGL 3D 浏览器进行交互式可视化。

### 核心特性

- 🧠 **V3draw 原生支持** — 直接读取 Vaa3D `.v3draw` 格式，自动转换为 NIfTI
- 🔬 **六向预览** — 自动生成 XY/XZ/YZ 正交切片 + 三方向最大强度投影 (MIP)
- 📐 **全局配准** — 集成 C++ 高性能配准引擎，异步后台执行
- 🖥️ **3D WebGL 浏览器** — 基于 NiiVue 的多平面/三维渲染查看器
- ⚡ **异步任务系统** — 后台线程池执行 + JSON 持久化 + 实时日志
- 📂 **多项目管理** — 项目级隔离索引，支持懒加载

---

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (HTML)                      │
│   ┌──────────────┐           ┌──────────────────────┐   │
│   │  Upload Page  │           │   NiiVue 3D Viewer   │   │
│   │  (拖拽上传)   │           │ (多平面/3D渲染/日志)  │   │
│   └──────┬───────┘           └──────────┬───────────┘   │
├──────────┼──────────────────────────────┼───────────────┤
│          │         FastAPI Backend       │               │
│          ▼                              ▼               │
│   ┌──────────┐  ┌───────────┐  ┌──────────────┐        │
│   │  Upload   │  │  Samples  │  │    Tasks     │        │
│   │  Route    │  │  Route    │  │   Route      │        │
│   └────┬─────┘  └─────┬─────┘  └──────┬───────┘        │
│        │              │               │                 │
│   ┌────▼──────────────▼───────────────▼──────────┐      │
│   │            Services Layer                     │      │
│   │  upload_service │ sample_service │ task_runner │      │
│   │  prepare_service │ registration_service       │      │
│   │  project_service │ task_service               │      │
│   └────────────────────┬─────────────────────────┘      │
│                        │                                │
│   ┌────────────────────▼─────────────────────────┐      │
│   │          Pipeline (Pure Functions)            │      │
│   │  reader_v3draw → converter → nii_io          │      │
│   │  build_previews │ global_registration (exe)   │      │
│   └──────────────────────────────────────────────┘      │
├─────────────────────────────────────────────────────────┤
│                    Data Layer                            │
│   data/projects/{project_id}/                           │
│     ├── project.json          # 项目索引                │
│     ├── samples/{sample_id}/  # 样本数据                │
│     └── tasks/{task_id}/      # 任务JSON + 日志         │
└─────────────────────────────────────────────────────────┘
```

### 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | HTML5 + CSS3 + Vanilla JS + [NiiVue](https://github.com/niivue/niivue) (WebGL) |
| **后端** | [FastAPI](https://fastapi.tiangolo.com/) (Python 3.13) + Uvicorn |
| **任务系统** | 自研 `ThreadPoolExecutor` + JSON 文件持久化 |
| **配准引擎** | C++ exe (基于 Vaa3D 插件) |
| **数据格式** | V3draw / NIfTI (.nii.gz) / Marker |
| **图像处理** | NumPy + NiBabel + Pillow + ImageIO |

---

## 📂 项目结构

```
brainatlas/
├── apps/brainatlas/
│   ├── backend/app/
│   │   ├── main.py                  # FastAPI 入口
│   │   ├── routes/                  # 路由层
│   │   │   ├── health.py            #   健康检查
│   │   │   ├── upload.py            #   文件上传
│   │   │   ├── prepare.py           #   预处理 (同步兼容)
│   │   │   ├── samples.py           #   样本查询 + 异步预处理
│   │   │   ├── registration.py      #   配准提交
│   │   │   ├── tasks.py             #   任务管理 + 日志
│   │   │   ├── projects.py          #   项目概览
│   │   │   └── results.py           #   任务结果
│   │   ├── services/                # 业务逻辑层
│   │   │   ├── task_service.py      #   任务元数据 (JSON 持久化)
│   │   │   ├── task_runner.py       #   后台线程执行器
│   │   │   ├── registration_service.py  # 配准业务逻辑
│   │   │   ├── prepare_service.py   #   预处理业务逻辑
│   │   │   ├── upload_service.py    #   上传处理
│   │   │   ├── sample_service.py    #   样本 CRUD
│   │   │   └── project_service.py   #   项目索引管理
│   │   └── utils/                   # 工具函数
│   │       ├── paths.py             #   路径管理
│   │       └── json_io.py           #   原子化 JSON 读写
│   └── frontend/
│       ├── upload/                  # 上传页面
│       ├── viewer/viewer.html       # 3D 浏览器
│       └── assets/                  # 静态资源 + NiiVue
├── pipeline/                        # 纯函数式管线 (无 FastAPI 依赖)
│   ├── io/
│   │   ├── reader_v3draw.py         #   V3draw 格式解析
│   │   ├── converter.py             #   V3draw → NIfTI 转换
│   │   └── nii_io.py                #   NIfTI 读写
│   ├── preprocess/
│   │   └── build_previews.py        #   六向预览图生成
│   └── wrappers/
│       └── global_registration.py   #   C++ 配准 exe 封装
├── tools/
│   ├── bin/                         # 外部二进制工具
│   │   ├── global/CPU/              #   Global 配准引擎
│   │   └── win64_bin/               #   辅助工具
│   └── templates/                   # Atlas 参考模板
│       ├── 25um_568/                #   25μm 568nm 模板
│       └── fmost/                   #   fMOST 模板
├── config/
│   ├── paths.yaml                   # 路径配置
│   └── demo.yaml                    # Demo 服务配置
├── data/                            # 运行时数据 (gitignored)
├── scripts/                         # 独立脚本
├── tests/                           # 测试用例
└── docs/                            # 文档
    └── design.md                    # 架构设计文档
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

### 运行服务

```bash
# 启动开发服务器（自动热重载）
python -m uvicorn apps.brainatlas.backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

打开浏览器访问：

| 页面 | 地址 |
|------|------|
| **上传页面** | http://localhost:8000/upload |
| **3D 浏览器** | http://localhost:8000/viewer |
| **API 文档** | http://localhost:8000/docs |
| **健康检查** | http://localhost:8000/api/health |

---

## 🔄 工作流程

### 完整流水线

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Upload   │───▶│ Convert  │───▶│ Preview  │───▶│ Register │───▶│  View    │
│ (.v3draw) │    │ (NIfTI)  │    │ (6x PNG) │    │ (Global) │    │ (NiiVue) │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
```

### 1. 数据上传
通过 Web 界面拖拽或选择 `.v3draw` 文件上传：
- 自动生成唯一 `sample_id`
- 保存原始文件至项目目录
- 创建样本元数据 (`sample.json`)

### 2. 预处理 (自动)
上传完成后自动触发后台预处理任务：
- **格式转换**：V3draw → NIfTI (`.nii.gz`)
- **预览生成**：6 张 PNG（3 正交切片 + 3 MIP 投影）
- **统计信息**：计算 shape、dtype、min/max/mean

### 3. 全局配准
在查看器中点击发起 Global Registration：
- 异步提交后台任务，立即返回 `task_id`
- 调用 C++ 配准引擎对齐到 Atlas 模板
- 实时日志可在浏览器中查看
- 完成后自动生成配准结果的 NIfTI + 预览

### 4. 可视化
在 NiiVue 3D 浏览器中交互式查看：
- 切换原图 / 配准结果
- 多平面视图 / 3D 渲染
- XYZ 切片滑块 + 颜色映射
- 鼠标交互：左键切片、右键亮度/对比度、滚轮缩放

---

## 📡 API 参考

### 核心端点

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/health` | 健康检查，返回版本号 |
| `POST` | `/api/upload` | 上传文件 (multipart/form-data) |
| `GET` | `/api/samples/{sample_id}` | 获取样本详情 (含 hydrate) |
| `POST` | `/api/samples/{sample_id}/prepare` | 异步预处理 → 返回 task_id |
| `POST` | `/api/tasks/register/global` | 提交全局配准 → 返回 task_id |
| `GET` | `/api/tasks` | 任务列表 (支持 `?status=` 过滤) |
| `GET` | `/api/tasks/{task_id}` | 任务详情 |
| `GET` | `/api/tasks/{task_id}/log` | 任务日志 (支持 `?tail=N`) |
| `GET` | `/api/projects/{project_id}` | 项目概览 + 样本/任务索引 |
| `GET` | `/api/results/{task_id}` | 任务执行结果 |

### 示例请求

```bash
# 上传文件
curl -X POST http://localhost:8000/api/upload \
  -F "file=@brain_sample.v3draw" \
  -F "project_id=default"

# 查看样本
curl http://localhost:8000/api/samples/a1b2c3d4e5f6

# 提交配准
curl -X POST http://localhost:8000/api/tasks/register/global \
  -H "Content-Type: application/json" \
  -d '{"project_id":"default","moving_sample_id":"a1b2c3d4e5f6"}'

# 查看任务日志（最后50行）
curl http://localhost:8000/api/tasks/{task_id}/log?tail=50
```

> 完整 API 文档可在服务启动后访问 http://localhost:8000/docs (Swagger UI)

---

## ⚡ 任务系统

BrainAtlas 采用自研的异步任务系统，支持后台执行耗时操作。

```
[HTTP 请求] → Routes → task_runner.submit_task()
                            ↓
                   ThreadPoolExecutor (后台线程)
                            ↓
                  handler(payload, task_logger)
                            ↓
               task_service.update_task()  ← JSON 持久化
               task_logger.info()          ← 日志文件
```

### 任务生命周期

```
queued → running → completed ✅
                 → failed ❌
```

### 特性

- **持久化存储**：每个任务独立目录，包含 `task.json` + `task.log`
- **Handler 注册**：通过 `register_handler(task_type, fn)` 注册处理函数
- **实时日志**：`TaskLogger` 写入带时间戳的结构化日志，前端可轮询查看
- **线程安全**：内存缓存 + 文件锁保证并发安全

### 已注册 Handler

| task_type | Handler | 说明 |
|-----------|---------|------|
| `global_registration` | `run_global_registration_task` | 全局配准流程 |
| `sample_prepare` | `run_prepare_task` | 预处理 (转换 + 预览) |

---

## 🧬 数据管线 (Pipeline)

Pipeline 层为纯函数设计，不依赖 FastAPI，可独立使用。

### V3draw 读取

```python
from pipeline.io.reader_v3draw import read_v3draw

volume, meta = read_v3draw("brain.v3draw")
# volume: ndarray (Z, Y, X) or (C, Z, Y, X)
# meta: dict with shape, dtype, channels, etc.
```

支持 Vaa3D 格式特性：
- Magic: `raw_image_stack_by_hpeng`
- 字节序：Little/Big Endian 自动检测
- 数据类型：uint8 / uint16 / float32
- 多通道自动处理

### 格式转换

```python
from pipeline.io.converter import convert_v3draw_to_nifti

result = convert_v3draw_to_nifti(
    v3draw_path="input.v3draw",
    nii_path="output.nii.gz",
    meta_path="output_meta.json",
    spacing=(1.0, 1.0, 1.0)
)
```

### 预览生成

```python
from pipeline.preprocess.build_previews import build_previews_from_volume

preview_paths = build_previews_from_volume(volume, output_dir)
# → {"xy": "...", "xz": "...", "yz": "...", "mip_xy": "...", "mip_xz": "...", "mip_yz": "..."}
```

生成 6 张 PNG：
- **正交切片**：XY / XZ / YZ（取中间层）
- **最大强度投影**：MIP_XY / MIP_XZ / MIP_YZ
- 使用 percentile (p1, p99) 鲁棒归一化

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
| `test_reader_v3draw.py` | V3draw 格式解析 |
| `test_convert_v3draw.py` | 格式转换流程 |
| `test_save_nifti.py` | NIfTI 保存 |
| `test_build_previews.py` | 预览图生成 |

---

## ⚙️ 配置

### 路径配置 (`config/paths.yaml`)

```yaml
data_root: data                    # 数据根目录
projects_dir: data/projects        # 项目存储目录
temp_dir: data/temp                # 临时文件目录
uploads_dir: data/temp/uploads     # 上传暂存目录
```

### 服务配置 (`config/demo.yaml`)

```yaml
server:
  host: 127.0.0.1
  port: 8000
project:
  id: demo
```

---

## 🗺️ 路线图

- [x] V3draw 格式读取与 NIfTI 转换
- [x] 六向预览图自动生成
- [x] Global Registration 集成
- [x] NiiVue WebGL 3D 浏览器
- [x] 异步任务系统 (后台执行 + JSON 持久化)
- [x] 实时任务日志 (浏览器内查看)
- [x] 项目级管理与索引
- [ ] Local Registration 集成
- [ ] Template 构建流程
- [ ] 多样本批量处理
- [ ] WebSocket 实时日志推送
- [ ] 用户认证与权限管理

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

MIT License - 详见 [LICENSE](LICENSE) 文件

---

<p align="center">
  <sub>Built with ❤️ for neuroscience research</sub>
</p>