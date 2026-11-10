"""Checks K0-K6 of the landmark cutaways (spec: v2/docs/specs/landmark-cutaways.md), on the built cutaway tiles.

The checks do not use the layer's own meshes. They read the tiles as the viewer will, and compare them with the
model worked out here a second time, from the scene's raw ACT triangles and footprints, cutaways.json and the
thickness rule (params.json g3 cutaway_*): a point of space is inside the building (over its footprint, under its
roof), in the removed slice, in the hollow inside, or in the kept material.

K0    the buildings listed for each landmark are the scene's buildings at the landmark's place
K1    the cut matches the 3D model: the line score of brief 6 (line_checks.score) on the model's section along the
      slice's faces (every raw roof and wall triangle cut by the face, sampled every 0.25 m): a drawn line within
      1 px over >= 95% of the seen length; 0 cut or inside pixels outside the whole model's outline
K2    the interior stays inside the cut: 0 interior pixels outside the opening mask (the k tile), >= 99.5% of it
      covered (`interior_in_mask`: today the placeholder's pixels, later a painting's). The mask itself is held to
      the model: every mask pixel is an inside face or a section of the model (its drawn point on the kept
      material's surface towards the hollow inside, or on a face of the slice, within 1 cm): 0 are not; and
      >= 99.5% of the pixels the model says are surely of the opening are in the mask
      (the last section pixel and the outside wall's pixel beside it are both within 1 cm of the outside: neither
      is asked for). The paint input's mask holds every opening pixel of the tiles, at the same depth
K3    no baked shadows in the interior: per kind of face, the median luminance of faces turned different ways,
      and of faces turned to and away from the photo's sun, within 5% (`flat_interior`, as the bake-off's
      flat-light check). The opening's own cast shadow moving with ?hour belongs to the viewer step
K4    no cars or people: the OWLv2 detector (owl_detect.py, run as check_no_cars runs it: its own environment, the
      local model, offline, $0) on every paint input and on every landmark's cutaway tiles put together, once for
      vehicles and once for "a person", "people": 0 detections at 0.1. About 20 s for the three landmarks, so it
      runs by default (cutaway_detector_run). The reference photos and the paintings join the list when they exist
K5    depth: every cut pixel lies on a face of the slice (analytic, <= 1 cm); every cut and inside pixel lies on
      the model's surface (kept material and free space both within 1 cm of the drawn point); the kept outside
      has layer 5's depth (<= 1 cm) wherever layer 5 shows the same surface. Vehicles and labels: the viewer step
K6    off means off, for the tiles: the cutaway is a layer of its own (no stage writes into layer 5), and it holds
      nothing where layer 5 shows a building it does not replace in front of it. The viewer's toggle: later
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
from pathlib import Path

import numpy as np
import shapely
from PIL import Image
from shapely.geometry import Polygon

from v2.checks.framework import Report
from v2.config import REPO
from v2.layers.common import CLASS, TILE, Scene, lum, project, read_tile, unproject
from v2.layers.raster import raster_tris

EPS_M = 0.01                                                     # K5's 1 cm
MASK_PROBE_M = 0.07                                              # K2: past the 5 cm a window stands off its wall


# ------------------------------------------------------------------------------------------------ the model, again
class Model:
    """A landmark's cut model as point tests, from the scene's raw data (not from the layer's meshes)."""

    def __init__(self, scene: Scene, lm: dict, P: dict):
        self.P, self.lm = P, lm
        self.floor_z = float(lm["floor_z"])
        bidx = {b["id"]: i for i, b in enumerate(scene.buildings)}
        self.idx = [bidx[i] for i in lm["buildings"]]
        m = scene.mesh
        V = m["verts"].astype(np.float64) + np.array([float(m["origin_en"][0]), float(m["origin_en"][1]), 0.0])
        self.parts = []
        for bi in self.idx:
            info = scene.buildings[bi]
            F = shapely.unary_union([Polygon(p[0], p[1:]).buffer(0) for p in info["footprint"] if p and len(p[0]) >= 4])
            sel = m["tri_bld"] == bi
            tri = {k: V[m["tris"][sel & (m["tri_kind"] == k)].astype(np.int64)] for k in (1, 2, 3)}
            # the hollow's plan: the footprint less the walls' thickness, less what stands under a steep roof
            Fin = F.buffer(-P["cutaway_wall_m"], join_style="mitre")
            nz = np.cross(tri[1][:, 1] - tri[1][:, 0], tri[1][:, 2] - tri[1][:, 0])
            slope = np.degrees(np.arctan2(np.hypot(nz[:, 0], nz[:, 1]), np.abs(nz[:, 2])))
            steep = [Polygon(t[:, :2]) for t, a in zip(tri[1], slope) if a > P["cutaway_solid_roof_deg"] and a < 89.999]
            if steep:
                Fin = Fin.difference(shapely.unary_union([g for g in steep if g.area > 1e-6]))
            self.parts.append({"bi": bi, "F": F, "Fin": Fin, "roof": tri[1], "wall": tri[2], "inst": tri[3],
                               "ground_z": float(info["ground_z"])})
        self.open = shapely.unary_union([Polygon(r) for r in lm["open_to_roof"]]) if lm.get("open_to_roof") else None
        self.half = []
        for p in lm["planes"]:
            o, n = np.array(p["origin"], float), np.array(p["normal"], float)
            n = n / np.linalg.norm(n)
            t = np.array([-n[1], n[0]])
            self.half.append({"n": n, "t": t, "c": float(n @ o), "t0": float(t @ o + p["extent"][0]),
                              "t1": float(t @ o + p["extent"][1])})

    @staticmethod
    def top(roof, e, n):
        """Height of the highest roof triangle over each point (-inf where none)."""
        out = np.full(e.shape, -np.inf)
        order = np.argsort(e)
        es = e[order]
        for r in roof:
            (ax, ay, az), (bx, by, bz), (cx, cy, cz) = r
            det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(det) < 1e-9:
                continue
            i0, i1 = np.searchsorted(es, [min(ax, bx, cx) - 1e-6, max(ax, bx, cx) + 1e-6])
            if i1 <= i0:
                continue
            j = order[i0:i1]
            x, y = e[j], n[j]
            l0 = ((by - cy) * (x - cx) + (cx - bx) * (y - cy)) / det
            l1 = ((cy - ay) * (x - cx) + (ax - cx) * (y - cy)) / det
            l2 = 1 - l0 - l1
            ins = (l0 >= -1e-9) & (l1 >= -1e-9) & (l2 >= -1e-9)
            z = l0 * az + l1 * bz + l2 * cz
            jj = j[ins]
            out[jj] = np.maximum(out[jj], z[ins])
        return out

    def removed(self, e, n, z):
        m = z > self.floor_z
        for h in self.half:
            s = h["t"][0] * e + h["t"][1] * n
            m &= (h["n"][0] * e + h["n"][1] * n > h["c"]) & (s > h["t0"]) & (s < h["t1"])
        return m

    def classify(self, e, n, z):
        """Per point: (inside the whole building, in the removed slice, in the hollow inside, in the kept material)."""
        e, n, z = (np.asarray(v, np.float64) for v in (e, n, z))
        solid = np.zeros(e.shape, bool)
        hollow = np.zeros(e.shape, bool)
        tr, ts = self.P["cutaway_roof_m"], self.P["cutaway_slab_m"]
        for p in self.parts:
            inF = shapely.contains_xy(p["F"], e, n)
            if not inF.any():
                continue
            top = np.full(e.shape, -np.inf)
            top[inF] = self.top(p["roof"], e[inF], n[inF])
            s = inF & (z < top)
            solid |= s
            room = s & (z > self.floor_z) & (z < top - tr)
            if room.any():
                room[room] = shapely.contains_xy(p["Fin"], e[room], n[room])
            if self.lm.get("floors", True) and room.any():
                h = p["ground_z"] + self.P["ground_floor_m"]
                slab = np.zeros(e.shape, bool)
                while h < z.max() + ts:
                    if h >= self.floor_z + self.P["cutaway_min_storey_m"]:
                        slab |= (z >= h - ts) & (z <= h)
                    h += self.P["floor_m"]
                slab &= room
                if self.open is not None and slab.any():
                    slab[slab] = ~shapely.contains_xy(self.open, e[slab], n[slab])
                room &= ~slab
            hollow |= room
        gone = self.removed(e, n, z) & solid
        return solid, gone, hollow & ~gone, solid & ~gone & ~hollow

    def near(self, surf, nrm, r=EPS_M, only=None):
        """What lies within r of each drawn point (n, 3): the model at the point, at 26 points r from it (along the
        axes and their diagonals) and at r and r / 10 either way along its drawn normal. Dict of (n,) bools: "kept"
        (kept material), "free" (anything else), "solid" (inside the whole building), "outside" (outside it),
        "hollow", "gone", "slice" (in the slice's space)."""
        out = {k: np.zeros(len(surf), bool) for k in ("kept", "free", "solid", "outside", "hollow", "gone", "slice")}
        g = np.array([[i, j, k] for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1)], float)
        g = g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1.0) * r
        for d in list(g) + [nrm * r, -nrm * r, nrm * r / 10, -nrm * r / 10]:
            q = surf + d
            out["slice"] |= self.removed(q[:, 0], q[:, 1], q[:, 2])
            if only == "slice":
                continue
            solid, gone, hollow, kept = self.classify(q[:, 0], q[:, 1], q[:, 2])
            out["kept"] |= kept
            out["free"] |= ~kept
            out["solid"] |= solid
            out["outside"] |= ~solid
            out["hollow"] |= hollow
            out["gone"] |= gone
        return out

    def opening(self, px, py, depth, surf, nrm, near):
        """The opening from the model, per drawn pixel: (possible, sure). A pixel may be of the opening when its
        drawn point is on the kept material's surface (material within 1 cm) towards the hollow inside (hollow
        within 1 cm), or on a face of the slice (within 1 cm, the slice's space within 1 cm): an inside face, a
        section; or when the space MASK_PROBE_M in front of it, along its normal, was inside the building: the
        inside of a wall that has no thickness. (Not 1 cm in front: windows and doors are decals 5 cm off their
        wall, on either side of it.) It is surely of the opening when, besides, the open air outside the building
        is not within 1 cm of it: at the rim of a section, where it meets the building's outside, the pixel next to
        the last section pixel is the outside wall's, and 1 cm cannot tell them apart."""
        q = surf + nrm * MASK_PROBE_M
        _, gone, hollow, _ = self.classify(q[:, 0], q[:, 1], q[:, 2])
        on_face = self.face_depth_error(px, py, depth) <= EPS_M
        front = gone | hollow
        on_it = near["kept"] & (near["hollow"] | (on_face & near["slice"]))
        return front | on_it, front | (on_it & ~near["outside"])

    def faces(self):
        """The slice's vertical faces as plan segments (p, q, normal into the slice), from the planes' data: each
        plane's own stretch, and the stretches that close the slice where a plane's extent ends."""
        from shapely.geometry import box
        from shapely.ops import unary_union
        b = unary_union([p["F"] for p in self.parts]).buffer(20).bounds
        poly = box(*b)
        big = 1e4
        for h in self.half:
            n, t = h["n"], h["t"]
            o = n * h["c"]
            a, c = o + t * (h["t0"] - t @ o), o + t * (h["t1"] - t @ o)
            poly = poly.intersection(Polygon([a, c, c + n * big, a + n * big]))
        if poly.is_empty:
            return []
        out = []
        ring = np.array(shapely.geometry.polygon.orient(poly).exterior.coords)
        for p, q in zip(ring[:-1], ring[1:]):
            mid = (p + q) / 2
            if min(mid[0] - b[0], b[2] - mid[0], mid[1] - b[1], b[3] - mid[1]) < 1e-6 or np.linalg.norm(q - p) < 1e-6:
                continue                                         # on the bounding box, not a face of the slice
            d = (q - p) / np.linalg.norm(q - p)
            out.append((p, q, np.array([-d[1], d[0]])))          # counter-clockwise ring: the inside is on the left
        return out

    def section_lines(self):
        """The model's section along the slice's faces: where each raw roof and wall triangle meets a face, above
        the floor. Returns (A, B, building index) segment ends in 3D."""
        A, B, O = [], [], []
        for p, q, n in self.faces():
            L = np.linalg.norm(q - p)
            t = (q - p) / L
            for part in self.parts:
                tri = np.concatenate([part["roof"], part["wall"]])
                d = (tri[..., :2] - p) @ n                        # signed distance of each corner from the face
                cross = (d.min(1) < -1e-9) & (d.max(1) > 1e-9)
                for T_, D_ in zip(tri[cross], d[cross]):
                    pts = []
                    for i in range(3):
                        a, b_, da, db = T_[i], T_[(i + 1) % 3], D_[i], D_[(i + 1) % 3]
                        if (da < 0) != (db < 0):
                            pts.append(a + (b_ - a) * (da / (da - db)))
                    if len(pts) != 2:
                        continue
                    a, b_ = pts
                    # keep the stretch on the face (0..L along it) and above the floor
                    lo, hi = 0.0, 1.0
                    for f0, f1, mn, mx in (((a[:2] - p) @ t, (b_[:2] - p) @ t, 0.0, L), (a[2], b_[2], self.floor_z, np.inf)):
                        if abs(f1 - f0) < 1e-12:
                            if not (mn <= f0 <= mx):
                                lo, hi = 1.0, 0.0
                            continue
                        u0, u1 = sorted(((mn - f0) / (f1 - f0), (mx - f0) / (f1 - f0)))
                        lo, hi = max(lo, u0), min(hi, u1)
                    if hi - lo > 1e-9:
                        A.append(a + (b_ - a) * lo)
                        B.append(a + (b_ - a) * hi)
                        O.append(part["bi"])
        return np.array(A, float).reshape(-1, 3), np.array(B, float).reshape(-1, 3), np.array(O, np.int64)

    def face_depth_error(self, px, py, depth):
        """For pixels drawn as cut faces: the distance (m, along the view ray) from the drawn depth to the nearest
        face of the slice (its vertical faces and the floor's level)."""
        e0, n0, z0 = unproject(px, py, np.zeros(len(px)))
        e1, n1, z1 = unproject(px, py, np.ones(len(px)))
        ve, vn, vz = e1 - e0, n1 - n0, z1 - z0
        err = np.abs((self.floor_z - z0) / vz - depth)
        for p, q, n in self.faces():
            den = n[0] * ve + n[1] * vn
            ok = np.abs(den) > 1e-9
            d = np.where(ok, (n @ p - n[0] * e0 - n[1] * n0) / np.where(ok, den, 1.0), np.inf)
            err = np.minimum(err, np.abs(d - depth))
        return err


