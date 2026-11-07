"""For each picked view: cleaned render (teacher input, 1024 jpg), layout map, line and kind crops; contact sheet."""
import json
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw

P = Path(__file__).resolve().parents[1]
W = P.parent / "data/work/style/detail"
v = json.loads((W / "views.json").read_text())
SRC = v["src"]
PY = str(P / ".venv/bin/python")
for d in ("render", "kind", "line", "hint", "layout", "captures"):
    (W / d).mkdir(exist_ok=True)
for x in v["views"]:
    i, (cx, cy) = x["id"], x["xy"]
    x0, y0 = cx - SRC // 2, cy - SRC // 2
    if (W / "captures" / f"{i}.jpg").exists():
        continue
    run = lambda *a: subprocess.run([PY, *map(str, a)], check=True, capture_output=True, cwd=P)
    run(P / "gpu_train/tiles/make_src.py", x0, y0, 1, 1, W / "render" / f"{i}.png")      # 600 wide; recut below
    # make_src cuts whole 600 cells; cut exactly SRC px instead:
    from importlib import import_module
    cut = {}
    for mode, folder, ext in (("RGB", "frames", "jpg"), ("L", "frames_kind", "png"), ("L", "frames_line", "png")):
        m = json.loads((P.parent / "data/work/mosaic.json").read_text()); F = m["frame"]
        im = Image.new(mode, (SRC, SRC), 255 if folder == "frames_line" else 0)
        for r in range(y0 // F, (y0 + SRC) // F + 1):
            for c in range(x0 // F, (x0 + SRC) // F + 1):
                f = P.parent / "data/work" / folder / f"{c}_{r}.{ext}"
                if f.exists():
                    im.paste(Image.open(f).convert(mode), (c * F - x0, r * F - y0))
        cut[folder] = im
    cut["frames"].save(W / "render" / f"{i}.png"); cut["frames_kind"].save(W / "kind" / f"{i}.png"); cut["frames_line"].save(W / "line" / f"{i}.png")
    run(P / "make_hint.py", W / "render" / f"{i}.png", x0, y0, "-", SRC, W / "hint" / f"{i}.png", W / "kind" / f"{i}.png")
    run(P / "layout.py", x0, y0, SRC, SRC, W / "layout" / f"{i}.png")
    Image.open(W / "hint" / f"{i}.png").convert("RGB").resize((1024, 1024), Image.LANCZOS).save(W / "captures" / f"{i}.jpg", quality=94)
    print(i, x["group"], flush=True)
# contact sheet: hint | layout per view, 6 per row
views = v["views"]; T = 260
sheet = Image.new("RGB", (6 * 2 * T, ((len(views) + 5) // 6) * (T + 18)), "white"); d = ImageDraw.Draw(sheet)
for k, x in enumerate(views):
    cx, cy = (k % 6) * 2 * T, (k // 6) * (T + 18)
    sheet.paste(Image.open(W / "captures" / f"{x['id']}.jpg").resize((T, T)), (cx, cy + 18))
    sheet.paste(Image.open(W / "layout" / f"{x['id']}.png").convert("RGB").resize((T, T)), (cx + T, cy + 18))
    d.text((cx + 4, cy + 3), f"{x['id']} {x['group']}", fill="black")
sheet.save(W / "contact_sheet.jpg", quality=85)
print("sheet", W / "contact_sheet.jpg")
