"""Christmas markets (Winterlights) on the v2 showcase: the drawing service adds the market to the painted WINTER art
(day) and WINTER NIGHT art (night), so the patches match the map the viewer shows when the toggle is on.

Sites are centred on the landmark positions from landmarks.json. Only the pixels the drawing changed (the market) are
kept: the mask is where output and input differ, grown and feathered, so nothing else of the map is replaced.
Output: web/public/events/xmas/<site>_<day|night>.webp (RGBA) and xmas.json.
Usage: xmas_v2.py <day|night> <variant.png> <x0> <y0> <src_w> <max usd>
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
import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from common import WORK  # noqa: E402

when, painted, X0, Y0, SW, MAX = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), float(sys.argv[6])
WORKD = WORK / "events" / "xmas_v2"; WORKD.mkdir(parents=True, exist_ok=True)
OUT = ROOT / "web/public/events/xmas"; OUT.mkdir(parents=True, exist_ok=True)
MODEL, TEXT_IN, IMAGE_IN, IMAGE_OUT = "gpt-image-2.6-sunburst", 5.0, 8.0, 30.0
CROP = 760  # map px around each square
lm = {c["slug"]: c for c in json.loads((ROOT / "web/public/data/landmarks.json").read_text())}
SITES = {
    "place-darmes": ("place-d-armes", "On the tree-lined square in the middle (Place d'Armes), add a Christmas market: a ring "
                     "of about 20 small wooden chalets with white and red roofs around the central bandstand, a tall decorated "
                     "Christmas tree (about 12 m) and a small nativity crib, string lights between the trees."),
    "constitution": ("place-de-la-constitution", "On the open square around the tall golden-statue monument in the middle "
                     "(Place de la Constitution, Gëlle Fra), add a Christmas market: about 30 small wooden chalets with white "
                     "and red roofs in rows, a big white Ferris wheel (about 32 m tall) and a tall wooden Christmas pyramid, "
                     "string lights."),
    "knuedler": ("place-guillaume-ii", "On the large paved square in the middle with the equestrian statue (Place Guillaume II), "
                 "add a Christmas fair: a big decorated Christmas tree, a small carousel, a long ice slide and a few wooden "
                 "chalets with white and red roofs, string lights."),
}
COMMON = ("Keep every existing building, roof, tree, street, colour and the camera exactly as they are, same inked "
          "illustration style with fine dark outlines and flat colour fills. Only add the market described, on the open "
          "square in the centre of the image; nothing else changes. No people, no vehicles, no text, no sky.")
LIGHT = {"day": "It is a snowy winter day: the chalet roofs carry snow like the other roofs; string lights are off.",
         "night": "It is a snowy winter night, exactly as dark as the input: the chalets, the tree, the rides and the "
                  "string lights glow warm gold and cast warm light pools on the snowy ground. No sun shadows."}
key = next(l.split("=", 1)[1].strip() for l in (ROOT / "pipeline/.env").read_text().splitlines() if l.startswith("OPENAI_API_KEY="))
log_path = WORK / "style/openai_spend.json"
full = Image.open(painted).convert("RGB")
k = full.width / SW


def draw(crop, prompt, tag):
    buf = io.BytesIO(); crop.save(buf, "JPEG", quality=94)
    b = uuid.uuid4().hex
    parts = [f'--{b}\r\nContent-Disposition: form-data; name="{kk}"\r\n\r\n{v}\r\n'.encode()
             for kk, v in {"model": MODEL, "prompt": prompt, "size": "1024x1024", "quality": "high", "n": "1"}.items()]
    parts.append(f'--{b}\r\nContent-Disposition: form-data; name="image"; filename="sq.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'.encode() + buf.getvalue() + b"\r\n")
    parts.append(f"--{b}--\r\n".encode())
    req = urllib.request.Request("https://api.openai.com/v1/images/edits", data=b"".join(parts),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": f"multipart/form-data; boundary={b}"})
    t0 = time.time()
    d = json.load(urllib.request.urlopen(req, timeout=290))
    im = Image.open(io.BytesIO(base64.b64decode(d["data"][0]["b64_json"]))).convert("RGB")
    u = d.get("usage", {}); det = u.get("input_tokens_details", {})
    usd = (det.get("text_tokens", 0) * TEXT_IN + det.get("image_tokens", 0) * IMAGE_IN + u.get("output_tokens", 0) * IMAGE_OUT) / 1e6
    with open(str(log_path) + ".lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        log = json.loads(log_path.read_text())
        log.append({"file": f"christmas2:{tag}", "model": MODEL, "usd": round(usd, 4), "usage": u, "seconds": round(time.time() - t0), "at": time.strftime("%Y-%m-%d %H:%M:%S")})
        tmp = log_path.with_suffix(".tmp"); tmp.write_text(json.dumps(log, indent=1)); tmp.replace(log_path)
    print(tag, f"{time.time() - t0:.0f}s ${usd:.3f}", flush=True)
    return im


def match_colour(out, base, keep):
    """LAB mean/std of the output matched to the input over the unchanged pixels (the drawing service drifts a little)."""
    o = cv2.cvtColor(out, cv2.COLOR_RGB2LAB).astype(np.float32); b = cv2.cvtColor(base, cv2.COLOR_RGB2LAB).astype(np.float32)
    for c in range(3):
        om, os_ = o[..., c][keep].mean(), o[..., c][keep].std() + 1e-3
        bm, bs = b[..., c][keep].mean(), b[..., c][keep].std() + 1e-3
        o[..., c] = (o[..., c] - om) * (bs / os_) + bm
    return cv2.cvtColor(np.clip(o, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB)


placed = {}
for name, (slug, what) in SITES.items():
    cx, cy = lm[slug]["x"], lm[slug]["y"]
    bx, by = cx - CROP // 2, cy - CROP // 2
    placed[name] = {"site": name, "x0": bx, "y0": by, "w": CROP, "h": CROP}
    crop = full.crop(tuple(int(round(v)) for v in ((bx - X0) * k, (by - Y0) * k, (bx + CROP - X0) * k, (by + CROP - Y0) * k))).resize((1024, 1024), Image.LANCZOS)
    crop.save(WORKD / f"{name}_{when}_base.png")
    raw = WORKD / f"{name}_{when}_raw.png"
    if not raw.exists():
        log = json.loads(log_path.read_text())
        if sum(e["usd"] for e in log if e["file"].startswith("christmas2")) + 0.07 > MAX:
            sys.exit("christmas cap reached")
        draw(crop, f"{what}\n\n{LIGHT[when]}\n\n{COMMON}", f"{name}_{when}").save(raw)
    base = np.asarray(crop); out = np.asarray(Image.open(raw).convert("RGB").resize((1024, 1024), Image.LANCZOS))
    yy, xx = np.mgrid[0:1024, 0:1024]
    disc = np.hypot(xx - 512, yy - 512) < 470
    diff = np.abs(cv2.GaussianBlur(out, (0, 0), 3).astype(int) - cv2.GaussianBlur(base, (0, 0), 3).astype(int)).sum(2)
    changed = (diff > 70) & disc
    changed = cv2.morphologyEx(changed.astype(np.uint8), cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    # keep only the large changed blobs near the centre (the market), not scattered redraw noise
    n, lab, st, cen = cv2.connectedComponentsWithStats(changed)
    keep = np.zeros_like(changed)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] > 1500 and np.hypot(cen[i][0] - 512, cen[i][1] - 512) < 330:
            keep[lab == i] = 1
    keep = cv2.dilate(keep, np.ones((31, 31), np.uint8))
    out = match_colour(out, base, keep == 0)
    alpha = cv2.GaussianBlur(keep.astype(np.float32), (0, 0), 9)
    alpha = np.clip(alpha * 1.4, 0, 1) * np.clip((470 - np.hypot(xx - 512, yy - 512)) / 40, 0, 1)
    Image.fromarray(np.dstack([out, (alpha * 255).astype(np.uint8)]), "RGBA").save(OUT / f"{name}_{when}.webp", quality=88)
    prev = (out * alpha[..., None] + base * (1 - alpha[..., None])).astype(np.uint8)
    Image.fromarray(prev).save(WORKD / f"{name}_{when}_preview.jpg", quality=88)
    print(name, when, f"kept {alpha.mean() * 100:.0f}% of the patch")
(OUT / "xmas.json").write_text(json.dumps(list(placed.values()), indent=1))
print("xmas", when, "done")
