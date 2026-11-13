"""Landmark cutaways ("slice of cake"): a landmark's 3D model with a slice taken out, drawn as a small layer of its
own above layer 5. Spec: v2/docs/specs/landmark-cutaways.md (rules 1-6, checks K1-K7 in v2/checks/cutaway_checks.py).

**The cut is data** (v2/data/structures/cutaways.json): per landmark the scene buildings it is made of and one or two
vertical cut planes, each an origin (E, N), a horizontal normal pointing into the removed slice and an extent
[t0, t1] in metres along the plane (along the normal turned a quarter turn left). The removed slice is what lies in
front of every plane, within its extent, above the floor: a convex prism in plan. Where an extent ends inside the
building the slice has a side face there, also a section of the model.

**The model is a hollow LoD2 shell**, so it is given a nominal thickness (params.json g3 cutaway_*; ACT's roofs cover
the footprint exactly once, so the building is the space under its roof surfaces):
    walls   cutaway_wall_m, measured in plan from the footprint's outline inwards
    roofs   cutaway_roof_m, measured straight down from every roof surface; under a roof surface steeper than
            cutaway_solid_roof_deg (a spire, a turret's cap) the model is solid
    floor   at the landmark's floor level (cutaways.json floor_z); below it the model is solid
    slabs   cutaway_slab_m thick, their tops at the facade layout's floor lines (ground + 3.6 m, then every 3.0 m),
            where the landmark has ordinary floors and outside its areas that are open to the roof (a nave)
A wall that stands on a lower roof (a tower's side above a nave) keeps ACT's single surface: no thickness there.

**What is drawn** (albedo only, no light; nothing that moves):
    outside        the kept shell, by method A's materials (art_a.py), exactly as layer 5 draws it
    cut faces      the model's section along the slice's faces (class "cut")
    inside faces   the inner sides of the kept walls and roofs, the floor, the slabs (classes "inside_wall",
                   "inside_roof", "floor", "slab")
    other          another building where it is nearer than the cut model, or seen through the slice (layer 5 holds
                   only the nearest building per pixel, so the cutaway brings what its landmark hid)
The cut and inside faces are a **code placeholder interior**: one flat palette colour per kind (palette cutaway.*)
and ink where surfaces meet.

**A painted interior** replaces the placeholder's colour inside the same mask, and nothing else (depth, normals,
ids and k stay the model's): v2/data/structures/cutaway_paintings/<name>.png, a painting in the landmark's paint
frame cut to the opening mask, with <name>.json (its frame, its checks, the file's hash, which candidate of which
run it is, and the owner's acceptance, K7). It is put there by `python -m v2.bakeoff adopt` from a candidate that
passed its gates and that the owner accepted by eye (bakeoff/cutaway_paint.py); a painting whose record does not
say it passed, or does not carry the owner's acceptance of that candidate, or whose file is not the recorded one,
stops the build. Without one the placeholder is drawn.

Every pixel lies inside the whole landmark's own silhouette, with exact depth and normals. Classes of the cut and
inside faces are this module's own (CUT_CLASS, above common.CLASS's ids), written with the tiles' index.
"""
from __future__ import annotations

import json
import math
from functools import cached_property
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon, box

from v2.config import REPO, params
from v2.layers import geometry as G
from v2.layers.common import TILE, VIEW, Scene, Tile, pal, project, write_tile

CUTS = REPO / "v2" / "data" / "structures" / "cutaways.json"
PAINTINGS = REPO / "v2" / "data" / "structures" / "cutaway_paintings"
# classes of the cut and inside faces in the cutaway's id tiles (id << 8 | class); common.CLASS ends at 30
CUT_CLASS = {"cut": 40, "inside_wall": 41, "inside_roof": 42, "floor": 43, "slab": 44}
# the k tile: what each pixel is. The opening mask is OPENING (the section and the inside faces)
KIND = {"none": 0, "outside": 1, "cut": 2, "inside_wall": 3, "inside_roof": 4, "floor": 5, "slab": 6, "other": 7}
OPENING = tuple(KIND[k] for k in ("cut", "inside_wall", "inside_roof", "floor", "slab"))
COLOUR = {"cut": "cutaway.section", "inside_wall": "cutaway.inside_wall", "inside_roof": "cutaway.inside_roof",
          "floor": "cutaway.floor", "slab": "cutaway.slab"}
TO_CAMERA = -VIEW
EPS = 1e-7


def load_cuts(path: Path = CUTS) -> dict:
    return json.loads(Path(path).read_text())


def owner_acceptance(record: dict) -> str | None:
    """What a painting's record lacks of K7 (None if nothing): the candidate and its run, and the owner's acceptance
    of that same candidate with the owner's words and date."""
    k7 = record.get("K7") or {}
    if not record.get("candidate") or not record.get("run"):
        return "which candidate of which run it is"
    if not k7.get("owner_words") or not k7.get("date"):
        return "the owner's acceptance (K7: the owner's words and date)"
    if k7.get("candidate") != record["candidate"]:
        return f"the owner's acceptance of {record['candidate']} (its K7 is of {k7.get('candidate')})"
    return None


def write_painting(folder: Path, name: str, rgb, mask, frame_px, record: dict) -> dict:
    """A landmark's painted interior as the layer reads it: the painting cut to the opening mask (RGBA, alpha = the
    mask) and its record. `frame_px`: the paint frame (x0, y0, width, height in map pixels); `record`: where it came
    from (candidate, run), its checks with "pass" true, and the owner's acceptance of that candidate (K7)."""
    import hashlib
    from PIL import Image
    rgb, mask = np.asarray(rgb, np.uint8), np.asarray(mask, bool)
    if not record.get("pass"):
        raise ValueError(f"{name}: only a painting that passed its checks is handed to the layer")
    if owner_acceptance(record):
        raise ValueError(f"{name}: the painting's record lacks {owner_acceptance(record)}")
    if rgb.shape[:2] != mask.shape or list(mask.shape) != [int(frame_px[3]), int(frame_px[2])]:
        raise ValueError(f"{name}: painting {rgb.shape}, mask {mask.shape}, frame {list(frame_px)}")
    folder.mkdir(parents=True, exist_ok=True)
    rgba = np.dstack([np.where(mask[..., None], rgb, 0), (mask * 255).astype(np.uint8)])
    Image.fromarray(rgba, "RGBA").save(folder / f"{name}.png", optimize=True)
    meta = {"landmark": name, "frame_px": [int(v) for v in frame_px], "opening_px": int(mask.sum()),
            "file": f"{name}.png", "sha256": hashlib.sha256((folder / f"{name}.png").read_bytes()).hexdigest(), **record}
    (folder / f"{name}.json").write_text(json.dumps(meta, indent=1))
    return meta


