"""Draw the transit shapes over the painted art, to check that trains and trams follow the painted tracks.

Green: the shapes in transit.json (matched onto the OSM rail lines by build_transit.py). Red: the raw GTFS shapes
through the old projection (terrain heights), for comparison. Thin grey: every lines.json rail way. Tunnel stretches
of the matched shapes are drawn dashed.

Usage: transit_check.py [--out DIR] [--size PX] [name=x,y ...]
  name=x,y   a crop centred on map px (x, y); by default the stations and viaducts of PLAN_NEXT.md item 10.
Writes <DIR>/transit_<name>.jpg (default DIR data/work/transit_check).
"""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from common import PILOT_LONLAT, ROOT, WORK, lonlat_to_en

VIEWS = {"gare": (5110, 8172), "pfaffenthal": (10816, 5131), "pulvermuehle": (8625, 7575), "cents_hamm": (16330, 8986)}
TILE = 512


def crop(tiles, x0, y0, w, h):
    """The painted art (summer day, full resolution) for a map px box."""
    im = Image.new("RGB", (w, h), (16, 24, 40))
    for ty in range(y0 // TILE, (y0 + h - 1) // TILE + 1):
        for tx in range(x0 // TILE, (x0 + w - 1) // TILE + 1):
            f = tiles / f"{tx}_{ty}.webp"
            if f.exists():
                im.paste(Image.open(f).convert("RGB"), (tx * TILE - x0, ty * TILE - y0))
    return im


def gtfs_shapes(data):
    """The raw GTFS shapes of transit.json's trips, through the old projection, or [] without the data."""
    try:
        import build_transit as bt
        lines = json.loads((data / "lines.json").read_text())
        ways = bt.rail_ways(lines)
        old = bt.TerrainPx(ways)
    except (FileNotFoundError, OSError, ImportError) as e:
        print("no GTFS comparison:", e)
        return []
    W0, S0, E0, N0 = PILOT_LONLAT
    shapes = defaultdict(list)
    for r in bt.gtfs_rows(bt.GTFS, "shapes.txt"):
        shapes[r["shape_id"]].append((int(r["shape_pt_sequence"]), float(r["shape_pt_lon"]), float(r["shape_pt_lat"])))
    rails = {r["route_id"] for r in bt.gtfs_rows(bt.GTFS, "routes.txt") if r["route_type"] in ("0", "2")}
    used = {t["shape_id"] for t in bt.gtfs_rows(bt.GTFS, "trips.txt") if t["route_id"] in rails}
    out = []
    for sid in used:
        p = sorted(shapes.get(sid, []))
        ll = [(lon, lat) for _, lon, lat in p if W0 - 0.01 <= lon <= E0 + 0.01 and S0 - 0.01 <= lat <= N0 + 0.01]
        if len(ll) >= 2:
            out.append(old.px(np.array([lonlat_to_en(*q) for q in ll])))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("views", nargs="*", help="name=x,y")
    ap.add_argument("--out", type=Path, default=WORK / "transit_check")
    ap.add_argument("--size", type=int, default=1400)
    ap.add_argument("--data", type=Path, default=ROOT / "web/public/data")
    ap.add_argument("--tiles", type=Path, default=ROOT / "web/public/tiles/map_files/15")
    a = ap.parse_args()
    views = dict(VIEWS)
    if a.views:
        views = {v.split("=")[0]: tuple(map(int, v.split("=")[1].split(","))) for v in a.views}
    lines = json.loads((a.data / "lines.json").read_text())
    tr = json.loads((a.data / "transit.json").read_text())
    tunnel = {w["id"]: bool(w.get("t")) for w in lines["rail"]}
    raw = gtfs_shapes(a.data)
    a.out.mkdir(parents=True, exist_ok=True)
    S = a.size
    for name, (cx, cy) in views.items():
        x0, y0 = cx - S // 2, cy - S // 2
        im = crop(a.tiles, x0, y0, S, S)
        ov = Image.new("RGBA", im.size)
        d = ImageDraw.Draw(ov)
        loc = lambda p: [(p[i] - x0, p[i + 1] - y0) for i in range(0, len(p), 2)]
        for w in lines["rail"]:
            d.line(loc(w["p"]), fill=(255, 255, 255, 170), width=2)
        for p in raw:
            d.line([(x - x0, y - y0) for x, y in p], fill=(255, 40, 40, 200), width=3)
        for p, runs in zip(tr["shapes"], tr.get("runs") or [[]] * len(tr["shapes"])):
            q = loc(p)
            d.line(q, fill=(40, 230, 90, 230), width=3)
            if runs:   # tunnel stretches: a dark dash every 12 px along the shape (by its px length)
                cum = np.r_[0, np.cumsum([math.dist(u, v) for u, v in zip(q[:-1], q[1:])])]
                s0 = 0.0
                for wid, sa, sb in runs:
                    L = abs(sb - sa)
                    if tunnel.get(wid):
                        for s in np.arange(s0, s0 + L, 12):
                            i = min(int(np.searchsorted(cum, s, side="right")) - 1, len(q) - 2)
                            f = (s - cum[i]) / max(cum[i + 1] - cum[i], 1e-9)
                            x = q[i][0] + (q[i + 1][0] - q[i][0]) * f
                            y = q[i][1] + (q[i + 1][1] - q[i][1]) * f
                            d.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(10, 10, 10, 255))
                    s0 += L
        out = a.out / f"transit_{name}.jpg"
        Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB").save(out, quality=88)
        print(out)


if __name__ == "__main__":
    main()
