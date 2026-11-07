"""Training set for the light/season model: day drawing -> night / golden / winter / winter_night / autumn / spring.

Same red-box infill recipe as the style model (so a whole map can be converted window by window without seams):
the input is the *target* picture with a region replaced by the *day* picture inside a red outline; the model
learns to convert the outlined day region to match the surrounding target. 20% of examples are full views.
One caption per target. Output: data/work/night/dataset/toolkit/{data,control}.
"""
import random
import shutil
import subprocess
import sys
from pathlib import Path
from PIL import Image

P = Path(__file__).resolve().parents[1]
W = P.parent / "data/work"
D = W / "night/dataset"
PY = str(P / ".venv/bin/python")
CAPTION = {
    "night": "Convert the outlined section to the <isometric luxembourg ink> style at night, warm and cozy, with no sun shadows, matching the surrounding image.",
    "golden": "Convert the outlined section to the <isometric luxembourg ink> style at golden hour, matching the surrounding image.",
    "winter": "Convert the outlined section to the <isometric luxembourg ink> style on a snowy winter day, matching the surrounding image.",
    "winter_night": "Convert the outlined section to the <isometric luxembourg ink> style on a snowy winter night, with no sun shadows, matching the surrounding image.",
    "autumn": "Convert the outlined section to the <isometric luxembourg ink> style in autumn, matching the surrounding image.",
    "spring": "Convert the outlined section to the <isometric luxembourg ink> style in spring, matching the surrounding image.",
}
OLD, NEW = W / "style/examples_openai", W / "style/detail/drawn"
pairs = []  # (day, target image, target name)
for f in sorted((W / "night/pairs").glob("*_night.png")):
    pairs.append((OLD / (f.name.replace("_night.png", ".png")), f, "night"))
for f in sorted((W / "night/transforms").glob("*.png")):
    stem = f.stem
    for tgt in sorted(CAPTION, key=len, reverse=True):
        if stem.endswith("_" + tgt):
            base = stem[: -len(tgt) - 1]
            day = (NEW if base.startswith("d") else OLD) / f"{base}.png"
            pairs.append((day, f, tgt))
            break
pairs = [p for p in pairs if p[0].exists()]
print("pairs", len(pairs), {t: sum(1 for p in pairs if p[2] == t) for t in CAPTION})
if D.exists():
    shutil.rmtree(D)
(D / "inputs").mkdir(parents=True); (D / "generations").mkdir()
names = {}
for k, (day, tgt, t) in enumerate(pairs):
    n = f"{t}_{k:03d}"
    Image.open(day).convert("RGB").resize((1024, 1024)).save(D / "inputs" / f"{n}.png")
    Image.open(tgt).convert("RGB").resize((1024, 1024)).save(D / "generations" / f"{n}.png")
    names[n] = t
subprocess.run([PY, str(P / "style/nyc/create_omni_dataset.py"), "--dataset-dir", str(D), "--variants", "3", "--seed", "7"], check=True, cwd=P)
T = D / "toolkit"
(T / "data").mkdir(parents=True); (T / "control").mkdir()
rows = [l.split(",")[:2] for l in (D / "omni.csv").read_text().splitlines()[1:]]
for omni, gen in rows:
    name = Path(omni).name
    shutil.copy(D / gen, T / "data" / name)
    shutil.copy(D / omni, T / "control" / name)
    (T / "data" / (Path(name).stem + ".txt")).write_text(CAPTION[names[Path(gen).stem]])
print("examples", len(rows))
