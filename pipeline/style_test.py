"""One-off: ask a Gemini image model to redraw one capture, to see the style and whether the key's tier allows it."""
import base64
import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from PIL import Image
from common import ROOT, WORK

key = next(l.split("=", 1)[1].strip() for l in (ROOT / "pipeline" / ".env").read_text().splitlines() if l.startswith("GEMINI_API_KEY="))
model = sys.argv[1]
OUT = WORK / "style_test"
m = json.loads((WORK / "mosaic.json").read_text())
# Cathedral and old town: mosaic pixels around x 7648, y 6265.
cx, cy, size = 7800, 6300, 1024
c0, r0 = cx // m["frame"], cy // m["frame"]
canvas = Image.new("RGB", (m["frame"] * 2, m["frame"] * 2))
for dc in (0, 1):
    for dr in (0, 1):
        canvas.paste(Image.open(WORK / "frames" / f"{c0 + dc}_{r0 + dr}.jpg"), (dc * m["frame"], dr * m["frame"]))
x, y = cx - c0 * m["frame"], cy - r0 * m["frame"]
src = canvas.crop((x, y, x + size, y + size))
src.save(OUT / "input.jpg", quality=92)
buf = io.BytesIO(); src.save(buf, "JPEG", quality=92)
prompt = ("Redraw this exact aerial view as detailed isometric pixel art in the style of a late-1990s city-building game. "
          "Keep every building, street, tree and the camera angle exactly where they are; do not add or move anything. "
          "Crisp hand-placed pixels, clean window grids on the walls, slate-grey and warm stone colours, rich green trees with rounded clusters, "
          "soft consistent sunlight from the upper left. No text, no labels, no people in the foreground.")
body = {"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}}]}],
        "generationConfig": {"responseModalities": ["IMAGE"]}}
req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                             data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": key})
try:
    d = json.load(urllib.request.urlopen(req, timeout=170))
except urllib.error.HTTPError as e:
    err = json.loads(e.read()).get("error", {})
    print(model, "HTTP", e.code, err.get("status"), err.get("message", "")[:300])
    sys.exit(0)
parts = d["candidates"][0]["content"]["parts"]
for p in parts:
    if "inlineData" in p:
        im = Image.open(io.BytesIO(base64.b64decode(p["inlineData"]["data"])))
        path = OUT / f"{model}.png"
        im.save(path)
        print(model, "OK", im.size, path.name, "usage", d.get("usageMetadata", {}).get("totalTokenCount"))
        break
else:
    print(model, "no image", str(parts)[:200], d["candidates"][0].get("finishReason"))
