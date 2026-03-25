# BrainAtlas v0.2.0 — 架构设计文档

> 最后更新：2025-01

## 1. 系统概览

BrainAtlas 是一个基于 Web 的全脑三维图谱构建与浏览平台，主要面向 fMOST 等大规模神经影像数据。

### 核心能力
- **样本管理**：上传 v3draw → 自动转换 NIfTI + 生成 6 向预览
- **配准流水线**：Global Registration（后台异步执行，基于外部 exe）
- **三维浏览**：NiiVue WebGL 3D 查看器，支持原图/配准结果切换
- **项目管理**：多项目隔离，project.json 索引

### 技术栈
| 层 | 技术 |
|---|---|
| 前端 | 原生 HTML + NiiVue (WebGL) |
| 后端 | FastAPI (Python 3.13) |
| 任务系统 | 自研 ThreadPoolExecutor + JSON 持久化 |
| 配准引擎 | C++ exe (Vaa3D 插件系列) |
| 数据格式 | v3draw / NIfTI (.nii.gz) / marker |

---

## 2. 目录结构

```
brainatlas/
├── apps/brainatlas/
│   ├── backend/app/
│   │   ├── main.py              # FastAPI 入口，路由注册 + 处理器注册
│   │   ├── routes/
│   │   │   ├── health.py        # GET /api/health
│   │   │   ├── upload.py        # POST /api/upload
│   │   │   ├── prepare.py       # POST /api/prepare (同步兼容)
│   │   │   ├── samples.py       # GET/POST /api/samples/{id}
│   │   │   ├── registration.py  # POST /api/registration
│   │   │   ├── tasks.py         # 统一任务 CRUD + 日志
│   │   │   ├── projects.py      # GET /api/projects/{id}
│   │   │   └── results.py       # GET /api/results/{task_id}
│   │   ├── services/
│   │   │   ├── task_service.py      # 任务元数据 JSON 持久化
│   │   │   ├── task_runner.py       # 后台线程执行器
│   │   │   ├── registration_service.py  # 配准业务逻辑
│   │   │   ├── prepare_service.py   # 预处理业务逻辑
│   │   │   ├── upload_service.py    # 上传处理
│   │   │   ├── sample_service.py    # 样本 CRUD
│   │   │   └── project_service.py   # 项目索引管理
│   │   └── utils/
│   │       ├── paths.py             # 所有路径集中管理
│   │       └── json_io.py           # 原子化 JSON 读写
│   └── frontend/
│       ├── upload/                  # 上传页面
│       ├── viewer/viewer.html       # 3D 浏览器页面
│       └── assets/                  # 静态资源
├── pipeline/                        # 纯函数式管线（无 FastAPI 依赖）
│   ├── io/                          # v3draw 读取、NIfTI 转换
│   ├── preprocess/                  # 预览图生成
│   └── wrappers/                    # exe 调用封装
├── data/
│   └── projects/{project_id}/
│       ├── project.json             # 项目元数据
│       ├── samples/{sample_id}/     # 样本数据目录
│       └── tasks/{task_id}/         # 任务数据 + 日志
├── tools/                           # 外部二进制工具
│   ├── bin/global/CPU/              # Global 配准 exe
│   └── templates/                   # 参考图谱模板
└── config/                          # 配置文件
```

---

## 3. 任务系统设计

### 3.1 架构

```
[HTTP Request] → routes → task_runner.submit_task()
                              ↓
                     ThreadPoolExecutor (background)
                              ↓
                   handler(payload, task_logger)
                              ↓
                 task_service.update_task() ← JSON file
                 task_logger.info()         ← log file
```

### 3.2 任务生命周期

```
queued → running → completed
                 → failed
```

### 3.3 持久化

每个任务存储在 `data/projects/{project_id}/tasks/{task_id}/` 下：
- `task.json` — 任务元数据（状态、时间戳、payload、result）
- `task.log` — 执行日志（时间戳行格式）

### 3.4 Handler 注册

在 `main.py` 中注册处理器：

```python
from .services.task_runner import register_handler

register_handler("global_registration", run_global_registration_task)
register_handler("sample_prepare", run_prepare_task)
```

Handler 签名：`(payload: dict, task_logger: TaskLogger) -> dict`

---

## 4. API 端点

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/health` | 健康检查，返回版本 |
| POST | `/api/upload` | 上传 v3draw 文件 |
| POST | `/api/prepare` | 同步预处理（兼容） |
| GET | `/api/samples/{sample_id}` | 获取样本详情（含 hydrate） |
| POST | `/api/samples/{sample_id}/prepare` | 异步预处理（后台任务） |
| POST | `/api/registration` | 发起 Global 配准（后台任务） |
| GET | `/api/registration/latest` | 获取最新配准任务 |
| POST | `/api/tasks/register/global` | 统一任务提交入口 |
| GET | `/api/tasks` | 任务列表（支持 status 过滤） |
| GET | `/api/tasks/{task_id}` | 任务详情 |
| GET | `/api/tasks/{task_id}/log` | 任务日志（支持 tail） |
| GET | `/api/projects/{project_id}` | 项目概览（含样本/模板/任务摘要） |
| GET | `/api/results/{task_id}` | 任务结果 |
| GET | `/api/static/{path}` | 静态文件服务 |

---

## 5. 前端架构

### 5.1 Viewer 三栏布局

```
┌──────────┬──────────────────┬──────────┐
│ 视图控制  │    NiiVue 3D     │ 样本详情  │
│          │                  │ 任务状态  │
│ 显示模式  │   预览图 Grid     │ 任务日志  │
│ 颜色映射  │                  │          │
└──────────┴──────────────────┴──────────┘
```

### 5.2 数据源切换

- **原图**：`converted/nii_url`
- **Global 配准**：`global_registration/global_nii_url`
- **Local 配准**：Coming Soon
- **Template 构建**：Coming Soon

### 5.3 日志面板

右侧面板底部的可折叠日志区域：
- 自动轮询 `GET /api/tasks/{task_id}/log?tail=200`
- 任务完成/失败时自动停止轮询
- 语法高亮（时间戳灰色、ERROR 红色）

---

## 6. 数据流

### 6.1 上传 → 预处理 → 配准

```
1. POST /api/upload
   └→ 保存到 uploads/{project_id}/
   └→ 创建 sample.json (status: uploaded)

2. POST /api/samples/{id}/prepare  (异步)
   └→ submit_task("sample_prepare", ...)
   └→ [后台] v3draw → nii.gz + 6 向预览
   └→ 更新 sample.json (status: ready)

3. POST /api/tasks/register/global  (异步)
   └→ submit_task("global_registration", ...)
   └→ [后台] 调用 exe → global.v3draw → nii.gz + 预览
   └→ 更新 sample.json (global_registration_status: completed)
```

---

## 7. 未来规划

- [ ] Local Registration 集成
- [ ] Template 构建流程
- [ ] WebSocket 实时日志推送（替代轮询）
