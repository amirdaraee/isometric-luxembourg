"""Before/after sheets of two releases at fixed views: python -m v2.build.sheets <before release> <after release>

Each release folder is served by the viewer in turn and shot headless at the same views and hours (day, golden hour,
night), so the code lighting is what is shown. One sheet per place goes to v2/docs/img/<area>_phase3_<place>.jpg
(each under 1 MB): the top row is the first release, the bottom row the second.

The shots of a release are kept in --tmp (default: a folder beside the sheets, removed at the end), so the "before"
row can be shot once (--only before) and the "after" row again after each build (--only after).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from v2.config import V2

WEB = V2 / "web"
IMG = V2 / "docs" / "img"
# place -> (x, y, zoom): the bake-off's views (v2/web/src/bakeoff.ts)
PLACES = {"grund": (62648, 34244, 0.5), "bock": (63327, 33697, 0.75), "abbey": (63135, 34267, 1.0),
          "facade": (62281, 34323, 2.0)}
HOURS = (("day, 13:00", 13.0), ("golden hour, 21:18", 21.3), ("night, 23:15", 23.25))
DATE = "2026-06-24"
SIZE = (1000, 625)


def shoot(release: Path, out: Path, places=PLACES):
    from v2.checks.g1_checks import viewer_server
    out.mkdir(parents=True, exist_ok=True)
    with viewer_server(release) as url:
        for place, (x, y, z) in places.items():
            for _, hour in HOURS:
                q = urllib.parse.urlencode({"x": x, "y": y, "z": z, "hour": hour, "date": DATE}) + "&nosim&noui"
                png = out / f"{place}_{hour}.png"
                r = subprocess.run(["node", "scripts/shot.mjs", q, str(png), str(SIZE[0]), str(SIZE[1])], cwd=WEB,
                                   capture_output=True, text=True, timeout=600, env={**__import__("os").environ, "V2_URL": url})
                if r.returncode:
                    raise RuntimeError(f"shot {place} {hour}: {(r.stderr or r.stdout)[-800:]}")
                print(png.name, flush=True)


def sheet(tmp: Path, place: str, dst: Path, labels=("before (phase 2)", "after (phase 3)")):
    W, H = SIZE
    bar = 30
    paper = Image.open(tmp / "before" / f"{place}_{HOURS[0][1]}.png").convert("RGB").getpixel((0, 0))
    out = Image.new("RGB", (W * len(HOURS), (H + bar) * 2), paper)
    d = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
    except OSError:
        font = ImageFont.load_default()
    for r, (row, lab) in enumerate(zip(("before", "after"), labels)):
        for c, (hl, hour) in enumerate(HOURS):
            im = Image.open(tmp / row / f"{place}_{hour}.png").convert("RGB").resize((W, H), Image.LANCZOS)
            out.paste(im, (c * W, r * (H + bar) + bar))
            d.rectangle([c * W, r * (H + bar), (c + 1) * W, r * (H + bar) + bar], fill="white")
            d.text((c * W + 8, r * (H + bar) + 4), f"{lab}: {hl}", fill="black", font=font)
    out.thumbnail((2400, 2400), Image.LANCZOS)
    for q in (86, 80, 74, 68, 60, 52, 44):
        out.save(dst, "JPEG", quality=q, optimize=True)
        if dst.stat().st_size < 950_000:
            break
    print(dst.name, dst.stat().st_size // 1024, "KB", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m v2.build.sheets", description=__doc__)
    ap.add_argument("before", type=Path)
    ap.add_argument("after", type=Path)
    ap.add_argument("--area", default="test")
    ap.add_argument("--tmp", type=Path, default=IMG / "_sheets")
    ap.add_argument("--only", choices=("before", "after"), help="shoot one row only (no sheets unless both exist)")
    ap.add_argument("--keep", action="store_true", help="keep the shots")
    a = ap.parse_args(argv)
    for row, rel in (("before", a.before), ("after", a.after)):
        if a.only in (None, row):
            shoot(rel, a.tmp / row)
    if all((a.tmp / row / f"{p}_{HOURS[0][1]}.png").exists() for row in ("before", "after") for p in PLACES):
        for place in PLACES:
            sheet(a.tmp, place, IMG / f"{a.area}_phase3_{place}.jpg")
    if not a.keep:
        shutil.rmtree(a.tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