def load_painting(name: str, folder: Path | None = PAINTINGS) -> dict | None:
    """The painted interior of a landmark, or None if there is none: {"rgb", "on" (bool: where it is painted),
    "frame_px", "meta"}."""
    import hashlib
    from PIL import Image
    if folder is None or not (folder / f"{name}.json").exists():
        return None
    meta = json.loads((folder / f"{name}.json").read_text())
    f = folder / meta["file"]
    if not meta.get("pass"):
        raise RuntimeError(f"{f}: its record does not say it passed its checks")
    if owner_acceptance(meta):
        raise RuntimeError(f"{f}: its record lacks {owner_acceptance(meta)}")
    if hashlib.sha256(f.read_bytes()).hexdigest() != meta["sha256"]:
        raise RuntimeError(f"{f}: not the file its record names (sha256)")
    a = np.asarray(Image.open(f).convert("RGBA"))
    if list(a.shape[:2]) != [meta["frame_px"][3], meta["frame_px"][2]]:
        raise RuntimeError(f"{f}: {a.shape[:2]} px, its frame is {meta['frame_px']}")
    return {"rgb": a[..., :3], "on": a[..., 3] > 127, "frame_px": meta["frame_px"], "meta": meta}


def paint_into(c: dict, frame, painting: dict) -> np.ndarray:
    """A painted interior into a drawn frame of the cut landmark (Cutaways.cut's dict), in place: the opening's
    pixels (k in OPENING) take the painting's colour at their map pixel; everything else, and depth, normals, ids
    and k, stay. Returns where it painted (bool, the frame's shape)."""
    fx, fy, fw, fh = painting["frame_px"]
    cols = np.floor(frame.centres[0]).astype(int) - fx
    rows = np.floor(frame.centres[1]).astype(int) - fy
    inside = ((rows >= 0) & (rows < fh))[:, None] & ((cols >= 0) & (cols < fw))[None, :]
    r, q = np.clip(rows, 0, fh - 1)[:, None], np.clip(cols, 0, fw - 1)[None, :]
    on = np.isin(c["k"], OPENING) & inside & painting["on"][r, q]
    c["rgb"] = np.where(on[..., None], painting["rgb"][r, q], c["rgb"]).astype(np.uint8)
    return on


def cut_params(P: dict | None = None) -> dict:
    """The thickness rule's numbers: params.json g3 cutaway_* and the facade layout's floor heights."""
    if P is None:
        g3, fac = params()["g3"], params()["facades"]
        P = {k: v for k, v in g3.items() if k.startswith("cutaway_")}
        P["ground_floor_m"], P["floor_m"] = fac["ground_floor_m"], fac["floor_m"]
    return P


def stage_params(area):
    return cut_params()


# ------------------------------------------------------------------------------------------------ convex clipping
def split_convex(P, d, eps=EPS):
    """A convex polygon P (k, dim) split where d (k,), a linear function at its corners, changes sign: (the part
    where d > 0, the part where d <= 0), each (m, dim) or None."""
    pos, neg = [], []
    k = len(P)
    for i in range(k):
        a, b, da, db = P[i], P[(i + 1) % k], d[i], d[(i + 1) % k]
        if da > eps:
            pos.append(a)
        elif da < -eps:
            neg.append(a)
        else:
            pos.append(a)
            neg.append(a)
        if (da > eps and db < -eps) or (da < -eps and db > eps):
            x = a + (b - a) * (da / (da - db))
            pos.append(x)
            neg.append(x)
    return (np.array(pos) if len(pos) >= 3 else None), (np.array(neg) if len(neg) >= 3 else None)


def fan(poly):
    """A convex polygon (k, 3) as triangles (k - 2, 3, 3), without those of no area."""
    t = np.stack([np.repeat(poly[:1], len(poly) - 2, 0), poly[1:-1], poly[2:]], 1)
    area = np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1)
    return t[area > 1e-10]


def clip_outside(tris, H, eps=EPS):
    """The parts of triangles (n, 3, 3) outside the convex region {p : H[:, :3] p > H[:, 3] for every row}.
    Returns (triangles (m, 3, 3), the index of the triangle each came from)."""
    tris = np.asarray(tris, float).reshape(-1, 3, 3)
    if not len(tris):
        return tris, np.zeros(0, np.int64)
    d = tris @ H[:, :3].T - H[:, 3]                             # (n, corner, half-space)
    whole = (d <= eps).all(1).any(1)                            # all of it outside one half-space
    gone = (d >= -eps).all((1, 2)) & ~whole
    out, par = [tris[whole]], [np.flatnonzero(whole)]
    for i in np.flatnonzero(~whole & ~gone):
        poly = tris[i]
        for h in H:
            poly, neg = split_convex(poly, poly @ h[:3] - h[3], eps)
            if neg is not None:
                f = fan(neg)
                out.append(f)
                par.append(np.full(len(f), i))
            if poly is None:
                break
    return np.concatenate(out), np.concatenate(par).astype(np.int64)


