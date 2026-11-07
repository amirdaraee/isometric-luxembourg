"""Have Gemini draw the 'after' half of each training pair. Spending is capped and every image is logged.

  python style/draw_examples.py --limit 1          # one sample, to judge the look before paying for more
  python style/draw_examples.py --limit 40 --max-usd 11
"""
import argparse
import base64
import io
import json
import sys
import time
import urllib.error
import urllib.request
from PIL import Image

sys.path.insert(0, ".")
from common import ROOT, WORK

MODEL = "gemini-3-pro-image"
USD_PER_IMAGE = 0.134  # Google's listed price for this model at 1K, checked 5 Nov 2026
PROMPT = """Redraw this exact view as a beautiful, richly colourful, extremely detailed isometric illustration, like the most charming hand-painted city-building game.
Keep the geometry exact: every building, roof, street, bridge, tree mass, river and the camera angle stay precisely where they are. Add nothing, remove nothing, move nothing.
Style:
- Crisp, sharp detail with no blur or smears and no black cartoon outlines.
- Every wall shows a regular, clearly countable grid of individual windows, with floor lines, cornices and door details.
- Roofs carry real texture: slate courses, dormers, chimneys and roof equipment.
- Vivid but natural colour throughout: a saturated, joyful palette with real variety from building to building.
- Rich, varied greens: individual trees with sunlit tops and shadowed bases, in many tones, some darker and some golden. Lawns are lush but not neon.
- Warm honey limestone, cream and ochre facades, blue-grey slate with visible highlights, terracotta accents, and glass that reflects blue sky on modern blocks.
- Small life in the streets: parked and moving cars, trams, street trees, painted crossings, cafe terraces.
- One consistent warm sun from the upper left, with clear, clean cast shadows that give every building depth.
- Replace any stretched or smeared texture, especially on cliffs and walls, with believable rock, masonry or trees.
No text, no labels, no borders."""

ap = argparse.ArgumentParser()
ap.add_argument("--limit", type=int, required=True)
ap.add_argument("--max-usd", type=float, default=11.0)
args = ap.parse_args()

key = next(l.split("=", 1)[1].strip() for l in (ROOT / "pipeline/.env").read_text().splitlines() if l.startswith("GEMINI_API_KEY="))
base = WORK / "style"
out = base / "examples"
out.mkdir(exist_ok=True)
log_path = base / "spend_log.json"
log = json.loads(log_path.read_text()) if log_path.exists() else []
index = json.loads((base / "captures.json").read_text())


def spent():
    return sum(e["usd"] for e in log)


done = 0
for item in index:
    if done >= args.limit:
        break
    dest = out / item["file"].replace(".jpg", ".png")
    if dest.exists():
        continue
    if spent() + USD_PER_IMAGE > args.max_usd:
        print(f"stopping at the spending cap: ${spent():.2f} of ${args.max_usd:.2f}")
        break
    data = (base / "captures" / item["file"]).read_bytes()
    body = {"contents": [{"parts": [{"text": PROMPT}, {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(data).decode()}}]}],
            "generationConfig": {"responseModalities": ["IMAGE"]}}
    req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        d = json.load(urllib.request.urlopen(req, timeout=170))
    except urllib.error.HTTPError as e:
        err = json.loads(e.read()).get("error", {})
        sys.exit(f"stopped on {item['file']}: HTTP {e.code} {err.get('status')} {err.get('message', '')[:200]}")
    img = next((p["inlineData"]["data"] for p in d["candidates"][0]["content"]["parts"] if "inlineData" in p), None)
    if img is None:
        print("no image for", item["file"], d["candidates"][0].get("finishReason"))
        continue
    im = Image.open(io.BytesIO(base64.b64decode(img))).convert("RGB")
    if im.size != (1024, 1024):
        im = im.resize((1024, 1024), Image.LANCZOS)
    im.save(dest)
    log.append({"file": item["file"], "usd": USD_PER_IMAGE, "at": time.strftime("%Y-%m-%d %H:%M:%S")})
    log_path.write_text(json.dumps(log, indent=1))
    done += 1
    print(f"{item['file']} {item['name']}: running total ${spent():.2f}", flush=True)