# ------------------------------------------------------------------------------------------------ tiles
class CutTiles:
    """One landmark's cutaway tiles (zoom 0), as the tile cache line_checks.score reads."""

    def __init__(self, folder: Path, tiles: dict):
        self.folder, self.tiles, self.c = Path(folder) / "0", tiles, {}

    def get(self, tx, ty):
        k = f"{tx}_{ty}"
        if k not in self.c:
            self.c[k] = read_tile(self.folder, k, self.tiles[k]) if k in self.tiles else None
        return self.c[k]

    def pixels(self):
        """Every drawn pixel of the landmark: dict of flat arrays px, py (centres), depth, k, ids, rgb, normal."""
        out = {k: [] for k in ("px", "py", "depth", "k", "ids", "rgb", "normal", "tile")}
        for ti, name in enumerate(sorted(self.tiles)):
            tx, ty = (int(v) for v in name.split("_"))
            t = self.get(tx, ty)
            r, c = np.nonzero(np.isfinite(t["depth"]))
            out["px"].append(tx * TILE + c + 0.5)
            out["py"].append(ty * TILE + r + 0.5)
            out["tile"].append(np.full(len(r), ti))
            for k in ("depth", "k", "ids", "rgb", "normal"):
                out[k].append(t[k][r, c])
        return {k: np.concatenate(v) for k, v in out.items()}