class Region:
    """The removed slice: in front of every cut plane, within its extent, above the floor."""

    def __init__(self, planes, floor_z):
        self.floor_z = float(floor_z)
        self.planes = planes
        half = []                                               # (a, b, c): inside where a e + b n > c
        for p in planes:
            o = np.array(p["origin"], float)
            n = np.array(p["normal"], float)
            n = n / np.linalg.norm(n)
            t = np.array([-n[1], n[0]])
            t0, t1 = (float(v) for v in p["extent"])
            half += [[n[0], n[1], n @ o], [t[0], t[1], t @ o + t0], [-t[0], -t[1], -(t @ o + t1)]]
        self.half = np.array(half, float)

    @property
    def H(self):
        """The slice as half-spaces of (E, N, z): rows (a, b, c, d), inside where a E + b N + c z > d."""
        h = np.zeros((len(self.half) + 1, 4))
        h[:-1, :2], h[:-1, 3] = self.half[:, :2], self.half[:, 2]
        h[-1, 2], h[-1, 3] = 1.0, self.floor_z
        return h

    def inside(self, e, n, z=None):
        e, n = np.asarray(e, float), np.asarray(n, float)
        m = np.ones(e.shape, bool)
        for a, b, c in self.half:
            m &= a * e + b * n > c
        return m if z is None else m & (np.asarray(z, float) > self.floor_z)

    def polygon(self, bounds):
        """The slice in plan, inside a bounding box (x0, y0, x1, y1): its corners (k, 2) (or None), and for each
        edge i (corner i to i + 1) the cut plane's row in `half` it lies on (-1 on the box)."""
        x0, y0, x1, y1 = bounds
        poly = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], float)
        for a, b, c in self.half:
            poly, _ = split_convex(poly, poly[:, 0] * a + poly[:, 1] * b - c, 1e-9)
            if poly is None:
                return None, []
        on = []
        for i in range(len(poly)):
            p, q = poly[i], poly[(i + 1) % len(poly)]
            j = [k for k, (a, b, c) in enumerate(self.half) if abs(a * p[0] + b * p[1] - c) < 1e-6
                 and abs(a * q[0] + b * q[1] - c) < 1e-6]
            on.append(j[0] if j and np.linalg.norm(q - p) > 1e-6 else -1)
        return poly, on

    def faces(self, bounds):
        """The slice's vertical faces inside the box: (p, q, the unit normal into the slice) each."""
        poly, on = self.polygon(bounds)
        return [] if poly is None else [(poly[i], poly[(i + 1) % len(poly)], self.half[j, :2].copy())
                                        for i, j in enumerate(on) if j >= 0]


# ------------------------------------------------------------------------------------------------ the solid
def _polys(g):
    """The polygons of any shapely geometry."""
    if g is None or g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g]
    return [p for q in getattr(g, "geoms", []) for p in _polys(q)]


def _lines(g):
    if g is None or g.is_empty:
        return []
    if g.geom_type in ("LineString", "LinearRing"):
        return [g] if g.length > 1e-7 else []
    return [p for q in getattr(g, "geoms", []) for p in _lines(q)]


def triangles2d(g):
    """Polygons as triangles (m, 3, 2) (a constrained triangulation: every triangle lies in the polygon)."""
    out = []
    for p in _polys(g):
        if p.area < 1e-8:
            continue
        for t in shapely.constrained_delaunay_triangles(p).geoms:
            out.append(np.array(t.exterior.coords)[:3])
    return np.array(out, float).reshape(-1, 3, 2)


class Solid:
    """One LoD2 building as the space under its roof surfaces: a footprint and the roof triangles over it."""

    def __init__(self, footprint, roof, ground_z):
        self.F = footprint
        self.ground_z = float(ground_z)
        roof = np.asarray(roof, float).reshape(-1, 3, 3)
        n = np.cross(roof[:, 1] - roof[:, 0], roof[:, 2] - roof[:, 0])
        ok = np.abs(n[:, 2]) > 2e-6                               # a roof triangle seen from above
        self.roof = roof[ok]
        self.grad = -n[ok, :2] / n[ok, 2:3]                       # dz/dE, dz/dN of each triangle's plane
        self.polys = shapely.polygons(self.roof[:, :, :2])
        self.tree = shapely.STRtree(self.polys)

    def plane_z(self, k, e, n):
        r = self.roof[k]
        return r[0, 2] + self.grad[k, 0] * (np.asarray(e, float) - r[0, 0]) + self.grad[k, 1] * (np.asarray(n, float) - r[0, 1])

    def top(self, e, n):
        """The roof's height over points (the highest roof triangle above each; -inf where there is none)."""
        e, n = np.asarray(e, float), np.asarray(n, float)
        out = np.full(e.shape, -np.inf)
        for k, r in enumerate(self.roof):
            m = (e >= r[:, 0].min() - 1e-6) & (e <= r[:, 0].max() + 1e-6) & (n >= r[:, 1].min() - 1e-6) & (n <= r[:, 1].max() + 1e-6)
            if not m.any():
                continue
            x, y = e[m], n[m]
            (ax, ay), (bx, by), (cx, cy) = r[:, :2]
            A = (bx - ax) * (cy - ay) - (cx - ax) * (by - ay)
            w0 = ((bx - x) * (cy - y) - (cx - x) * (by - y)) / A
            w1 = ((cx - x) * (ay - y) - (ax - x) * (cy - y)) / A
            ins = (w0 >= -1e-9) & (w1 >= -1e-9) & (1 - w0 - w1 >= -1e-9)
            z = self.plane_z(k, x, y)
            sub = out[m]
            sub[ins] = np.maximum(sub[ins], z[ins])
            out[m] = sub
        return out

    def inside(self, e, n, z):
        """Points inside the building: over its footprint, under its roof."""
        e, n = np.asarray(e, float), np.asarray(n, float)
        return shapely.contains_xy(self.F, e, n) & (np.asarray(z, float) < self.top(e, n))

    def pieces(self, line):
        """A plan line cut by the roof triangles above it: (k, a, b) with a, b its end points (2,) under triangle k."""
        out = []
        for k in self.tree.query(line, predicate="intersects"):
            for piece in _lines(line.intersection(self.polys[k])):
                c = np.array(piece.coords)
                out.append((int(k), c[0], c[-1]))
        return out


def _up_to(a, b, za, zb, lo, hi=None):
    """The vertical face over the plan segment a-b from height lo up to the line za-zb (and at most hi), as a
    convex polygon (k, 3), or None."""
    if za <= lo + 1e-9 and zb <= lo + 1e-9:
        return None
    if za >= lo and zb >= lo:
        q = np.array([[a[0], a[1], lo], [b[0], b[1], lo], [b[0], b[1], zb], [a[0], a[1], za]], float)
    else:                                                        # the top line dips under lo part of the way
        x = a + (b - a) * ((lo - za) / (zb - za))
        q = np.array([[a[0], a[1], lo], [x[0], x[1], lo], [a[0], a[1], za]] if za > lo else
                     [[x[0], x[1], lo], [b[0], b[1], lo], [b[0], b[1], zb]], float)
    if hi is not None:
        q, _ = split_convex(q, hi - q[:, 2])
    return q


