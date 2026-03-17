from pathlib import Path

from pipeline.preprocess.build_previews import build_preview_assets


def prepare_preview(input_path: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    return build_preview_assets(input_path=input_path, output_dir=output_dir)
