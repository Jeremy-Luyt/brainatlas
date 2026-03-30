# BrainAtlas — 统一架构设计文档

> 最后更新：2026-03-25

---

## 1. 项目定位

BrainAtlas 是一个面向小样本、多模态三维鼠脑影像的数据处理、配准、模板构建与可视化平台。平台不是只做"单次配准演示"，而是形成从原始数据到动态脑图谱的工程化流程，包括：数据接入、预处理、质量评估、全局配准、局部对齐、模板构建、版本更新和结果展示。

项目定位为"小样本动态脑图谱构建与可视化平台"，强调以统一平台集成预处理、配准、模板更新与可视化展示。主流图谱往往采用"静态模板+单次配准"范式，而本项目探索"小样本+动态模板"的更新机制，并配套平台化实现。

### 1.1 技术栈

| 层 | 技术 |
|---|---|
| 前端 | 原生 HTML + NiiVue (WebGL) |
| 后端 | FastAPI (Python 3.13) |
| 任务系统 | 自研 ThreadPoolExecutor + JSON 持久化 |
| 配准引擎 | C++ exe (Global/Local/Harris/STPS) |
| STPS | 现代 C++17 重构 (Eigen3 + CLI11)，tools/src_modern/stps/ |
| 数据格式 | v3draw / NIfTI (.nii.gz) / marker |

---

## 2. 设计原则

### 2.1 工程原则

- **一套代码，两套配置**：同一套代码同时支持 demo 和 lab 版本，只通过参数切换行为，不允许维护两套分叉代码。
- **先跑通，再增强**：优先保证最小闭环可运行，再逐步提高点数、样本数和迭代深度。
- **算法与平台分层**：前端、后端、预处理、配准、模板构建、可视化要分层，不把旧工具逻辑直接塞进页面。
- **旧工具先接管，不轻易重写**：已有 exe / bat / legacy C++ 工具先接入平台，后续再视情况重构。
- **结果可追溯**：每一步都必须保存日志、配置、输入输出路径和版本信息。
- **真实功能与示意功能区分**：界面中已接通的真实能力和后续规划功能必须明确区分。

### 2.2 当前阶段硬约束

以下约束视为当前版本的硬约束：

1. 不直接使用现成均值模板作为最终模板，而是从自己的样本开始构建。
2. QC 已纳入平台，模板脑选择必须基于 QC 结果。
3. local 支持自定义模板。
4. 当前阶段不要求提供 segmentation 图像。
5. 模板点由 harris.exe 自动提取。
6. 取点个数可配置，demo 默认 50 点。
7. STPS 已编译完成并可调用（tools/src_modern/stps/build/bin/stps.exe）。
8. STPS 不输出独立形变场参数文件，只输出 warp 后图像和 JSON 摘要。
9. local 输出的 sub/tar 点序跨样本严格一致，可按索引直接平均。
10. 模板主体来自局部配准后图像的逐体素平均，不是点坐标平均。
11. 点平均只用于形状校正，不直接生成模板图像。
12. 模板迭代次数最多不超过 7 次。
13. 支持人工提前终止迭代，停止后当前模板必须作为正式版本保留。
14. demo 与 lab 版本共用同一套流程，只通过配置文件调整参数与规模。
15. 已完成全局配准的样本，再次点"一键全部全局配准"时自动跳过。

---

## 3. 平台功能模块

### 3.1 数据接入模块

- 上传 .v3draw 等三维脑图像
- 生成 project_id、sample_id
- 样本目录与元数据管理
- 原始文件与结果文件组织

### 3.2 预处理模块

- 数据质量检查
- 降采样（可选）
- 去伪影（可选）
- 亮度自适应 / 亮度纹理增强（可选）
- 去条纹（可选）
- 预览图生成

所有预处理步骤由配置驱动，可在 demo 和 lab 模式下启用不同参数。

### 3.3 配准模块

- 全局配准
- 局部配准
- Harris 自动取点
- STPS 图像变形
- 日志和中间结果保存

