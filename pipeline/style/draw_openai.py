"""Draw training examples with OpenAI's image API. Cost is measured from each response, capped, and logged.

  python style/draw_openai.py --files 00.jpg --max-usd 1 --out test
"""
import argparse
import base64
import io
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from PIL import Image

sys.path.insert(0, ".")
from common import ROOT, WORK

MODEL = "gpt-image-2.6-sunburst"
# USD per 1M tokens, from OpenAI's pricing page on 5 Nov 2026.
TEXT_IN, IMAGE_IN, IMAGE_OUT = 5.0, 8.0, 30.0
PROMPT = """Redraw this exact view as a beautiful, highly detailed isometric city illustration, like a superbly hand-crafted city-building game.

Tone, which matters most:
- Calm, natural, grounded colour with real depth. Think a clear late afternoon, not a sunny cartoon. Overall exposure is moderate, never bright or washed out.
- Deep, soft shadows between buildings and in streets, giving strong contrast and weight.
- Muted, restrained saturation. Greens are deep, dark and slightly desaturated: forest and olive, never lime or neon.
- Limestone is a soft grey-beige, not yellow. Slate roofs are dark grey-blue. Roads are a neutral mid grey. Colour accents are rare and small.
- Modern glass is dark and subtly reflective, not bright blue.

Detail:
- Crisp and sharp, with no blur or smears and no black cartoon outlines.
- Every wall shows a regular grid of individual windows, with floor lines and cornices. Roofs show slate courses, dormers, chimneys and roof equipment.
- Individual trees with lit tops and dark bases.
- Replace any stretched or smeared texture, especially on cliffs and walls, with believable rock, masonry or trees.

Hard rules, which outrank everything above:
- Trace the input. Every building outline, roof shape, road, bridge, tree mass and open space must line up with the input when overlaid. Do not tidy, straighten, regularise or redesign anything.
- Water stays calm, narrow and exactly as wide as in the input, in a dark natural green-grey. No rapids, no foam.
- Add no trams, buses, trains, buildings, towers, statues, market stalls or awnings that are not visible in the input. Only a few small cars on existing roads. People only as rare tiny dots.
No text, no labels, no borders."""

INK = """Redraw this exact view as a superbly detailed isometric ink illustration of a city, like a meticulous hand-inked graphic novel map.

Line and colour, which matter most:
- Fine, confident, dark navy-brown ink outlines around every building, roof, window group and tree. The lines are thin and even, never thick or cartoonish.
- Clean flat colour fills with one or two crisp cel-shaded steps. No soft airbrush, no photo texture, no 3D-render look, no pixel grid.
- Rich but controlled colour with strong contrast: warm honey-grey limestone, cool dark slate-blue roofs with lighter ridges, deep shadow side walls, neutral grey roads, occasional brick red or copper green.
- Deep, dark, flat shadows cast from the upper left, grounding every building. Moderate overall exposure, never washed out.
- Trees are rich deep greens with inked clumps of foliage and lit tops, in several tones. Never lime or neon.
- Modern glass is deep navy with crisp diagonal reflections.

Detail:
- Every wall shows a regular grid of individually inked windows, with floor lines and cornices. Roofs show slate courses, dormers, chimneys and roof equipment.
- Replace any stretched or smeared texture, especially on cliffs and walls, with believable inked rock, masonry or trees.

Hard rules, which outrank everything above:
- Trace the input. Every building outline, roof shape, road, bridge, tree mass and open space must line up with the input when overlaid. Do not tidy, straighten, regularise or redesign anything.
- Water is flat, calm and exactly as wide as in the input, in one even deep green-blue with no ripples, foam, reflections, boats or rapids.
- Leave every road, street, car park and railway track completely empty: no cars, buses, trams, trains, bicycles, people, birds or animals anywhere, even if the input shows some.
- Add no buildings, towers, statues, market stalls or awnings that are not visible in the input.
- Trees are in full green summer leaf, with no autumn colour, blossom or snow.
No text, no labels, no borders."""

