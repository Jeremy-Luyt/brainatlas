import os
import sys
from pathlib import Path

# 设置 PYTHONPATH 以便导入 app 和 pipeline
sys.path.append(os.path.join(os.getcwd(), "apps", "brainatlas", "backend"))
sys.path.append(os.getcwd())

from app.services.sample_service import create_sample
from app.services.prepare_service import run_prepare

def test():
    project_id = "default"
    v3draw_path = Path("data/demo_inputs/test.v3draw").resolve()
    
    if not v3draw_path.exists():
        print(f"Error: {v3draw_path} not found")
        return

    print(f"Creating sample for {v3draw_path}...")
    sample = create_sample(project_id, v3draw_path.name, v3draw_path)
    sample_id = sample["sample_id"]
    print(f"Sample created: {sample_id}")

    print(f"Running prepare for {sample_id}...")
    updated = run_prepare(sample_id)
    print("Prepare completed!")
    print("Updated Sample JSON:")
    import json
    print(json.dumps(updated, indent=2))

if __name__ == "__main__":
    test()
