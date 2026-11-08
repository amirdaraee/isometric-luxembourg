"""Christmas markets (Winterlights): the drawing service adds the market to the painted WINTER art (day) and WINTER
NIGHT art (night) of each square; patchlib.py then keeps only the market, over the current art, with no halo.

Two steps:
  xmas_v2.py draw <day|night> <cap usd> [site,site] [--relight]   the paid call. Sends the square cut from the newest winter or
                                                      winter-night canvas of the block that holds it (city_blocks.py
                                                      state) and caches what was sent and what came back in
                                                      data/work/events/xmas_v3/. Refuses to spend past the cap
                                                      (counted over every "xmas3:" entry of openai_spend.json).
                                                      --relight (night): send the night art with the chosen day
                                                      market laid in, so that day and night show the same market.
  xmas_v2.py composite                                free, rerun whenever winter or winter night is repainted
                                                      (issue I11). Uses the newest drawing of each site (xmas_v3,
                                                      else the earlier xmas_v2 one) and writes
                                                      web/public/events/xmas/<site>_<day|night>.webp and xmas.json
                                                      (each patch's box in map px). Rerun it after every rebuild of
                                                      the winter or winter-night tiles.
  xmas_v2.py unframe <cap usd>                        the chosen Constitution drawings with the Ferris wheel's
                                                      painted support taken out (a masked edit, about $0.06 each,
                                                      cached, so rerunning it is free); saved as the next try and
                                                      recorded in chosen.json. Then run composite.

The moving parts (the carousel's horses, the pyramid's top blades) are left out of the drawings: they are live
sprites (build_event_sprites.py, EventLayer.tsx). The Ferris wheel, supports included, is drawn live in the map's
projection (web/src/components/ferrisWheel.ts).
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
sys.path.insert(0, str(Path(__file__).parent))
from common import WORK  # noqa: E402
import patchlib  # noqa: E402

OLD = WORK / "events" / "xmas_v2"
NEW = WORK / "events" / "xmas_v3"
OUT = ROOT / "web/public/events/xmas"
MODEL, TEXT_IN, IMAGE_IN, IMAGE_OUT = "gpt-image-2.6-sunburst", 5.0, 8.0, 30.0
CROP = 760  # map px around each square; the patch is made at this size (1:1 with the tiles)
SEND = 1024
TAG = "xmas3"
VERSION = {"day": "winter", "night": "winter_night"}
lm = {c["slug"]: c for c in json.loads((ROOT / "web/public/data/landmarks.json").read_text())}
SITES = {
    "place-darmes": ("place-d-armes", "On the tree-lined square in the middle (Place d'Armes), add a Christmas market: a ring "
                     "of about 20 small wooden chalets with white and red roofs around the central bandstand, a tall decorated "
                     "Christmas tree (about 12 m) and a small nativity crib, string lights between the trees."),
    "constitution": ("place-de-la-constitution", "On the open square around the tall golden-statue monument in the middle "
                     "(Place de la Constitution, Gëlle Fra), add a Christmas market: about 30 small wooden chalets with white "
                     "and red roofs in rows; on the left of the square, the white steel A-frame support of a Ferris wheel "
                     "(about 32 m tall: two tall slanted white legs meeting at the hub) standing on a round boarding platform, "
                     "with NO wheel rim, NO spokes and NO gondolas (the wheel itself is added later); and a tall wooden "
                     "Christmas pyramid with several tiers of carved figures, its top fan blades left out; string lights."),
    "knuedler": ("place-guillaume-ii", "On the large paved square in the middle with the equestrian statue (Place Guillaume II), "
                 "add a Christmas fair: a big decorated Christmas tree, a long ice slide, a few wooden chalets with white and "
                 "red roofs, string lights, and on the right a carousel shown only as a round wooden platform with a flat "
                 "round red-and-gold canopy roof on a central pole, with NO horses and nothing between platform and roof "
                 "(the horses are added later)."),
}
COMMON = ("Keep every existing building, roof, tree, street, colour and the camera exactly as they are, same inked "
          "illustration style with fine dark outlines and flat colour fills. Only add the market described, on the open "
          "square in the centre of the image; nothing else changes. No people, no vehicles, no text, no sky.")
LIGHT = {"day": "It is a snowy winter day: the chalet roofs carry snow like the other roofs; string lights are off.",
         "night": "It is a snowy winter night, exactly as dark as the input: the chalets, the tree and the string lights "
                  "glow warm gold and cast warm light pools on the snowy ground. No sun shadows."}
log_path = WORK / "style/openai_spend.json"


def box(name):
    slug = SITES[name][0]
    return lm[slug]["x"] - CROP // 2, lm[slug]["y"] - CROP // 2


def spent():
    return sum(e["usd"] for e in json.loads(log_path.read_text()) if e["file"].startswith(TAG + ":"))


def call(crop: Image.Image, prompt: str, tag: str, mask: Image.Image | None = None) -> Image.Image:
    """One paid edit. mask (optional): an RGBA image the size of `crop`, transparent where the drawing may change."""
    key = next(l.split("=", 1)[1].strip() for l in (ROOT / "pipeline/.env").read_text().splitlines() if l.startswith("OPENAI_API_KEY="))
    buf = io.BytesIO(); crop.save(buf, "JPEG", quality=94)
    b = uuid.uuid4().hex
    parts = [f'--{b}\r\nContent-Disposition: form-data; name="{kk}"\r\n\r\n{v}\r\n'.encode()
             for kk, v in {"model": MODEL, "prompt": prompt, "size": "1024x1024", "quality": "high", "n": "1"}.items()]
    parts.append(f'--{b}\r\nContent-Disposition: form-data; name="image"; filename="sq.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'.encode() + buf.getvalue() + b"\r\n")
    if mask is not None:
        mb = io.BytesIO(); mask.save(mb, "PNG")
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="mask"; filename="mask.png"\r\nContent-Type: image/png\r\n\r\n'.encode() + mb.getvalue() + b"\r\n")
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
        log.append({"file": f"{TAG}:{tag}", "model": MODEL, "usd": round(usd, 4), "usage": u, "seconds": round(time.time() - t0), "at": time.strftime("%Y-%m-%d %H:%M:%S")})
        tmp = log_path.with_suffix(".tmp"); tmp.write_text(json.dumps(log, indent=1)); tmp.replace(log_path)
    print(tag, f"{time.time() - t0:.0f}s ${usd:.3f}, {TAG} total ${spent():.3f}", flush=True)
    return im


def unlit(day_raw: Image.Image, day_sent: Image.Image, day_base: np.ndarray, night_base: np.ndarray) -> Image.Image:
    """The night input for a relit drawing: the winter-night art with the day drawing's market laid in, graded
    like the night versions (build_variant_tiles.py), so the drawing service only has to light it."""
    raw, mask = patchlib.prepare(day_raw, day_sent, day_base, night=False)
    f = raw.astype(np.float32)
    lum = f[..., 0] * 0.3 + f[..., 1] * 0.55 + f[..., 2] * 0.15
    dark = np.dstack([lum * 0.2 + 6, lum * 0.25 + 10, lum * 0.42 + 22])
    soft = cv2.GaussianBlur(cv2.dilate(mask, np.ones((5, 5), np.uint8)).astype(np.float32), (0, 0), 1.2)[..., None]
    out = dark * soft + night_base.astype(np.float32) * (1 - soft)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


RELIGHT = ("The Christmas market on the square is already drawn, still unlit: keep every chalet, tree, ride, slide, "
           "statue and string of lights exactly where and as it is, and add nothing new. Light it for a snowy winter "
           "night, exactly as dark as the input elsewhere: the chalets' windows and counters, the Christmas tree and the "
           "string lights glow warm gold and cast warm light pools on the snowy ground. No sun shadows.")


def draw(when: str, cap: float, only: list[str], relight: bool = False):
    """relight (night only): send the night art with the chosen day market already in it, so day and night show
    the same market (the night patch fades in over the day one)."""
    NEW.mkdir(parents=True, exist_ok=True)
    rl = NEW / "relit.json"
    relit = json.loads(rl.read_text()) if rl.exists() else []
    for name in only:
        x0, y0 = box(name)
        base = patchlib.base_crop(x0, y0, CROP, CROP, VERSION[when])
        if relight:
            assert when == "night"
            dr, ds = pick(name, "day")
            base = np.asarray(unlit(Image.open(dr), Image.open(ds), patchlib.base_crop(x0, y0, CROP, CROP, VERSION["day"]), base))
        sent = Image.fromarray(base).resize((SEND, SEND), Image.LANCZOS)
        if spent() + 0.08 > cap:
            sys.exit(f"cap reached: ${spent():.3f} of ${cap:.2f} spent")
        n = len(list(NEW.glob(f"{name}_{when}_raw*.png")))
        prompt = f"{RELIGHT}\n\n{COMMON}" if relight else f"{SITES[name][1]}\n\n{LIGHT[when]}\n\n{COMMON}"
        raw = call(sent, prompt, f"{name}_{when}_{n}")
        sent.save(NEW / f"{name}_{when}_sent{n}.png")
        raw.save(NEW / f"{name}_{when}_raw{n}.png")
        if relight:
            relit.append(f"{name}_{when}_raw{n}")
            rl.write_text(json.dumps(relit))


def pick(name: str, when: str) -> tuple[Path, Path]:
    """The chosen drawing of a site: data/work/events/xmas_v3/chosen.json, else the newest try, else the old one."""
    ch = NEW / "chosen.json"
    chosen = json.loads(ch.read_text()) if ch.exists() else {}
    if f"{name}_{when}" in chosen:
        n = chosen[f"{name}_{when}"]
        return NEW / f"{name}_{when}_raw{n}.png", NEW / f"{name}_{when}_sent{n}.png"
    tries = sorted(NEW.glob(f"{name}_{when}_raw*.png"), key=lambda p: int(p.stem.rsplit("raw", 1)[1])) if NEW.exists() else []
    if tries:
        return tries[-1], tries[-1].with_name(tries[-1].name.replace("_raw", "_sent"))
    return OLD / f"{name}_{when}_raw.png", OLD / f"{name}_{when}_base.png"


def composite():
    placed = []
    sheet = []
    for name in SITES:
        x0, y0 = box(name)
        bases = {w: patchlib.base_crop(x0, y0, CROP, CROP, VERSION[w]) for w in ("day", "night")}
        picked = {w: pick(name, w) for w in ("day", "night")}
        rl = NEW / "relit.json"
        share = picked["night"][0].stem in (json.loads(rl.read_text()) if rl.exists() else [])
        pd, pn, info = patchlib.composite_pair(*[(Image.open(picked[w][0]), Image.open(picked[w][1]), bases[w]) for w in ("day", "night")],
                                               share=share)
        bx, by, bw, bh = info.pop("box")
        placed.append({"site": name, "x0": x0 + bx, "y0": y0 + by, "w": bw, "h": bh})
        for when, patch in (("day", pd), ("night", pn)):
            patchlib.save_patch(patch, OUT / f"{name}_{when}.webp")
            sheet.append(np.hstack([bases[when], patchlib.over(patch, bases[when], (bx, by))]))
        print(name, " + ".join(str(picked[w][0].relative_to(WORK)) for w in ("day", "night")), info,
              "/".join(f"{(OUT / f'{name}_{w}.webp').stat().st_size // 1024}" for w in ("day", "night")), "KB", flush=True)
    (OUT / "xmas.json").write_text(json.dumps(placed, indent=1))
    (WORK / "events").mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.vstack(sheet)).resize((CROP, CROP * len(sheet) // 2)).save(WORK / "events" / "xmas_composite_sheet.jpg", quality=85)
    print("composite done")


# The painted Ferris-wheel support on Place de la Constitution faced the camera, which forced a flat, face-on wheel.
# The whole wheel (supports included) is now drawn live in the map's projection (EventLayer.tsx), so the support is
# taken out of the drawings: hand-traced polygons round its legs and hub, in drawing px (1024 square), per drawing.
FRAME = {
    "constitution_day_raw0": {
        "legs": [[(316, 414), (337, 430), (318, 548), (281, 556), (280, 541)],
                 [(326, 414), (346, 428), (399, 546), (365, 557), (352, 528)]],
        "hub": (331.5, 423.5, 15), "grow": 2},
    "constitution_night_raw1": {
        "legs": [[(318, 414), (340, 430), (311, 551), (276, 553), (282, 536)],
                 [(326, 414), (347, 428), (398, 552), (370, 556), (352, 528)]],
        "hub": (333, 422, 16), "grow": 4},
}


UNFRAME = ("Remove the white steel Ferris-wheel A-frame support completely: its slanted legs, their feet and the round "
           "hub. Where it stood, show what is behind it: the paved snowy square, the string lights and, at the bottom, "
           "the empty round wooden boarding platform with its white railing, nothing standing on it. Keep everything "
           "else exactly as it is: same inked illustration style, same camera, same colours and light.")


def unframe(cap: float):
    """Paid (about $0.06 a drawing): copies of the chosen Constitution drawings with the wheel's painted support
    removed, saved as the next try and recorded in chosen.json (and in relit.json for the relit night). The drawing
    service redraws inside the traced mask only; its result is pasted back inside that mask (feathered 1 px), so the
    rest of the drawing stays exactly as chosen."""
    ch = NEW / "chosen.json"
    chosen = json.loads(ch.read_text()) if ch.exists() else {}
    rl = NEW / "relit.json"
    relit = json.loads(rl.read_text()) if rl.exists() else []
    for when in ("day", "night"):
        raw_p, sent_p = pick("constitution", when)
        spec = FRAME.get(raw_p.stem)
        if spec is None:
            print("no traced support for", raw_p.name, "(already removed?)")
            continue
        raw = np.asarray(Image.open(raw_p).convert("RGB"))
        m = np.zeros(raw.shape[:2], np.uint8)
        for leg in spec["legs"]:
            cv2.fillPoly(m, [np.array(leg, np.int32)], 255)
        hx, hy, hr = spec["hub"]
        cv2.circle(m, (int(hx), int(hy)), int(hr), 255, -1)
        g = spec["grow"]
        m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * g + 1, 2 * g + 1)))
        wide = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)))   # room for the service to blend
        alpha = np.where(wide > 0, 0, 255).astype(np.uint8)
        mask = Image.fromarray(np.dstack([raw, alpha]), "RGBA")
        light = LIGHT[when].split(":")[0] + "."
        n = len(list(NEW.glob(f"constitution_{when}_raw*.png")))
        cached = NEW / f"constitution_{when}_unframe{n}.png"
        if cached.exists():   # the paid edit is kept, so the paste can be redone for free
            ed = np.asarray(Image.open(cached).convert("RGB"))
        else:
            if spent() + 0.08 > cap:
                sys.exit(f"cap reached: ${spent():.3f} of ${cap:.2f} spent")
            ed = np.asarray(call(Image.fromarray(raw), f"{UNFRAME} {light}", f"constitution_{when}_unframe{n}", mask).convert("RGB")
                            .resize(raw.shape[1::-1], Image.LANCZOS))
            Image.fromarray(ed).save(cached)
        # paste the whole hull of the support: the back legs show between the front ones, and the edit removed them
        hull = cv2.convexHull(np.argwhere(m > 0)[:, ::-1].astype(np.int32))
        m = cv2.fillPoly(m.copy(), [hull], 255)
        soft = cv2.GaussianBlur(cv2.dilate(m, np.ones((5, 5), np.uint8)).astype(np.float32) / 255, (0, 0), 1.0)[..., None]
        out = (ed * soft + raw * (1 - soft)).astype(np.uint8)
        Image.fromarray(out).save(NEW / f"constitution_{when}_raw{n}.png")
        Image.open(sent_p).save(NEW / f"constitution_{when}_sent{n}.png")
        chosen[f"constitution_{when}"] = n
        if raw_p.stem in relit:
            relit.append(f"constitution_{when}_raw{n}")
        print(raw_p.name, "->", f"constitution_{when}_raw{n}.png", f"({int((m > 0).sum())} px redrawn)")
    ch.write_text(json.dumps(chosen, indent=1))
    rl.write_text(json.dumps(relit))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "unframe":
        unframe(float(sys.argv[2]))
        sys.exit()
    if cmd == "draw":
        rest = [a for a in sys.argv[4:] if not a.startswith("--")]
        draw(sys.argv[2], float(sys.argv[3]), rest[0].split(",") if rest else list(SITES), "--relight" in sys.argv)
    elif cmd == "composite":
        composite()
    else:
        sys.exit(__doc__)
