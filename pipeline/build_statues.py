"""Famous statues and monuments as a separate drawn layer over the map (BACKLOG T4 / B10), with no repainting.

Each statue is a small ink drawing (OpenAI image API, from Commons photos used as reference only), cut out of a flat
magenta backdrop with a soft 1 px edge, and placed on its plinth at its OSM position. The viewer draws them on their
own layer, sorted by depth and cut by the occlusion data like vehicles (web/src/components/Statues.tsx).

  pipeline/.venv/bin/python pipeline/build_statues.py            # cut out and place the drawings already made
  pipeline/.venv/bin/python pipeline/build_statues.py --draw     # first draw the missing ones (capped, logged)

Positions: OSM node (or way centre) -> build_landmarks.to_px -> plus the painter's offset of the block (the "phase"
in data/work/roadfit/shifts.json, about +0.2, +7 map px: the painted buildings and squares sit that much lower than
the projection) -> plus a small nudge where the plinth would otherwise land on a painted roof edge (checked against
the occlusion data and the painted map).

Writes web/public/statues/<id>.webp (day) and <id>_night.webp (darkened, warm floodlight on lit ones) and
web/public/data/statues.json:
  [{id, name, landmark (card slug), x, y (map px of the plinth's ground centre), h (true height in map px),
    hm (height, m), w (true width in map px), ax (anchor: sprite px of the ground centre from the left, as a fraction
    of the width; ay: how far the drawing reaches below the ground centre, as a fraction of its height), lit (floodlit at night), glow (warm glow radius in map px, 0 for none), flame (an eternal flame:
    flickers), day, night (urls)}]
Drawings and references are kept in data/work/statues/ (raw/<id>.png, ref/<file>).
"""
import argparse
import base64
import fcntl
import io
import json
import math
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
from common import ROOT, WORK, ORIGIN_E, ORIGIN_N, R, ELEV, lonlat_to_en  # noqa: E402

OUT = ROOT / "web/public/statues"
DATA = ROOT / "web/public/data/statues.json"
W = WORK / "statues"
RAW, REF = W / "raw", W / "ref"
SPEND = WORK / "style/openai_spend.json"
MPP = 0.25
UP = math.cos(ELEV) / MPP          # map px a point rises per metre of height
MODEL = "gpt-image-2.6-sunburst"
TEXT_IN, IMAGE_IN, IMAGE_OUT = 5.0, 8.0, 30.0   # USD per 1M tokens (as in style/draw_openai.py)
TAG = "statues:"                   # spend log prefix: the cap counts only these entries
KEY = (255, 0, 255)                # the flat backdrop the drawings are made on
LM = "/landmarks"