### 3.4 模板构建模块

- 初始模板脑候选排序与选择
- 局部配准后图像强度归一化 + 逐体素均值
- 平均点集计算
- STPS 形状校正
- 模板版本生成与更新
- 收敛判断和人工停止控制

### 3.5 质量评估模块

- 样本级 QC
- 配准结果级 QC
- 模板候选排序
- 模板版本比较

### 3.6 可视化与平台交互模块

- upload 页面：上传、任务控制、状态查看
- viewer 页面：preview、结果信息、版本展示
- 后期扩展：脑区浏览、3D atlas、模板差异查看

---

## 4. 工程目录结构

```
brainatlas/
├── apps/brainatlas/
│   ├── backend/app/
│   │   ├── main.py                      # FastAPI 入口，路由+处理器注册
│   │   ├── routes/
│   │   │   ├── health.py                # GET /api/health
│   │   │   ├── upload.py                # POST /api/upload
│   │   │   ├── prepare.py               # POST /api/prepare
│   │   │   ├── samples.py               # GET/POST /api/samples/{id}
│   │   │   ├── registration.py          # POST /api/registration
│   │   │   ├── batch.py                 # POST /api/batch/register/global 等
│   │   │   ├── tasks.py                 # 统一任务 CRUD + 日志
│   │   │   ├── projects.py              # GET /api/projects/{id}
│   │   │   └── results.py               # GET /api/results/{task_id}
│   │   ├── services/
│   │   │   ├── task_service.py          # 任务元数据 JSON 持久化
│   │   │   ├── task_runner.py           # 后台线程执行器（heavy task 信号量=1）
│   │   │   ├── registration_service.py  # 配准业务逻辑
│   │   │   ├── batch_service.py         # 批量任务过滤与投递
│   │   │   ├── prepare_service.py       # 预处理业务逻辑
│   │   │   ├── upload_service.py        # 上传处理
│   │   │   ├── sample_service.py        # 样本 CRUD
│   │   │   └── project_service.py       # 项目索引管理
│   │   └── utils/
│   │       ├── paths.py                 # 所有路径集中管理
│   │       └── json_io.py               # 原子化 JSON 读写
│   └── frontend/
│       ├── upload/                      # 上传页面（含一键批量按钮）
│       ├── viewer/viewer.html           # 3D 浏览器页面
│       └── assets/                      # 静态资源
├── pipeline/                            # 纯函数式管线（无 FastAPI 依赖）
│   ├── io/                              # v3draw 读取、NIfTI 转换
│   ├── preprocess/                      # 预处理实现
│   ├── wrappers/                        # exe 调用封装
│   │   ├── global_registration.py
│   │   ├── local_registration.py
│   │   ├── harris_wrapper.py
│   │   └── stps_wrapper.py
│   ├── atlas/                           # 模板构建核心
│   │   ├── template_selector.py         # 初始模板选择
│   │   ├── template_builder.py          # 迭代模板构建
│   │   ├── intensity_normalize.py       # 强度归一化
│   │   ├── marker_average.py            # 点集平均
│   │   └── convergence.py              # 收敛判断
│   └── common/                          # 共享工具
├── tools/
│   ├── bin/                             # 外部二进制（global/local/harris）
│   ├── src_modern/stps/                 # 现代化 STPS（C++17, 已编译）
│   ├── src_legacy/                      # 原始代码备份
│   ├── templates/                       # 参考图谱模板
│   └── batch/                           # 批处理脚本
├── data/
│   └── projects/{project_id}/
│       ├── project.json                 # 项目元数据
│       ├── samples/{sample_id}/         # 样本数据目录
│       ├── templates/{version}/         # 模板版本目录
│       └── tasks/{task_id}/             # 任务数据 + 日志
├── config/
│   ├── demo.yaml                        # demo 版本配置
│   └── lab.yaml                         # 实验室版本配置
└── docs/
```

---

## 5. 任务系统设计

### 5.1 架构

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

### 5.2 任务生命周期

```
queued → running → completed
                 → failed
```

