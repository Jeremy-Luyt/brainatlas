from pipeline.io.reader_v3draw import read_v3draw

path = r"data\demo_inputs\test.v3draw"

volume, meta = read_v3draw(path)

print("===== READ OK =====")
print("shape_out =", meta["shape_out"])
print("dtype =", meta["dtype"])
print("min =", meta["min"])
print("max =", meta["max"])
print("mean =", meta["mean"])
print("meta =", meta)