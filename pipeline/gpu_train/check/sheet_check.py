"""Side-by-side: each pilot view (row) as input, then each checkpoint's output (columns)."""
import json
import sys
from pathlib import Path
from PIL import Image, ImageDraw

V = Path(sys.argv[1]); O = Path(sys.argv[2]); steps = sys.argv[3].split(",")
views = json.loads((V / "views.json").read_text())
S = 400
sheet = Image.new("RGB", (S * (1 + len(steps)), 24 + S * len(views)), "white")
d = ImageDraw.Draw(sheet)
for c, name in enumerate(["input"] + [f"step {s}" for s in steps]):
    d.text((c * S + 6, 6), name, fill="black")
for r, v in enumerate(views):
    ims = [V / v["file"]] + [O / s / v["file"] for s in steps]
    for c, p in enumerate(ims):
        if p.exists():
            sheet.paste(Image.open(p).convert("RGB").resize((S, S)), (c * S, 24 + r * S))
    d.rectangle((0, 24 + r * S, 230, 40 + r * S), fill="white")
    d.text((4, 26 + r * S), v["name"], fill="black")
sheet.save(O / "sheet.jpg", quality=88)
print(O / "sheet.jpg")