class Faces:
    """Collects the cut and inside faces of one building, culling those turned away from the camera (each face is
    one-sided: it is seen from the slice or from the inside of the building, never through the model)."""

    def __init__(self, obj):
        self.M = G.Mesh()
        self.obj = obj
        self.count = {k: 0 for k in CUT_CLASS}

    def add(self, tris, kind, normal, group=None):
        tris = np.asarray(tris, float).reshape(-1, 3, 3)
        if not len(tris) or float(np.asarray(normal, float) @ TO_CAMERA) <= 1e-9:
            return group
        self.count[kind] += len(tris)
        return self.M.add(tris.reshape(-1, 3), np.arange(len(tris) * 3).reshape(-1, 3), CUT_CLASS[kind], self.obj,
                          COLOUR[kind], group)


def lift(t2, z):
    """Plan triangles (m, 3, 2) at heights z (a number, or a function of (E, N))."""
    t2 = np.asarray(t2, float).reshape(-1, 3, 2)
    zz = z(t2[..., 0], t2[..., 1]) if callable(z) else np.full(t2.shape[:2], float(z))
    return np.concatenate([t2, zz[..., None]], -1)


def interior_faces(S: Solid, walls, region: Region, P: dict, obj: int, floors=True, open_areas=None):
    """The cut and inside faces of one building for a slice (a geometry.Mesh dict), with `membrane`: for each of
    `walls` (ACT wall triangles (m, 3, 3)) the horizontal unit normal out of the building where the wall stands on
    a lower roof (zeros elsewhere), and counts."""
    tw, tr, ts = P["cutaway_wall_m"], P["cutaway_roof_m"], P["cutaway_slab_m"]
    fz = region.floor_z
    out = Faces(obj)
    F = S.F
    Fin = F.buffer(-tw, join_style="mitre")
    steep = np.degrees(np.arctan(np.hypot(S.grad[:, 0], S.grad[:, 1]))) > P["cutaway_solid_roof_deg"]
    if steep.any():                                               # solid under spires and turret caps
        Fin = Fin.difference(shapely.unary_union(S.polys[steep]))
    O = shapely.unary_union([Polygon(r) for r in (open_areas or [])]) if open_areas else None
    x0, y0, x1, y1 = F.bounds
    bounds = (x0 - 20, y0 - 20, x1 + 20, y1 + 20)
    rpoly, _ = region.polygon(bounds)
    Rp = Polygon(rpoly) if rpoly is not None else None
    levels = []
    if floors:
        h = S.ground_z + P["ground_floor_m"]
        ztop = float(S.roof[..., 2].max()) if len(S.roof) else fz
        while h < ztop:
            if h >= fz + P["cutaway_min_storey_m"]:
                levels.append(h)
            h += P["floor_m"]
    slab_area = Fin if O is None else Fin.difference(O)

    # ---- the inner side of the roofs, and the slabs' tops (both follow the roof triangles in plan)
    slab_groups = [out.M.new_group() for _ in levels]
    for k, r in enumerate(S.roof):
        c, _ = split_convex(r, r[:, 2] - tr - fz)
        if c is None:
            continue
        g = Polygon(c[:, :2]).intersection(Fin) if not Fin.is_empty else None
        t2 = triangles2d(g)
        if len(t2):
            down = np.array([S.grad[k, 0], S.grad[k, 1], -1.0])
            out.add(lift(t2, lambda e, n, k=k: S.plane_z(k, e, n) - tr), "inside_roof", down, group=None)
        for h, grp in zip(levels, slab_groups):
            c, _ = split_convex(r, r[:, 2] - tr - h)
            if c is None or slab_area.is_empty:
                continue
            out.add(lift(triangles2d(Polygon(c[:, :2]).intersection(slab_area)), h), "slab", [0, 0, 1.0], group=grp)

    # ---- the inner side of the outside walls: along the inner footprint, from the floor to the roof's inner side
    for poly in _polys(Fin):
        for ring in [poly.exterior] + list(poly.interiors):
            c = np.array(ring.coords)[:, :2]
            for a, b in zip(c[:-1], c[1:]):
                d = b - a
                L = np.linalg.norm(d)
                if L < 1e-6:
                    continue
                nrm = np.array([-d[1], d[0]]) / L
                mid = (a + b) / 2
                if not shapely.contains_xy(Fin, *(mid + nrm * 1e-3)):
                    nrm = -nrm
                n3 = np.array([nrm[0], nrm[1], 0.0])
                if n3 @ TO_CAMERA <= 1e-9:
                    continue
                grp = out.M.new_group()
                # the roof over the room's side of the wall (1 mm inside it): the wall ends under that roof
                for k, pa, pb in S.pieces(LineString([a + nrm * 1e-3, b + nrm * 1e-3])):
                    pa, pb = pa - nrm * 1e-3, pb - nrm * 1e-3
                    q = _up_to(pa, pb, S.plane_z(k, *pa) - tr, S.plane_z(k, *pb) - tr, fz)
                    if q is not None:
                        out.add(fan(q), "inside_wall", n3, group=grp)

    # ---- walls standing on a lower roof: ACT's one surface is the wall's outside and its inside (no thickness)
    walls = np.asarray(walls, float).reshape(-1, 3, 3)
    membrane = np.zeros((len(walls), 3))
    odd = 0
    if len(walls):
        wn = np.cross(walls[:, 1] - walls[:, 0], walls[:, 2] - walls[:, 0])
        wn /= np.maximum(np.linalg.norm(wn, axis=1, keepdims=True), 1e-12)
        cen = walls.mean(1)
        bd = F.boundary
        for i in np.flatnonzero(np.abs(wn[:, 2]) < 0.05):
            w = walls[i]
            if shapely.distance(bd, shapely.points(w[:, :2])).max() < 0.02:
                continue                                          # an outside wall, on the footprint's outline
            h = wn[i, :2] / np.linalg.norm(wn[i, :2])
            side = []
            for s in (1.0, -1.0):
                p = cen[i, :2] + s * 0.05 * h
                side.append(bool(shapely.contains_xy(F, *p)) and cen[i, 2] < float(S.top(p[:1], p[1:])[0]) - 1e-6)
            if side[0] == side[1]:
                odd += 1                                          # inside the model on both sides, or on neither
                continue
            hi = h if side[0] else -h                             # towards the higher part: the wall's inside
            membrane[i, :2] = -hi
            n3 = np.array([hi[0], hi[1], 0.0])
            if n3 @ TO_CAMERA <= 1e-9 or Fin.is_empty:
                continue
            # the triangle in (s along the wall, z), cut to the inner footprint in plan
            t = np.array([-h[1], h[0]])
            s = (w[:, :2] - w[0, :2]) @ t
            base = w[0, :2] + np.outer([s.min() - 1.0, s.max() + 1.0], t)
            for piece in _lines(LineString(base).intersection(Fin)):
                pc = np.array(piece.coords)
                s0, s1 = sorted(((pc[0] - w[0, :2]) @ t, (pc[-1] - w[0, :2]) @ t))
                poly = np.column_stack([s, w[:, 2] - tr])
                for d in (lambda q: q[:, 0] - s0, lambda q: s1 - q[:, 0], lambda q: q[:, 1] - fz):
                    poly, _ = split_convex(poly, d(poly)) if poly is not None else (None, None)
                if poly is None:
                    continue
                p3 = np.column_stack([w[0, 0] + poly[:, 0] * t[0], w[0, 1] + poly[:, 0] * t[1], poly[:, 1]])
                out.add(fan(p3), "inside_wall", n3)

    # ---- the floor (kept under the slice too), and the walls' trace on it where the slice took them
    up = [0, 0, 1.0]
    out.add(lift(triangles2d(Fin), fz), "floor", up, group=out.M.new_group())
    if Rp is not None:
        out.add(lift(triangles2d(F.difference(Fin).intersection(Rp)), fz), "cut", up, group=out.M.new_group())

    # ---- the slabs' edges towards an area that is open to the roof
    if levels and O is not None and not slab_area.is_empty:
        for line in _lines(O.boundary.intersection(Fin)):
            c = np.array(line.coords)[:, :2]
            for a, b in zip(c[:-1], c[1:]):
                d = b - a
                L = np.linalg.norm(d)
                if L < 1e-6:
                    continue
                nrm = np.array([-d[1], d[0]]) / L
                if not shapely.contains_xy(O, *((a + b) / 2 + nrm * 1e-3)):
                    nrm = -nrm
                n3 = np.array([nrm[0], nrm[1], 0.0])
                for k, pa, pb in S.pieces(LineString([a, b])):
                    for h, grp in zip(levels, slab_groups):
                        q = _up_to(pa, pb, S.plane_z(k, *pa) - tr, S.plane_z(k, *pb) - tr, h - ts, hi=h)
                        if q is not None:
                            out.add(fan(q), "slab", n3, group=grp)

    # ---- the section: on each face of the slice, the model's material (outer profile less the hollow inside)
    section_m2 = 0.0
    for p, q, n2 in region.faces(bounds):
        n3 = np.array([n2[0], n2[1], 0.0])
        L = np.linalg.norm(q - p)
        t = (q - p) / L
        edge = LineString([p, q])
        if n3 @ TO_CAMERA <= 1e-9 or not edge.intersects(F):
            continue

        def profile(area, drop):
            parts = []
            for seg in _lines(edge.intersection(area)) if not area.is_empty else []:
                for k, a, b in S.pieces(seg):
                    poly = _up_to(a, b, S.plane_z(k, *a) - drop, S.plane_z(k, *b) - drop, fz)
                    if poly is not None:
                        pp = Polygon(np.column_stack([(poly[:, :2] - p) @ t, poly[:, 2]]))
                        parts.append(shapely.set_precision(pp, 1e-5))
            return shapely.unary_union([g for g in parts if not g.is_empty]) if parts else Polygon()
        outer = profile(F, 0.0)
        inner = profile(Fin, tr)
        if levels and not inner.is_empty:
            room = profile(slab_area, tr)
            bands = shapely.unary_union([box(-1.0, h - ts, L + 1.0, h) for h in levels])
            inner = inner.difference(shapely.set_precision(bands.intersection(room), 1e-5))
        sec = shapely.set_precision(outer.difference(inner), 1e-5)
        t2 = triangles2d(sec)
        if not len(t2):
            continue
        section_m2 += float(sec.area)
        p3 = np.concatenate([p + t2[..., :1] * t, t2[..., 1:]], -1)
        out.add(p3, "cut", n3, group=out.M.new_group())

    M = out.M.done()
    keys = sorted(COLOUR.values())                                # the same colour keys for every building's faces
    M["col"] = np.array([keys.index(M["col_keys"][c]) for c in M["col"]], np.int64)
    M["col_keys"] = keys
    if len(M["T"]):                                               # nothing of the inside is left inside the slice
        tris, par = clip_outside(M["V"][M["T"]], region.H)
        M = {"V": tris.reshape(-1, 3), "T": np.arange(len(tris) * 3).reshape(-1, 3), "group": M["group"][par],
             "cls": M["cls"][par], "obj": M["obj"][par], "col": M["col"][par], "col_keys": M["col_keys"]}
    stats = {"faces": {k: int(v) for k, v in out.count.items()}, "walls_on_roofs": int((membrane != 0).any(1).sum()),
             "walls_unresolved": odd, "slab_levels": [round(h, 2) for h in levels], "section_m2": round(section_m2, 2),
             "inner_footprint_m2": round(float(Fin.area), 1), "footprint_m2": round(float(F.area), 1)}
    return M, membrane, stats