COMMONS = "https://commons.wikimedia.org/wiki/Special:FilePath/"
# id, name, card slug, OSM (lat, lon of the node or way centre), height in metres (ground to top), nudge (map px),
# floodlit at night, references (landmark photos under web/public, or Commons files), what to draw.
STATUES = [
    dict(id="gelle-fra", name="Gëlle Fra (Monument of Remembrance)", landmark="gelle-fra", osm="node/7773018734",
         ll=(49.6092704, 6.1293598), hm=21.0, lit=True,
         refs=[f"{LM}/gelle-fra/aerial.webp", f"{LM}/gelle-fra/exterior.webp"],
         what="the Gëlle Fra, Luxembourg's Monument of Remembrance: a tall slender grey granite obelisk on a wide "
              "square stepped stone base with inscribed panels, two small dark bronze soldiers seated at the foot of "
              "the obelisk, and on the very top a small gilded bronze woman holding a golden laurel wreath up high. "
              "The obelisk is very tall and thin, about twelve times as tall as it is wide"),
    dict(id="charlotte", name="Grand Duchess Charlotte", landmark="grand-duchess-charlotte-monument", osm="node/370138978",
         ll=(49.6098467, 6.1324488), hm=3.4, lit=True,
         refs=[f"{LM}/grand-duchess-charlotte-monument/photo.webp"],
         what="the Grand Duchess Charlotte monument by Jean Cardot: a simplified dark bronze standing woman wrapped in "
              "a long cloak, one arm raised with the palm turned upwards, on a low round stepped grey stone plinth"),
    dict(id="guillaume-ii", name="William II equestrian statue", landmark="place-guillaume-ii", osm="way/153272628",
         ll=(49.6106847, 6.1312977), hm=8.0, lit=True,
         refs=[f"{LM}/place-guillaume-ii/statue.webp"],
         what="the equestrian statue of King-Grand Duke William II by Antonin Mercié: a dark green-black bronze rider "
              "in uniform with a bicorne hat on a walking horse, on a tall rectangular pale grey stone pedestal with "
              "a moulded cornice and base, inside a low square stone kerb"),
    dict(id="dicks-lentz", name="Dicks–Lentz Monument", landmark="dicks-lentz-monument", osm="node/647570347",
         ll=(49.6112893, 6.1286033), hm=7.5, lit=True, nudge=(16, 2),
         refs=[f"{LM}/dicks-lentz-monument/photo.webp"],
         what="the Dicks-Lentz monument: a round stepped pale stone base and basin, a pale stone column rising from "
              "it, crowned by a small dark bronze lion holding the Luxembourg coat of arms; at the foot of the column "
              "two white stone figures, a singing blacksmith and a woman arranging flowers"),
    dict(id="amelie", name="Princess Amélie", landmark="municipal-park", osm="node/634361192",
         ll=(49.6140615, 6.1243796), hm=5.0, lit=False,
         refs=[f"{COMMONS}Princess_Amalia_of_Saxe-Weimar-Eisenach_-_Parc_Am%C3%A9lie_-_Luxembourg_City_-_DSC06351.JPG?width=800"],
         what="the monument to Princess Amélie: a dark green-grey bronze standing woman in a long 19th-century gown "
              "and shawl, on a tall pale grey granite pedestal with a moulded top and base and an inscription panel"),
    dict(id="rodange", name="Michel Rodange monument (Renert the fox)", landmark="place-guillaume-ii",
         osm="node/621847732", ll=(49.6103282, 6.1308616), hm=4.5, lit=True,
         refs=[f"{COMMONS}Fontaine_Michel_Rodange_Place_Guillaume_II_-_Luxembourg_(LU03)_-_2026-09-27_-_1.jpg?width=800"],
         what="the Michel Rodange monument and fountain: a pale cream stone pedestal carved with garlands and a round "
              "bronze portrait medallion, a small stone basin in front, and on top a seated stone fox (Renert) "
              "with pointed ears"),
    dict(id="churchill", name="Winston Churchill statue", landmark=None, osm="node/634345949",
         ll=(49.611435, 6.1197215), hm=3.2, lit=False,
         refs=[f"{COMMONS}Luxembourg-Churchill,_Nemon(1).jpg?width=800"],
         what="Oscar Nemon's statue of Winston Churchill: a heavy, roughly modelled dark bronze half-length figure of "
              "Churchill in a coat, head slightly bowed, on a plain square pale grey stone plinth"),
    dict(id="solidarity-flame", name="Eternal flame, National Monument of Solidarity",
         landmark="national-monument-of-luxembourg-solidarity", osm="node/651352911",
         ll=(49.60704, 6.1340802), hm=1.6, lit=True, flame=True, refs=[],
         what="the eternal flame of Luxembourg's National Monument of Solidarity: a low square dark granite block "
              "holding a wide shallow bronze bowl, with a bright orange and yellow flame rising from it"),
]

PROMPT = """Draw {what}.

Draw it alone as a single small object for an isometric city map, in the style of a meticulous hand-inked graphic novel map:
- Seen from above at a 30 degree angle, from the south-east, as in an isometric city-building game. The whole object from the bottom of its base to its very top, nothing cut off, centred, filling about 85% of the image height.
- Fine, confident dark navy-brown ink outlines, clean flat colour fills with one or two crisp cel-shaded steps, sunlight from the upper left, the right-hand sides in clear shade. No photo texture, no 3D-render look.
- Natural, controlled colours: pale grey or honey limestone, dark bronze with green-grey highlights, real gold only where it is gilded.
- Background: fully transparent everywhere around the object (if transparency is impossible, one perfectly flat uniform pure magenta #FF00FF; never black, never a glow or vignette). No ground, no pavement, no grass, no cast shadow, no people, no trees, no buildings, no sky, no frame.
- The reference photos only show what the monument looks like; do not copy their background, angle or lighting.
No text, no labels, no borders."""