### 5.3 持久化

每个任务存储在 `data/projects/{project_id}/tasks/{task_id}/` 下：
- `task.json` — 任务元数据（状态、时间戳、payload、result）
- `task.log` — 执行日志（时间戳行格式）

### 5.4 Handler 注册

```python
register_handler("global_registration", run_global_registration_task)
register_handler("local_registration", run_local_registration_task)
register_handler("template_build", run_template_build_task)
register_handler("sample_prepare", run_prepare_task)
```

Handler 签名：`(payload: dict, task_logger: TaskLogger) -> dict`

### 5.5 幂等性保护

批量任务在 `batch_service.py` 中做状态过滤：
- `global_registration_status == "completed"` → 自动跳过
- `global_registration_status == "running"` → 自动跳过
- `filename == "global.v3draw"` → 不能配准模板自身
- `prepare_status not in {"completed"}` → 预处理未完成不提交

---

## 6. API 端点

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/upload` | 上传 v3draw |
| POST | `/api/prepare` | 同步预处理（兼容） |
| GET | `/api/samples/{sample_id}` | 样本详情 |
| POST | `/api/samples/{sample_id}/prepare` | 异步预处理 |
| POST | `/api/registration` | 单样本 Global 配准 |
| POST | `/api/batch/register/global` | 一键全部全局配准 |
| POST | `/api/batch/register/local` | 一键全部局部配准 |
| POST | `/api/template/build` | 启动模板构建迭代 |
| POST | `/api/template/stop` | 人工停止模板迭代 |
| GET | `/api/templates/{version}` | 模板版本详情 |
| GET | `/api/tasks` | 任务列表 |
| GET | `/api/tasks/{task_id}` | 任务详情 |
| GET | `/api/tasks/{task_id}/log` | 任务日志 |
| GET | `/api/projects/{project_id}` | 项目概览 |
| GET | `/api/static/{path}` | 静态文件服务 |

---

## 7. 前端架构

### 7.1 upload 页面

定位为"数据接入与任务控制台"，负责：上传样本、查看样本状态、启动预处理、启动 global/local、启动模板构建、跳转 viewer。

### 7.2 viewer 页面

定位为"结果展示与模板浏览页"。

**三栏布局：**

```
┌──────────┬──────────────────┬──────────┐
│ 视图控制  │    NiiVue 3D     │ 样本详情  │
│          │                  │ 任务状态  │
│ 显示模式  │   预览图 Grid     │ 任务日志  │
│ 颜色映射  │                  │          │
└──────────┴──────────────────┴──────────┘
```

**数据源切换：**
- 原图：`converted/nii_url`
- Global 配准：`global_registration/global_nii_url`
- Local 配准：local_registration/local_nii_url
- 模板版本：templates/{version}/template.nii.gz

**真实功能 vs 示意功能：** 真实 preview、sample/template 信息、QC 结果、版本信息、日志入口必须是真实功能。3D atlas、脑区高亮、版本差异热图可先做示意，标注 "Coming Soon"。

---

## 8. 配置驱动设计

### 8.1 配置文件

```
config/
├── demo.yaml     # demo 版本（自己电脑）
└── lab.yaml      # 实验室电脑版本
```

### 8.2 demo 版本默认参数

```yaml
runtime:
  mode: demo

template_build:
  enabled: true
  max_iterations: 3
  allow_manual_stop: true
  convergence_threshold: 0.5   # 体素单位

landmarks:
  extractor: harris
  point_count: 50

dataset:
  max_samples_for_v1: 3

intensity_normalize:
  method: percentile           # percentile | minmax
  low_percentile: 1
  high_percentile: 99

stps:
  exe: tools/src_modern/stps/build/bin/stps.exe
  df_method: 1                 # 0=TPS, 1=STPS
  block_size: 4
  lambda: 0.2
```

### 8.3 lab 版本默认参数

```yaml
runtime:
  mode: lab

template_build:
  enabled: true
  max_iterations: 7
  allow_manual_stop: true
  convergence_threshold: 0.2