def layer_at(folder: Path, index: dict, px, py):
    """A built layer's zoom-0 tiles at pixel centres: (depth, ids or None); inf / 0 where it has nothing."""
    depth = np.full(len(px), np.inf)
    ids = np.zeros(len(px), np.uint32)
    tx, ty = np.floor(px / TILE).astype(int), np.floor(py / TILE).astype(int)
    for kx, ky in set(zip(tx.tolist(), ty.tolist())):
        name = f"{kx}_{ky}"
        if name not in index["tiles"]["0"]:
            continue
        t = read_tile(Path(folder) / "0", name, index["tiles"]["0"][name])
        m = (tx == kx) & (ty == ky)
        r, c = np.floor(py[m]).astype(int) - ky * TILE, np.floor(px[m]).astype(int) - kx * TILE
        depth[m] = t["depth"][r, c]
        if "ids" in t:
            ids[m] = t["ids"][r, c]
    return depth, ids


# ------------------------------------------------------------------------------------------------ K2, K3
def interior_in_mask(interior, mask):
    """K2 for any interior: (interior pixels outside the opening's mask, share of the mask covered)."""
    interior, mask = np.asarray(interior, bool), np.asarray(mask, bool)
    return int((interior & ~mask).sum()), float((interior & mask).sum() / max(int(mask.sum()), 1))