# ------------------------------------------------------------------------------------------------ meshes
ROW_KEYS = ("group", "cls", "obj", "col")


def take(M, rows):
    """Rows (triangles) of a mesh dict, each with `parent`: its row in M."""
    rows = np.asarray(rows, np.int64)
    out = {"V": M["V"], "T": M["T"][rows], "col_keys": M["col_keys"], "parent": rows}
    for k in ROW_KEYS + (("bias",) if "bias" in M else ()):
        out[k] = M[k][rows]
    return out


def clip_mesh(M, rows, H):
    """Rows of a mesh dict with the convex region H cut out of them (`parent` as take)."""
    rows = np.asarray(rows, np.int64)
    tris, par = clip_outside(M["V"][M["T"][rows]], H)
    out = {"V": tris.reshape(-1, 3), "T": np.arange(len(tris) * 3).reshape(-1, 3), "col_keys": M["col_keys"],
           "parent": rows[par]}
    for k in ROW_KEYS + (("bias",) if "bias" in M else ()):
        out[k] = M[k][rows[par]]
    return out


def join(a, b):
    """Two mesh dicts with the same colour keys as one."""
    out = {"V": np.concatenate([a["V"], b["V"]]), "T": np.concatenate([a["T"], b["T"] + len(a["V"])]),
           "col_keys": a["col_keys"]}
    for k in ROW_KEYS + ("parent",) + (("bias",) if "bias" in a else ()):
        out[k] = np.concatenate([a[k], b[k]])
    return out


