"""Training set for style v2: old 40 + new detail drawings, red-box infill examples (NYC omni recipe), and a
second control image per example: the layout map of that view (blank in 25% of examples).

Writes data/work/style/dataset_v2/toolkit/{data,control,layout}: same file names in each folder, as ai-toolkit
expects for multiple control images; data/ holds targets + captions. Also builds the fixed test inputs.
"""
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path
from PIL import Image

P = Path(__file__).resolve().parents[1]
W = P.parent / "data/work"
D = W / "style/dataset_v2"
PY = str(P / ".venv/bin/python")
PROMPT = (P / "style/prompt.txt").read_text().strip()
rng = random.Random(1867)
if D.exists():
    shutil.rmtree(D)
for d in ("inputs", "generations", "layouts"):
    (D / d).mkdir(parents=True)

# old 40: capture centre at SRC 1200
caps = json.loads((W / "style/captures.json").read_text())
for c in caps:
    i = Path(c["file"]).stem
    Image.open(W / "style/dataset/inputs" / f"{i}.png").convert("RGB").resize((1024, 1024)).save(D / "inputs" / f"o{i}.png")
    Image.open(W / "style/examples_openai" / f"{i}.png").convert("RGB").resize((1024, 1024)).save(D / "generations" / f"o{i}.png")
    lay = D / "layouts" / f"o{i}.png"
    subprocess.run([PY, str(P / "layout.py"), str(c["x"] - 600), str(c["y"] - 600), "1200", "1200", str(lay)], check=True, capture_output=True, cwd=P)
    Image.open(lay).convert("RGB").resize((1024, 1024), Image.NEAREST).save(lay)
# new detail views (drawn ones only)
v = json.loads((W / "style/detail/views.json").read_text())
for x in v["views"]:
    i = x["id"]
    if not (W / "style/detail/drawn" / f"{i}.png").exists():
        continue
    Image.open(W / "style/detail/captures" / f"{i}.jpg").convert("RGB").save(D / "inputs" / f"{i}.png")
    Image.open(W / "style/detail/drawn" / f"{i}.png").convert("RGB").resize((1024, 1024)).save(D / "generations" / f"{i}.png")
    Image.open(W / "style/detail/layout" / f"{i}.png").convert("RGB").resize((1024, 1024), Image.NEAREST).save(D / "layouts" / f"{i}.png")
n = len(list((D / "generations").glob("*.png")))
print("views", n)

# red-box infill examples (5 per view), with the NYC script
subprocess.run([PY, str(P / "style/nyc/create_omni_dataset.py"), "--dataset-dir", str(D), "--variants", "5", "--seed", "1867"],
               check=True, cwd=P)
T = D / "toolkit"
for d in ("data", "control", "layout"):
    (T / d).mkdir(parents=True)
blank = Image.new("RGB", (1024, 1024), (255, 255, 255))
rows = [l.split(",")[:2] for l in (D / "omni.csv").read_text().splitlines()[1:]]
for omni, gen in rows:
    name = Path(omni).name
    view = Path(gen).stem
    shutil.copy(D / gen, T / "data" / name)
    (T / "data" / (Path(name).stem + ".txt")).write_text(PROMPT)
    shutil.copy(D / omni, T / "control" / name)
    (blank if rng.random() < 0.25 else Image.open(D / "layouts" / f"{view}.png")).save(T / "layout" / name)
print("examples", len(rows))

# fixed test inputs (never trained on): cleaned render + layout at 900 src px
tests = v["tests"]
TD = D / "tests"
TD.mkdir()
for name, (cx, cy) in tests.items():
    slug = name.split()[0].lower().replace("'", "").replace("ô", "o")
    x0, y0 = int(cx) - 450, int(cy) - 450
    src, kind = TD / f"{slug}_src.png", TD / f"{slug}_kind.png"
    subprocess.run([PY, str(P / "gpu_train/tiles/make_src.py"), str(x0), str(y0), "2", "2", str(src)], check=True, capture_output=True, cwd=P)
    subprocess.run([PY, str(P / "gpu_train/tiles/make_src.py"), str(x0), str(y0), "2", "2", str(kind), "kind"], check=True, capture_output=True, cwd=P)
    for f in (src, kind):
        Image.open(f).crop((0, 0, 900, 900)).save(f)
    hint = TD / f"{slug}_hint.png"
    subprocess.run([PY, str(P / "make_hint.py"), str(src), str(x0), str(y0), "-", "900", str(hint), str(kind)], check=True, capture_output=True, cwd=P)
    lay = TD / f"{slug}_layout.png"
    subprocess.run([PY, str(P / "layout.py"), str(x0), str(y0), "900", "900", str(lay)], check=True, capture_output=True, cwd=P)
    # full-view generation input: the whole view inside a red outline (like the NYC "full" type)
    im = Image.open(hint).convert("RGB").resize((1024, 1024), Image.LANCZOS)
    from PIL import ImageDraw
    d = ImageDraw.Draw(im)
    for k in range(2):
        d.rectangle((k, k, 1023 - k, 1023 - k), outline=(255, 0, 0))
    im.save(TD / f"{slug}_in.png")
    Image.open(lay).convert("RGB").resize((1024, 1024), Image.NEAREST).save(TD / f"{slug}_lay.png")
print("tests", list(tests))