def flat_interior(rgb, material, normal, sun=None, min_px=150, edge=None):
    """K3's shadow detector on an interior. rgb (n, 3), material (n,) (a kind of face; 0 = not interior), normal
    (n, 3), all for pixels away from edges (`edge` (n,) bool marks pixels to leave out: ink lines are the drawing,
    not light). Per material: the median luminance of its faces turned different ways (octants of the normal's
    compass direction, and up) may differ by a share `worst`; with a sun vector, also sunlit against turned away.
    Returns {material: {"sides": k, "worst": share, "sun": share or None}}."""
    L = lum(np.asarray(rgb, float))
    ok = (material > 0) if edge is None else (material > 0) & ~edge
    h = np.hypot(normal[:, 0], normal[:, 1])
    side = np.where(h < 0.3, 8, (np.round(np.degrees(np.arctan2(normal[:, 0], normal[:, 1])) / 45) % 8)).astype(int)
    out = {}
    for m in np.unique(material[ok]):
        mm = ok & (material == m)
        meds = [float(np.median(L[mm & (side == s)])) for s in range(9) if (mm & (side == s)).sum() >= min_px]
        r = {"sides": len(meds), "worst": (max(meds) - min(meds)) / max(max(meds), 1e-6) if len(meds) > 1 else 0.0,
             "sun": None}
        if sun is not None:
            lit, away = mm & (normal @ sun > 0.05), mm & (normal @ sun < -0.05)
            if lit.sum() >= min_px and away.sum() >= min_px:
                r["sun"] = abs(float(np.median(L[away])) / max(float(np.median(L[lit])), 1e-6) - 1)
        out[int(m)] = r
    return out