class Frame:
    """A square window of zoom-0 map pixels, drawn like a tile."""
    apron = 0

    def __init__(self, x0, y0, size):
        self.px0, self.py0, self.size = int(x0), int(y0), int(size)
        self.centres = (self.px0 + np.arange(self.size) + 0.5, self.py0 + np.arange(self.size) + 0.5)
        self.name = f"{self.px0}_{self.py0}"

    def crop(self, a):
        return a


def draw(meshes, frame, shader=None, outline=True):
    """Meshes rasterised as layers 5 and 6 are (render.Renderer._mesh_layer: flat albedo, exact depth and normals,
    ink where surfaces meet), without a scene."""
    from v2.layers.render import Renderer
    return Renderer._mesh_layer(Renderer.__new__(Renderer), frame, meshes, outline=outline, shader=shader)


def kinds_of(ids, depth, own):
    """The k tile from a drawn frame's ids: what each pixel is (KIND). `own`: the landmark's building indices."""
    cls = (ids & 255).astype(np.int64)
    obj = (ids >> 8).astype(np.int64)
    k = np.where(np.isin(obj, list(own)), KIND["outside"], KIND["other"]).astype(np.uint8)
    for name, c in CUT_CLASS.items():
        k[cls == c] = KIND[name]
    k[~np.isfinite(depth)] = KIND["none"]
    return k


def cut_model(solids, shell, openings, region, P, floors=True, open_areas=None):
    """A landmark's cut model. solids: {building index: Solid}; shell: the buildings' mesh (geometry.buildings_mesh,
    with "kind"); openings: the openings' mesh or None. Returns the three meshes drawn (the kept shell, the kept
    openings, the cut and inside faces), the rows of the whole landmark in shell and openings, and counts."""
    own = sorted(solids)
    H = region.H
    is_own = np.isin(shell["obj"], own)
    keep = is_own.copy()
    faces, stats = None, {}
    for bi in own:
        wrows = np.flatnonzero((shell["obj"] == bi) & (shell["kind"] == 2))
        M, membrane, st = interior_faces(solids[bi], shell["V"][shell["T"][wrows]], region, P, bi, floors, open_areas)
        # a wall standing on a lower roof, seen from behind, is its inside face (drawn above): not the outside
        keep[wrows[(membrane @ TO_CAMERA < 0) & (membrane != 0).any(1)]] = False
        M["parent"] = np.zeros(len(M["T"]), np.int64)
        faces = M if faces is None else join(faces, M)
        stats[bi] = st
    out = {"own": own, "shell_rows": np.flatnonzero(is_own), "shell": clip_mesh(shell, np.flatnonzero(keep), H),
           "faces": faces, "stats": stats, "open_rows": np.zeros(0, np.int64), "openings": None}
    if openings is not None and len(openings["T"]):
        orow = np.flatnonzero(np.isin(openings["obj"], own))
        tri = openings["V"][openings["T"][orow]]
        n, _ = G.tri_normals(openings["V"], openings["T"][orow])
        cen = tri.mean(1)
        # an opening lies just outside its wall; seen from behind (through the building) it is not drawn. Which
        # way it faces: the side of it that is inside the building is its back
        back = np.zeros(len(orow), bool)
        for bi in own:
            m = openings["obj"][orow] == bi
            a, b = cen[m] + 0.3 * n[m], cen[m] - 0.3 * n[m]
            ia, ib = solids[bi].inside(a[:, 0], a[:, 1], a[:, 2]), solids[bi].inside(b[:, 0], b[:, 1], b[:, 2])
            out_n = np.where((ia & ~ib)[:, None], -n[m], n[m])
            back[m] = (ia != ib) & (out_n @ TO_CAMERA <= 0)
        out["open_rows"] = orow
        out["openings"] = clip_mesh(openings, orow[~back], H)
    return out


# ------------------------------------------------------------------------------------------------ a scene's cutaways
def footprint(info):
    return shapely.unary_union([Polygon(p[0], p[1:]).buffer(0) for p in info["footprint"] if p and len(p[0]) >= 4])


def place_buildings(scene, slug, max_dist):
    """The scene buildings at a landmark's place (v1's landmark card `slug`): the one whose footprint holds the
    place's point, or the nearest footprint within max_dist metres. Returns [(building id, distance m)]."""
    from shapely.geometry import Point
    pl = [p for p in scene.places if p.get("slug") == slug and p.get("source") == "landmark"]
    if not pl:
        return []
    pt = Point(pl[0]["e"], pl[0]["n"])
    best = None
    for b in scene.buildings:
        if abs(b["centre"][0] - pt.x) > 150 or abs(b["centre"][1] - pt.y) > 150:
            continue
        d = footprint(b).distance(pt)
        if d <= max_dist and (best is None or d < best[1]):
            best = (b["id"], round(float(d), 2))
    return [best] if best else []