INK2 = """Redraw this exact view as a superbly detailed isometric ink illustration of a city, like a meticulous hand-inked graphic novel map.

Line and colour, which matter most:
- Fine, confident, dark navy-brown ink outlines around every building, roof, window group and tree. The lines are thin and even, never thick or cartoonish.
- Clean flat colour fills with one or two crisp cel-shaded steps. No soft airbrush, no photo texture, no 3D-render look, no pixel grid.
- Rich but controlled colour with strong contrast: warm honey-grey limestone, cool dark slate-blue roofs with lighter ridges, deep shadow side walls, neutral grey roads, occasional brick red or copper green.
- Deep, dark, flat shadows cast from the upper left, grounding every building. Moderate overall exposure, never washed out.
- Trees are rich deep greens with inked clumps of foliage and lit tops, in several tones. Never lime or neon.
- Modern glass is deep navy with crisp diagonal reflections.

Detail:
- Every wall shows a regular grid of individually inked windows, with floor lines and cornices. Roofs show slate courses, dormers, chimneys and roof equipment.
- Replace any stretched or smeared texture, especially on cliffs and walls, with believable inked rock, masonry or trees.

Hard rules, which outrank everything above:
- Trace the input. Every building outline, roof shape, road, bridge, tree mass and open space must line up with the input when overlaid. Do not move, add, remove or redesign anything.
- But draw it cleanly: every wall is a straight, flat plane; vertical edges are truly vertical; walls, eaves and roof ridges run parallel to the isometric axes of the view. Windows sit in regular, evenly spaced rows and columns aligned with each wall and its floor lines, all the same size on a given facade. Never bend, smear or wobble a facade, even where the input texture is blurred or stretched.
- Water is flat, calm and exactly as wide as in the input, in one even deep green-blue with no ripples, foam, reflections, boats or rapids.
- Leave every road, street, car park and railway track completely empty: no cars, buses, trams, trains, bicycles, people, birds or animals anywhere, even if the input shows some.
- Add no buildings, towers, statues, market stalls or awnings that are not visible in the input.
- Trees are in full green summer leaf, with no autumn colour, blossom or snow.
No text, no labels, no borders.
- Bridges and viaducts keep the colour and material the input shows: stone bridges stay honey-grey stone, concrete stays grey. Never paint a bridge red unless the input clearly shows a red steel bridge.
- Railway tracks: two steel rails on sleepers over a gravel bed, exactly where the input shows them, empty.
"""

BLEND = """Redraw this exact view as a beautiful, joyful, superbly detailed isometric city illustration: a charming storybook map with delicate ink linework and warm sunshine.

Line and colour, which matter most:
- Fine, delicate, dark warm-brown ink outlines around buildings, roofs, windows and trees. Softer and lighter than a comic, never thick.
- Colour fills with gentle painted shading: three or four soft tonal steps, not flat, and no photo texture or 3D-render look.
- Warm, colourful and inviting, but with moderate exposure: like clear mid-afternoon light, with rich mid-tones. Never high-key, washed out, golden or neon.
- Real variety from building to building: soft grey-beige and cream limestone with only a little warmth, not yellow or orange; a few muted rose, brick-red or sage facades; darker blue-grey slate roofs. Roads are a neutral mid grey.
- Natural greens in many tones, mostly deep emerald and forest, with sunlit tops and dark bases on individual round trees. Rich, not yellow or lime.
- Deep, clear shadows from the sun at the upper left: streets and courtyards fall properly into shade, and the shadow side of every building is distinctly darker, giving real depth and contrast.
- Modern glass is a clear mid blue with crisp reflections.

Detail:
- Every wall shows a regular grid of individually drawn windows, with shutters, floor lines and cornices. Roofs show slate courses, dormers and chimneys.
- Replace any stretched or smeared texture, especially on cliffs and walls, with believable rock, masonry or trees.

Hard rules, which outrank everything above:
- Trace the input. Every building outline, roof shape, road, bridge, tree mass and open space must line up with the input when overlaid. Do not tidy, straighten, regularise or redesign anything.
- Water stays calm, narrow and exactly as wide as in the input, in a natural soft teal. No rapids, no foam.
- Add no trams, buses, trains, buildings, towers, statues, market stalls or awnings that are not visible in the input. Only a few small cars on existing roads. People only as rare tiny dots.
No text, no labels, no borders."""

