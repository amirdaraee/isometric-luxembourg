"""Gate G1 report: every phase 1 check's result, the speed numbers and the previews of the test area, published into
v2/docs (results/g1_<area>.json, img/<area>_*.jpg) for the owner's review in the pull request.

Previews are screenshots of the viewer itself (the code lighting is what is shown), JPEGs under 1 MB each.
"""
from __future__ import annotations

import io
import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from v2.config import V2

WEB = V2 / "web"


def jpeg(src: Path, dst: Path, max_px=1600, quality=86):
    im = Image.open(src).convert("RGB")
    im.thumbnail((max_px, max_px), Image.LANCZOS)
    q = quality
    while True:
        im.save(dst, "JPEG", quality=q, optimize=True)
        if dst.stat().st_size < 950_000 or q <= 40:
            return
        q -= 8


def grid(srcs, labels, dst: Path, cols=3, cell=(800, 500)):
    W, H = cell
    rows = (len(srcs) + cols - 1) // cols
    out = Image.new("RGB", (cols * W, rows * (H + 28)), (239, 232, 220))
    d = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
    except OSError:
        font = ImageFont.load_default()
    for i, (s, lab) in enumerate(zip(srcs, labels)):
        im = Image.open(s).convert("RGB")
        im = im.resize((W, int(im.height * W / im.width)), Image.LANCZOS).crop((0, 0, W, H))
        x, y = (i % cols) * W, (i // cols) * (H + 28)
        out.paste(im, (x, y + 28))
        d.text((x + 8, y + 4), lab, fill=(46, 40, 36), font=font)
    buf = dst.with_suffix(".png")
    out.save(buf)
    jpeg(buf, dst, max_px=2400, quality=84)
    buf.unlink()


def g1(ctx):
    from v2.checks.g1_checks import viewer_server
    area = ctx.area
    rel = ctx.dep("release")
    checks = {}
    passed = True
    for name, folder in ctx.deps.items():
        m = json.loads((folder / "manifest.json").read_text())
        if m["kind"] == "check":
            s = m["summary"] or {}
            checks[name] = {"passed": s.get("passed"), "entries": s.get("entries", [])}
            passed &= bool(s.get("passed"))
    speed = next((e["value"] for e in checks.get("check_viewer", {}).get("entries", []) if e["id"] == "C2"), None)
    # previews from the viewer
    shots = ctx.out / "shots"
    shots.mkdir()
    with viewer_server(rel) as base:
        r = subprocess.run(["node", str(WEB / "scripts" / "previews.mjs"), base, str(shots)], cwd=WEB, capture_output=True,
                           text=True, timeout=1800)
    if r.returncode:
        raise RuntimeError("previews failed: " + (r.stderr or r.stdout)[-3000:])
    img = V2 / "docs" / "img"
    img.mkdir(parents=True, exist_ok=True)
    published = []
    for n in ("test_day_1300", "test_golden_hour", "test_night", "test_night_grund", "test_shadows_1000", "test_shadows_1600",
              "test_portal_vehicles", "test_viaduct_vehicles"):
        dst = img / f"{n.replace('test_', area + '_g1_')}.jpg"
        jpeg(shots / f"{n}.png", dst)
        published.append(dst.name)
    pair = img / f"{area}_g1_shadows_pair.jpg"
    grid([shots / "test_shadows_1000.png", shots / "test_shadows_1600.png"], ["10:00", "16:00 (same view)"], pair, cols=2,
         cell=(1000, 625))
    published.append(pair.name)
    tog = img / f"{area}_g1_layer_toggles.jpg"
    grid([shots / f"toggle_{k}.png" for k in ("all", "nolight", "nobuildings", "notrees", "base", "layers")],
         ["all layers, 15:00", "light off (the layers' own colour)", "buildings off (no building shadows)", "trees off",
          "only ground, relief and water", "which layer is nearest (debug)"], tog)
    published.append(tog.name)
    meta = json.loads((shots / "previews.json").read_text())
    res = {"area": area, "gate": "G1", "passed": passed, "checks": checks, "speed": speed, "previews": published,
           "preview_views": meta, "release": str(rel)}
    out = V2 / "docs" / "results" / f"g1_{area}.json"
    out.write_text(json.dumps(res, indent=1, default=str))
    ctx.write_json("g1.json", res, indent=1, default=str)
    return {"passed": passed, "checks": {k: v["passed"] for k, v in checks.items()}, "previews": published}