class Cutaways:
    """The cutaways of one scene: their models and their drawings."""

    def __init__(self, scene: Scene, P: dict | None = None, cuts: dict | None = None, paintings: Path | None = PAINTINGS):
        from v2.layers.render import Renderer
        self.scene = scene
        self.P = cut_params(P)
        self.cuts = cuts or load_cuts()
        self.paintings = paintings                                # the folder of painted interiors (None: placeholders)
        self._painting = {}
        self.R = Renderer(scene, art="a")                         # the outside by method A's materials
        self._models = {}

    @cached_property
    def bidx(self):
        return {b["id"]: i for i, b in enumerate(self.scene.buildings)}

    def missing(self):
        """Landmarks of cutaways.json whose buildings are not in this scene: {name: [ids]}."""
        return {k: [i for i in v["buildings"] if i not in self.bidx] for k, v in self.cuts["landmarks"].items()
                if any(i not in self.bidx for i in v["buildings"])}

    def model(self, name):
        if name not in self._models:
            lm = self.cuts["landmarks"][name]
            shell, openings = self.R.building_meshes
            solids = {}
            for bid in lm["buildings"]:
                bi = self.bidx[bid]
                info = self.scene.buildings[bi]
                rows = (shell["obj"] == bi) & (shell["kind"] == 1)
                solids[bi] = Solid(footprint(info), shell["V"][shell["T"][rows]], info["ground_z"])
            m = cut_model(solids, shell, openings, Region(lm["planes"], lm["floor_z"]), self.P,
                          floors=lm.get("floors", True), open_areas=lm.get("open_to_roof"))
            own = np.isin(shell["obj"], m["own"])
            m["whole"] = [take(shell, np.flatnonzero(own)), take(openings, m["open_rows"])]
            # the landmark's cut model among the scene's other buildings
            m["scene"] = [join(take(shell, np.flatnonzero(~own)), m["shell"]),
                          join(take(openings, np.flatnonzero(~np.isin(openings["obj"], m["own"]))), m["openings"])]
            V = shell["V"][np.unique(shell["T"][own])]
            px, py, _ = project(V[:, 0], V[:, 1], V[:, 2])
            m["bbox_px"] = [int(math.floor(px.min())), int(math.floor(py.min())), int(math.ceil(px.max())), int(math.ceil(py.max()))]
            self._models[name] = m
        return self._models[name]

    def _shader(self, parents):
        """Method A's shading for clipped meshes (each pixel from its place on the surface it came from); the cut
        and inside faces (the third mesh) keep their flat placeholder colour."""
        def shade(mi, ti, P, nrm, base, px, py, cls, obj):
            rgb, pc = base.copy(), cls.copy()
            for k, par in enumerate(parents):
                on = mi == k
                if on.any():
                    rgb[on], pc[on] = self.R._shade_buildings_a(mi[on], par[ti[on]], P[on], nrm[on], base[on], px[on],
                                                                 py[on], cls[on], obj[on])
            return rgb, pc
        return shade

    def whole(self, name, frame, outline=True):
        """The whole landmark alone, as layer 5 draws it."""
        w = self.model(name)["whole"]
        return draw(w, frame, shader=self._shader([w[0]["parent"], w[1]["parent"]]), outline=outline)

    def painting(self, name):
        if name not in self._painting:
            self._painting[name] = load_painting(name, self.paintings)
        return self._painting[name]

    def cut(self, name, frame, others=True, painted=True):
        """The cut landmark in a frame: dict rgb, depth, normal, ids, k (KIND), outline (the whole landmark's own
        silhouette); nothing outside that silhouette. others=False draws the landmark alone. The interior is the
        landmark's painting if it has one (and `painted`), else the placeholder; with a painting the dict also has
        "painted": where it was drawn."""
        c = self._cut(name, frame, others)
        p = self.painting(name) if painted else None
        if p is not None:
            c["painted"] = paint_into(c, frame, p)
        return c

    def _cut(self, name, frame, others):
        m = self.model(name)
        shell, opn = m["scene"] if others else (m["shell"], m["openings"])
        faces = m["faces"]
        L = draw([shell, opn, faces], frame, shader=self._shader([shell["parent"], opn["parent"]]))
        sil = np.isfinite(draw(m["whole"], frame, outline=False).depth)
        keep = sil & np.isfinite(L.depth)
        k = kinds_of(L.ids, L.depth, m["own"])
        k[~keep] = KIND["none"]
        return {"rgb": np.where(keep[..., None], L.rgb, 0).astype(np.uint8), "depth": np.where(keep, L.depth, np.inf),
                "normal": np.where(keep[..., None], L.normal, 0.0), "ids": np.where(keep, L.ids, 0).astype(np.uint32),
                "k": k, "outline": sil}

    def tiles(self, name):
        x0, y0, x1, y1 = self.model(name)["bbox_px"]
        return [Tile(tx, ty) for ty in range(y0 // TILE, y1 // TILE + 1) for tx in range(x0 // TILE, x1 // TILE + 1)]

    def paint_frame(self, name, multiple=64, least=1024, margin=24):
        """The square frame a painting of this landmark is made in: the landmark's extent and a margin, at least
        1024 px (one model pixel per map pixel, as the bake-off's windows), a multiple of 64."""
        x0, y0, x1, y1 = self.model(name)["bbox_px"]
        size = max(least, int(math.ceil((max(x1 - x0, y1 - y0) + 2 * margin) / multiple)) * multiple)
        return Frame((x0 + x1) // 2 - size // 2, (y0 + y1) // 2 - size // 2, size)


def on_paper(rgb, drawn):
    """A drawing over the palette's paper colour."""
    out = np.empty(rgb.shape, np.uint8)
    out[:] = np.round(pal("ink", "paper")).astype(np.uint8)
    out[drawn] = rgb[drawn]
    return out


def write_paint_inputs(C: Cutaways, name, folder: Path):
    """The inputs of the later paid painting of one landmark: the unlit render of the cut model alone (flat albedo,
    no light, nothing that moves), the opening mask (the section and the inside faces: where a painted interior
    may go), the whole landmark's silhouette, the geometry behind every pixel, and the frame."""
    from PIL import Image
    folder.mkdir(parents=True, exist_ok=True)
    f = C.paint_frame(name)
    c = C.cut(name, f, others=False, painted=False)               # the painter's input is always the placeholder
    drawn = np.isfinite(c["depth"])
    mask = np.isin(c["k"], OPENING)
    Image.fromarray(on_paper(c["rgb"], drawn)).save(folder / f"{name}.unlit.png")
    Image.fromarray((mask * 255).astype(np.uint8)).save(folder / f"{name}.mask.png")
    Image.fromarray((c["outline"] * 255).astype(np.uint8)).save(folder / f"{name}.outline.png")
    np.savez_compressed(folder / f"{name}.geom.npz", ids=c["ids"], k=c["k"], normal=c["normal"].astype(np.float16),
                        depth=np.where(drawn, c["depth"], 1e9).astype(np.float32))
    lm = C.cuts["landmarks"][name]
    yy, xx = np.nonzero(mask)
    meta = {"landmark": name, "name": lm["name"], "slug": lm["slug"], "buildings": lm["buildings"],
            "frame_px": [f.px0, f.py0, f.size, f.size], "mpp": 0.125, "zoom": 0,
            "about": "frame_px = x0, y0, width, height in v2 map pixels at zoom 0; one image pixel per map pixel",
            "opening_px": int(mask.sum()), "outline_px": int(c["outline"].sum()),
            "opening_bbox": [int(xx.min()), int(yy.min()), int(xx.max()) + 1, int(yy.max()) + 1] if len(xx) else None,
            "k": KIND, "opening_k": list(OPENING), "classes": CUT_CLASS, "planes": lm["planes"], "floor_z": lm["floor_z"],
            "files": {"unlit": f"{name}.unlit.png", "mask": f"{name}.mask.png", "outline": f"{name}.outline.png",
                      "geom": f"{name}.geom.npz"}}
    (folder / f"{name}.json").write_text(json.dumps(meta, indent=1))
    return meta


def write_preview(C: Cutaways, name, path: Path, max_bytes=1_000_000):
    """The whole landmark beside the cut one (both alone, unlit albedo, on paper): a JPEG under max_bytes."""
    from PIL import Image
    x0, y0, x1, y1 = C.model(name)["bbox_px"]
    size = max(x1 - x0, y1 - y0) + 48
    f = Frame((x0 + x1) // 2 - size // 2, (y0 + y1) // 2 - size // 2, size)
    w = C.whole(name, f)
    c = C.cut(name, f, others=False)
    a = on_paper(w.rgb, np.isfinite(w.depth))
    b = on_paper(c["rgb"], np.isfinite(c["depth"]))
    gap = np.empty((size, 16, 3), np.uint8)
    gap[:] = np.round(pal("ink", "paper")).astype(np.uint8)
    im = Image.fromarray(np.concatenate([a, gap, b], 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    for q in range(90, 40, -5):
        im.save(path, "JPEG", quality=q, optimize=True)
        if path.stat().st_size < max_bytes:
            break
    return {"file": path.name, "bytes": path.stat().st_size, "size_px": list(im.size)}


def layer_cutaways(ctx):
    """Build stage: per landmark of cutaways.json a tile set in the release's tile coding (colour, depth and normal,
    k = what each pixel is, ids), the paint inputs and a preview; index.json lists them."""
    from v2.layers.tiles import levels_for, pyramid
    sc = Scene(ctx.dep("scene"))
    C = Cutaways(sc, ctx.params)
    miss = C.missing()
    if miss:
        raise RuntimeError(f"landmarks of cutaways.json not in the scene of area {ctx.area}: {miss}")
    levels = levels_for(sc.tiles)
    index = {"layer": "cutaways", "tile_px": TILE, "files": ["c.webp", "g.bin", "k.bin", "i.bin"], "k": KIND,
             "opening_k": list(OPENING), "classes": CUT_CLASS, "above_layer": "buildings", "params": C.P,
             "note": "the cut and inside faces are a code placeholder interior (flat palette colours), or the "
                     "landmark's painted interior where \"interior\" says so", "landmarks": {}}
    summary = {}
    for name, lm in C.cuts["landmarks"].items():
        m = C.model(name)
        folder = ctx.out / "tiles" / name
        idx0, px = {}, {k: 0 for k in KIND}
        got = [0, 0]
        for t in C.tiles(name):
            c = C.cut(name, t)
            if "painted" in c:
                on = np.isin(t.crop(c["k"]), OPENING)
                got[0] += int(on.sum())
                got[1] += int((on & ~t.crop(c["painted"])).sum())
            depth = t.crop(c["depth"])
            if not np.isfinite(depth).any():
                continue
            k = t.crop(c["k"])
            idx0[t.name] = write_tile(folder / "0", t.name, rgb=t.crop(c["rgb"]), depth=depth, normal=t.crop(c["normal"]),
                                      k=k, ids=t.crop(c["ids"]), q=101)
            for kn, kv in KIND.items():
                px[kn] += int((k == kv).sum())
        if got[1]:
            raise RuntimeError(f"{name}: the painting leaves {got[1]} of the tiles' {got[0]} opening pixels unpainted "
                               f"(it was made for another cut or frame)")
        idx = pyramid(folder, idx0, levels, lossless=True, has_k=True, has_ids=True)
        paint = write_paint_inputs(C, name, ctx.out / "paint")
        prev = write_preview(C, name, ctx.out / "previews" / f"{ctx.area}_cutaway_{name}_placeholder.jpg")
        index["landmarks"][name] = {
            "name": lm["name"], "slug": lm["slug"], "replaces": lm["buildings"], "replaces_index": m["own"],
            "planes": lm["planes"], "floor_z": lm["floor_z"], "bbox_px": m["bbox_px"], "levels": max(idx),
            "tiles": {str(z): v for z, v in idx.items()}, "pixels": px,
            "interior": ({"kind": "painted", "pixels": got[0], **{k: v for k, v in C.painting(name)["meta"].items()
                                                                  if k in ("job", "candidate", "seed", "sha256")}}
                         if C.painting(name) else {"kind": "placeholder"}),
            "paint": {"frame_px": paint["frame_px"], "files": paint["files"], "opening_px": paint["opening_px"]},
            "preview": prev["file"], "model": {str(k): v for k, v in m["stats"].items()}}
        summary[name] = {"tiles_z0": len(idx0), "pixels": px, "interior": index["landmarks"][name]["interior"]["kind"],
                         "paint_frame_px": paint["frame_px"][2:],
                         "preview_bytes": prev["bytes"]}
        ctx.log(name, summary[name])
    ctx.write_json("tiles/index.json", index)
    return {"landmarks": summary, "levels": levels}