def to_px_factory():
    m = json.loads((WORK / "mosaic.json").read_text())
    t = np.load(WORK / "terrain.npz")
    tz, te0, tn0, ts = t["z"], float(t["e0"]), float(t["n0"]), float(t["step"])

    def to_px(lat, lon):
        """As in build_landmarks.py, without rounding."""
        e, n = lonlat_to_en(lon, lat)
        iy = min(max(int((n - tn0) / ts), 0), tz.shape[0] - 1); ix = min(max(int((e - te0) / ts), 0), tz.shape[1] - 1)
        z = float(tz[iy, ix]); le, ln = e - ORIGIN_E, n - ORIGIN_N
        sx = (le + ln) * R; sy = (-le + ln) * R * math.sin(ELEV) + z * math.cos(ELEV)
        return (sx - m["sx0"]) / m["mpp"], (m["sy1"] - sy) / m["mpp"]
    return to_px


def painter_offset(x, y):
    """The painted map's offset from the projection where (x, y) lies: the block's measured phase (+0.2, +7)."""
    meta = json.loads((ROOT / "web/public/tiles/meta.json").read_text())
    shifts = json.loads((WORK / "roadfit/shifts.json").read_text())
    best = None
    for p in meta.get("painted", []):
        cx, cy = p["x0"] + p["w"] / 2, p["y0"] + p["h"] / 2
        if p["x0"] <= x < p["x0"] + p["w"] and p["y0"] <= y < p["y0"] + p["h"]:
            d = math.hypot(x - cx, y - cy)
            if best is None or d < best[0]:
                best = (d, p["block"])
    ph = shifts.get(best[1], {}).get("phase") if best else None
    return (ph[0], ph[1]) if ph else (0.2, 7.0)


# ---- drawing --------------------------------------------------------------------------------------------------

def ref_bytes(r):
    """A reference image as JPEG bytes (cached under data/work/statues/ref)."""
    REF.mkdir(parents=True, exist_ok=True)
    name = r.rsplit("/", 1)[-1].split("?")[0].replace("%", "_")
    dst = REF / (Path(name).stem + ".jpg")
    if not dst.exists():
        if r.startswith("http"):
            req = urllib.request.Request(r, headers={"User-Agent": "isometric-luxembourg/1.0 (statue references)"})
            data = urllib.request.urlopen(req, timeout=60).read()
        else:
            data = (ROOT / "web/public" / r.lstrip("/")).read_bytes()
        im = Image.open(io.BytesIO(data)).convert("RGB")
        im.thumbnail((1024, 1024))
        im.save(dst, quality=90)
    return dst.name, dst.read_bytes()


def spend_log():
    return json.loads(SPEND.read_text()) if SPEND.exists() else []


def form(fields, images):
    b = uuid.uuid4().hex
    parts = [f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items()]
    for fn, data in images:
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="image[]"; filename="{fn}"\r\nContent-Type: image/jpeg\r\n\r\n'.encode()
                     + data + b"\r\n")
    parts.append(f"--{b}--\r\n".encode())
    return b"".join(parts), b


