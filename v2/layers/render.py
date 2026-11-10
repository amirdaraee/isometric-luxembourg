"""The renderer of the code layers: one function per layer, each drawing a tile from the scene alone.

Every layer function returns a LayerTile (rgb, depth, normal, k, ids) for the tile with its apron. Layers never read
each other's pixels; they share only the scene (terrain with the water levels, the area). The independence check
(brief 4) re-renders each layer with every other layer's own inputs removed and requires identical pixels.

Draped layers (ground, relief, water and the transport on the ground) are drawn on the terrain as seen through the
camera (raster.terrain_scan): each visible terrain pixel looks its colour up in a plan canvas of the tile drawn in
the (u, f) frame (common.py), one canvas column per screen column. 3D objects (bridge decks, portals, walls,
buildings, structures, crowns) are rasterised with their own depth.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from functools import cached_property

import numpy as np
import shapely
from PIL import Image, ImageDraw
from scipy import ndimage
from shapely.geometry import LineString, Point, Polygon, box
from shapely.strtree import STRtree

from v2.layers import geometry as G
from v2.layers.common import (C30, CLASS, R2, S30, VIEW, cam, grain, pal, project)
from v2.layers.raster import HeightField, bary, raster_ellipsoids, raster_tris, terrain_scan

# ground classes, lowest priority first (layer-01-ground.md rule 1); k byte = index
GROUND_CLASSES = ["none", "paved", "buildsite", "railground", "parking", "square", "grass", "cemetery", "garden",
                  "meadow", "scrub", "wood", "pitch", "water"]
GREEN = {"grass", "cemetery", "garden", "meadow", "scrub", "wood", "pitch"}
URBAN = {"residential", "commercial", "retail", "industrial", "construction", "railway", "education", "religious",
         "civic", "institutional", "garages", "military"}
TREE_TYPES = ["deciduous_green", "deciduous_red", "conifer", "other"]
DU = 0.125            # plan canvas: metres per column (= one screen column) and per row


def ground_class(tg: dict):
    lu, le, na, am = tg.get("landuse"), tg.get("leisure"), tg.get("natural"), tg.get("amenity")
    if na == "water" or tg.get("waterway") == "riverbank" or lu in ("reservoir", "basin") or tg.get("water"):
        return "water"
    if le in ("pitch", "track", "sports_centre", "stadium") and tg.get("surface") not in ("asphalt", "concrete", "paving_stones"):
        return "pitch"
    if lu == "forest" or na == "wood":
        return "wood"
    if na in ("scrub", "heath"):
        return "scrub"
    if lu in ("meadow", "farmland", "orchard", "vineyard", "greenfield") or na == "grassland":
        return "meadow"
    if le == "garden" or lu in ("allotments", "plant_nursery"):
        return "garden"
    if lu == "cemetery" or am == "grave_yard":
        return "cemetery"
    if lu in ("grass", "village_green", "recreation_ground", "flowerbed") or le in ("park", "playground", "dog_park"):
        return "grass"
    if tg.get("place") == "square" or tg.get("area:highway") or am == "marketplace":
        return "square"
    if am == "parking" and tg.get("parking", "surface") in ("surface", "lane", "street_side"):
        return "parking"
    if lu == "railway":
        return "railground"
    if lu in ("construction", "brownfield"):
        return "buildsite"
    return None


def colour_of(key: str) -> np.ndarray:
    """A palette colour 'group.name', or a blend 'a.b|c.d|t' (t of the second)."""
    if "|" in key:
        a, b, t = key.split("|")
        t = float(t)
        return pal(*a.split(".")) * (1 - t) + pal(*b.split(".")) * t
    return pal(*key.split("."))


@dataclass
class LayerTile:
    rgb: np.ndarray                      # (H, W, 3) uint8
    depth: np.ndarray                    # (H, W) float, inf = empty
    normal: np.ndarray                   # (H, W, 3)
    k: np.ndarray | None = None          # (H, W) uint8
    ids: np.ndarray | None = None        # (H, W) uint32: id << 8 | class
    extra: dict = field(default_factory=dict)


def empty(tile):
    H = W = tile.size
    return LayerTile(np.zeros((H, W, 3), np.uint8), np.full((H, W), np.inf), np.zeros((H, W, 3)),
                     np.zeros((H, W), np.uint8), np.zeros((H, W), np.uint32))


# ------------------------------------------------------------------------------------------------ plan canvas
class Canvas:
    """A plan raster of one tile in the (u, f) frame: column j = screen column j, rows every DU metres of f."""

    def __init__(self, tile, f0, f1):
        c = cam()
        self.u0 = c["frame"]["sx0"] + tile.px0 * c["mpp"]
        self.f0 = math.floor(f0 / DU) * DU - 2.0
        self.W = tile.size
        self.H = int(math.ceil((f1 - self.f0) / DU)) + 16
        oe, on = c["origin_en"]
        self.oe, self.on = oe, on

    def bounds_en(self):
        """The canvas's plan footprint as a polygon in (E, N)."""
        u = [self.u0, self.u0 + self.W * DU]
        f = [self.f0, self.f0 + self.H * DU]
        pts = [(uu, ff) for uu, ff in ((u[0], f[0]), (u[1], f[0]), (u[1], f[1]), (u[0], f[1]))]
        return Polygon([(self.oe + (uu - ff) * R2, self.on + (uu + ff) * R2) for uu, ff in pts])

    def xy(self, e, n):
        le, ln = np.asarray(e) - self.oe, np.asarray(n) - self.on
        return ((le + ln) * R2 - self.u0) / DU, ((ln - le) * R2 - self.f0) / DU

    def geom(self, g):
        return shapely.transform(g, lambda a: np.column_stack(self.xy(a[:, 0], a[:, 1])))

    def sample(self, img: np.ndarray, u, f):
        j = np.clip(((u - self.u0) / DU).astype(np.int64), 0, self.W - 1)
        i = np.clip(((f - self.f0) / DU).astype(np.int64), 0, self.H - 1)
        return img[i, j]


def fill_geom(img: Image.Image, g, value):
    """Fill a (canvas-space) polygon or multipolygon, holes left as they were."""
    for p in getattr(g, "geoms", [g]):
        if p.geom_type != "Polygon" or p.is_empty:
            continue
        x0, y0, x1, y1 = p.bounds
        x0, y0 = max(int(math.floor(x0)), 0), max(int(math.floor(y0)), 0)
        x1, y1 = min(int(math.ceil(x1)) + 1, img.width), min(int(math.ceil(y1)) + 1, img.height)
        if x1 <= x0 or y1 <= y0:
            continue
        if not p.interiors:
            ImageDraw.Draw(img).polygon([(x, y) for x, y in p.exterior.coords], fill=value)
            continue
        m = Image.new("1", (x1 - x0, y1 - y0), 0)
        d = ImageDraw.Draw(m)
        d.polygon([(x - x0, y - y0) for x, y in p.exterior.coords], fill=1)
        for r in p.interiors:
            d.polygon([(x - x0, y - y0) for x, y in r.coords], fill=0)
        img.paste(value, (x0, y0, x1, y1), m)