landmarks:
  extractor: harris
  point_count: 50              # 后续可调至 100/150/200

dataset:
  max_samples_for_v1: 5

intensity_normalize:
  method: percentile
  low_percentile: 1
  high_percentile: 99

stps:
  exe: tools/src_modern/stps/build/bin/stps.exe
  df_method: 1
  block_size: 4
  lambda: 0.2
```

---

## 9. 全局配准设计

### 9.1 作用

将所有样本先放入统一粗参考空间，统一方向、尺寸和大尺度结构。global 不直接产出最终模板，它为 QC、模板候选选择和后续 local 提供输入。

### 9.2 输出

- global.v3draw（配准后图像）
- sub.marker / tar.marker（marker 形式的形变信息）
- 运行日志

### 9.3 幂等性

批量执行时，`global_registration_status == "completed"` 的样本自动跳过，避免重复计算。

---

## 10. 初始模板脑选择

### 10.1 策略

1. QC 综合分排序
2. 取 Top 3 候选
3. 若 Top1 与 Top2 分差 > 10%，自动选 Top1
4. 否则由用户人工确认

### 10.2 当前不使用

YOLO、CNN 黑盒打分、复杂深度学习选择器。当前阶段优先可解释、稳定、快速可验证的方案。

---

## 11. Harris 自动取点

### 11.1 作用

harris.exe 在当前模板脑上提取控制点，为 local 配准建立统一的索引基准。

### 11.2 关键规则

- 默认取 50 点，必须参数化
- 取点源为当前模板脑
- 点序必须保留，后续禁止随意重排
- **每轮迭代重新取点**（模板形状变了，控制点也需要更新）

---

## 12. 局部配准设计

### 12.1 定位

将每个样本更精细地对齐到当前模板脑。

### 12.2 输出

| 文件 | 说明 |
|------|------|
| local_registered_image.v3draw | 局部配准后的图像 W_i |
| local_registered_sub.marker | 在 subject 空间中检测到的匹配点 |
| local_registered_tar.marker | 模板控制点（≈固定模板点，有 padding 微调） |

### 12.3 关键事实

- tar 点本质上是模板点本身（padding 调整后减回来，坐标几乎不变）
- sub 点是在 subject 图像中通过相关性/Harris 检测到的对应点
- sub/tar 跨样本按索引严格对应，顺序由模板 landmark 文件行序决定
- local 支持自定义模板（T0 或后续的 template_vN）
- 当前不要求 segmentation

### 12.4 接入前必须验证

- local 是否支持自定义模板脑 T0
- local 是否支持 Harris 生成的模板点
- local 在无 segmentation 时能否稳定运行

---

## 13. 模板构建核心流程

### 13.1 流程总览

```
样本上传 → 预处理 → 全局配准 → QC 排序
→ 选择初始模板脑 T0 (= template_v0)
→ 迭代 k = 1, 2, ..., max_iterations:
    → Harris 取点 (在 template_v{k-1} 上)
    → 所有样本向 template_v{k-1} 做局部配准
    → 得到 W_i, sub_i, tar_i
    → 强度归一化 + 逐体素平均 → M_raw
    → 按索引平均 sub_i → sub_avg
    → STPS 形状校正 → template_v{k}
    → 收敛判断 / 达到最大轮数 / 人工停止
