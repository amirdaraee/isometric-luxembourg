"""Isometric cutaway illustrations ("Inside" tab) for key landmarks, in the map's ink style.

Input image: the landmark as it looks on our map (painted showcase where available, else the 3D render), so the
outside matches. Brief: the interior from research/02-buildings-interiors (layout, main spaces, materials).
Output: web/public/landmarks/<slug>/cutaway.webp; adds "cutaway" to landmarks.json.
"""
import base64
import fcntl
import io
import json
import sys
import time
import urllib.request
import uuid
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from common import WORK  # noqa: E402

MAX = float(sys.argv[1]) if len(sys.argv) > 1 else 0.8
PICK = ["notre-dame-cathedral", "grand-ducal-palace", "bock-casemates", "philharmonie-luxembourg", "cercle-cite",
        "villa-vauban", "mudam", "luxembourg-railway-station", "neumunster-abbey", "fort-thungen-three-acorns-museum"]
MODEL, TEXT_IN, IMAGE_IN, IMAGE_OUT = "gpt-image-2.6-sunburst", 5.0, 8.0, 30.0
key = next(l.split("=", 1)[1].strip() for l in (ROOT / "pipeline/.env").read_text().splitlines() if l.startswith("OPENAI_API_KEY="))
log_path = WORK / "style/openai_spend.json"
lm_path = ROOT / "web/public/data/landmarks.json"
cards = json.loads(lm_path.read_text())
painted = json.loads((WORK / "tiles/painted.json").read_text())
m = json.loads((WORK / "mosaic.json").read_text()); F = m["frame"]


def view(x, y, size=700):
    for p in painted:
        if p["x0"] + size / 2 <= x <= p["x0"] + p["w"] - size / 2 and p["y0"] + size / 2 <= y <= p["y0"] + p["h"] - size / 2:
            im = Image.open(WORK / "tiles" / p["file"]).convert("RGB")
            k = im.width / p["w"]
            return im.crop(tuple(int(v) for v in ((x - size / 2 - p["x0"]) * k, (y - size / 2 - p["y0"]) * k,
                                                  (x + size / 2 - p["x0"]) * k, (y + size / 2 - p["y0"]) * k)))
    x0, y0 = int(x - size / 2), int(y - size / 2)
    out = Image.new("RGB", (size, size))
    for r in range(y0 // F, (y0 + size) // F + 1):
        for c in range(x0 // F, (x0 + size) // F + 1):
            f = WORK / "frames" / f"{c}_{r}.jpg"
            if f.exists():
                out.paste(Image.open(f), (c * F - x0, r * F - y0))
    return out


for c in cards:
    if c["slug"] not in PICK or not c.get("interior"):
        continue
    dest = ROOT / "web/public/landmarks" / c["slug"] / "cutaway.webp"
    if dest.exists():
        c["cutaway"] = f"/landmarks/{c['slug']}/cutaway.webp"
        continue
    log = json.loads(log_path.read_text())
    if sum(e["usd"] for e in log if e["file"].startswith("cutaway")) + 0.07 > MAX:
        print("cutaway cap reached"); break
    it = c["interior"]
    brief = (f"Redraw this building, {c['name']} in Luxembourg City, as a detailed isometric cutaway illustration in the same "
             "inked style: fine dark outlines, flat colour fills, warm limestone and slate-blue roof. Keep the outside shape, "
             "roof and towers recognisable, but cut away the near walls and part of the roof like an architectural model, to "
             "reveal the inside: " + " ".join(filter(None, [it.get("layout"), it.get("main_spaces"), it.get("materials_colours")]))
             + " Show the rooms furnished and lit, a few tiny people for scale inside only. Plain light paper background "
             "around the building, no surrounding streets, no text or labels.")[:3900]
    buf = io.BytesIO(); view(c["x"], c["y"]).resize((1024, 1024), Image.LANCZOS).save(buf, "JPEG", quality=92)
    b = uuid.uuid4().hex
    parts = [f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
             for k, v in {"model": MODEL, "prompt": brief, "size": "1024x1024", "quality": "high", "n": "1"}.items()]
    parts.append(f'--{b}\r\nContent-Disposition: form-data; name="image"; filename="lm.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'.encode() + buf.getvalue() + b"\r\n")
    parts.append(f"--{b}--\r\n".encode())
    req = urllib.request.Request("https://api.openai.com/v1/images/edits", data=b"".join(parts),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": f"multipart/form-data; boundary={b}"})
    t0 = time.time()
    try:
        d = json.load(urllib.request.urlopen(req, timeout=290))
    except Exception as e:
        print("failed", c["slug"], e); continue
    im = Image.open(io.BytesIO(base64.b64decode(d["data"][0]["b64_json"]))).convert("RGB")
    im.save(dest, quality=86)
    u = d.get("usage", {}); det = u.get("input_tokens_details", {})
    usd = (det.get("text_tokens", 0) * TEXT_IN + det.get("image_tokens", 0) * IMAGE_IN + u.get("output_tokens", 0) * IMAGE_OUT) / 1e6
    with open(str(log_path) + ".lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        log = json.loads(log_path.read_text())
        log.append({"file": f"cutaway:{c['slug']}", "model": MODEL, "usd": round(usd, 4), "usage": u, "seconds": round(time.time() - t0), "at": time.strftime("%Y-%m-%d %H:%M:%S")})
        tmp = log_path.with_suffix(".tmp"); tmp.write_text(json.dumps(log, indent=1)); tmp.replace(log_path)
    c["cutaway"] = f"/landmarks/{c['slug']}/cutaway.webp"
    print(c["slug"], f"{time.time() - t0:.0f}s ${usd:.3f}", flush=True)
lm_path.write_text(json.dumps(cards, ensure_ascii=False, indent=0))
print("cutaways:", [c["slug"] for c in cards if c.get("cutaway")])
