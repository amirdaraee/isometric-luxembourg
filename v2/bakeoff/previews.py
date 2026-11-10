"""The bake-off's previews: the same fixed views of every registered method, as screenshots of the real viewer, and
one comparison sheet (v2/docs/img/test_<method>_<view>.jpg, test_bakeoff_compare.jpg; each under 1 MB).

    python -m v2.view test --bakeoff --port 5175 &        # the bake-off server
    python -m v2.bakeoff previews --url http://localhost:5175/

The views are v2/web/src/bakeoff.ts's (the same list the bake-off page offers), read from that file.
"""
from __future__ import annotations

import json
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from v2.config import V2

WEB = V2 / "web"
IMG = V2 / "docs" / "img"
# view id -> file name part; the brief's six, and the pilot views where C has paintings
NAMES = {"grund-day": "grund_day", "grund-golden": "grund_golden_hour", "grund-night": "grund_night", "bock": "bock",
         "facade": "facades", "abbey": "abbey", "c-pilot": "pilot_windows", "c-pilot-wide": "pilot_windows_wide",
         "c4-1": "c4_trial_1", "c4-2": "c4_trial_2", "c4-3": "c4_trial_3", "c4-4": "c4_trial_4"}
LABEL = {"a": "A: all code", "b": "B: code + AI", "c": "C: code + AI-painted buildings",
         "c4": "C4: facades painted front-on"}
BRIEF = ("grund-day", "grund-golden", "grund-night", "bock", "abbey", "facade")      # the comparison sheet's rows
# which methods are shot at which views: the pilot's windows for C, the trial's buildings for C4 (A beside each)
ONLY = {"c": ("c-pilot", "c-pilot-wide"), "c4": ("c4-1", "c4-2", "c4-3", "c4-4")}


def views() -> list:
    src = (WEB / "src" / "bakeoff.ts").read_text()
    out = []
    for m in re.finditer(r'\{ id: "([^"]+)", label: "([^"]+)", x: (\d+), y: (\d+), z: ([\d.]+), hour: ([\d.]+) \}', src):
        out.append({"id": m.group(1), "label": m.group(2), "x": int(m.group(3)), "y": int(m.group(4)),
                    "z": float(m.group(5)), "hour": float(m.group(6))})
    return out


def jpeg(src: Path, dst: Path, max_bytes=950_000, max_px=1600):
    im = Image.open(src).convert("RGB")
    if max(im.size) > max_px:
        k = max_px / max(im.size)
        im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    for q in (88, 84, 80, 74, 68, 60, 50):
        im.save(dst, quality=q, optimize=True)
        if dst.stat().st_size <= max_bytes:
            break
    return dst


def shoot(url: str, methods=None, size=(1400, 875), only=None, tmp: Path | None = None) -> dict:
    idx = json.loads(urllib.request.urlopen(url.rstrip("/") + "/bake/index.json", timeout=30).read())
    methods = [m for m in (methods or ["a", "b", "c", "c4"]) if idx.get(m, {}).get("release")]
    tmp = tmp or (IMG / "_tmp")
    tmp.mkdir(parents=True, exist_ok=True)
    made = {}
    for v in views():
        if v["id"] not in NAMES or (only and v["id"] not in only):
            continue
        for m in methods:
            if m in ONLY and v["id"] not in ONLY[m]:
                continue
            if v["id"].startswith("c4-") and m in ("b", "c"):
                continue
            q = urllib.parse.urlencode({"data": f"/bake/{m}/", "x": v["x"], "y": v["y"], "z": v["z"], "hour": v["hour"],
                                        "date": "2026-06-24"}) + "&nosim&noui"
            png = tmp / f"{m}_{v['id']}.png"
            r = subprocess.run(["node", "scripts/shot.mjs", q, str(png), str(size[0]), str(size[1])], cwd=WEB,
                               capture_output=True, text=True, timeout=600, env={**__import__("os").environ, "V2_URL": url})
            if r.returncode:
                raise RuntimeError(f"shot {m} {v['id']}: {(r.stderr or r.stdout)[-800:]}")
            dst = jpeg(png, IMG / f"test_{m}_{NAMES[v['id']]}.jpg")
            made[(m, v["id"])] = (png, dst, v["label"])
            print(dst.name, dst.stat().st_size // 1024, "KB", flush=True)
    return {"methods": methods, "made": made, "tmp": tmp}


def sheet(res: dict, dst: Path, cell=(700, 438), notes: dict | None = None):
    """One row per view, one column per method."""
    methods = res["methods"]
    vids = [v["id"] for v in views() if any((m, v["id"]) in res["made"] for m in methods)]
    W, H = cell
    pad = 26
    out = Image.new("RGB", (W * len(methods), (H + pad) * len(vids) + 30), (247, 241, 228))
    d = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
    except OSError:
        font = ImageFont.load_default()
    for j, m in enumerate(methods):
        d.text((j * W + 8, 6), LABEL[m] + (f" ({notes[m]})" if notes and notes.get(m) else ""), fill=(46, 40, 36), font=font)
    for i, vid in enumerate(vids):
        y = 30 + i * (H + pad)
        for j, m in enumerate(methods):
            if (m, vid) not in res["made"]:
                continue
            png, _, label = res["made"][(m, vid)]
            im = Image.open(png).convert("RGB").resize((W, H), Image.LANCZOS)
            out.paste(im, (j * W, y + pad))
            if j == 0:
                d.text((8, y + 4), label, fill=(46, 40, 36), font=font)
    tmp = dst.with_suffix(".png")
    out.save(tmp)
    jpeg(tmp, dst, max_px=2400)
    tmp.unlink()
    return dst


def before_after(before: Path, res: dict, dst: Path, cell=(700, 438)):
    """The code lighting before and after (owner, 10 Nov 2026): method A's golden hour and night at the Grund view,
    the earlier previews on the left, this build's on the right."""
    W, H = cell
    pad = 26
    rows = [("grund-golden", "test_a_grund_golden_hour.jpg", "Grund, golden hour (21:18, 24 June)"),
            ("grund-night", "test_a_grund_night.jpg", "Grund, night (23:15)")]
    out = Image.new("RGB", (W * 2, (H + pad) * len(rows) + 30), (247, 241, 228))
    d = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
    except OSError:
        font = ImageFont.load_default()
    d.text((8, 6), "Before (9 Nov)", fill=(46, 40, 36), font=font)
    d.text((W + 8, 6), "After (10 Nov): the same art, only the viewer's light changed", fill=(46, 40, 36), font=font)
    for i, (vid, old, label) in enumerate(rows):
        y = 30 + i * (H + pad)
        d.text((8, y + 4), label, fill=(46, 40, 36), font=font)
        out.paste(Image.open(before / old).convert("RGB").resize((W, H), Image.LANCZOS), (0, y + pad))
        out.paste(Image.open(res["made"][("a", vid)][0]).convert("RGB").resize((W, H), Image.LANCZOS), (W, y + pad))
    tmp = dst.with_suffix(".png")
    out.save(tmp)
    jpeg(tmp, dst, max_px=2400)
    tmp.unlink()
    return dst