def draw(s, key, cap):
    """One drawing, or None when the cap would be passed. Logs the measured cost."""
    spent = sum(e["usd"] for e in spend_log() if e["file"].startswith(TAG))
    if spent + 0.25 > cap:
        print(f"{s['id']}: not drawn, ${spent:.3f} of the ${cap:.2f} cap spent")
        return None
    prompt = PROMPT.format(what=s["what"])
    tall = s["hm"] > 6
    fields = {"model": MODEL, "prompt": prompt, "size": "1024x1536" if tall else "1024x1024", "quality": "high", "n": "1", "background": "transparent", "output_format": "png"}
    imgs = [ref_bytes(r) for r in s["refs"]]
    if imgs:
        body, b = form(fields, imgs)
        req = urllib.request.Request("https://api.openai.com/v1/images/edits", data=body,
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": f"multipart/form-data; boundary={b}"})
    else:
        req = urllib.request.Request("https://api.openai.com/v1/images/generations", data=json.dumps({**fields, "n": 1}).encode(),
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    t = time.time()
    try:
        d = json.load(urllib.request.urlopen(req, timeout=290))
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="ignore")
        print(f"{s['id']}: not drawn, HTTP {e.code} {raw[:300]}")
        return None
    im = Image.open(io.BytesIO(base64.b64decode(d["data"][0]["b64_json"]))).convert("RGBA")
    RAW.mkdir(parents=True, exist_ok=True)
    im.save(RAW / f"{s['id']}.png")
    u = d.get("usage", {})
    det = u.get("input_tokens_details", {})
    usd = (det.get("text_tokens", 0) * TEXT_IN + det.get("image_tokens", 0) * IMAGE_IN + u.get("output_tokens", 0) * IMAGE_OUT) / 1e6
    with open(str(SPEND) + ".lock", "w") as lk:   # other jobs may be appending at the same time
        fcntl.flock(lk, fcntl.LOCK_EX)
        log = spend_log()
        log.append({"file": TAG + s["id"], "model": MODEL, "usd": round(usd, 4), "usage": u,
                    "seconds": round(time.time() - t), "at": time.strftime("%Y-%m-%d %H:%M:%S")})
        tmp = SPEND.with_suffix(".tmp"); tmp.write_text(json.dumps(log, indent=1)); tmp.replace(SPEND)
    print(f"{s['id']}: drawn in {time.time() - t:.0f}s, ${usd:.3f}")
    return im


# ---- cut-out --------------------------------------------------------------------------------------------------

def cut_out(im):
    """RGBA cut-out of a drawing on magenta: soft 1 px edge, magenta spill removed, cropped to the object."""
    rgba = np.asarray(im.convert("RGBA")).astype(np.float32)
    a = rgba[..., :3].copy()
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    # drawn on a transparent backdrop (asked for), else keyed out of the flat magenta one
    if (rgba[..., 3] < 128).mean() > 0.05:
        alpha = rgba[..., 3] / 255
    else:
        # how magenta a pixel is: red and blue both well above green
        alpha = 1 - np.clip((np.minimum(r, b) - g - 60) / 90, 0, 1)
    # keep only the largest connected object and what touches it (no specks of stray ink)
    from scipy import ndimage
    solid = alpha > 0.5
    lab, n = ndimage.label(solid)
    if n > 1:
        sizes = ndimage.sum(solid, lab, range(1, n + 1))
        keep = np.isin(lab, 1 + np.where(sizes >= max(sizes.max() * 0.01, 30))[0])
        alpha = alpha * ndimage.binary_dilation(keep, iterations=2)
    # pull the edge in by half a pixel and soften it over about 1 px
    alpha = ndimage.grey_erosion(alpha, size=(2, 2))
    alpha = ndimage.gaussian_filter(alpha, 0.6)
    # despill: on the semi-transparent edge, drop the magenta cast towards the object's own colour
    spill = np.clip(np.minimum(r, b) - g, 0, None) * (1 - alpha)
    a[..., 0] -= spill * 0.8; a[..., 2] -= spill * 0.8
    out = np.dstack([np.clip(a, 0, 255), np.clip(alpha * 255, 0, 255)]).astype(np.uint8)
    ys, xs = np.where(out[..., 3] > 8)
    return Image.fromarray(out[ys.min():ys.max() + 1, xs.min():xs.max() + 1], "RGBA")


def anchor(im):
    """The ground centre of the plinth, as fractions (ax of the width from the left, ay of the height up from the
    bottom). The plinth's footprint is its widest extent in the bottom fifth; seen at 30 degrees a footprint W wide
    is W / 2 deep on screen, so its centre lies W / 4 above its lowest point."""
    a = np.asarray(im)[..., 3]
    h = a.shape[0]
    xs = np.where(a[h - max(3, h // 5):].max(0) > 128)[0]
    if not len(xs):
        return 0.5, 0.0
    w = xs.max() + 1 - xs.min()
    return float((xs.min() + xs.max() + 1) / 2 / a.shape[1]), float(min(w / 4, h * 0.3) / h)


def night_version(im, lit, flame):
    """Darker and cooler, like the night art; floodlit ones keep a warm light rising from the base."""
    a = np.asarray(im).astype(np.float32)
    rgb, al = a[..., :3], a[..., 3:]
    h = rgb.shape[0]
    night = rgb * np.array([0.30, 0.34, 0.48])
    if lit:
        # floodlights at the foot: warm, strongest low down, fading towards the top; the lit (left) side brighter
        yy = np.linspace(0, 1, h)[:, None, None]
        xx = np.linspace(0, 1, rgb.shape[1])[None, :, None]
        k = (0.55 + 0.45 * yy) * (1.05 - 0.35 * xx)
        warm = rgb * np.array([0.88, 0.70, 0.46]) * k
        night = np.maximum(night, warm)
    if flame:
        # the flame itself stays bright
        r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
        f = ((r > 200) & (g > 90) & (b < 120))[..., None]
        night = np.where(f, rgb, night)
    return Image.fromarray(np.dstack([np.clip(night, 0, 255), al]).astype(np.uint8), "RGBA")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--draw", action="store_true", help="draw the statues that have no drawing yet (OpenAI)")
    ap.add_argument("--redraw", nargs="*", default=[], help="ids to draw again")
    ap.add_argument("--only", nargs="*", default=[], help="draw only these ids (the others are still placed)")
    ap.add_argument("--max-usd", type=float, default=3.0, help="cap for all statue drawings together")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    to_px = to_px_factory()
    key = None
    out = []
    for s in STATUES:
        rawp = RAW / f"{s['id']}.png"
        if args.draw and (not rawp.exists() or s["id"] in args.redraw) and (not args.only or s["id"] in args.only):
            if key is None:
                key = next(l.split("=", 1)[1].strip() for l in (ROOT / "pipeline/.env").read_text().splitlines()
                           if l.startswith("OPENAI_API_KEY="))
            draw(s, key, args.max_usd)
        if not rawp.exists():
            print(f"{s['id']}: no drawing yet (run with --draw)")
            continue
        x, y = to_px(*s["ll"])
        ox, oy = painter_offset(x, y)
        nx, ny = s.get("nudge", (0, 0))
        x, y = x + ox + nx, y + oy + ny
        im = cut_out(Image.open(rawp))
        # stored at up to 6x the true size (crisp on a 2x screen zoomed in, drawn larger than life), at least 128 px
        h_true = s["hm"] * UP
        sh = int(min(max(h_true * 6, 128), im.height, 480))
        im = im.resize((max(1, round(im.width * sh / im.height)), sh), Image.LANCZOS)
        w_true = h_true * im.width / im.height
        im.save(OUT / f"{s['id']}.webp", lossless=False, quality=90, alpha_quality=100, method=6)
        night_version(im, s["lit"], s.get("flame", False)).save(OUT / f"{s['id']}_night.webp", quality=90,
                                                                alpha_quality=100, method=6)
        out.append({"id": s["id"], "name": s["name"], "landmark": s["landmark"], "osm": s["osm"],
                    "x": round(x, 1), "y": round(y, 1), "h": round(h_true, 1), "hm": s["hm"], "w": round(w_true, 1),
                    "ax": round(anchor(im)[0], 3), "ay": round(anchor(im)[1], 3), "lit": s["lit"], "flame": s.get("flame", False),
                    "glow": round((4 if s.get("flame") else min(12, 3 + s["hm"] * 0.6)) / MPP, 1) if s["lit"] else 0,
                    "day": f"/statues/{s['id']}.webp", "night": f"/statues/{s['id']}_night.webp"})
        print(f"{s['id']}: at ({x:.0f}, {y:.0f}), {h_true:.0f} x {w_true:.0f} map px, sprite {im.size}")
    DATA.write_text(json.dumps(out, ensure_ascii=False, indent=0))
    spent = sum(e["usd"] for e in spend_log() if e["file"].startswith(TAG))
    print(f"{len(out)} statues; drawings so far ${spent:.3f}")


if __name__ == "__main__":
    main()
