"""Generate minimal v3draw test image and marker files, then run stps.exe."""
import struct
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_DIR   = os.path.join(SCRIPT_DIR, "testdata")
EXE_PATH   = os.path.join(SCRIPT_DIR, "..", "build", "bin", "stps.exe")

os.makedirs(TEST_DIR, exist_ok=True)

# ── Generate a small v3draw (32x32x16x1, uint8, gradient) ──
W, H, D, C = 32, 32, 16, 1
total = W * H * D * C
pixels = bytes([(x + y + z) % 256 for z in range(D) for y in range(H) for x in range(W)])

v3draw_path = os.path.join(TEST_DIR, "test_subject.v3draw")
with open(v3draw_path, "wb") as f:
    f.write(b"raw_image_stack_by_hpeng")   # 24-byte magic
    f.write(b"L")                           # endianness
    f.write(struct.pack("<H", 1))           # dtype_size = 1 (uint8)
    f.write(struct.pack("<IIII", W, H, D, C))
    f.write(pixels)
print(f"Created: {v3draw_path}  ({os.path.getsize(v3draw_path)} bytes)")

# ── Generate marker files ──
# target_markers: 6 control points (STPS requires n>4 for QR decompose)
target_markers_path = os.path.join(TEST_DIR, "target.marker")
with open(target_markers_path, "w") as f:
    f.write("##x,y,z,radius,shape,name,comment\n")
    f.write("8,8,4,0,1,p1,t\n")
    f.write("24,8,4,0,1,p2,t\n")
    f.write("8,24,12,0,1,p3,t\n")
    f.write("24,24,12,0,1,p4,t\n")
    f.write("16,16,8,0,1,p5,t\n")
    f.write("16,8,12,0,1,p6,t\n")
print(f"Created: {target_markers_path}")

# subject_markers: same 6 points with small offsets (source positions)
subject_markers_path = os.path.join(TEST_DIR, "subject.marker")
with open(subject_markers_path, "w") as f:
    f.write("##x,y,z,radius,shape,name,comment\n")
    f.write("9,9,5,0,1,p1,s\n")
    f.write("25,7,3,0,1,p2,s\n")
    f.write("7,25,11,0,1,p3,s\n")
    f.write("23,23,13,0,1,p4,s\n")
    f.write("17,15,9,0,1,p5,s\n")
    f.write("15,9,11,0,1,p6,s\n")
print(f"Created: {subject_markers_path}")

output_path = os.path.join(TEST_DIR, "warped_output.v3draw")

# ── Run stps.exe (df_method=1 = STPS, block_size=4) ──
cmd = [
    EXE_PATH,
    "-s", v3draw_path,
    "-T", target_markers_path,
    "-S", subject_markers_path,
    "-o", output_path,
    "-d", "1",       # STPS
    "-b", "4",
    "-v",             # verbose
]
print(f"\nRunning: {' '.join(cmd)}\n")
result = subprocess.run(cmd, capture_output=True, text=True)
print("=== STDOUT ===")
print(result.stdout)
if result.stderr:
    print("=== STDERR ===")
    print(result.stderr)
print(f"Return code: {result.returncode}")

# Check output exists
if os.path.isfile(output_path):
    sz = os.path.getsize(output_path)
    print(f"\nOutput file created: {output_path} ({sz} bytes)")
    # Verify it's a valid v3draw
    with open(output_path, "rb") as f:
        magic = f.read(24)
        assert magic == b"raw_image_stack_by_hpeng", f"Bad magic: {magic}"
        print("Output v3draw magic OK")
else:
    print(f"\nERROR: output file not found: {output_path}")
    sys.exit(1)

# ── Also test df_method=0 (classic TPS) ──
output_tps = os.path.join(TEST_DIR, "warped_tps.v3draw")
cmd_tps = [
    EXE_PATH,
    "-s", v3draw_path,
    "-T", target_markers_path,
    "-S", subject_markers_path,
    "-o", output_tps,
    "-d", "0",       # classic TPS
    "-b", "4",
    "-v",
]
print(f"\nRunning TPS: {' '.join(cmd_tps)}\n")
result2 = subprocess.run(cmd_tps, capture_output=True, text=True)
print("=== STDOUT ===")
print(result2.stdout)
if result2.stderr:
    print("=== STDERR ===")
    print(result2.stderr)
print(f"Return code: {result2.returncode}")

if os.path.isfile(output_tps):
    print(f"TPS output OK: {output_tps} ({os.path.getsize(output_tps)} bytes)")
else:
    print("ERROR: TPS output missing")
    sys.exit(1)

print("\n=== ALL TESTS PASSED ===")
