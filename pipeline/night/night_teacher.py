"""Mock-up C: ask the image teacher (OpenAI image edit) to repaint one painted day view as a night scene.
Usage: night_teacher.py <day.jpg> <out.png> [--max-usd 0.5]"""
import base64
import io
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline" / "style"))
src, dest = sys.argv[1], sys.argv[2]
MAX = float(sys.argv[sys.argv.index("--max-usd") + 1]) if "--max-usd" in sys.argv else 0.5
MODEL, TEXT_IN, IMAGE_IN, IMAGE_OUT = "gpt-image-2.6-sunburst", 5.0, 8.0, 30.0
PROMPT = """Repaint this exact illustrated isometric map view as the same place at night. Keep every building,
street, tree, river and the camera exactly where they are, and keep the same inked illustration style with fine
outlines. Mood: warm and cozy, storybook night: deep blue sky light, warm golden lit windows (about a third of
them), warm street lamps along the streets with soft pools of light, landmarks, churches and bridges gently floodlit,
warm light reflections shimmering on any water, a faint mist low in the valleys. Do not add or remove any object:
no extra lamp posts, arches or buildings beyond small light sources. No moon or sky in the picture, no people,
no new vehicles, no text."""

key = next(l.split("=", 1)[1].strip() for l in (ROOT / "pipeline/.env").read_text().splitlines() if l.startswith("OPENAI_API_KEY="))
log_path = ROOT / "data/work/style/openai_spend.json"
log = json.loads(log_path.read_text()) if log_path.exists() else []
night_spend = sum(e["usd"] for e in log if e["file"].startswith("night"))
if night_spend + 0.08 > MAX:
    sys.exit(f"stopping at the night cap: ${night_spend:.2f} of ${MAX:.2f}")
b = uuid.uuid4().hex
data = Path(src).read_bytes()
parts = [f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
         for k, v in {"model": MODEL, "prompt": PROMPT, "size": "1024x1024", "quality": "high", "n": "1"}.items()]
parts.append(f'--{b}\r\nContent-Disposition: form-data; name="image"; filename="day.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'.encode() + data + b"\r\n")
parts.append(f"--{b}--\r\n".encode())
req = urllib.request.Request("https://api.openai.com/v1/images/edits", data=b"".join(parts),
                             headers={"Authorization": f"Bearer {key}", "Content-Type": f"multipart/form-data; boundary={b}"})
t = time.time()
try:
    d = json.load(urllib.request.urlopen(req, timeout=290))
except urllib.error.HTTPError as e:
    sys.exit(f"HTTP {e.code} {e.read().decode(errors='ignore')[:300]}")
Image.open(io.BytesIO(base64.b64decode(d["data"][0]["b64_json"]))).convert("RGB").save(dest)
u = d.get("usage", {}); det = u.get("input_tokens_details", {})
usd = (det.get("text_tokens", 0) * TEXT_IN + det.get("image_tokens", 0) * IMAGE_IN + u.get("output_tokens", 0) * IMAGE_OUT) / 1e6
log.append({"file": "night:" + Path(src).name, "model": MODEL, "usd": round(usd, 4), "usage": u, "seconds": round(time.time() - t), "at": time.strftime("%Y-%m-%d %H:%M:%S")})
log_path.write_text(json.dumps(log, indent=1))
print(f"saved {dest} in {time.time() - t:.0f}s, ${usd:.3f}; OpenAI total ${sum(e['usd'] for e in log):.2f}")
