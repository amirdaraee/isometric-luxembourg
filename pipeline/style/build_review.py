"""Review page for the training set, plus side-by-side sheets for checking."""
import json
from pathlib import Path
from PIL import Image, ImageDraw

S = Path("../data/work/style")
index = json.loads((S / "captures.json").read_text())
WEB = Path("../web/public/style-test/review")
WEB.mkdir(parents=True, exist_ok=True)
cards = ""
done = []
for it in index:
    png = S / "examples_openai" / it["file"].replace(".jpg", ".png")
    if not png.exists():
        print("missing", it["file"])
        continue
    done.append(it)
    n = it["file"][:2]
    Image.open(S / "captures" / it["file"]).convert("RGB").resize((768, 768)).save(WEB / f"{n}_in.jpg", quality=85)
    Image.open(png).convert("RGB").save(WEB / f"{n}_out.jpg", quality=92)
    label = it["name"] if not it["name"].startswith("area") else "Ordinary area"
    cards += f'<section><h2>{n} {label}</h2><div class=r><a href="{n}_in.jpg" target=_blank><img loading=lazy src="{n}_in.jpg" alt="3D capture {n}"></a><a href="{n}_out.jpg" target=_blank><img loading=lazy src="{n}_out.jpg" alt="Inked drawing {n}"></a></div></section>'
(WEB / "index.html").write_text('<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Training set review</title><style>body{margin:0;padding:20px;background:#101828;color:#f4f1ea;font:15px system-ui}h1{font-size:22px;margin:0 0 6px}p{color:#aeb4c2;margin:0}h2{font-size:15px;margin:22px 0 6px}.r{display:grid;grid-template-columns:1fr 1fr;gap:8px}img{width:100%;display:block;border-radius:6px}</style><h1>Training set review: 40 inked examples</h1><p>Left is our 3D capture, right is the drawing. Click to open full size.</p>' + cards)
T = 400
for part, group in enumerate((done[:20], done[20:])):
    sheet = Image.new("RGB", (5 * T, ((len(group) + 4) // 5) * T), (16, 24, 40))
    for i, it in enumerate(group):
        im = Image.open(S / "examples_openai" / it["file"].replace(".jpg", ".png")).convert("RGB").resize((T, T))
        d = ImageDraw.Draw(im)
        d.rectangle((0, 0, 36, 18), fill=(0, 0, 0))
        d.text((4, 3), it["file"][:2], fill=(255, 255, 255))
        sheet.paste(im, (i % 5 * T, i // 5 * T))
    sheet.save(S / f"review_sheet_{part}.jpg", quality=86)
print("pairs", len(done))
