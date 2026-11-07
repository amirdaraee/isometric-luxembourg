"""Christmas market (Winterlights) patches: the drawing service adds the market to painted views of the market squares,
in day and night versions. The viewer blends these patches in when the Christmas toggle is on.

Each site: a painted crop (from the current showcase painting) centred on the square + the site-specific brief from
research/05-events/events.json. Output: data/work/events/christmas/<site>_<day|night>.png and sites.json (placement).
Usage: christmas_teacher.py <showcase.png> <x0> <y0> <src_w> <max usd>
"""
import base64
import io
import json
import math
import sys
import time
import urllib.request
import uuid
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from common import WORK, ORIGIN_E, ORIGIN_N, R, ELEV, lonlat_to_en  # noqa: E402
import numpy as np  # noqa: E402

painted, X0, Y0, SW, MAX = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), float(sys.argv[5])
OUT = WORK / "events" / "christmas"
OUT.mkdir(parents=True, exist_ok=True)
MODEL, TEXT_IN, IMAGE_IN, IMAGE_OUT = "gpt-image-2.6-sunburst", 5.0, 8.0, 30.0
m = json.loads((WORK / "mosaic.json").read_text())
t = np.load(WORK / "terrain.npz")
tz, te0, tn0, ts = t["z"], float(t["e0"]), float(t["n0"]), float(t["step"])


def to_px(lat, lon):
    e, n = lonlat_to_en(lon, lat)
    iy = min(max(int((n - tn0) / ts), 0), tz.shape[0] - 1); ix = min(max(int((e - te0) / ts), 0), tz.shape[1] - 1)
    z = float(tz[iy, ix]); le, ln = e - ORIGIN_E, n - ORIGIN_N
    sx = (le + ln) * R; sy = (-le + ln) * R * math.sin(ELEV) + z * math.cos(ELEV)
    return round((sx - m["sx0"]) / m["mpp"]), round((m["sy1"] - sy) / m["mpp"])


SITES = {
    "place-darmes": (49.6111, 6.1301, "On the tree-lined square in the middle (Place d'Armes), add a Christmas market: a ring "
                     "of about 20 small wooden chalets with white and red roofs around the central bandstand, a tall decorated "
                     "Christmas tree (about 12 m) and a small nativity crib, warm string lights strung between the plane trees."),
    "constitution": (49.6095, 6.1292, "On the open square with the tall golden-statue monument (Place de la Constitution, "
                     "Gëlle Fra), add a Christmas market: about 40 small wooden chalets with white and red roofs in rows, a big "
                     "Ferris wheel (about 32 m tall, white with lights) and a tall wooden Christmas pyramid, warm string lights."),
    "knuedler": (49.6106, 6.1322, "On the large paved square with the equestrian statue (Place Guillaume II), add a Christmas "
                 "fair: a big illuminated Christmas tree, a carousel, a long giant ice slide and a few wooden chalets with "
                 "warm string lights."),
}
COMMON = """Keep every existing building, roof, tree, street and the camera exactly where they are, in the same inked
illustration style with fine dark outlines and flat colour fills. Only add the market elements described, on the open
square; nothing elsewhere changes. No people, no vehicles, no text, no sky."""
LIGHT = {"day": "It is a crisp winter day with light snow on the roofs and trees and on the chalet roofs; string lights are off.",
         "night": "It is a snowy winter night, warm and cozy: deep blue tones, snow on roofs and trees, the chalets, tree, "
                  "wheel and string lights glowing warm gold, warm light pools on the snowy ground, lit windows around the "
                  "square. No sun shadows."}
key = next(l.split("=", 1)[1].strip() for l in (ROOT / "pipeline/.env").read_text().splitlines() if l.startswith("OPENAI_API_KEY="))
log_path = WORK / "style/openai_spend.json"
full = Image.open(painted).convert("RGB")
k = full.width / SW
CROP = 900  # mosaic px around the square
sites = {}
for name, (lat, lon, what) in SITES.items():
    x, y = to_px(lat, lon)
    bx, by = x - CROP // 2, y - CROP // 2
    sites[name] = {"x0": bx, "y0": by, "w": CROP, "h": CROP}
    crop = full.crop(tuple(int(round(v)) for v in ((bx - X0) * k, (by - Y0) * k, (bx + CROP - X0) * k, (by + CROP - Y0) * k))).resize((1024, 1024), Image.LANCZOS)
    crop.save(OUT / f"{name}_base.png")
    for when in ("day", "night"):
        dest = OUT / f"{name}_{when}.png"
        if dest.exists():
            continue
        log = json.loads(log_path.read_text())
        if sum(e["usd"] for e in log if e["file"].startswith("christmas")) + 0.07 > MAX:
            sys.exit("christmas cap reached")
        buf = io.BytesIO(); crop.save(buf, "JPEG", quality=94)
        b = uuid.uuid4().hex
        prompt = f"{what}\n\n{LIGHT[when]}\n\n{COMMON}"
        parts = [f'--{b}\r\nContent-Disposition: form-data; name="{kk}"\r\n\r\n{v}\r\n'.encode()
                 for kk, v in {"model": MODEL, "prompt": prompt, "size": "1024x1024", "quality": "high", "n": "1"}.items()]
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="image"; filename="sq.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'.encode() + buf.getvalue() + b"\r\n")
        parts.append(f"--{b}--\r\n".encode())
        req = urllib.request.Request("https://api.openai.com/v1/images/edits", data=b"".join(parts),
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": f"multipart/form-data; boundary={b}"})
        t0 = time.time()
        d = json.load(urllib.request.urlopen(req, timeout=290))
        Image.open(io.BytesIO(base64.b64decode(d["data"][0]["b64_json"]))).convert("RGB").save(dest)
        u = d.get("usage", {}); det = u.get("input_tokens_details", {})
        usd = (det.get("text_tokens", 0) * TEXT_IN + det.get("image_tokens", 0) * IMAGE_IN + u.get("output_tokens", 0) * IMAGE_OUT) / 1e6
        import fcntl
        with open(str(log_path) + ".lock", "w") as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            log = json.loads(log_path.read_text())
            log.append({"file": f"christmas:{name}_{when}", "model": MODEL, "usd": round(usd, 4), "usage": u, "seconds": round(time.time() - t0), "at": time.strftime("%Y-%m-%d %H:%M:%S")})
            tmp = log_path.with_suffix(".tmp"); tmp.write_text(json.dumps(log, indent=1)); tmp.replace(log_path)
        print(dest.name, f"{time.time() - t0:.0f}s ${usd:.3f}", flush=True)
(OUT / "sites.json").write_text(json.dumps(sites, indent=1))
print("christmas done")