→ 最终模板版本
```

### 13.2 单轮迭代的精确步骤

```
iteration k (k >= 1):

  输入: template_v{k-1}

  步骤 1 — 取点
    harris.exe(template_v{k-1}, n_points=50)
    → template_landmarks_k.marker

  步骤 2 — 局部配准（每个样本）
    for each sample i:
      local_registration(
        subject   = global_registered_i.v3draw,
        template  = template_v{k-1},
        landmarks = template_landmarks_k.marker
      )
      → W_i.v3draw, sub_i.marker, tar_i.marker

  步骤 3 — 点集平均
    tar_ref = tar_1                  // 所有 tar_i 相同（固定模板点）
    sub_avg = (1/N) * Σ sub_i        // 按索引逐坐标平均

  步骤 4 — 图像均值
    for each W_i:
      p1  = percentile(W_i, 1)
      p99 = percentile(W_i, 99)
      W_i_norm = clip((W_i - p1) / (p99 - p1), 0, 1) * 255
    M_raw = (1/N) * Σ W_i_norm      // 逐体素平均

  步骤 5 — STPS 形状校正
    stps.exe(
      --subject-image  M_raw,        // 要变形的图像
      --subject-markers tar_ref,     // M_raw 的当前形状 = 模板点
      --target-markers  sub_avg,     // 目标形状 = 平均 subject 点
      --output template_v{k}.v3draw,
      --df-method 1,                 // STPS
      --block-size 4
    )
    → template_v{k}

  步骤 6 — 收敛判断
    if k >= 2:
      delta = ||sub_avg_k - sub_avg_{k-1}||₂ / sqrt(n_points)
      if delta < convergence_threshold:
        CONVERGED → 停止

  步骤 7 — 保存版本
    save template_v{k} + 元数据 + 日志 + preview
```

### 13.3 STPS 传参方向（关键）

STPS 做的是"将 subject 形状的图像变形到 target 形状"。在模板构建中：

- **subject_markers = tar_ref**（模板点，代表 M_raw 的当前几何形状，因为所有样本都是往模板点配准的）
- **target_markers = sub_avg**（平均 subject 点，代表目标平均形状）

这实现了"从当前模板形状 → 平均形状"的校正。

### 13.4 为什么模板主体来自图像均值

模板脑图谱的主体必须是局部配准后图像的逐体素平均。点平均只描述"平均几何形状"，通过 STPS 把原始均值模板从当前模板形状拉向平均形状。每轮迭代先"局部配准–均值计算"，再"形状归一化"。

### 13.5 强度归一化方法

采用百分位裁剪 + 线性拉伸：

```
p1  = percentile(image, low_percentile)    # 默认 1
p99 = percentile(image, high_percentile)   # 默认 99
normalized = clip((image - p1) / (p99 - p1), 0, 1) * 255
```

理由：fMOST 有背景噪声和偶尔高亮异常点，百分位比 min-max 鲁棒，比直方图匹配简单。需保存每个样本归一化前后的 p1/p99 值供 QC 和调试。

### 13.6 收敛判断

量化指标：

```
delta = ||sub_avg_k - sub_avg_{k-1}||₂ / sqrt(n_points)
```

- demo 阈值：0.5 体素
- lab 阈值：0.2 体素

这比比较图像本身（数十 GB）计算量小几个数量级，且直接反映形状是否还在变化。

---

## 14. 模板版本管理

### 14.1 版本命名

- template_v0：初始模板脑 T0
- template_v1：第一轮迭代模板
- template_v2 ~ template_v7：后续迭代

### 14.2 每个版本必须保存

```
data/projects/{project_id}/templates/v{k}/
├── template.v3draw          # 模板图像
├── template.nii.gz          # NIfTI 转换
├── template_landmarks.marker # Harris 取的控制点
├── sub_avg.marker           # 该轮平均 subject 点
├── preview/                 # 6 向预览图
├── build_log.txt            # 构建日志
├── build_config.json        # 构建参数快照
├── convergence.json         # 收敛指标
└── summary.json             # 版本摘要（样本列表、QC 统计等）
```

### 14.3 停止规则

三种终止方式：

1. **达到最大迭代次数**（demo=3, lab=7）
2. **自动收敛**（sub_avg 欧氏距离 < 阈值）
3. **人工提前终止**（用户在任意一轮后手动停止，当前模板保留为正式版本）

---

## 15. 新样本增量更新

### 15.1 策略

```yaml
template_update:
  strategy: full_rebuild    # full_rebuild | incremental