# ------------------------------------------------------------------------------------------------ renderer
class Renderer:
    """Draws any code layer's tile from a scene. `omit` names layers whose own inputs are left out (to prove the
    others never use them); `ground_osm` and `transport_osm` are the shared OSM fetches (paths)."""

    PRIVATE = {"ground": "ground_osm", "relief": "walls", "water": "water_draw", "transport": "transport_draw",
               "buildings": "buildings", "structures": "structures", "trees": "trees"}

    def __init__(self, scene, ground_osm=None, transport_osm=None, omit=frozenset(), art=None):
        from v2.config.art import art_method
        self.scene = scene
        self.art = art or art_method()
        self.ground_osm_path = ground_osm
        self.transport_osm_path = transport_osm
        self.omit = set(omit)
        self._tcache = {}

    def _guard(self, layer):
        if layer in self.omit:
            raise RuntimeError(f"layer {layer} is switched off in this renderer; another layer asked for its inputs")

    # ---------------------------------------------------------------- shared: terrain with the water levels
    @cached_property
    def water_polys(self):
        from shapely.geometry import Polygon as P
        out = []
        for a in self.scene.water["areas"]:
            for rings in a["rings"]:
                p = P(rings[0], rings[1:])
                out.append(p if p.is_valid else p.buffer(0))
        return out

    @cached_property
    def hf(self) -> HeightField:
        """The LiDAR terrain, with every water area held at a flat level: the lowest terrain round it locally
        (a 25 m minimum filter of the bank heights, so a reach is flat between weirs), never above the bank."""
        T = self.scene.terrain
        z = T["mnt"].astype(np.float64).copy()
        e0, n0, step = float(T["e0"]), float(T["n0"]), float(T["step"])
        h, w = z.shape
        mask = np.zeros(z.shape, bool)
        if self.water_polys:
            ee = e0 + (np.arange(w) + 0.5) * step
            nn = n0 + (np.arange(h) + 0.5) * step
            E, N = np.meshgrid(ee, nn)
            for p in self.water_polys:
                x0, y0, x1, y1 = p.bounds
                j0, j1 = np.searchsorted(ee, [x0, x1])
                i0, i1 = np.searchsorted(nn, [y0, y1])
                if j1 <= j0 or i1 <= i0:
                    continue
                sub = shapely.contains_xy(p, E[i0:i1, j0:j1], N[i0:i1, j0:j1])
                mask[i0:i1, j0:j1] |= sub
            if mask.any():
                bank = ndimage.binary_dilation(mask, iterations=3) & ~mask
                zb = np.where(bank, z, np.inf)
                k = max(3, int(round(25 / step)) | 1)
                lvl = ndimage.minimum_filter(zb, size=k)
                # spread the bank levels into the water (nearest bank cell), then hold the water at that level
                idx = ndimage.distance_transform_edt(~np.isfinite(lvl), return_distances=False, return_indices=True)
                lvl = lvl[tuple(idx)]
                z = np.where(mask, np.minimum(z, lvl), z)
        self.water_grid = mask
        return HeightField(z, e0, n0, step)

    @cached_property
    def hf_smooth(self) -> HeightField:
        """The terrain smoothed over about 1.5 m: the land's form for the relief drawing."""
        hf = self.hf
        return HeightField(ndimage.gaussian_filter(hf.z, 1.5 / hf.step), hf.e0, hf.n0, hf.step)

    def terrain(self, tile):
        key = (tile.tx, tile.ty, tile.apron)
        if key not in self._tcache:
            if len(self._tcache) > 2:
                self._tcache.clear()
            zmin, zmax = self.scene.z_range
            r = terrain_scan(self.hf, tile, zmin - 1, zmax + 1)
            r["inarea"] = r["hit"].copy()
            if r["hit"].any():
                r["inarea"][r["hit"]] = shapely.contains_xy(self.scene.polygon, r["e"][r["hit"]], r["n"][r["hit"]])
            nrm = np.zeros(r["e"].shape + (3,))
            nv = self.hf.normal(r["e"][r["hit"]], r["n"][r["hit"]])
            # a seen surface faces the camera; the gradient (over a grid cell) can lean past the view ray on a
            # crest: bend it back to grazing (the light is then that of a surface seen edge-on)
            w = -VIEW
            dot = nv @ w
            back = dot < 0.02
            if back.any():
                nv[back] = nv[back] + (0.02 - dot[back])[:, None] * w
                nv[back] /= np.linalg.norm(nv[back], axis=1, keepdims=True)
            nrm[r["hit"]] = nv
            r["normal"] = nrm
            self._tcache[key] = r
        return self._tcache[key]

    def _canvas(self, tile, t, extra_f=()):
        ff = np.r_[t["f"][t["inarea"]], np.asarray(extra_f, float)]
        if not len(ff):
            return None
        return Canvas(tile, float(ff.min()), float(ff.max()))

    # ---------------------------------------------------------------- layer 1: ground
    @cached_property
    def ground_polys(self):
        """(class, polygon) for every OSM land-use area near the area, and the built-up land (urban land uses)."""
        if "ground" in self.omit:
            return [], Polygon()
        from v2.data.geo import osm_area_en
        g = json.loads(self.ground_osm_path.read_text())
        clip = self.scene.polygon.buffer(200)
        out, urban = [], []
        for el in g["elements"]:
            if el["type"] not in ("way", "relation"):
                continue
            tg = el.get("tags", {})
            cl = ground_class(tg)
            isurb = tg.get("landuse") in URBAN
            if cl is None and not isurb:
                continue
            p = osm_area_en(el)
            if p is None or not p.intersects(clip):
                continue
            p = p.intersection(clip)
            if cl:
                out.append((cl, p))
            if isurb:
                urban.append(p)
        if self.transport_osm_path is not None:
            t = json.loads(self.transport_osm_path.read_text())
            for el in t["elements"]:
                tg = el.get("tags", {})
                if el["type"] == "way" and tg.get("area") == "yes" and tg.get("highway") in ("pedestrian", "footway", "service"):
                    p = osm_area_en(el)
                    if p is not None and p.intersects(clip):
                        out.append(("parking" if tg["highway"] == "service" else "square", p.intersection(clip)))
        from shapely.ops import unary_union
        return out, unary_union(urban) if urban else Polygon()

    @cached_property
    def ground_tree(self):
        polys, _ = self.ground_polys
        return STRtree([p for _, p in polys]) if polys else None

    def ground(self, tile) -> LayerTile:
        self._guard("ground")
        t = self.terrain(tile)
        out = empty(tile)
        m = t["inarea"]
        if not m.any():
            return out
        cv = self._canvas(tile, t)
        polys, urban = self.ground_polys
        footprint = cv.bounds_en()
        cls = Image.new("L", (cv.W, cv.H), GROUND_CLASSES.index("meadow"))
        if not urban.is_empty and urban.intersects(footprint):
            fill_geom(cls, cv.geom(urban), GROUND_CLASSES.index("paved"))   # whole polygons: a cut would differ per tile
        if self.ground_tree is not None:
            hits = sorted(self.ground_tree.query(footprint), key=lambda i: GROUND_CLASSES.index(polys[i][0]))
            for i in hits:
                c, p = polys[i]
                fill_geom(cls, cv.geom(p), GROUND_CLASSES.index(c))
        cls = np.asarray(cls)
        k = np.zeros(m.shape, np.uint8)
        k[m] = cv.sample(cls, t["u"][m], t["f"][m])
        lut = np.zeros((len(GROUND_CLASSES), 3))
        for i, c in enumerate(GROUND_CLASSES[1:], 1):
            lut[i] = pal("water", "river") if c == "water" else pal("ground", c)
        px, py = tile.centres
        rgb = lut[k] * grain(px, py, 0.03, seed=1)[..., None]
        # class borders: 1 px soft ink (40%) where the class changes to the right or below
        edge = np.zeros(m.shape, bool)
        edge[:, :-1] |= (k[:, :-1] != k[:, 1:]) & m[:, :-1] & m[:, 1:]
        edge[:-1, :] |= (k[:-1, :] != k[1:, :]) & m[:-1, :] & m[1:, :]
        ink = pal("ink", "line_soft")
        rgb[edge] = rgb[edge] * 0.6 + ink * 0.4
        out.rgb = np.clip(np.round(rgb), 0, 255).astype(np.uint8) * m[..., None]
        out.depth = np.where(m, t["depth"], np.inf)
        out.normal = t["normal"] * m[..., None]
        out.k = k
        out.ids = np.where(m, CLASS["ground"], 0).astype(np.uint32)
        return out

    # ---------------------------------------------------------------- layer 2: relief
    @cached_property
    def walls_geo(self):
        if "relief" in self.omit:
            return G.Mesh().done()
        return G.wall_mesh(self.scene, poly=self.scene.polygon, ground=self.hf.sample)

    def relief(self, tile) -> LayerTile:
        """A multiply layer: form shading from a fixed north-west light (never the sun), capped so flat ground is
        untouched, fall-line hatching on steep ground and cliffs, and the measured walls as stone faces."""
        self._guard("relief")
        t = self.terrain(tile)
        out = empty(tile)
        m = t["inarea"]
        H = W = tile.size
        fac = np.ones((H, W, 3))
        k = np.zeros((H, W), np.uint8)
        if m.any():
            n = np.zeros(m.shape + (3,))
            n[m] = self.hf_smooth.normal(t["e"][m], t["n"][m])     # the form, not the LiDAR's grain
            light = np.array([-0.5, 0.5, math.sqrt(0.5)])
            light /= np.linalg.norm(light)
            shade = n @ light
            raw = np.degrees(np.arccos(np.clip(t["normal"][..., 2], -1, 1)))      # the surface's own slope
            slope = np.minimum(np.degrees(np.arccos(np.clip(n[..., 2], -1, 1))), raw)
            ramp = np.clip((slope - 3.5) / 9.0, 0, 1)        # flat (< 3 deg, with room for the normal's coding): 1
            f1 = np.clip(1 + 0.9 * (shade - light[2]) * ramp, 0.62, 1.0)
            fac *= f1[..., None]
            T = self.scene.terrain
            # steep and cliff classes of the scene (scene_terrain: slope >= 35 deg; cliff >= 60 deg with a drop)
            gi, gj = self.hf.ij(t["e"], t["n"])
            ci = np.clip(np.round(gi).astype(int), 0, T["cls"].shape[0] - 1)
            cj = np.clip(np.round(gj).astype(int), 0, T["cls"].shape[1] - 1)
            tcls = np.where(m, T["cls"][ci, cj], 0)
            k[m] = 1
            steep = m & (tcls >= 1) & (raw >= 3.5)
            if steep.any():
                gx, gy = -n[..., 0], -n[..., 1]
                gl = np.maximum(np.hypot(gx, gy), 1e-9)
                tx, ty = -gy / gl, gx / gl                              # along the contour
                spacing = np.where(tcls == 2, 0.55, 1.1)
                phase = (t["e"] * tx + t["n"] * ty) / spacing
                line = np.abs(phase - np.round(phase)) < 0.13
                hatch = pal("relief", "hatch") / 255
                rock = pal("relief", "rock") / 255
                tint = np.where((tcls == 2)[..., None], 0.45 * rock + 0.55, 0.15 * rock + 0.85)
                fac = np.where(steep[..., None], fac * tint, fac)
                h = steep & line
                fac[h] = fac[h] * (0.45 + 0.55 * hatch)
                k[steep] = 2
        depth = np.where(m, t["depth"], np.inf)
        normal = t["normal"] * m[..., None]
        rgb = np.clip(np.round(fac * 255), 0, 255)
        ids = np.where(m, CLASS["ground"], 0).astype(np.uint32)
        # the walls, with their own depth (stone faces and an ink top), drawn where nearer than the terrain
        W3 = self.walls_geo
        if len(W3["T"]):
            zb = np.full((H, W), np.inf)
            tb = np.full((H, W), -1, np.int64)
            px, py, dd = project(W3["V"][:, 0], W3["V"][:, 1], W3["V"][:, 2])
            P = np.column_stack([px - tile.px0, py - tile.py0])
            sel = self._tris_in_tile(P, W3["T"], tile)
            raster_tris(P, dd - 0.15, W3["T"][sel], W, H, zb, tb)   # 15 cm towards the camera: on the terrain step
            got = tb >= 0
            tsel = sel[tb[got]]
            near = zb[got] < depth[got] + 1.0          # a wall stands on a step the 0.5 m terrain rounds off
            gi = np.flatnonzero(got.ravel())[near]
            tt = tsel[near]
            nrm, _ = G.tri_normals(W3["V"], W3["T"])
            cols = np.array([colour_of(c) for c in W3["col_keys"]])
            rgb.reshape(-1, 3)[gi] = cols[W3["col"][tt]]
            depth.reshape(-1)[gi] = zb.reshape(-1)[gi]
            nn = nrm[tt] * np.sign(-(nrm[tt] @ VIEW))[:, None]
            normal.reshape(-1, 3)[gi] = nn
            k.reshape(-1)[gi] = 3
            ids.reshape(-1)[gi] = (W3["obj"][tt].astype(np.uint32) << 8) | CLASS["wall"]
        out.rgb = rgb.astype(np.uint8)
        out.depth, out.normal, out.k, out.ids = depth, normal, k, ids
        return out

    # ---------------------------------------------------------------- layer 3: water
    def water(self, tile) -> LayerTile:
        self._guard("water")
        t = self.terrain(tile)
        out = empty(tile)
        m = t["inarea"]
        if not m.any() or not self.water_polys:
            return out
        cv = self._canvas(tile, t)
        img = Image.new("L", (cv.W, cv.H), 0)
        fp = cv.bounds_en()
        for p in self.water_polys:
            if p.intersects(fp):
                fill_geom(img, cv.geom(p), 1)
        wm = np.zeros(m.shape, bool)
        wm[m] = cv.sample(np.asarray(img), t["u"][m], t["f"][m]) > 0
        if not wm.any():
            return out
        rgb = np.zeros(m.shape + (3,))
        rgb[wm] = pal("water", "river")
        edge = np.zeros(m.shape, bool)
        nb = np.zeros(m.shape, bool)
        nb[:, :-1] |= ~wm[:, 1:]; nb[:, 1:] |= ~wm[:, :-1]; nb[:-1, :] |= ~wm[1:, :]; nb[1:, :] |= ~wm[:-1, :]
        edge = wm & nb
        rgb[edge] = pal("water", "bank")
        out.rgb = np.round(rgb).astype(np.uint8)
        out.depth = np.where(wm, t["depth"], np.inf)
        nrm = np.zeros(m.shape + (3,))
        nrm[wm] = (0, 0, 1)
        out.normal = nrm
        out.k = wm.astype(np.uint8)
        out.ids = np.where(wm, CLASS["water"], 0).astype(np.uint32)
        return out

    # ---------------------------------------------------------------- layer 4: transport
    @cached_property
    def edges(self):
        return self.scene.graph["edges"]

    @cached_property
    def deck_masks(self):
        """Per edge, per sample: drawn at its profile as a deck, or on the terrain (geometry.deck_mask). Shared by
        layer 4 (the deck surfaces), layer 6 (the abutments under raised approaches), layer 9 and the checks."""
        bridge_nodes = {int(e[k]) for e in self.edges if e["structure"] == "bridge" for k in ("a", "b")}
        return [G.deck_mask(e, self.hf.sample, (int(e["a"]) in bridge_nodes, int(e["b"]) in bridge_nodes))
                for e in self.dense_edges]

    @cached_property
    def dense_edges(self):
        """The graph's edges resampled every 0.5 m (geometry.densify): the pieces of layer 4 and 6 are cut on them."""
        return [G.densify(e) for e in self.edges]

    @cached_property
    def surfaces(self):
        """Per drawn piece of an edge: (index, style, polygon of its surface, centre line, on a deck). Tunnels and
        indoor ways are not drawn. An edge is cut where it leaves the terrain for a deck (geometry.pieces)."""
        if "transport" in self.omit:
            return []
        out = []
        for i, e in enumerate(self.edges):
            if e["structure"] in ("tunnel", "indoor", "elevator") or e["mode"] == "elevator":
                continue
            en = np.array(self.dense_edges[i]["en"], float)
            if len(en) < 2:
                continue
            style = surface_style(e)
            w = float(e["width"])
            parts = G.pieces(self.deck_masks[i])
            for deck, i0, i1 in parts:
                line = LineString(en[i0:i1 + 1])
                # a piece on the terrain runs 0.5 m on under the deck next to it (hidden there by the deck, which is
                # nearer at the joint), so no rounding at the joint leaves a sliver of ground between them
                drape = line if deck else extend_line(en, i0, i1, 0.5)
                # round ends where a way ends (junctions), flat where it continues as the other kind of piece
                cap = "flat" if e["mode"] in ("rail", "tram", "funicular") or len(parts) > 1 else "round"
                poly = drape.buffer(w / 2, cap_style=cap, join_style="round", quad_segs=6)
                if cap == "flat" and e["mode"] not in ("rail", "tram", "funicular"):
                    ends = [Point(en[k]).buffer(w / 2, quad_segs=6) for k, last in ((0, i0 == 0), (-1, i1 == len(en) - 1)) if last]
                    if ends:
                        poly = shapely.union_all([poly] + ends)
                out.append((i, style, poly, line, deck))
        return out

    @cached_property
    def surface_tree(self):
        return STRtree([s[2] for s in self.surfaces]) if self.surfaces else None

    @cached_property
    def decks(self):
        if "transport" in self.omit:
            return G.Mesh().done()
        return G.deck_mesh(self.scene, masks=self.deck_masks, edges=self.dense_edges)

    @cached_property
    def portals(self):
        if "transport" in self.omit:
            return G.Mesh().done()
        return G.portal_mesh(self.scene, ceiling=self.deck_ceiling)

    def deck_ceiling(self, e, n, z, r, thickness=1.0):
        """The lowest underside (deck top - thickness, as layer 6 builds it) of a deck within r m (plan) of (e, n)
        and above z + 0.5 m; inf if none."""
        D = self.decks
        if not len(D["V"]):
            return np.inf
        V, T = D["V"], D["T"]
        cand = np.flatnonzero((np.hypot(V[T, 0] - e, V[T, 1] - n).min(1) <= r + 15) & (V[T, 2].min(1) > z + 0.5))
        disc = Point(e, n).buffer(r)
        zs = [V[T[t], 2].min() for t in cand if disc.intersects(Polygon(V[T[t], :2]))]
        return float(min(zs)) - thickness if zs else np.inf

    def _draw_transport(self, cv, bridge: bool):
        """The transport canvas (colour, ids) for ground-level ways or for bridge decks."""
        fp = cv.bounds_en()
        rgb = Image.new("RGB", (cv.W, cv.H), (0, 0, 0))
        ids = Image.new("I", (cv.W, cv.H), 0)
        has = Image.new("L", (cv.W, cv.H), 0)
        if self.surface_tree is None:
            return np.asarray(rgb), np.asarray(ids), np.asarray(has)
        hits = [self.surfaces[i] for i in self.surface_tree.query(fp)]
        hits = [h for h in hits if h[4] == bridge]
        hits.sort(key=lambda h: STYLE_ORDER.index(h[1]))
        ink = tuple(int(x) for x in np.round(pal("ink", "line_soft") * 0.45 + pal("ground", "paved") * 0.55))
        d_rgb, d_ids, d_has = ImageDraw.Draw(rgb), ImageDraw.Draw(ids), ImageDraw.Draw(has)
        px1 = 1 / DU
        # pass 1: casings (outline), pass 2: surfaces, pass 3: markings
        for i, style, poly, line, _ in hits:
            g = cv.geom(poly.buffer(0.18, quad_segs=4))
            fill_geom(rgb, g, ink)
            fill_geom(ids, g, (i + 1) << 8 | STYLE_CLASS[style])
            fill_geom(has, g, 1)
        for i, style, poly, line, _ in hits:
            e = self.edges[i]
            g = cv.geom(poly)
            fill_geom(rgb, g, tuple(int(x) for x in np.round(STYLE_COLOUR[style]())))
            fill_geom(ids, g, (i + 1) << 8 | STYLE_CLASS[style])
            fill_geom(has, g, 1)
        for i, style, poly, line, _ in hits:
            e = self.edges[i]
            en = np.array(line.coords)
            if style in ("rail", "funicular", "tram"):
                gauge = 1.435 if style != "funicular" else 1.0
                if style == "rail":
                    for s, t0 in sleepers(en, 0.65):
                        a = s - t0 * 1.3
                        b = s + t0 * 1.3
                        d_rgb.line([tuple(cv_xy(cv, a)), tuple(cv_xy(cv, b))], fill=_c("transport.sleeper"), width=2)
                col = _c("transport.rail") if style != "tram" else _c("transport.tram")
                for off in (gauge / 2, -gauge / 2):
                    o = offset_line(en, off)
                    d_rgb.line([tuple(cv_xy(cv, p)) for p in o], fill=col, width=1)
            elif style == "steps":
                for s, t0 in sleepers(en, 0.32):
                    w = float(e["width"]) / 2
                    d_rgb.line([tuple(cv_xy(cv, s - t0 * w)), tuple(cv_xy(cv, s + t0 * w))],
                               fill=_c("transport.steps|ink.line|0.35"), width=1)
            elif style == "road":
                lanes = int(float(e.get("lanes") or 1))
                oneway = str(e.get("oneway")) == "True"
                w = float(e["width"])
                if lanes >= 2 and w >= 5.5:
                    if oneway:
                        offs = [w / 2 - k * w / lanes for k in range(1, lanes)]
                    else:
                        offs = [0.0]
                    for off in offs:
                        o = offset_line(en, off) if off else en
                        for a, b in dashes(o, 3.0, 6.0):
                            d_rgb.line([tuple(cv_xy(cv, a)), tuple(cv_xy(cv, b))], fill=_c("transport.lane_dash"),
                                       width=max(1, int(round(0.15 * px1))))
        return np.asarray(rgb), np.asarray(ids), np.asarray(has)

    def transport(self, tile) -> LayerTile:
        self._guard("transport")
        t = self.terrain(tile)
        out = empty(tile)
        H = W = tile.size
        m = t["inarea"]
        rgb = np.zeros((H, W, 3), np.uint8)
        depth = np.full((H, W), np.inf)
        normal = np.zeros((H, W, 3))
        k = np.zeros((H, W), np.uint8)
        ids = np.zeros((H, W), np.uint32)
        if m.any() and self.surfaces:
            cv = self._canvas(tile, t)
            crgb, cids, chas = self._draw_transport(cv, bridge=False)
            on = np.zeros(m.shape, bool)
            on[m] = cv.sample(chas, t["u"][m], t["f"][m]) > 0
            rgb[on] = cv.sample(crgb, t["u"][on], t["f"][on])
            ids[on] = cv.sample(cids, t["u"][on], t["f"][on]).astype(np.uint32)
            depth[on] = t["depth"][on]
            normal[on] = t["normal"][on]
            k[on] = 1
        # bridge decks, with their own depth; their surface from the deck canvas at the deck point's (u, f)
        D = self.decks
        if len(D["T"]):
            px, py, dd = project(D["V"][:, 0], D["V"][:, 1], D["V"][:, 2])
            P = np.column_stack([px - tile.px0, py - tile.py0])
            sel = self._tris_in_tile(P, D["T"], tile)
            if len(sel):
                zb = np.full((H, W), np.inf)
                tb = np.full((H, W), -1, np.int64)
                raster_tris(P, dd, D["T"][sel], W, H, zb, tb)
                got = tb >= 0
                if got.any():
                    tt = sel[tb[got]]
                    rr, cc = np.nonzero(got)
                    cx, cy = cc + 0.5, rr + 0.5
                    wts = bary(P, D["T"], tt, cx, cy)
                    Vt = D["V"][D["T"][tt]]
                    wp = (wts[..., None] * Vt).sum(1)
                    c = cam()
                    le, ln = wp[:, 0] - c["origin_en"][0], wp[:, 1] - c["origin_en"][1]
                    u, f = (le + ln) * R2, (ln - le) * R2
                    inarea = shapely.contains_xy(self.scene.polygon, wp[:, 0], wp[:, 1])
                    cv2 = Canvas(tile, float(f.min()), float(f.max()))
                    drgb, dids, dhas = self._draw_transport(cv2, bridge=True)
                    has = cv2.sample(dhas, u, f) > 0
                    near = zb[got] < depth[got]
                    use = inarea & near                        # the deck is the ribbon; the canvas only colours it
                    gi = np.flatnonzero(got.ravel())[use]
                    obj = D["obj"][tt[use]]
                    base = np.array([STYLE_COLOUR[surface_style(self.edges[o])]() for o in obj]).reshape(-1, 3)
                    hu = has[use]
                    col = np.round(base).astype(np.uint8)
                    col[hu] = cv2.sample(drgb, u[use][hu], f[use][hu])
                    rgb.reshape(-1, 3)[gi] = col
                    idv = ((obj.astype(np.uint32) + 1) << 8) | CLASS["deck"]
                    cid = cv2.sample(dids, u[use], f[use]).astype(np.uint32)
                    idv[hu & (cid > 0)] = cid[hu & (cid > 0)]
                    ids.reshape(-1)[gi] = idv
                    depth.reshape(-1)[gi] = zb.reshape(-1)[gi]
                    nrm, _ = G.tri_normals(D["V"], D["T"])
                    nn = nrm[tt[use]] * np.sign(-(nrm[tt[use]] @ VIEW) + 1e-12)[:, None]   # the side seen
                    normal.reshape(-1, 3)[gi] = nn
                    k.reshape(-1)[gi] = 2
        # tunnel portals: dark arch faces where they face the camera
        Pm = self.portals
        if len(Pm["T"]):
            px, py, dd = project(Pm["V"][:, 0], Pm["V"][:, 1], Pm["V"][:, 2])
            P = np.column_stack([px - tile.px0, py - tile.py0])
            nrm, _ = G.tri_normals(Pm["V"], Pm["T"])
            sel = self._tris_in_tile(P, Pm["T"], tile)
            if len(sel):
                zb = np.full((H, W), np.inf)
                tb = np.full((H, W), -1, np.int64)
                raster_tris(P, dd, Pm["T"][sel], W, H, zb, tb)
                got = tb >= 0
                tt = sel[tb[got]]
                near = zb[got] < depth[got]
                gi = np.flatnonzero(got.ravel())[near]
                rgb.reshape(-1, 3)[gi] = np.round(pal("ink", "line")).astype(np.uint8)
                depth.reshape(-1)[gi] = zb.reshape(-1)[gi]
                nn = nrm[tt[near]] * np.sign(-(nrm[tt[near]] @ VIEW))[:, None]
                normal.reshape(-1, 3)[gi] = nn
                k.reshape(-1)[gi] = 3
                ids.reshape(-1)[gi] = (Pm["obj"][tt[near]].astype(np.uint32) + 1) << 8 | CLASS["portal"]
        out.rgb, out.depth, out.normal, out.k, out.ids = rgb, depth, normal, k, ids
        return out

    # ---------------------------------------------------------------- meshes (layers 5 and 6 placeholders)
    def _tris_in_tile(self, P, T, tile):
        x = P[T, 0]
        y = P[T, 1]
        s = tile.size
        return np.flatnonzero((x.max(1) >= 0) & (x.min(1) < s) & (y.max(1) >= 0) & (y.min(1) < s))

    def _mesh_layer(self, tile, meshes, outline=True, shader=None) -> LayerTile:
        """Rasterise meshes (dicts from geometry) with flat palette colours (albedo, no light) and ink outlines
        where the surface changes. `shader(mesh_index, tri_index, world, normal, base_rgb, px, py, cls, obj)`, if
        given, returns each covered pixel's albedo from its place on its surface (bake-off method A's detail)."""
        H = W = tile.size
        out = empty(tile)
        zb = np.full((H, W), np.inf)
        tb = np.full((H, W), -1, np.int64)
        off = 0
        allP, allT, groups, cols, cls, obj, nrms, src, biases = [], [], [], [], [], [], [], [], []
        for mi, M in enumerate(meshes):
            if not len(M["T"]):
                continue
            px, py, dd = project(M["V"][:, 0], M["V"][:, 1], M["V"][:, 2])
            P = np.column_stack([px - tile.px0, py - tile.py0])
            sel = self._tris_in_tile(P, M["T"], tile)
            nrm, _ = G.tri_normals(M["V"], M["T"])
            if len(sel):
                bias = M.get("bias")
                raster_tris(P, dd, M["T"][sel], W, H, zb, tb, tri_offset=off,
                            bias=None if bias is None else bias[sel])
            colours = np.array([colour_of(c) for c in M["col_keys"]])
            biases.append(np.zeros(len(sel)) if M.get("bias") is None else M["bias"][sel])
            allT.append(sel)
            groups.append(M["group"][sel] + (0 if not groups else 0))
            cols.append(colours[M["col"][sel]])
            cls.append(M["cls"][sel])
            obj.append(M["obj"][sel])
            nrms.append(nrm[sel])
            src.append(np.column_stack([np.full(len(sel), mi), sel]))
            off += len(sel)
        if off == 0:
            return out
        groups = [g + 10_000_000 * i for i, g in enumerate(groups)]
        group = np.concatenate(groups)
        col = np.concatenate(cols)
        cl = np.concatenate(cls)
        ob = np.concatenate(obj)
        nr = np.concatenate(nrms)
        got = tb >= 0
        t = tb[got]
        zb[got] -= np.concatenate(biases)[t]          # a decal's bias decides what is seen, never the depth stored
        rgb = np.zeros((H, W, 3))
        rgb[got] = col[t]
        pix_cls = None
        if shader is not None and len(t):
            from v2.layers.common import unproject
            sm = np.concatenate(src)
            pxc, pyc = tile.centres
            rr, cc = np.nonzero(got)
            X, Y = pxc[cc], pyc[rr]
            wx, wy, wz = unproject(X, Y, zb[got])
            nn0 = nr[t] * np.sign(-(nr[t] @ VIEW) + 1e-12)[:, None]
            res = shader(sm[t, 0], sm[t, 1], np.column_stack([wx, wy, wz]), nn0, col[t], X, Y, cl[t], ob[t])
            if isinstance(res, tuple):                    # (albedo, the pixels' classes: a shader's own materials)
                res, pix_cls = res
            rgb[got] = res
        gid = np.full((H, W), -1, np.int64)
        gid[got] = group[t]
        if outline:
            ink = pal("ink", "line_soft")
            # a crease is where one object's surface turns by 20 degrees or more: facets of a round tower (ACT models
            # them as planes a few degrees apart) are one smooth wall, and a line between each pair would darken the
            # tower's side towards its outline like shading (a baked light); nor is there a line between surfaces in
            # one plane (ACT repeats some walls), where their rasters interleave
            npx = np.zeros((H, W, 3)); npx[got] = nr[t]
            obp = np.full((H, W), -1, np.int64); obp[got] = ob[t]
            clp = np.full((H, W), -1, np.int64); clp[got] = cl[t]

            def same_surface(a, b, ga, gb, za, zb_):
                """One surface: the same group, or one object's surface of one class (a wall, a roof; a window is
                never the wall's) turning by less than 20 degrees with no gap in depth (a surface seen at a grazing
                angle steps in depth from pixel to pixel without a break)."""
                smooth = (np.abs((npx[a] * npx[b]).sum(-1)) > 0.94) & (np.abs(za - zb_) < 1.0) & \
                    (obp[a] == obp[b]) & (clp[a] == clp[b])
                return (ga == gb) | smooth
            zf = np.where(got, zb, 1e9)
            sh = same_surface((slice(None), slice(None, -1)), (slice(None), slice(1, None)), gid[:, :-1], gid[:, 1:],
                              zf[:, :-1], zf[:, 1:]) & got[:, :-1] & got[:, 1:]
            sv = same_surface((slice(None, -1), slice(None)), (slice(1, None), slice(None)), gid[:-1, :], gid[1:, :],
                              zf[:-1, :], zf[1:, :]) & got[:-1, :] & got[1:, :]
            gdh = (gid[:, :-1] != gid[:, 1:]) & ~sh
            gdv = (gid[:-1, :] != gid[1:, :]) & ~sv
            e = np.zeros((H, W), bool)
            dz = (np.abs(np.diff(zf, axis=1)) > 0.6) & ~sh
            e[:, :-1] |= (gdh | dz) & (got[:, :-1] | got[:, 1:])
            dzy = (np.abs(np.diff(zf, axis=0)) > 0.6) & ~sv
            e[:-1, :] |= (gdv | dzy) & (got[:-1, :] | got[1:, :])
            # the line goes on the nearer side of a change (so outlines hug the object, not what is behind it)
            e2 = np.zeros((H, W), bool)
            zz = np.where(got, zb, np.inf)
            right_nearer = np.zeros((H, W), bool); right_nearer[:, :-1] = zz[:, 1:] < zz[:, :-1]
            down_nearer = np.zeros((H, W), bool); down_nearer[:-1, :] = zz[1:, :] < zz[:-1, :]
            eh = np.zeros((H, W), bool); eh[:, :-1] = (gdh | dz) & (got[:, :-1] | got[:, 1:])
            ev = np.zeros((H, W), bool); ev[:-1, :] = (gdv | dzy) & (got[:-1, :] | got[1:, :])
            e2 |= eh & ~right_nearer
            e2[:, 1:] |= eh[:, :-1] & right_nearer[:, :-1]
            e2 |= ev & ~down_nearer
            e2[1:, :] |= ev[:-1, :] & down_nearer[:-1, :]
            e2 &= got
            rgb[e2] = rgb[e2] * 0.35 + ink * 0.65
        n = np.zeros((H, W, 3))
        nn = nr[t]
        nn = nn * np.sign(-(nn @ VIEW) + 1e-12)[:, None]          # the side seen by the camera
        n[got] = nn
        out.rgb = np.clip(np.round(rgb), 0, 255).astype(np.uint8)
        out.depth = zb
        out.normal = n
        out.k = np.where(got, 1, 0).astype(np.uint8)
        idv = np.zeros((H, W), np.uint32)
        pcls = pix_cls if pix_cls is not None else cl[t]
        idv[got] = (ob[t].astype(np.uint32) << 8) | pcls.astype(np.uint32)
        out.ids = idv
        return out

    @cached_property
    def building_meshes(self):
        if "buildings" in self.omit:
            return []
        b = G.buildings_mesh(self.scene)
        if self.art == "a":
            o = self.art_a.openings_mesh()
        else:
            o = G.openings_mesh(self.scene)
        o["group"] = o["group"] + int(b["group"].max()) + 1 if len(b["group"]) else o["group"]
        return [b, o]

    @cached_property
    def art_a(self):
        from v2.layers.art_a import ArtA
        return ArtA(self.scene, G.buildings_mesh(self.scene))

    def _shade_buildings_a(self, mi, ti, P, nrm, base, px, py, cls, obj):
        A = self.art_a
        b, o = self.building_meshes
        rgb = base.copy()
        pcls = cls.copy()
        on_b = mi == 0
        if on_b.any():
            tb_, P_, n_, x_, y_ = ti[on_b], P[on_b], nrm[on_b], px[on_b], py[on_b]
            kind = b["kind"][tb_]
            bi = obj[on_b]
            sub = np.zeros((len(tb_), 3))
            wall = kind == 2
            wc = pcls[on_b][wall]
            sub[wall] = A.walls_rgb(bi[wall], A.tri_wall[tb_[wall]], P_[wall], x_[wall], y_[wall], cls_out=wc)
            sc_ = pcls[on_b]
            sc_[wall] = wc
            pcls[on_b] = sc_
            roof = kind == 1
            sub[roof] = A.roofs_rgb(bi[roof], P_[roof], n_[roof], x_[roof], y_[roof])
            part = kind == 3
            if part.any():
                vert = np.abs(n_[part][:, 2]) < 0.3
                pw = np.array([A.styles[x].wall for x in bi[part]]).reshape(-1, 3)
                pr = A.roofs_rgb(bi[part], P_[part], n_[part], x_[part], y_[part])
                sub[part] = np.where(vert[:, None], pw, pr)
                # a dormer's or chimney's sloped faces are roof (the building's roof material), its sides are part
                sc_ = pcls[on_b]
                pc = sc_[part]
                pc[~vert] = CLASS["roof"]
                sc_[part] = pc
                pcls[on_b] = sc_
            rgb[on_b] = sub
        on_o = mi == 1
        if on_o.any():
            rgb[on_o], pcls[on_o] = A.openings_rgb(o, ti[on_o], P[on_o], o["open_bld"][ti[on_o]])
        return rgb, pcls

    def buildings(self, tile) -> LayerTile:
        """Layer 5 by the art method (config art_method): "a" the inked code render with generated detail
        (art_a.py); "plain" Phase 1's flat placeholder. Both evenly lit (albedo), with straight outlines and the facade
        layout's windows, doors and shop fronts. No light, no shadow. "b" and "c" draw from their painted inputs
        (bakeoff.py)."""
        self._guard("buildings")
        if not self.building_meshes:
            return empty(tile)
        if self.art in ("b", "c"):
            from v2.layers import bakeoff
            return bakeoff.painted_layer(self, "buildings", tile)
        return self._mesh_layer(tile, self.building_meshes,
                                shader=self._shade_buildings_a if self.art == "a" else None)

    @cached_property
    def structure_meshes(self):
        if "structures" in self.omit:
            return []
        return [G.structures_mesh(self.scene, masks=self.deck_masks, terrain=self.hf.sample, dense=self.dense_edges)]

    def structures(self, tile) -> LayerTile:
        """Placeholder for layer 6: bridge sides, parapets, the viaducts' slab, arches and piers, the lift."""
        self._guard("structures")
        if not self.structure_meshes:
            return empty(tile)
        if self.art in ("b", "c"):
            from v2.layers import bakeoff
            return bakeoff.painted_layer(self, "structures", tile)
        if self.art == "a":
            from v2.layers.art_a import ArtA

            def shade(mi, ti, P, nrm, base, px, py, cls, obj):
                return ArtA.stone_rgb(base, P, nrm, px, py, cls)
            return self._mesh_layer(tile, self.structure_meshes, shader=shade)
        return self._mesh_layer(tile, self.structure_meshes)

    # ---------------------------------------------------------------- layer 7 placeholder: trees
    @cached_property
    def tree_geo(self):
        if "trees" in self.omit:
            return None
        T = self.scene.trees
        e, n = T["e"].astype(float), T["n"].astype(float)
        base, h = T["base_z"].astype(float), T["height"].astype(float)
        r = T["crown_r"].astype(float)
        typ = T["type"].astype(int)
        b = np.where(typ == 2, np.clip(h * 0.42, 1.0, None), np.clip(np.minimum(h * 0.36, r * 1.7), 0.8, None))
        if self.art != "plain":
            # the crown fills the tree's measured height down to a trunk of a quarter of it (at least 2 m), as a
            # crown does; its width is the scene's (the survey's, widened to the tree's shape by species and age:
            # layer-07 rule 1, L7.1)
            b = np.maximum(b, (h - np.maximum(2.0, h * 0.25)) / 2)
        b = np.minimum(b, np.maximum(h / 2 - 0.2, 0.5))
        cz = base + h - b
        C = np.column_stack([e, n, cz])
        # trunks: thin boxes from the ground to the crown's centre
        M = G.Mesh()
        for i in range(len(e)):
            if cz[i] - base[i] < 0.5:
                continue
            G.box(M, np.array([e[i], n[i]]), np.array([1.0, 0.0]), 0.35, 0.35, base[i], cz[i], CLASS["trunk"], i, "trees.trunk")
        return {"C": C, "r": r, "b": b, "type": typ, "trunks": M.done()}

    def trees(self, tile) -> LayerTile:
        """Layer 7 (code crowns for methods A and B, both with A's leaf clumps: owner, 10 Nov 2026): every surveyed tree at its measured place and size, a flat crown colour by type
        (albedo; layer 9 lights and shades it), a trunk under it."""
        self._guard("trees")
        if self.art == "c":
            from v2.layers import bakeoff
            return bakeoff.painted_layer(self, "trees", tile)
        out = empty(tile)
        g = self.tree_geo
        if g is None:
            return out
        H = W = tile.size
        tr = self._mesh_layer(tile, [g["trunks"]], outline=False)
        zb = tr.depth.copy()
        ib = np.full((H, W), -1, np.int64)
        nb = tr.normal.copy()
        raster_ellipsoids(g["C"], g["r"], g["b"], tile, zb, ib, nb)
        crown = ib >= 0
        rgb = tr.rgb.astype(float)
        if crown.any():
            typ = g["type"][ib[crown]]
            light = np.array([pal("trees", "summer_light"), pal("trees", "red_light"), pal("trees", "conifer_light"),
                              pal("trees", "summer_light")])
            dark = np.array([pal("trees", "summer_dark"), pal("trees", "red_dark"), pal("trees", "conifer_dark"),
                             pal("trees", "summer_dark")])
            # albedo: a per-tree mix of the type's light and dark ends, and a leaf texture (no light in it)
            mix = 0.5 + 0.12 * (np.sin(ib[crown] * 12.9898) * 0.5)
            px, py = tile.centres
            leaf = grain(px, py, 0.08, seed=7)[crown]
            col = (dark[typ] * (1 - mix[:, None]) + light[typ] * mix[:, None]) * leaf[:, None]
            if self.art in ("a", "b"):
                # methods A and B: leaf clumps on the crown's surface (art_a.crown_rgb), from the pixel's world point
                from v2.layers.art_a import ArtA
                from v2.layers.common import unproject
                rr, cc = np.nonzero(crown)
                X, Y = px[cc], py[rr]
                wx, wy, wz = unproject(X, Y, zb[crown])
                base = dark[typ] * (1 - mix[:, None]) + light[typ] * mix[:, None]
                col = ArtA.crown_rgb(base, np.column_stack([wx, wy, wz]), ib[crown], X, Y)
            rgb[crown] = col
            # crown outline: 1 px of soft ink where a crown meets anything else
            idg = np.where(crown, ib, -1)
            e = np.zeros((H, W), bool)
            e[:, :-1] |= idg[:, :-1] != idg[:, 1:]
            e[:, 1:] |= idg[:, :-1] != idg[:, 1:]
            e[:-1, :] |= idg[:-1, :] != idg[1:, :]
            e[1:, :] |= idg[:-1, :] != idg[1:, :]
            e &= crown
            ink = pal("trees", "summer_dark")
            rgb[e] = rgb[e] * 0.5 + ink * 0.5
        got = np.isfinite(zb)
        k = np.where(crown, 1 + g["type"][np.maximum(ib, 0)], np.where(got, 8, 0)).astype(np.uint8)
        ids = tr.ids.copy()
        ids[crown] = (ib[crown].astype(np.uint32) << 8) | CLASS["tree"]
        out.rgb = np.clip(np.round(rgb), 0, 255).astype(np.uint8)
        out.depth, out.normal, out.k, out.ids = zb, nb, k, ids
        return out

    # ---------------------------------------------------------------- dispatch
    def layer(self, name, tile) -> LayerTile:
        return getattr(self, name)(tile)


