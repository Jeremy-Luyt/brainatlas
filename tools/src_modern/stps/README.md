# STPS — Modern Subsampled Thin-Plate Spline Warp Tool

基于 C++17 / Eigen / CLI11 重构的 STPS 图像和控制点配准变形工具。

## 功能

- **TPS** (df_method=0): 经典 Thin-Plate Spline，三线性位移场插值
- **STPS** (df_method=1): Subsampled TPS + B-spline 位移场插值 + QR 分解正则化
- 分块处理大图像，内存高效
- v3draw 格式输入/输出，.marker 控制点格式
- JSON 结果摘要输出（stdout + .summary.json 文件）
- 可被 Python/FastAPI 通过 subprocess 调用

## 依赖

| 依赖 | 版本 | 说明 |
|------|------|------|
| Eigen3 | ≥3.4 | 矩阵运算（替代 Newmat + CUDA） |
| CLI11 | ≥2.4 | 命令行解析 |
| nlohmann/json | ≥3.11 | JSON 输出 |
| CMake | ≥3.16 | 构建系统 |
| Ninja | - | 推荐构建工具 |

### msys2/ucrt64 安装依赖

```bash
pacman -S mingw-w64-ucrt-x86_64-eigen3 mingw-w64-ucrt-x86_64-cli11 mingw-w64-ucrt-x86_64-nlohmann-json
```

## 构建

```bash
cd tools/src_modern/stps
mkdir build && cd build
cmake .. -G Ninja -DCMAKE_BUILD_TYPE=Release
ninja
```

产出: `build/bin/stps.exe`

## 命令行用法

```
stps.exe [OPTIONS]

OPTIONS:
  -s, --subject-image   <FILE>  被配准图像 (v3draw)
  -T, --target-markers  <FILE>  目标控制点 (.marker)
  -S, --subject-markers <FILE>  被配准控制点 (.marker)
  -o, --output          <FILE>  输出变形图像 (v3draw)
  -d, --df-method       <INT>   位移场方法: 0=TPS, 1=STPS (默认: 1)
  -b, --block-size      <INT>   分块大小 2~64 (默认: 4)
  -i, --img-interp      <INT>   图像插值: 0=双线性, 1=最近邻 (默认: 0)
      --lambda          <FLOAT> STPS 正则化参数 (默认: 0.2)
  -R, --output-size     <W,H,D> 指定输出尺寸 (可选)
  -l, --log             <FILE>  日志文件路径 (可选)
  -v, --verbose                 详细输出
      --version                 版本号
  -h, --help                    帮助
```

### 示例

```bash
stps.exe -s brain.v3draw -T target.marker -S subject.marker -o warped.v3draw -d 1 -b 4
```

## JSON 输出

执行完成后在 stdout 输出 JSON 摘要，同时写入 `<output>.summary.json`：

```json
{
  "success": true,
  "elapsed_seconds": 12.345,
  "num_control_points": 30,
  "mean_marker_distance": 5.67,
  "std_marker_distance": 2.34,
  "input_dims": {"w": 568, "h": 320, "d": 456, "c": 1},
  "output_dims": {"w": 568, "h": 320, "d": 456, "c": 1},
  "output_file": "/path/to/warped.v3draw",
  "error_message": ""
}
```

## Python 调用示例

```python
import subprocess, json

result = subprocess.run(
    ["tools/src_modern/stps/build/bin/stps.exe",
     "-s", "brain.v3draw",
     "-T", "target.marker",
     "-S", "subject.marker",
     "-o", "warped.v3draw",
     "-d", "1", "-b", "4"],
    capture_output=True, text=True, timeout=600
)

if result.returncode == 0:
    summary = json.loads(result.stdout)
    print(f"Success: {summary['elapsed_seconds']:.2f}s")
else:
    print(f"Failed: {result.stderr}")
```

## 项目结构

```
stps/
├── CMakeLists.txt
├── README.md
├── include/stps/
│   ├── types.hpp         # 核心数据类型 (Point3D, Volume3D, StpsConfig, ...)
│   ├── logger.hpp        # 轻量日志
│   ├── io.hpp            # v3draw I/O + marker 解析
│   ├── tps_solver.hpp    # TPS/STPS 位移场计算
│   ├── warp_engine.hpp   # 分块图像变形
│   └── api.hpp           # 高级 API
├── src/
│   ├── io.cpp
│   ├── tps_solver.cpp
│   ├── warp_engine.cpp
│   ├── api.cpp
│   └── main.cpp          # CLI 入口
├── tests/
│   └── gen_testdata_and_run.py
└── build/bin/stps.exe
```

## 与原始代码对比

| 特性 | 旧版 | 新版 |
|------|------|------|
| 语言标准 | C++03/CUDA | C++17 |
| 矩阵库 | Newmat + cuBLAS/cuSOLVER | Eigen3 (CPU) |
| GUI 依赖 | Qt5 (QList, QString, QFile) | 无 |
| V3D 框架 | 深度耦合 (Vol3DSimple, Image2DSimple) | 独立 (Volume3D 模板类) |
| CLI | getopt | CLI11 |
| 构建 | Visual Studio .sln | CMake + Ninja |
| 输出 | 文件仅 | 文件 + JSON 摘要 |
| 备份 | — | `tools/src_legacy/stps_original_backup_20260325/` |