def edges_of(tile, reach=2):
    """Pixels of a decoded tile within `reach` px of a change of kind, id, facing or a step in depth (as L5.1)."""
    from scipy import ndimage
    ok = np.isfinite(tile["depth"])
    key = tile["ids"].astype(np.int64) * 16 + tile["k"]
    dd = np.where(ok, tile["depth"], 1e9)
    nz = np.round(tile["normal"] * 20)
    edge = np.zeros(ok.shape, bool)
    for a, b in (((slice(None), slice(None, -1)), (slice(None), slice(1, None))),
                 ((slice(None, -1), slice(None)), (slice(1, None), slice(None)))):
        ch = (key[a] != key[b]) | (np.abs(dd[a] - dd[b]) > 0.5) | (nz[a] != nz[b]).any(-1) | (ok[a] != ok[b])
        edge[a] |= ch
        edge[b] |= ch
    return ndimage.binary_dilation(edge, iterations=reach)


# ------------------------------------------------------------------------------------------------ K4
def detector_jobs(cut_folder: Path, index: dict, out: Path) -> list:
    """Every image the detector must see: each landmark's paint input, and its cutaway tiles put together over
    paper (written to `out`; the detector skips a tile that is nine tenths empty, and a landmark's tiles mostly are)."""
    from PIL import Image
    from v2.layers.common import pal
    jobs = []
    for name, lm in index["landmarks"].items():
        jobs.append({"layer": "cutaway-input", "path": str(cut_folder / "paint" / lm["paint"]["files"]["unlit"]),
                     "tile": f"{name}.unlit"})
        tiles = CutTiles(cut_folder / "tiles" / name, lm["tiles"]["0"])
        xs = [int(t.split("_")[0]) for t in lm["tiles"]["0"]]
        ys = [int(t.split("_")[1]) for t in lm["tiles"]["0"]]
        im = np.empty(((max(ys) - min(ys) + 1) * TILE, (max(xs) - min(xs) + 1) * TILE, 3), np.uint8)
        im[:] = np.round(pal("ink", "paper")).astype(np.uint8)
        for t in lm["tiles"]["0"]:
            tx, ty = (int(v) for v in t.split("_"))
            d = tiles.get(tx, ty)
            sub = im[(ty - min(ys)) * TILE:(ty - min(ys) + 1) * TILE, (tx - min(xs)) * TILE:(tx - min(xs) + 1) * TILE]
            sub[np.isfinite(d["depth"])] = d["rgb"][np.isfinite(d["depth"])]
        Image.fromarray(im).save(out / f"owl_{name}.png")
        jobs.append({"layer": "cutaway", "path": str(out / f"owl_{name}.png"), "tile": f"{name}.tiles"})
    return jobs


