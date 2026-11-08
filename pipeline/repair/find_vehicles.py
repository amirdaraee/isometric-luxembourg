"""Find vehicles painted into the finished day art (PLAN_NEXT item 4), so they can be reviewed and removed.

Two finders, joined:
  blobs  the make_hint.py car rules run on the painted art instead of the render, with lower thresholds, inside a
         wider mask: roads (1.3 x their lane width), parking, service ways, and any ground within 15 m of a road,
         all only where the render's kind pass shows ground or a bridge deck (not roofs). Needs OpenCV.
  owl    an open-vocabulary detector (OWLv2, through transformers, on the Mac's GPU) on overlapping 256 px crops
         (enlarged to the model's 960 px, so a painted car is about 55 px: at 512 px crops it missed whole rows),
         queries "car", "van", "bus", "truck", "train", "person"; boxes of 3 to 14 m kept. Needs torch and
         transformers (any Python that has them; no OpenCV needed).
  join   joins both into data/work/repair/vehicles_<block>.json (boxes in map px, score, source, in_mask) and a
         contact sheet per block, sorted by score (the low end is worth a look too: dark cars in shadow).

Usage: find_vehicles.py blobs <block|all> | owl <block|all> | join <block|all> [--canvas name]
The detector needs torch and transformers; without them in the pipeline venv:
  uv run --offline --no-project --with torch --with transformers --with pillow --with numpy python find_vehicles.py owl ...
The canvas is the block's day canvas from city_blocks.py state (default), or --canvas <file name in the block
folder>, e.g. a repaired canvas for the second pass.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "data" / "work"
CITY = WORK / "city"
OUT = WORK / "repair"
Image.MAX_IMAGE_PIXELS = None
LANES_M = {"motorway": 14, "trunk": 12, "primary": 10, "secondary": 9, "tertiary": 8, "residential": 6.5,
           "unclassified": 6, "living_street": 5, "service": 4.5, "motorway_link": 6, "trunk_link": 6,
           "primary_link": 6, "secondary_link": 6, "tertiary_link": 6, "pedestrian": 6}
QUERIES = ["a car", "a parked car", "a van", "a bus", "a truck", "a train", "a person"]
MIN_M, MAX_M = 3.0, 14.0
AUTO = 0.14       # detector score from which a road vehicle counts as found without a person's review
AUTO_ROAD = 0.08  # ... or from this score when the box is car-sized (under 7 m) and on a road or car park: side-on
                  # cars packed in a row along a street score low but are nearly always real
MAP_MPP = 0.25


def state():
    return json.loads((CITY / "blocks.json").read_text())


def blocks(arg):
    st = state()
    ids = [b["id"] for b in st["blocks"] if b["id"] in st["done"]]
    return ids if arg == "all" else arg.split(",")


def canvas_path(bid, name=None):
    st = state()
    return CITY / bid / name if name else Path(st["done"][bid])


def block(bid):
    return next(b for b in state()["blocks"] if b["id"] == bid)


def road_mask(b, W, H, k):
    """Roads, parking and service ways of the block, at canvas scale (k canvas px per map px)."""
    L = json.loads((ROOT / "web/public/data/lines.json").read_text())
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    for r in L["roads"]:
        w = LANES_M.get(r["k"])
        if not w or r.get("t"):
            continue
        q = [((r["p"][i] - b["x0"]) * k, (r["p"][i + 1] - b["y0"]) * k) for i in range(0, len(r["p"]), 2)]
        d.line(q, fill=255, width=max(int(w * 1.3 / MAP_MPP * k), 2), joint="curve")
    for pk in L.get("parking", []):
        q = [((pk["p"][i] - b["x0"]) * k, (pk["p"][i + 1] - b["y0"]) * k) for i in range(0, len(pk["p"]), 2)]
        if len(q) > 2:
            d.polygon(q, fill=255)
    return np.asarray(m) > 0


def find_blobs(bid, canvas=None):
    import cv2
    b = block(bid)
    im = np.asarray(Image.open(canvas_path(bid, canvas)).convert("RGB"))
    H, W = im.shape[:2]
    k = W / b["w"]
    roads = road_mask(b, W, H, k)
    kind = CITY / bid / "kind.png"
    if not kind.exists():
        kind = OUT / f"kind_{bid}.png"   # b00, the old-town showcase: a copy of pipeline/gpu_train/tiles/kind_showcase.png
    kv = np.asarray(Image.open(kind).convert("L").resize((W, H), Image.NEAREST)) if kind.exists() else None
    ground = ((kv > 200) | (np.abs(kv.astype(int) - 128) < 8)) if kv is not None else np.ones((H, W), bool)  # ground, bridges
    near = cv2.dilate(roads.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(2 * 15 / MAP_MPP * k) | 1,) * 2)) > 0
    a = im.astype(int)
    veg = (a[..., 1] > a[..., 0] + 6) & (a[..., 1] >= a[..., 2])
    veg = cv2.dilate(veg.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    area = (roads | near) & ground & ~veg
    med = cv2.medianBlur(im, 31)
    diff = np.abs(a - med.astype(int)).sum(2)
    cand = ((diff > 45) & area).astype(np.uint8)
    cand = cv2.morphologyEx(cand, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(cand)
    out = []
    s = k / 0.853   # the make_hint rules were tuned at render scale; the canvas is ~0.85 of it
    pk = road_mask(b, W, H, k)
    for i in range(1, n):
        x, y, w, h, ar = st[i]
        fill = ar / max(w * h, 1)
        aspect = max(w, h) / max(min(w, h), 1)
        one_car = 18 * s * s <= ar <= 700 * s * s and max(w, h) <= 48 * s and aspect <= 3.5 and fill >= 0.35
        row = 25 * s * s <= ar <= 6000 * s * s and min(w, h) <= 40 * s and fill >= 0.3 and pk[lab == i].mean() > 0.5 and not one_car
        if not (one_car or row):
            continue
        contrast = float(diff[lab == i].mean())
        score = min(1.0, contrast / 160) * (0.6 + 0.4 * fill)
        out.append({"x": b["x0"] + x / k, "y": b["y0"] + y / k, "w": w / k, "h": h / k, "score": round(score, 3),
                    "source": "blobs-row" if row else "blobs", "in_mask": True})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"blobs_{bid}{'_' + Path(canvas).stem if canvas else ''}.json").write_text(json.dumps(out))
    print(bid, "blobs:", len(out))


def find_owl(bid, canvas=None, crop=256, overlap=40, thr=0.07, batch=8):
    import torch
    from transformers import Owlv2ForObjectDetection, Owlv2Processor
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    name = "google/owlv2-base-patch16-ensemble"
    proc = Owlv2Processor.from_pretrained(name)
    model = Owlv2ForObjectDetection.from_pretrained(name).to(dev).eval()
    text = proc.tokenizer(QUERIES, padding="max_length", return_tensors="pt").to(dev)
    S = 960   # the model's input size; crops are resized straight to it (the processor's own resize is slow)
    mean = torch.tensor([0.48145466, 0.4578275, 0.40821073], device=dev).view(1, 3, 1, 1)
    std = torch.tensor([0.26862954, 0.26130258, 0.27577711], device=dev).view(1, 3, 1, 1)
    b = block(bid)
    im = Image.open(canvas_path(bid, canvas)).convert("RGB")
    W, H = im.size
    k = W / b["w"]
    a = np.asarray(im)
    jobs = []
    step = crop - overlap
    for y0 in range(0, H - overlap, step):
        for x0 in range(0, W - overlap, step):
            c = a[y0:y0 + crop, x0:x0 + crop]
            if c.shape[0] < crop or c.shape[1] < crop:
                c = np.pad(c, ((0, crop - c.shape[0]), (0, crop - c.shape[1]), (0, 0)))
            if (np.abs(c.astype(int) - (16, 24, 40)).sum(2) < 20).mean() > 0.9:
                continue   # outside the map
            jobs.append((x0, y0, c))
    out = []
    sc = S / crop
    for i in range(0, len(jobs), batch):
        part = jobs[i:i + batch]
        px = np.stack([np.asarray(Image.fromarray(c).resize((S, S), Image.BICUBIC)) for _, _, c in part])
        pv = (torch.from_numpy(px).to(dev).permute(0, 3, 1, 2).float() / 255 - mean) / std
        with torch.no_grad():
            o = model(input_ids=text["input_ids"].repeat(len(part), 1), attention_mask=text["attention_mask"].repeat(len(part), 1),
                      pixel_values=pv)
        post = getattr(proc, "post_process_object_detection", None) or proc.post_process_grounded_object_detection  # transformers 5
        res = post(o, threshold=thr, target_sizes=torch.tensor([[S, S]] * len(part)))
        for (x0, y0, _), r in zip(part, res):
            for box, s_, lb in zip(r["boxes"].cpu().numpy(), r["scores"].cpu().numpy(), r["labels"].cpu().numpy()):
                bx0, by0, bx1, by1 = (box / sc).tolist()
                wm, hm = (bx1 - bx0) / k * MAP_MPP, (by1 - by0) / k * MAP_MPP
                if not (MIN_M <= max(wm, hm) <= MAX_M):
                    continue
                out.append({"x": b["x0"] + (x0 + bx0) / k, "y": b["y0"] + (y0 + by0) / k, "w": (bx1 - bx0) / k, "h": (by1 - by0) / k,
                            "score": round(float(s_), 3), "source": "owl:" + QUERIES[lb].split()[-1]})
        if i % (batch * 10) == 0:
            print(bid, f"{i}/{len(jobs)} crops", len(out), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"owl_{bid}{'_' + Path(canvas).stem if canvas else ''}.json").write_text(json.dumps(out))
    print(bid, "owl:", len(out))


def iou(a, b):
    x0, y0 = max(a["x"], b["x"]), max(a["y"], b["y"])
    x1, y1 = min(a["x"] + a["w"], b["x"] + b["w"]), min(a["y"] + a["h"], b["y"] + b["h"])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    return inter / (a["w"] * a["h"] + b["w"] * b["h"] - inter + 1e-6)


def join(bid, canvas=None):
    sfx = "_" + Path(canvas).stem if canvas else ""
    bl = json.loads((OUT / f"blobs_{bid}{sfx}.json").read_text()) if (OUT / f"blobs_{bid}{sfx}.json").exists() else []
    ow = json.loads((OUT / f"owl_{bid}{sfx}.json").read_text()) if (OUT / f"owl_{bid}{sfx}.json").exists() else []
    ow.sort(key=lambda d: -d["score"])
    kept = []
    for d in ow:   # non-maximum suppression across queries and crop overlaps
        if all(iou(d, e) < 0.4 for e in kept):
            kept.append(d)
    joined = []
    for d in bl + kept:
        hit = next((e for e in joined if iou(d, e) > 0.25), None)
        if hit:
            hit["score"] = round(min(1.0, max(hit["score"], d["score"]) + 0.2), 3)
            hit["source"] = "+".join(sorted(set(hit["source"].split("+")) | {d["source"]}))
            x0, y0 = min(hit["x"], d["x"]), min(hit["y"], d["y"])
            x1, y1 = max(hit["x"] + hit["w"], d["x"] + d["w"]), max(hit["y"] + hit["h"], d["y"] + d["h"])
            hit.update(x=x0, y=y0, w=x1 - x0, h=y1 - y0)
        else:
            joined.append(dict(d))
    b = block(bid)
    kr = 0.25   # road mask at a quarter of map scale is enough to tell whether a box sits on a road
    roads = road_mask(b, int(b["w"] * kr), int(b["h"] * kr), kr)
    import cv2
    roads = cv2.dilate(roads.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0   # + 2 m
    kind = CITY / bid / "kind.png"
    kind = kind if kind.exists() else OUT / f"kind_{bid}.png"
    kv = np.asarray(Image.open(kind).convert("L").resize(roads.shape[::-1], Image.NEAREST)) if kind.exists() else None
    for d in joined:
        cx, cy = int((d["x"] + d["w"] / 2 - b["x0"]) * kr), int((d["y"] + d["h"] / 2 - b["y0"]) * kr)
        inside = 0 <= cx < roads.shape[1] and 0 <= cy < roads.shape[0]
        d["on_road"] = bool(inside and roads[cy, cx])
        # the render's kind pass: ground (white) or a bridge deck (mid grey); a box on a roof or wall is no car
        d["on_ground"] = bool(kv is None or (inside and (kv[cy, cx] > 200 or abs(int(kv[cy, cx]) - 128) < 8)))
    for d in joined:
        # Review rule (from the b00 contact sheets): the detector's road vehicles at 0.14 and above are nearly all
        # painted vehicles; its "train" boxes are mostly tracks and bridges, and the blob rule alone mostly finds
        # dormers and markings, so those wait for a person's decision (decisions.json).
        road_vehicle = any(s.startswith("owl:") and s not in ("owl:train", "owl:person") for s in d["source"].split("+"))
        car_sized = max(d["w"], d["h"]) * MAP_MPP <= 7
        big = any(s in ("owl:bus", "owl:truck") for s in d["source"].split("+"))   # up to 14 m; a "car" box that
        d["auto"] = road_vehicle and d["on_ground"] and (big or car_sized) and (                      # long is a whole row: its
            d["score"] >= AUTO or (d["score"] >= AUTO_ROAD and d["on_road"] and car_sized))   # cars get boxes of their own
    joined.sort(key=lambda d: -d["score"])
    for i, d in enumerate(joined):
        d["id"] = f"{bid}-{i:04d}"
        for kk in ("x", "y", "w", "h"):
            d[kk] = round(d[kk], 1)
    (OUT / f"vehicles_{bid}{sfx}.json").write_text(json.dumps(joined, indent=0))
    # the sheet shows the detector's vehicles first, then rows in car parks, then the rest, each by score
    sheet(bid, sorted(joined, key=lambda d: (not d["auto"], "blobs-row" not in d["source"], -d["score"])), canvas)
    print(bid, "joined:", len(joined), f"(blobs {len(bl)}, owl {len(kept)})")


def sheet(bid, cands, canvas=None, n=400, cell=96):
    """Contact sheet: each candidate's crop (3x its box, at least 24 m) with its box, id and score."""
    b = block(bid)
    im = Image.open(canvas_path(bid, canvas)).convert("RGB")
    k = im.width / b["w"]
    cols = 16
    cs = cands[:n]
    S = Image.new("RGB", (cols * cell, ((len(cs) + cols - 1) // cols) * (cell + 12)), (20, 20, 24))
    d = ImageDraw.Draw(S)
    crops = OUT / "crops" / bid
    crops.mkdir(parents=True, exist_ok=True)
    for i, c in enumerate(cs):
        cx, cy = (c["x"] + c["w"] / 2 - b["x0"]) * k, (c["y"] + c["h"] / 2 - b["y0"]) * k
        half = max(c["w"], c["h"], 96 / 3) * k * 1.5
        cr = im.crop((int(cx - half), int(cy - half), int(cx + half), int(cy + half)))
        dd = ImageDraw.Draw(cr)
        bx0, by0 = (c["x"] - b["x0"]) * k - (cx - half), (c["y"] - b["y0"]) * k - (cy - half)
        dd.rectangle((bx0, by0, bx0 + c["w"] * k, by0 + c["h"] * k), outline=(255, 0, 255))
        cr = cr.resize((cell, cell), Image.LANCZOS)
        cr.save(crops / f"{c['id']}.jpg", quality=85)
        x, y = (i % cols) * cell, (i // cols) * (cell + 12)
        S.paste(cr, (x, y))
        d.text((x + 2, y + cell), f"{c['id'][-4:]} {c['score']:.2f} {c['source'][:6]}", fill=(220, 220, 220))
    S.save(OUT / f"sheet_{bid}{'_' + Path(canvas).stem if canvas else ''}.jpg", quality=85)


if __name__ == "__main__":
    cmd, arg = sys.argv[1], sys.argv[2]
    cv = sys.argv[sys.argv.index("--canvas") + 1] if "--canvas" in sys.argv else None
    for bid in blocks(arg):
        {"blobs": find_blobs, "owl": find_owl, "join": join}[cmd](bid, cv)