```

- **full_rebuild**（当前默认）：新样本加入后，所有样本重新 local → 均值 → STPS。小样本（3~10）计算量可接受。
- **incremental**：仅新样本做 local，均值增量更新。大样本时才启用。

### 15.2 增量均值公式

```
M_raw_{N+1} = (N * M_raw_N + Normalize(W_{N+1})) / (N+1)
sub_avg_{N+1} = (N * sub_avg_N + sub_{N+1}) / (N+1)
```

当前阶段直接 full_rebuild 即可。

---

## 16. 数据流

### 16.1 上传 → 预处理 → 全局配准

```
1. POST /api/upload
   └→ 保存原文件，创建 sample.json (status: uploaded)

2. POST /api/samples/{id}/prepare
   └→ [后台] v3draw → nii.gz + 6 向预览
   └→ 更新 sample.json (prepare_status: completed)

3. POST /api/batch/register/global
   └→ 过滤：跳过 completed/running/global.v3draw
   └→ [后台] 调用 exe → global.v3draw → nii.gz + 预览
   └→ 更新 sample.json (global_registration_status: completed)
```

### 16.2 模板构建数据流

```
4. QC 排序 → 选 T0 → 存为 template_v0

5. 迭代 k=1..max:
   a) Harris(template_v{k-1}) → landmarks
   b) 每样本 local_registration → W_i + sub_i/tar_i
   c) 强度归一化 + 体素均值 → M_raw
   d) 点均值 → sub_avg
   e) STPS(M_raw, tar_ref→sub_avg) → template_v{k}
   f) 收敛检查 → 继续/停止
```

---

## 17. 两种运行模式

### 17.1 demo 版本

在自己电脑上保证能运行、能演示、能验证流程。样本数少、点数少、预处理保守、只跑通 v1 最小实验。

### 17.2 lab 版本

在实验室电脑上跑更完整的模板构建。样本数更多、可跑更高质量配准、更多轮次。

### 17.3 统一要求

不允许两套代码逻辑。点数、样本数、路径、步骤开关全部参数化。

---

## 18. 当前阶段最小可运行目标

```
样本上传
→ 预处理
→ 全局配准
→ QC 排序
→ 选择初始模板脑 T0
→ Harris 取 50 个点
→ 3~5 个样本局部配准到 T0
→ 强度归一化 + 逐体素平均 → M_raw
→ 计算 sub_avg
→ STPS(M_raw, tar_ref, sub_avg) → template_v1
→ viewer 展示 template_v1 与相关信息
```

### 当前阶段不追求

- 全量样本一次跑完
- 7 轮全部自动跑完
- 完整解剖模板映射
- 真实 3D 脑区交互浏览

---

## 19. 当前阶段明确不做的内容

- 不直接采用现成均值模板作为最终模板
- 不把 segmentation 作为 local 强制前提
- 不做 YOLO / CNN 模板脑选择
- 不先做复杂 3D atlas 主流程
- 不做无限迭代
- 不维护两套代码
- 不为"高级"而重写现有可用 exe 本体
- 不强制引入数据库
- 不做复杂分布式调度
- 不做多用户权限系统

---

## 20. AI 辅助开发硬性约束

1. 当前主线是自建均值模板。
2. 同一套代码支持 demo 和 lab，仅配置切换。
3. Harris 取点数必须参数化，默认 50。
4. local 支持自定义模板。
5. 当前不要求 segmentation。
6. STPS 只负责图像 warp，不假设输出形变场文件。
7. sub/tar 点序跨样本一致，可按索引平均。
8. 图谱主体来自图像均值，不来自点均值。
9. 点平均只用于形状校正。
10. STPS 形状校正方向：subject_markers=tar_ref, target_markers=sub_avg。
11. 强度归一化用百分位裁剪（p1/p99）。
12. 收敛判断用 sub_avg 欧氏距离。
13. 每轮迭代 Harris 重新取点。
14. 模板迭代最多 7 次，必须支持人工停止。
15. 不允许引入与当前主线无关的深度学习评分、SQL、复杂 3D 流程作为阻塞项。
16. 已完成的配准任务再次批量提交时自动跳过。