# ------------------------------------------------------------------------------------------------ transport style
STYLE_ORDER = ["path", "steps", "pedestrian", "road_minor", "road", "railbed", "tram", "funicular", "rail"]
STYLE_CLASS = {"path": CLASS["path"], "steps": CLASS["steps"], "pedestrian": CLASS["path"], "road_minor": CLASS["road"],
               "road": CLASS["road"], "railbed": CLASS["rail"], "tram": CLASS["tram"], "funicular": CLASS["rail"],
               "rail": CLASS["rail"]}
STYLE_COLOUR = {
    "path": lambda: pal("transport", "path"),
    "steps": lambda: pal("transport", "steps"),
    "pedestrian": lambda: pal("transport", "pedestrian"),
    "road_minor": lambda: pal("transport", "road") * 0.8 + pal("transport", "pedestrian") * 0.2,
    "road": lambda: pal("transport", "road"),
    "railbed": lambda: pal("ground", "railground"),
    "tram": lambda: pal("transport", "road") * 0.6 + pal("transport", "pedestrian") * 0.4,
    "funicular": lambda: pal("ground", "railground"),
    "rail": lambda: pal("ground", "railground"),
}


def surface_style(e) -> str:
    m, c = e["mode"], e.get("cls", "")
    if m == "rail":
        return "rail"
    if m == "tram":
        return "tram"
    if m == "funicular":
        return "funicular"
    if m == "steps":
        return "steps"
    if m == "path":
        return "path"
    if c in ("pedestrian", "living_street"):
        return "pedestrian"
    if c in ("service", "track", "unclassified", "residential"):
        return "road_minor"
    return "road"


