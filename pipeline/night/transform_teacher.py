"""Teacher pairs for the transformation model: the same drawn view in another light or season.

Usage: transform_teacher.py <target> <out dir> <max total night+transform usd> <day image> [<day image> ...]
Targets: night, golden, winter, autumn, spring, winter_night. Keeps every object in place; only light/season change.
"""
import base64
import fcntl
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
target, out_dir, MAX = sys.argv[1], Path(sys.argv[2]), float(sys.argv[3])
files = sys.argv[4:]
MODEL, TEXT_IN, IMAGE_IN, IMAGE_OUT = "gpt-image-2.6-sunburst", 5.0, 8.0, 30.0
KEEP = """Repaint this exact illustrated isometric map view of Luxembourg City in a different light/season. Keep every
building, roof, window, street, bridge, tree, river and the camera exactly where they are, at the same size, and
keep the same inked illustration style with fine dark outlines and flat colour fills. Do not add or remove any
building, bridge, road or tree. No people, no vehicles, no text, no sky or horizon in the picture."""
TARGETS = {
    "night": """Make it night. Warm and cozy storybook night: deep blue moonlit tones, warm golden light in about a
third of the windows, warm street lamps along the streets with soft pools of light on the ground, landmarks,
churches and bridges gently floodlit, warm light reflections shimmering on any water, faint mist low in the valleys.
There is no sunlight: remove every cast sun shadow from the day picture completely; the only shadows are soft
ones around the pools of artificial light.""",
    "golden": """Make it late-afternoon golden hour. Low warm sun from the upper left: warm orange-gold light on the
sunlit walls and roofs, long soft shadows stretching to the lower right, cool blue-violet tones in the shade, a
gentle warm haze. Street lamps are off.""",
    "winter": """Make it a sunny winter day after snowfall. Fresh white snow lies on every roof, ledge, lawn, park and
on tree branches; deciduous trees are bare (dark branches dusted with snow), conifers stay dark green with snow.
Roads and pavements are cleared but wet and grey with snow banks along the edges. Water is dark and cold with
thin ice at the banks. Cool, crisp blue-white light with clear shadows.""",
    "autumn": """Make it a sunny autumn day. Deciduous trees in rich orange, red, gold and brown, some already thinning;
fallen leaves on lawns, parks and along pavements; conifers stay dark green. Warm, slightly lower sun with
longer shadows.""",
    "spring": """Make it a fresh spring day. Bright light-green new leaves on all deciduous trees, some trees in pink
and white blossom in parks and along streets, lush green lawns with a few flower beds. Clear, soft, bright light.""",
    "winter_night": """Make it a snowy winter night. Fresh snow on every roof, ledge, lawn, park and tree branch
(deciduous trees bare and snow-dusted), roads cleared with snow banks. Warm and cozy: deep blue night tones, the
snow catching the light, warm golden light in about a third of the windows, warm street lamps with glowing pools
on the snow, landmarks gently floodlit, faint mist in the valleys. There is no sunlight: no cast sun shadows.
No Christmas decorations.""",
}
PROMPT = KEEP + "\n\n" + TARGETS[target]
out_dir.mkdir(parents=True, exist_ok=True)
key = next(l.split("=", 1)[1].strip() for l in (ROOT / "pipeline/.env").read_text().splitlines() if l.startswith("OPENAI_API_KEY="))
log_path = ROOT / "data/work/style/openai_spend.json"
for src in files:
    dest = out_dir / (Path(src).stem + f"_{target}.png")
    if dest.exists():
        continue
    with open(str(log_path) + ".lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        log = json.loads(log_path.read_text()) if log_path.exists() else []
    spent = sum(e["usd"] for e in log if e["file"].startswith(("night", "transform")))
    if spent + 0.07 > MAX:
        sys.exit(f"stopping at the transform cap: ${spent:.2f} of ${MAX:.2f}")
    buf = io.BytesIO(); Image.open(src).convert("RGB").save(buf, "JPEG", quality=94)
    b = uuid.uuid4().hex
    parts = [f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
             for k, v in {"model": MODEL, "prompt": PROMPT, "size": "1024x1024", "quality": "high", "n": "1"}.items()]
    parts.append(f'--{b}\r\nContent-Disposition: form-data; name="image"; filename="day.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'.encode() + buf.getvalue() + b"\r\n")
    parts.append(f"--{b}--\r\n".encode())
    req = urllib.request.Request("https://api.openai.com/v1/images/edits", data=b"".join(parts),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": f"multipart/form-data; boundary={b}"})
    t = time.time()
    for attempt in range(3):
        try:
            d = json.load(urllib.request.urlopen(req, timeout=290))
            break
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="ignore")[:300]
            if e.code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(30); continue
            sys.exit(f"HTTP {e.code} {msg}")
        except Exception as e:  # network hiccup
            if attempt < 2:
                time.sleep(30); continue
            sys.exit(f"failed: {e}")
    Image.open(io.BytesIO(base64.b64decode(d["data"][0]["b64_json"]))).convert("RGB").save(dest)
    u = d.get("usage", {}); det = u.get("input_tokens_details", {})
    usd = (det.get("text_tokens", 0) * TEXT_IN + det.get("image_tokens", 0) * IMAGE_IN + u.get("output_tokens", 0) * IMAGE_OUT) / 1e6
    with open(str(log_path) + ".lock", "w") as lk:   # several targets run in parallel: append under a lock
        fcntl.flock(lk, fcntl.LOCK_EX)
        log = json.loads(log_path.read_text()) if log_path.exists() else []
        log.append({"file": f"transform:{target}:{Path(src).name}", "model": MODEL, "usd": round(usd, 4), "usage": u,
                    "seconds": round(time.time() - t), "at": time.strftime("%Y-%m-%d %H:%M:%S")})
        tmp = log_path.with_suffix(".tmp"); tmp.write_text(json.dumps(log, indent=1)); tmp.replace(log_path)
    print(f"{dest.name} {time.time() - t:.0f}s ${usd:.3f} (transform total ${spent + usd:.2f})", flush=True)
print("TARGET DONE", target)