def run_detector(jobs, out: Path, tag, queries, threshold, box_m) -> dict:
    """The OWLv2 detector as check_no_cars runs it (its own environment, the local model cache, offline)."""
    spec = {"jobs": jobs, "queries": queries, "queries_water": [], "threshold": threshold, "box_m": box_m,
            "mpp": 0.125, "out": str(out / f"owl_{tag}.json")}
    (out / f"owl_jobs_{tag}.json").write_text(json.dumps(spec))
    cmd = ["uv", "run", "--offline", "--no-project", "--with", "torch", "--with", "transformers", "--with", "pillow",
           "--with", "numpy", "python", "-I", str(REPO / "v2" / "checks" / "owl_detect.py"), str(out / f"owl_jobs_{tag}.json")]
    r = subprocess.run(cmd, capture_output=True, text=True, env=dict(os.environ, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1"))
    if r.returncode:
        raise RuntimeError("detector failed: " + r.stderr[-3000:])
    return json.loads((out / f"owl_{tag}.json").read_text())


# ------------------------------------------------------------------------------------------------ the stage
def check_cutaways(ctx):
    from v2.checks import line_checks as lic
    from v2.layers import cutaways as cw
    from v2.layers.light import sun_vector
    P = ctx.params
    g1 = P["g1"]
    cut_folder = ctx.dep("layer_cutaways")
    index = json.loads((cut_folder / "tiles" / "index.json").read_text())
    sc = Scene(ctx.dep("scene"))
    cuts = cw.load_cuts()
    rep = Report("cutaways")
    b5 = ctx.dep("layer_buildings") / "tiles"
    i5 = json.loads((b5 / "index.json").read_text())
    g_dir = ctx.dep("layer_ground") / "tiles"
    gi = json.loads((g_dir / "index.json").read_text())
    _, _, sun = sun_vector(dt.datetime.fromisoformat(g1["shadow_photo_sun"]))
    interior_k = list(index["opening_k"])
    K = index["k"]
    bidx = {b["id"]: i for i, b in enumerate(sc.buildings)}
    for name, lm in cuts["landmarks"].items():
        built = index["landmarks"].get(name)
        # ---------------------------------------------------------------- K0
        at = cw.place_buildings(sc, lm["slug"], lm["place_max_m"])
        rep.add(f"K0-{name}", f"{lm['name']}: the listed buildings are the scene's at the landmark's place "
                f"(within {lm['place_max_m']} m)", built is not None and [a[0] for a in at] == lm["buildings"],
                {"listed": lm["buildings"], "at_place": at})
        if built is None or any(b not in bidx for b in lm["buildings"]):
            continue
        M = Model(sc, lm, P)
        tiles = CutTiles(cut_folder / "tiles" / name, built["tiles"]["0"])
        px = tiles.pixels()
        k = px["k"]
        opening = np.isin(k, interior_k)                              # the opening mask, as the k tile holds it
        # ---------------------------------------------------------------- K1
        A, B, O = M.section_lines()
        Ps, Ds, Os = lic.samples(A, B, O)
        seen, on = lic.score(tiles, Ps, Ds, P["cutaway_line_px"], P["cutaway_line_min_step"], obj=Os)
        n = int(seen.sum())
        bad = np.flatnonzero(seen & ~on)
        ex = [{"e": round(float(Ps[i, 0]), 2), "n": round(float(Ps[i, 1]), 2), "z": round(float(Ps[i, 2]), 2)}
              for i in bad[:: max(len(bad) // 8, 1)][:8]]
        rep.at_least(f"K1a-{name}", f"{lm['name']}: the cut's outline on the model's section: share of {n} seen samples "
                     f"(every 0.25 m of {float(np.linalg.norm(B - A, axis=1).sum()):.0f} m of section, {len(Ps)} samples) "
                     f"with a drawn line within {P['cutaway_line_px']} px", round(float(on.sum() / max(n, 1)), 4),
                     P["cutaway_line_share"], ex)
        rep.at_least(f"K1a-n-{name}", f"{lm['name']}: section samples seen (the score needs some)", n, 20)
        outside = 0
        for tname in sorted(built["tiles"]["0"]):
            tx, ty = (int(v) for v in tname.split("_"))
            t = tiles.get(tx, ty)
            zb = np.full((TILE, TILE), np.inf)
            tb = np.full((TILE, TILE), -1, np.int64)
            for part in M.parts:
                tri = np.concatenate([part["roof"], part["wall"]]).reshape(-1, 3)
                qx, qy, qd = project(tri[:, 0], tri[:, 1], tri[:, 2])
                raster_tris(np.column_stack([qx - tx * TILE, qy - ty * TILE]), qd, np.arange(len(tri)).reshape(-1, 3),
                            TILE, TILE, zb, tb)
            outside += int((np.isin(t["k"], interior_k) & ~np.isfinite(zb)).sum())
        rep.at_most(f"K1b-{name}", f"{lm['name']}: cut and inside pixels outside the whole model's outline (its raw "
                    f"roofs and walls, 0 px growth; of {int(opening.sum())})", outside, P["cutaway_outside_px"])
        # ---------------------------------------------------------------- the model at every drawn pixel
        surf = np.column_stack(unproject(px["px"], px["py"], px["depth"]))
        nrm = px["normal"]
        near = M.near(surf, nrm)
        # ---------------------------------------------------------------- K2
        placeholder = np.isin(px["ids"] & 255, list(index["classes"].values()))   # the interior that is drawn
        out_px, cover = interior_in_mask(placeholder, opening)
        rep.at_most(f"K2a-{name}", f"{lm['name']}: placeholder interior pixels outside the opening mask (the k tile: "
                    f"{int(opening.sum())} px)", out_px, 0)
        rep.at_least(f"K2b-{name}", f"{lm['name']}: share of the opening mask covered by the interior",
                     round(cover, 5), P["cutaway_mask_cover"])
        possible, sure = M.opening(px["px"], px["py"], px["depth"], surf, nrm, near)
        out_px, _ = interior_in_mask(opening, possible)
        _, cover = interior_in_mask(opening, sure)
        rep.at_most(f"K2c-{name}", f"{lm['name']}: opening mask pixels that the model does not allow (not an inside "
                    f"face or a section of the model within 1 cm)", out_px, 0)
        rep.at_least(f"K2d-{name}", f"{lm['name']}: share of the model's own opening in the mask ({int(sure.sum())} px "
                     f"that are surely of it; {int((possible & ~sure).sum())} more within 1 cm of the outside)",
                     round(cover, 5), P["cutaway_mask_cover"])
        # the paint input is the same model alone: every opening pixel of the tiles is in its mask, at its depth
        fx, fy, fw, fh = built["paint"]["frame_px"]
        pm = np.asarray(Image.open(cut_folder / "paint" / built["paint"]["files"]["mask"])) > 127
        pd = np.load(cut_folder / "paint" / built["paint"]["files"]["geom"])["depth"]
        ci, ri = (px["px"][opening] - fx).astype(int), (px["py"][opening] - fy).astype(int)
        inf = (ci >= 0) & (ci < fw) & (ri >= 0) & (ri < fh)
        ok_e = np.zeros(len(ci), bool)
        ok_e[inf] = pm[ri[inf], ci[inf]] & (np.abs(pd[ri[inf], ci[inf]] - px["depth"][opening][inf]) <= P["cutaway_depth_cm"] / 100)
        rep.at_most(f"K2e-{name}", f"{lm['name']}: opening pixels of the tiles that are not in the paint input's mask at "
                    f"the same depth (the paint input: the cut model alone, {fw} x {fh} px, {int(pm.sum())} px of opening)",
                    int((~ok_e).sum()), 0)
        # ---------------------------------------------------------------- K3
        edge = np.zeros(len(k), bool)
        for ti, tname in enumerate(sorted(built["tiles"]["0"])):
            tx, ty = (int(v) for v in tname.split("_"))
            t = tiles.get(tx, ty)
            r, c = np.nonzero(np.isfinite(t["depth"]))
            edge[px["tile"] == ti] = edges_of(t)[r, c]
        fl = flat_interior(px["rgb"], np.where(opening, k, 0), px["normal"], sun, P["cutaway_shadow_min_px"], edge)
        names = {v: kk for kk, v in K.items()}
        worst = max([max(v["worst"], v["sun"] or 0.0) for v in fl.values()] or [0.0])
        rep.at_most(f"K3-{name}", f"{lm['name']}: placeholder interior, largest difference in median luminance between "
                    f"faces of one kind turned different ways, or to and away from the photo's sun "
                    f"({g1['shadow_photo_sun']})", round(worst, 4), P["cutaway_shadow_lum_tol"],
                    [{names[m]: {a: (round(b, 4) if isinstance(b, float) else b) for a, b in v.items()}} for m, v in fl.items()])
        # ---------------------------------------------------------------- K5
        cutpx = k == K["cut"]
        err = M.face_depth_error(px["px"][cutpx], px["py"][cutpx], px["depth"][cutpx]) if cutpx.any() else np.zeros(1)
        rep.at_most(f"K5a-{name}", f"{lm['name']}: cut pixels, largest distance of the depth from the slice's faces "
                    f"(cm, {int(cutpx.sum())} px)", round(float(err.max()) * 100, 3), P["cutaway_depth_cm"])
        # a wall standing on a lower roof has no thickness (ACT's one surface): the room on one side of it, the open
        # air on the other
        thin = opening & (k == K["inside_wall"]) & near["hollow"] & near["outside"] & ~near["kept"]
        off = opening & ~((near["kept"] & near["free"]) | thin)
        rep.at_most(f"K5b-{name}", f"{lm['name']}: cut and inside pixels not on the model's surface within 1 cm (kept "
                    f"material and free space both within 1 cm of the drawn point; of {int(opening.sum())})",
                    int(off.sum()), 0,
                    [{"px": [float(px['px'][i]), float(px['py'][i])], "k": names[int(k[i])]} for i in np.flatnonzero(off)[:8]])
        rep.info(f"K5b-thin-{name}", f"{lm['name']}: of those on it, inside-wall pixels on a wall with no thickness (a "
                 "wall standing on a lower roof)", int(thin.sum()))
        own = k == K["outside"]
        d5, id5 = layer_at(b5, i5, px["px"], px["py"])
        same = own & (id5 == px["ids"])
        dz = np.abs(d5 - px["depth"])
        # layer 5's surface there is in the slice (or on its face): the cut shows what was behind it
        s5 = np.column_stack(unproject(px["px"], px["py"], np.where(np.isfinite(d5), d5, 0.0)))
        shown_gone = M.near(s5, nrm, only="slice")["slice"]
        differs = same & (dz > P["cutaway_depth_cm"] / 100) & ~shown_gone
        rep.at_most(f"K5c-{name}", f"{lm['name']}: kept outside pixels whose depth differs from layer 5's by more than "
                    f"{P['cutaway_depth_cm']} cm where layer 5 shows the same surface (of {int((same & ~shown_gone).sum())} compared)",
                    int(differs.sum()), 0)
        cmp_ = same & ~shown_gone
        rep.info(f"K5c-max-{name}", f"{lm['name']}: largest such difference (cm)",
                 round(float(dz[cmp_].max()) * 100, 3) if cmp_.any() else 0.0)
        # kept outside surfaces the slice brought to view: on the building's own surface
        newly = own & ~cmp_ & np.isin(px["ids"] & 255, [CLASS["building"], CLASS["roof"]])
        off_new = newly & ~(near["solid"] & near["outside"])
        rep.info(f"K5d-{name}", f"{lm['name']}: kept walls and roofs layer 5 does not show there (hidden before the "
                 f"cut): pixels, and those not on the building's surface within 1 cm", [int(newly.sum()), int(off_new.sum())])
        other = k == K["other"]
        same_o = other & (id5 == px["ids"])
        rep.info(f"K5e-{name}", f"{lm['name']}: other buildings' pixels in the cutaway: all, those layer 5 also shows "
                 f"(largest depth difference, cm), those the slice brought to view",
                 [int(other.sum()), int(same_o.sum()), round(float(dz[same_o].max()) * 100, 3) if same_o.any() else 0.0,
                  int((other & ~same_o).sum())])
        # ---------------------------------------------------------------- K6
        obj5 = (id5 >> 8).astype(np.int64)
        replaced = np.isin(obj5, built["replaces_index"]) & np.isfinite(d5)
        stray = ~replaced & ~(d5 <= px["depth"] + P["cutaway_depth_cm"] / 100)
        rep.at_most(f"K6b-{name}", f"{lm['name']}: cutaway pixels where layer 5 shows neither a replaced building nor "
                    f"another building at or in front of them (of {len(k)})", int(stray.sum()), 0)
        # ---------------------------------------------------------------- facts
        dg, _ = layer_at(g_dir, gi, px["px"], px["py"])
        covered = opening & (dg < px["depth"])
        rep.info(f"K-ground-{name}", f"{lm['name']}: opening pixels the ground layer is in front of (the terrain "
                 f"stands above floor_z {lm['floor_z']} there), of {int(opening.sum())}", int(covered.sum()))
        rep.info(f"K-px-{name}", f"{lm['name']}: pixels by kind", built["pixels"])
    # -------------------------------------------------------------------- K4
    jobs = detector_jobs(cut_folder, index, ctx.out)
    passes = (("vehicles", g1["detector_queries"], g1["detector_score"], g1["detector_box_m"]),
              ("people", P["cutaway_person_queries"], P["cutaway_detector_score"], P["cutaway_person_box_m"]))
    if P["cutaway_detector_run"]:
        for tag, queries, thr, box_m in passes:
            res = run_detector(jobs, ctx.out, tag, queries, thr, box_m)
            hits = sorted(res["detections"], key=lambda d: -d["score"])
            rep.at_most(f"K4-{tag}", f"detections >= {thr} of {queries} ({box_m[0]}-{box_m[1]} m) on {res['images']} "
                        f"paint inputs and cutaway tiles (highest score of any query {res['max_score']})", len(hits), 0, hits)
    else:
        for tag, queries, thr, box_m in passes:
            (ctx.out / f"owl_jobs_{tag}.json").write_text(json.dumps(
                {"jobs": jobs, "queries": queries, "queries_water": [], "threshold": thr, "box_m": box_m, "mpp": 0.125,
                 "out": str(ctx.out / f"owl_{tag}.json")}))
        rep.info("K4", f"the detector was not run (cutaway_detector_run is false); {len(jobs)} images are listed for "
                 "it, for vehicles and for people", [f"owl_jobs_{t[0]}.json" for t in passes])
    # -------------------------------------------------------------------- K6a
    f5 = (ctx.dep("layer_buildings")).resolve()
    inside5 = [str(p) for p in cut_folder.rglob("*") if f5 in p.resolve().parents]
    names5 = set(json.loads((ctx.dep("layer_buildings") / "manifest.json").read_text()).get("files", []))
    rep.at_most("K6a", "files of the cutaway layer inside layer 5's folder, or files named 'cutaway' in layer 5 (the "
                "cutaway is a layer of its own: with it off, layer 5's tiles are what is drawn)",
                len(inside5) + sum("cutaway" in f for f in names5), 0)
    return rep.result()