def extend_line(en, i0, i1, by):
    """The polyline en[i0..i1], run on by `by` metres along en at either end where en continues."""
    pts = [np.asarray(p, float) for p in en[i0:i1 + 1]]
    if i0 > 0:
        d = en[i0 - 1] - en[i0]
        L = float(np.linalg.norm(d))
        if L > 1e-9:
            pts.insert(0, en[i0] + d / L * min(by, L))
    if i1 < len(en) - 1:
        d = en[i1 + 1] - en[i1]
        L = float(np.linalg.norm(d))
        if L > 1e-9:
            pts.append(en[i1] + d / L * min(by, L))
    return LineString(pts)


def _c(key):
    return tuple(int(x) for x in np.round(colour_of(key)))


def cv_xy(cv, p):
    x, y = cv.xy(p[0], p[1])
    return float(x), float(y)


def offset_line(en, off):
    _, left = G.edge_frame(en)
    return en + left * off


def sleepers(en, every):
    """Points every `every` metres along a polyline, with the unit normal there."""
    seg = np.linalg.norm(np.diff(en, axis=0), axis=1)
    cum = np.r_[0, np.cumsum(seg)]
    if cum[-1] < every:
        return []
    s = np.arange(every / 2, cum[-1], every)
    x = np.interp(s, cum, en[:, 0]); y = np.interp(s, cum, en[:, 1])
    i = np.clip(np.searchsorted(cum, s) - 1, 0, len(seg) - 1)
    d = (en[i + 1] - en[i]) / np.maximum(seg[i], 1e-9)[:, None]
    nrm = np.column_stack([-d[:, 1], d[:, 0]])
    return [(np.array([x[k], y[k]]), nrm[k]) for k in range(len(s))]


def dashes(en, on, off):
    seg = np.linalg.norm(np.diff(en, axis=0), axis=1)
    cum = np.r_[0, np.cumsum(seg)]
    out = []
    s = off / 2
    while s + on <= cum[-1]:
        a = np.array([np.interp(s, cum, en[:, 0]), np.interp(s, cum, en[:, 1])])
        b = np.array([np.interp(s + on, cum, en[:, 0]), np.interp(s + on, cum, en[:, 1])])
        out.append((a, b))
        s += on + off
    return out
