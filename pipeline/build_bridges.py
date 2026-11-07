"""Rebuild bridges as simple solids: deck, side walls and piers. The AI pass supplies the masonry detail."""
import json
import math
from collections import defaultdict
import numpy as np
from common import RAW, WORK, ORIGIN_E, ORIGIN_N, lonlat_to_en, en_to_lonlat

STONE = (186, 176, 158)
RED = (172, 44, 40)
RAIL = (196, 198, 200)   # light grey railings and walkways on the Red Bridge
WIDTHS = {"motorway": 22, "trunk": 16, "primary": 15, "secondary": 13, "tertiary": 11}
PIER_EVERY = 28.0
MIN_CLEARANCE = 3.0
FASCIA = 1.6


def main():
    t = np.load(WORK / "terrain.npz")
    tz, e0, n0, step = t["z"], float(t["e0"]), float(t["n0"]), float(t["step"])

    def ground(e, n):
        iy = np.clip(((n - n0) / step).astype(int), 0, tz.shape[0] - 1)
        ix = np.clip(((e - e0) / step).astype(int), 0, tz.shape[1] - 1)
        return tz[iy, ix]

    ways = json.loads((RAW / "osm" / "bridges.json").read_text())["elements"]
    # Join ways that meet, so a bridge's height runs between its true abutments, not mid-span joints.
    # Dual carriageways stay separate because their nodes differ.
    items = []
    for w in ways:
        if "geometry" not in w:
            continue
        pts = [(round(p["lon"], 7), round(p["lat"], 7)) for p in w["geometry"]]
        items.append({"pts": pts, "tags": w["tags"]})
    ends = defaultdict(list)
    for i, it in enumerate(items):
        ends[it["pts"][0]].append(i)
        ends[it["pts"][-1]].append(i)
    used = set()
    chains = []
    for i, it in enumerate(items):
        if i in used:
            continue
        used.add(i)
        pts = list(it["pts"])
        tags = dict(it["tags"])
        grew = True
        while grew:
            grew = False
            for side in (0, -1):
                for j in ends[pts[side]]:
                    if j in used:
                        continue
                    o = items[j]["pts"]
                    if side == -1:
                        pts += (o if o[0] == pts[-1] else o[::-1])[1:]
                    else:
                        pts = (o if o[-1] == pts[0] else o[::-1])[:-1] + pts
                    tags = {**items[j]["tags"], **tags}
                    used.add(j)
                    grew = True
                    break
        chains.append((pts, tags))

    deck, solid, solid_col = [], [], []

    def quad(a, b, c, d, col):
        solid.extend([a, b, c, b, d, c])
        solid_col.extend([col] * 6)

    def prism(b, t, ux, uy, vx, vy, a, w, col):
        """A straight box leg from bottom centre b to top centre t (x, y, z), a x w metres in section."""
        cs = [(i * a / 2, j * w / 2) for i, j in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        B = [np.array([b[0] + p * ux + q * vx, b[1] + p * uy + q * vy, b[2]]) for p, q in cs]
        T = [np.array([t[0] + p * ux + q * vx, t[1] + p * uy + q * vy, t[2]]) for p, q in cs]
        for k in range(4):
            quad(T[k], T[(k + 1) % 4], B[k], B[(k + 1) % 4], col)

    def v_legs(e, n, z, g, ss, length, dx, dy, nrm, width, col):
        """Pont Grande-Duchesse Charlotte: the deck rests on two V-shaped piers, one on each valley side.
        Each V is a pair of slanted legs from one foot on the slope up to the deck, under both deck edges."""
        for frac in (0.22, 0.78):
            sf = frac * length
            i = int(np.argmin(np.abs(ss - sf)))
            foot_z = float(g[i]) - 1.0
            ux, uy = dx[i] / nrm[i], dy[i] / nrm[i]   # along the deck
            vx, vy = -uy, ux                          # across the deck
            spread = 0.11 * length                    # how far along the deck each arm reaches
            for side in (-1, 1):
                off = side * (width / 2 - 1.8)
                fx = e[i] - ORIGIN_E + vx * off; fy = n[i] - ORIGIN_N + vy * off
                for arm in (-1, 1):
                    sa = min(max(sf + arm * spread, 0), length)
                    j = int(np.argmin(np.abs(ss - sa)))
                    tx = e[j] - ORIGIN_E + vx * off; ty = n[j] - ORIGIN_N + vy * off
                    prism((fx, fy, foot_z), (tx, ty, float(z[j]) - 5.5), ux, uy, vx, vy, 4.5, 3.6, col)

    kept = 0
    names = set()
    # Pont Grande-Duchesse Charlotte is one 25 m deck, but OSM maps it as two carriageways. Two decks side by
    # side leave a gap that shows their red inner walls as stripes down the road, so merge them into one deck
    # on the centre line between them.
    rb = [c for c in chains if "Charlotte" in (c[1].get("name") or c[1].get("bridge:name") or "")]
    if len(rb) >= 2:
        rb.sort(key=lambda c: -len(c[0]))
        a = np.array([lonlat_to_en(*p) for p in rb[0][0]])
        others = np.concatenate([np.array([lonlat_to_en(*p) for p in c[0]]) for c in rb[1:]])
        # densify the other carriageway(s) so "nearest point" is a point on the line, not a far vertex
        dense = []
        for c in rb[1:]:
            o = np.array([lonlat_to_en(*p) for p in c[0]])
            for k in range(len(o) - 1):
                for t in np.linspace(0, 1, 20, endpoint=False):
                    dense.append(o[k] + (o[k + 1] - o[k]) * t)
            dense.append(o[-1])
        dense = np.array(dense) if dense else others
        mid = []
        for q in a:
            j = int(np.argmin(np.hypot(*(dense - q).T)))
            mid.append((q + dense[j]) / 2)
        mid_ll = [en_to_lonlat(e_, n_) for e_, n_ in mid]
        tags = dict(rb[0][1]); tags["width"] = "25"
        chains = [c for c in chains if c not in rb] + [([(round(x, 7), round(y, 7)) for x, y in mid_ll], tags)]
        print("Red Bridge: merged", len(rb), "carriageways into one 25 m deck")

    deck_red = []
    for pts, tags in chains:
        en = np.array([lonlat_to_en(*p) for p in pts])
        seg = np.hypot(*np.diff(en, axis=0).T)
        length = float(seg.sum())
        if length < 12:
            continue
        # Resample every 4 m along the centreline.
        s = np.r_[0, np.cumsum(seg)]
        ss = np.arange(0, length + 4, 4.0)
        ss[-1] = length
        e = np.interp(ss, s, en[:, 0]); n = np.interp(ss, s, en[:, 1])
        g = ground(e, n)
        # The deck meets the approach roads: take each end's height from the ground just beyond the bridge
        # (where the road continues), not from the first metres of the span, which already dip into the valley.
        def beyond(k0, k1, dist=8.0):
            ux, uy = e[k0] - e[k1], n[k0] - n[k1]
            l = math.hypot(ux, uy) or 1.0
            return float(ground(np.array([e[k0] + ux / l * dist]), np.array([n[k0] + uy / l * dist]))[0])
        z0 = max(float(np.median(g[:2])), beyond(0, 1))
        z1 = max(float(np.median(g[-2:])), beyond(-1, -2))
        z = z0 + (z1 - z0) * (ss / length)
        clearance = z - g
        if clearance.max() < MIN_CLEARANCE:
            continue
        z = np.maximum(z, g + 0.4)
        name = tags.get("name") or tags.get("bridge:name") or ""
        is_rail = "railway" in tags
        width = float(tags.get("width", "0").split()[0].replace(",", ".") or 0) if tags.get("width", "").replace(".", "").replace(" m", "").isdigit() else 0
        if not width:
            width = 8.0 if is_rail else float(WIDTHS.get(tags.get("highway", ""), 9))
        col = RED if "Charlotte" in name else STONE
        red_bridge = "Charlotte" in name
        # Pont Grande-Duchesse Charlotte: one 25 m deck (OSM draws two carriageways), a grey road with light
        # walkways and grey railings on top; red only on the deep sides of the steel box girder and on the legs.
        fascia = 5.5 if red_bridge else FASCIA
        top_col = RAIL if red_bridge else col
        if red_bridge:
            width = max(width, 14.0)
        # The Red Bridge stands on two V-shaped piers of huge slanted legs (built below), not on vertical piers.
        no_piers = "Charlotte" in name
        kept += 1
        if name:
            names.add(name)

        # Run the deck a few metres onto the approach road at road level, so it joins the road instead of
        # starting as a cut-off block.
        EXT = 5.0
        ux0, uy0 = e[0] - e[1], n[0] - n[1]; l0 = math.hypot(ux0, uy0) or 1.0
        ux1, uy1 = e[-1] - e[-2], n[-1] - n[-2]; l1 = math.hypot(ux1, uy1) or 1.0
        e = np.r_[e[0] + ux0 / l0 * EXT, e, e[-1] + ux1 / l1 * EXT]
        n = np.r_[n[0] + uy0 / l0 * EXT, n, n[-1] + uy1 / l1 * EXT]
        z = np.r_[z[0], z, z[-1]]
        g = np.r_[g[0], g, g[-1]]
        ss = np.r_[-EXT, ss, length + EXT]
        clearance = z - g
        dx = np.gradient(e); dy = np.gradient(n)
        nrm = np.hypot(dx, dy) + 1e-6
        ox, oy = -dy / nrm * width / 2, dx / nrm * width / 2
        L = np.column_stack((e + ox - ORIGIN_E, n + oy - ORIGIN_N, z))
        Rr = np.column_stack((e - ox - ORIGIN_E, n - oy - ORIGIN_N, z))
        for i in range(len(ss) - 1):
            a, b, c, d = L[i], L[i + 1], Rr[i], Rr[i + 1]
            # The Red Bridge's road is plain grey asphalt (drawn flat, not from the aerial photo, whose red
            # girder edges tint it); other decks keep the photo.
            (deck_red if red_bridge else deck).extend([a, b, c, b, d, c])
            # Side walls and parapets only where the deck is really off the ground: near the abutments the
            # road just continues, so a wall there reads as a step.
            if min(clearance[i], clearance[i + 1]) < 2.5:
                continue
            for p, q in ((L[i], L[i + 1]), (Rr[i], Rr[i + 1])):
                quad(p, q, p - [0, 0, fascia], q - [0, 0, fascia], col)
                # Low parapet, so the deck edge reads from above.
                quad(p + [0, 0, 1.1], q + [0, 0, 1.1], p, q, top_col)
        # Piers across the deck, wherever there's real height under it.
        next_pier = PIER_EVERY / 2
        for i in range(1, len(ss) - 1):
            if not no_piers and ss[i] >= next_pier and clearance[i] > MIN_CLEARANCE:
                next_pier = ss[i] + PIER_EVERY
                # Two slim columns under the deck edges, not a full-width wall, so the valley stays visible.
                top = z[i] - FASCIA
                bot = float(g[i]) - 1
                ux, uy = dx[i] / nrm[i], dy[i] / nrm[i]   # along the deck
                vx, vy = -uy, ux                          # across the deck
                half = 1.1
                for side in (-1, 1):
                    cx = e[i] - ORIGIN_E + side * vx * (width / 2 - 1.6)
                    cy = n[i] - ORIGIN_N + side * vy * (width / 2 - 1.6)
                    cs = [np.array([cx + a * ux * half + b * vx * half, cy + a * uy * half + b * vy * half])
                          for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
                    for u, v in zip(cs, cs[1:] + cs[:1]):
                        quad(np.r_[u, top], np.r_[v, top], np.r_[u, bot], np.r_[v, bot], col)

        if no_piers:
            v_legs(e, n, z, g, ss, length, dx, dy, nrm, width, col)

    np.savez(WORK / "bridges.npz", deck=np.array(deck, np.float32).reshape(-1, 3),
             deck_red=np.array(deck_red, np.float32).reshape(-1, 3),
             solid=np.array(solid, np.float32).reshape(-1, 3), solid_col=np.array(solid_col, np.uint8).reshape(-1, 3))
    print("chains", len(chains), "bridges built", kept)
    print(sorted(names))


if __name__ == "__main__":
    main()
