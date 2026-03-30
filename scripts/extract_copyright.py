"""软件著作权代码提取脚本: 提取前30页+后30页(每页50行), 去除注释和空行"""
import re
import sys
from pathlib import Path

LINES_PER_PAGE = 50
PAGES = 30
TOTAL_LINES = LINES_PER_PAGE * PAGES  # 1500

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 收集源码文件, 按目录层级排序
SOURCE_DIRS = [
    PROJECT_ROOT / "pipeline",
    PROJECT_ROOT / "apps",
]
EXTENSIONS = {".py", ".html", ".js", ".css"}
SKIP_DIRS = {"__pycache__", ".git", "node_modules", "__pypackages__"}


def collect_files() -> list[Path]:
    files = []
    for src_dir in SOURCE_DIRS:
        if not src_dir.exists():
            continue
        for p in sorted(src_dir.rglob("*")):
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            if p.is_file() and p.suffix in EXTENSIONS:
                files.append(p)
    return files


def strip_python_comments(source: str) -> list[str]:
    """去除Python文件中的注释(#行)和docstring(三引号块), 返回非空行列表"""
    # 先去掉三引号docstring (贪婪匹配最短块)
    source = re.sub(r'"{3}[\s\S]*?"{3}', '', source)
    source = re.sub(r"'{3}[\s\S]*?'{3}", '', source)

    lines = []
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('#'):
            continue
        lines.append(line.rstrip())
    return lines


def strip_html_comments(source: str) -> list[str]:
    """去除HTML中的 <!-- --> 注释和空行"""
    source = re.sub(r'<!--[\s\S]*?-->', '', source)
    # 同时去掉 JS/CSS 中的 // 和 /* */ 注释
    source = re.sub(r'/\*[\s\S]*?\*/', '', source)

    lines = []
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # 去掉 // 开头的注释行 (在script标签内)
        if stripped.startswith('//'):
            continue
        lines.append(line.rstrip())
    return lines


def process_file(path: Path) -> list[str]:
    try:
        content = path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return []

    if path.suffix == '.py':
        return strip_python_comments(content)
    elif path.suffix in ('.html', '.js', '.css'):
        return strip_html_comments(content)
    return [l.rstrip() for l in content.splitlines() if l.strip()]


def main():
    files = collect_files()
    print(f"共找到 {len(files)} 个源码文件")

    all_lines: list[str] = []
    for f in files:
        rel = f.relative_to(PROJECT_ROOT)
        processed = process_file(f)
        if processed:
            all_lines.append(f"// ========== {rel} ==========")
            all_lines.extend(processed)

    total = len(all_lines)
    print(f"去除注释后总行数: {total}")

    if total <= TOTAL_LINES * 2:
        # 总行数不足60页, 直接全部输出
        result = all_lines
        print(f"总行数不足 {TOTAL_LINES * 2} 行, 输出全部代码")
    else:
        head = all_lines[:TOTAL_LINES]
        tail = all_lines[-TOTAL_LINES:]
        result = head + ["", "// .......... (中间部分省略) ...........", ""] + tail
        print(f"输出前 {TOTAL_LINES} 行 + 后 {TOTAL_LINES} 行")

    out_path = PROJECT_ROOT / "data" / "temp" / "copyright_code.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(result), encoding='utf-8')
    print(f"已写入: {out_path}")
    print(f"输出总行数: {len(result)}")
    print(f"约 {len(result) // LINES_PER_PAGE} 页 (每页{LINES_PER_PAGE}行)")


if __name__ == "__main__":
    main()
