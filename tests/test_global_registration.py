from pathlib import Path

from pipeline.wrappers.global_registration import run_global_registration

moving = Path("data/demo_inputs/test.v3draw")
fixed = Path("tools/templates/25um_568/atlas_v3draw/CCF_u8_xpad.v3draw")  # CCF template file
output_dir = Path("data/temp/global_registration_test")

print("moving exists:", moving.exists())
print("fixed exists:", fixed.exists())

try:
    result = run_global_registration(moving=moving, fixed=fixed, output_dir=output_dir)
    print("Global registration result:", result)
    print("output dir exists:", output_dir.exists())
    print("result json exists:", Path(result["result_path"]).exists())
except Exception as e:
    print("Global registration failed:", type(e).__name__, e)
    raise
