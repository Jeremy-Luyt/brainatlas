from pathlib import Path


def _svg_preview(title: str, subtitle: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0ea5e9"/>
      <stop offset="100%" stop-color="#22c55e"/>
    </linearGradient>
  </defs>
  <rect width="640" height="360" fill="#020617"/>
  <rect x="16" y="16" width="608" height="328" rx="18" fill="#0f172a" stroke="#1e3a8a"/>
  <text x="34" y="64" fill="#e2e8f0" font-size="28" font-family="Segoe UI, Arial">{title}</text>
  <text x="34" y="98" fill="#94a3b8" font-size="18" font-family="Segoe UI, Arial">{subtitle}</text>
  <circle cx="520" cy="178" r="82" fill="url(#g)" opacity="0.75"/>
  <circle cx="520" cy="178" r="56" fill="#0f172a" opacity="0.85"/>
</svg>"""


def build_preview_assets(input_path: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    views = ["xy", "xz", "yz", "mip_xy", "mip_xz", "mip_yz"]
    preview_paths: dict[str, str] = {}
    for view in views:
        p = output_dir / f"{view}.svg"
        p.write_text(_svg_preview(f"BrainAtlas Preview · {view}", input_path.name), encoding="utf-8")
        preview_paths[view] = str(p)
    return {"preview_paths": preview_paths, "source_path": str(input_path), "size_bytes": input_path.stat().st_size}