ap = argparse.ArgumentParser()
ap.add_argument("--brief", choices=["calm", "ink", "ink2", "blend"], default="blend")
ap.add_argument("--files", nargs="+", required=True)
ap.add_argument("--max-usd", type=float, required=True)
ap.add_argument("--out", default="examples_openai")
ap.add_argument("--captures", default="captures", help="input folder under data/work/style")
args = ap.parse_args()

key = next(l.split("=", 1)[1].strip() for l in (ROOT / "pipeline/.env").read_text().splitlines() if l.startswith("OPENAI_API_KEY="))
base = WORK / "style"
out = base / args.out
out.mkdir(exist_ok=True)
log_path = base / "openai_spend.json"
log = json.loads(log_path.read_text()) if log_path.exists() else []


def spent():
    return sum(e["usd"] for e in log)


def form(fields, filename, data):
    b = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{b}\r\nContent-Disposition: form-data; name="image"; filename="{filename}"\r\nContent-Type: image/jpeg\r\n\r\n'.encode() + data + b"\r\n")
    parts.append(f"--{b}--\r\n".encode())
    return b"".join(parts), b


for f in args.files:
    dest = out / f.replace(".jpg", ".png")
    if dest.exists():
        continue
    if log and spent() + max(e["usd"] for e in log) > args.max_usd:
        print(f"stopping at the cap: ${spent():.3f} of ${args.max_usd:.2f}")
        break
    hints = json.loads((base / "hints.json").read_text()) if (base / "hints.json").exists() else {}
    prompt = {"calm": PROMPT, "ink": INK, "ink2": INK2, "blend": BLEND}[args.brief] + ("\n\n" + hints[f] if f in hints else "")
    body, boundary = form({"model": MODEL, "prompt": prompt, "size": "1024x1024", "quality": "high", "n": "1"}, f, (base / args.captures / f).read_bytes())
    req = urllib.request.Request("https://api.openai.com/v1/images/edits", data=body,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": f"multipart/form-data; boundary={boundary}"})
    t = time.time()
    try:
        d = json.load(urllib.request.urlopen(req, timeout=290))
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="ignore")
        try:
            err = json.loads(raw).get("error", {})
            sys.exit(f"stopped on {f}: HTTP {e.code} {err.get('code')} {str(err.get('message'))[:220]}")
        except ValueError:
            sys.exit(f"stopped on {f}: HTTP {e.code} {raw[:220]}")
    im = Image.open(io.BytesIO(base64.b64decode(d["data"][0]["b64_json"]))).convert("RGB")
    im.save(dest)
    u = d.get("usage", {})
    det = u.get("input_tokens_details", {})
    usd = (det.get("text_tokens", 0) * TEXT_IN + det.get("image_tokens", 0) * IMAGE_IN + u.get("output_tokens", 0) * IMAGE_OUT) / 1e6
    import fcntl
    with open(str(log_path) + ".lock", "w") as lk:   # transform pairs may be appending in parallel
        fcntl.flock(lk, fcntl.LOCK_EX)
        log = json.loads(log_path.read_text()) if log_path.exists() else []
        log.append({"file": f, "model": MODEL, "usd": round(usd, 4), "usage": u, "seconds": round(time.time() - t), "at": time.strftime("%Y-%m-%d %H:%M:%S")})
        tmp = log_path.with_suffix(".tmp"); tmp.write_text(json.dumps(log, indent=1)); tmp.replace(log_path)
    print(f"{f}: {im.size} {time.time() - t:.0f}s measured ${usd:.3f}, total ${spent():.3f}, tokens {u.get('output_tokens')}", flush=True)
