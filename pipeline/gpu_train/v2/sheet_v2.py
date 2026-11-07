"""Rows: the 7 fixed test views; columns: input, layout, then each sampled step."""
import glob, re, sys
from pathlib import Path
from PIL import Image, ImageDraw
R = Path(__file__).resolve().parents[3] / "data/work/style"
S = R / "lora_v2/samples"; T = R / "dataset_v2/tests"
tests = ["place", "station", "grund", "red", "glacis", "kirchberg", "hotel"]
by = {}
for f in glob.glob(str(S / "*.jpg")):
    m = re.search(r"__(\d+)_(\d)\.jpg$", f)
    if m: by.setdefault(int(m[1]), {})[int(m[2])] = f
steps = sorted(by)
if len(sys.argv) > 1: steps = [s for s in steps if s in {int(x) for x in sys.argv[1].split(",")}]
Z = 300
sheet = Image.new("RGB", (Z * (2 + len(steps)), 20 + Z * len(tests)), "white"); d = ImageDraw.Draw(sheet)
for c, n in enumerate(["input", "layout"] + [f"step {s}" for s in steps]): d.text((c * Z + 5, 4), n, fill="black")
for r, t in enumerate(tests):
    ims = [T / f"{t}_in.png", T / f"{t}_lay.png"] + [by[s].get(r) for s in steps]
    for c, p in enumerate(ims):
        if p: sheet.paste(Image.open(p).convert("RGB").resize((Z, Z)), (c * Z, 20 + r * Z))
sheet.save(R / "lora_v2/sheet.jpg", quality=86); print(steps)
