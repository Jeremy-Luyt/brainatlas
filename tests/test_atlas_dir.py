from pathlib import Path

from pipeline.wrappers.global_registration import run_global_registration

moving = Path("data/demo_inputs/test.v3draw")
fixed = Path("tools/templates/25um_568")  # Use the directory containing atlas_v3draw
output_dir = Path("data/temp/global_registration_test_atlas_dir")

print("moving exists:", moving.exists())
print("fixed exists:", fixed.exists())
print("atlas_v3draw in fixed:", (fixed / "atlas_v3draw").exists())

try:
    result = run_global_registration(moving=moving, fixed=fixed, output_dir=output_dir)
    print("Global registration result:", result)
    print("output dir exists:", output_dir.exists())
    print("result json exists:", Path(result["result_path"]).exists())
except Exception as e:
    print("Global registration failed:", type(e).__name__, e)
    raise