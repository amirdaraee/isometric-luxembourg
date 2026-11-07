import glob, re, sys
from pathlib import Path
from PIL import Image, ImageDraw
R = Path(__file__).resolve().parents[3] / "data/work/night"
names = ["night t1", "night t2", "winter t1", "winter t2", "golden t1", "golden t2", "winter night t1", "winter night t2"]
by = {}
for f in glob.glob(str(R / "lora_light/samples/*.jpg")):
    m = re.search(r"__(\d+)_(\d)\.jpg$", f)
    if m: by.setdefault(int(m[1]), {})[int(m[2])] = f
steps = sorted(by)[-3:]
Z = 280
sh = Image.new("RGB", (Z * (1 + len(steps)), 20 + Z * 8), "white"); d = ImageDraw.Draw(sh)
for c, n in enumerate(["day input"] + [f"step {s}" for s in steps]): d.text((c * Z + 5, 4), n, fill="black")
for r in range(8):
    sh.paste(Image.open(R / f"tests/t{r % 2 + 1}_full.png").convert("RGB").resize((Z, Z)), (0, 20 + r * Z))
    d.text((5, 24 + r * Z), names[r], fill="white")
    for c, s in enumerate(steps):
        if r in by[s]: sh.paste(Image.open(by[s][r]).convert("RGB").resize((Z, Z)), ((c + 1) * Z, 20 + r * Z))
sh.save(R / "lora_light/sheet.jpg", quality=85); print(steps)
