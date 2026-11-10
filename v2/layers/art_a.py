"""Bake-off method A (PLAN_V2 section 7): the inked code render of layers 5-7, with more detail.

Everything here is albedo (layer-05 rule 1): flat material colours, generated detail and ink, never light. Detail is
computed per pixel from the pixel's world position on its surface (from the depth), so it is fixed to the 3D model:
  walls       one facade colour per building (palette buildings.facade_*) in the building's own tone, a sandstone
              plinth, a cornice line at every floor line of the facade layout, an eave cornice, quoins on some
              buildings; coursed ashlar on stone buildings, a banded (rusticated) ground floor on some rendered ones,
              a faint mottle on render; a stone surround, lintel with a keystone and sill round every window, a
              surround and a lintel round every door (phase 3)
  roofs       slate or tile courses parallel to the eave with staggered joints, tile-to-tile tone (a hash per tile),
              seven roof colours in the building's own tone; gravel on flat roofs
  openings    windows with a white frame, glazing bars (a cross, or six panes) and a sill line, each window's glass
              its own tone; shutters on some buildings; doors with a frame, panels and a fanlight; garage doors with
              panels; shop fronts with glazing bars and a striped awning band
  structures  ashlar courses and joints on stone (viaducts, piers, arches, bridge sides), railings as bars
  trees       crowns of leaf clumps (a cell pattern on the crown's surface) with darker gaps between them
Windows, doors and shop fronts are the facade layout's rectangles (straight by construction, brief 6); shutters stand
beside a window only where both fit inside the wall's outline.
"""
from __future__ import annotations

import math

import numpy as np

from v2.layers.common import CLASS, RIGHT, UP, VIEW, pal
from v2.layers.detail import band, gp, ihash, slabs, soft_band, vnoise
from v2.layers.geometry import Mesh, h01, tri_normals

FACADES = ["facade_cream", "facade_ochre", "facade_pink", "facade_yellow", "facade_blue", "facade_sage",
           "facade_white", "facade_apricot", "facade_rose", "facade_green", "facade_terracotta", "facade_grey",
           "facade_butter"]
# pitched roofs: (palette colour, courses, share of the buildings); slate is the city's roof
ROOFS = [("roof_tile_old", "tile", 0.1), ("roof_tile", "tile", 0.08), ("roof_tile_brown", "tile", 0.05),
         ("roof_slate_dark", "slate", 0.27), ("roof_slate_blue", "slate", 0.17), ("roof_slate_warm", "slate", 0.08),
         ("roof_slate", "slate", 0.25)]
SHUTTERS = ["shutter_green", "shutter_blue", "shutter_red", "shutter_grey"]
DOORS = ["door_green", "door_red", "door_blue", "door_wood"]
AWNINGS = ["awning_red", "awning_green", "awning_blue", "awning_yellow"]
OPEN_KIND = {"window": 0, "door": 1, "garage": 2, "shopfront": 3, "shutter": 4}


def B(name):
    return pal("buildings", name)


def mix(a, b, t):
    return a * (1 - t) + b * t


def landmark_styles() -> dict:
    """Well-known buildings' own materials, by ACT building id (v2/data/structures/landmark_styles.json)."""
    import json
    from v2.config import V2
    return json.loads((V2 / "data" / "structures" / "landmark_styles.json").read_text())["buildings"]


class Style:
    """One building's materials, chosen once from its id (deterministic)."""

    def __init__(self, bid: str, roof_shape: str, known: dict | None = None):
        known = known or {}                    # a well-known building's own materials (landmark_styles.json)
        self.facade = known.get("facade") or FACADES[int(h01(bid + "facade") * len(FACADES)) % len(FACADES)]
        stone = known["stone"] if "stone" in known else (h01(bid + "w") < 0.18 and "facade" not in known)
        # the building's own tone: every house a little lighter or darker than its neighbour of the same colour
        self.stone = stone
        self.wall = np.minimum((B("wall_stone") if stone else B(self.facade)) * (0.93 + 0.11 * h01(bid + "t")), 255.0)
        self.rustic = (not stone) and h01(bid + "g") < 0.3
        self.surround = np.minimum(mix(B("trim"), B("plinth"), 0.12 if stone else 0.3) * (0.96 + 0.06 * h01(bid + "u")), 255.0)
        self.panes = "six" if h01(bid + "p") < 0.4 else "cross"
        rt = 0.93 + 0.12 * h01(bid + "rt")
        if roof_shape == "flat":
            self.roof, self.courses, self.roof_name = B("roof_flat") * rt, None, "roof_flat"
        else:
            r, acc = h01(bid + "r"), 0.0
            for name, courses, share in ROOFS:
                acc += share
                if r < acc:
                    break
            if known.get("roof"):
                name, courses = next((n, c) for n, c, _ in ROOFS if n == known["roof"])
            self.roof, self.courses, self.roof_name = B(name) * rt, courses, name
        self.quoins = h01(bid + "q") < 0.35
        self.shutters = h01(bid + "s") < 0.45
        self.shutter = B(SHUTTERS[int(h01(bid + "sc") * len(SHUTTERS)) % len(SHUTTERS)])
        self.door = B(DOORS[int(h01(bid + "d") * len(DOORS)) % len(DOORS)])
        self.awning = B(AWNINGS[int(h01(bid + "a") * len(AWNINGS)) % len(AWNINGS)])


class ArtA:
    """Per-pixel materials of method A for one scene."""

    def __init__(self, scene, bmesh):
        self.scene = scene
        known = landmark_styles()
        self.styles = [Style(b["id"], b.get("roof_shape", ""), known.get(b["id"])) for b in scene.buildings]
        walls = scene.facades["walls"]
        self.walls = walls
        self.w_base = np.array([w["base"][0] for w in walls], float).reshape(-1, 3)
        b1 = np.array([w["base"][1] for w in walls], float).reshape(-1, 3)
        d = b1[:, :2] - self.w_base[:, :2]
        self.w_len = np.maximum(np.linalg.norm(d, axis=1), 1e-6)
        self.w_u = d / self.w_len[:, None]
        self.w_h = np.array([w.get("height", 0.0) for w in walls], float)
        self.w_floors = np.array([w.get("floors", 0) for w in walls], int)
        # every wall's windows and doors as (u0, v0, u1, v1) across and up the wall, for their stone surrounds
        self.w_win = [np.array([r[:4] for r in w["windows"]], float).reshape(-1, 4) for w in walls]
        self.w_door = [np.array([r[:4] for r in w["doors"]], float).reshape(-1, 4) for w in walls]
        self.tri_wall = self._wall_of_tris(bmesh)
        self.materials = None        # method B: {name: (image (H, W, 3) float, (width_m, height_m))}

    def tex(self, name, a, b):
        """Method B: material `name` sampled at (a, b) metres across and up (tiled); None without that material."""
        if not self.materials or name not in self.materials:
            return None
        img, (wm, hm) = self.materials[name]
        H, W = img.shape[:2]
        x = (np.mod(a, wm) / wm * W).astype(int).clip(0, W - 1)
        y = ((1 - np.mod(b, hm) / hm) * H).astype(int).clip(0, H - 1)
        return img[y, x]

    def _wall_of_tris(self, M):
        """The facade wall each wall triangle lies on (same building, same plane), or -1."""
        bidx = {b["id"]: i for i, b in enumerate(self.scene.buildings)}
        by_b = {}
        for wi, w in enumerate(self.walls):
            by_b.setdefault(bidx.get(w["building"], -1), []).append(wi)
        V, T = M["V"], M["T"]
        nrm, _ = tri_normals(V, T)
        cen = V[T].mean(1)
        out = np.full(len(T), -1, np.int64)
        for t in np.flatnonzero(M["kind"] == 2):
            ws = by_b.get(int(M["obj"][t]))
            if not ws:
                continue
            ws = np.array(ws)
            un = np.column_stack([-self.w_u[ws, 1], self.w_u[ws, 0]])          # wall plane normal (either side)
            align = np.abs(un @ nrm[t, :2])
            rel = cen[t, :2] - self.w_base[ws, :2]
            dist = np.abs((rel * un).sum(1))
            u = (rel * self.w_u[ws]).sum(1)
            ok = (align > 0.98) & (dist < 0.25) & (u > -0.3) & (u < self.w_len[ws] + 0.3)
            if ok.any():
                out[t] = ws[ok][np.argmin(dist[ok])]
        return out

    # ------------------------------------------------------------------ openings (and shutters) as quads
    def openings_mesh(self, offset=0.05):
        from shapely.geometry import Polygon, box
        from v2.data.scene.facades import window_world
        bidx = {b["id"]: i for i, b in enumerate(self.scene.buildings)}
        M = Mesh()
        kind, frame, bld = [], [], []

        def add(w, bi, r, k, cls):
            c = np.array(window_world(w, [float(x) for x in r[:4]]), float)
            nx, ny = w["normal"]
            c = c + np.array([nx * offset, ny * offset, 0.0])
            M.quad(c[0], c[1], c[2], c[3], cls, bi, "buildings.window")
            kind.extend([OPEN_KIND[k]] * 2)
            frame.extend([np.r_[c[0], c[1] - c[0], c[3] - c[0]]] * 2)
            bld.extend([bi] * 2)
        for w in self.walls:
            bi = bidx.get(w["building"])
            if bi is None:
                continue
            st = self.styles[bi]
            outline = Polygon(w["outline"]) if len(w.get("outline", [])) >= 4 else None
            for r in w["windows"]:
                add(w, bi, r, "window", CLASS["window"])
                if st.shutters and outline is not None and outline.is_valid:
                    u0, v0, u1, v1 = (float(x) for x in r[:4])
                    sw = (u1 - u0) / 2
                    for s in ((u0 - sw - 0.05, v0, u0 - 0.05, v1), (u1 + 0.05, v0, u1 + 0.05 + sw, v1)):
                        if outline.buffer(-0.05).contains(box(*s)):
                            add(w, bi, s, "shutter", CLASS["shutter"])
            for r in w["doors"]:
                add(w, bi, r, "garage" if (len(r) > 5 and r[5] == "garage") else "door", CLASS["door"])
            for r in w["shopfronts"]:
                add(w, bi, r, "shopfront", CLASS["shopfront"])
        out = M.done()
        # decals: an opening is seen over its own wall even where ACT has another surface of the building within
        # 0.25 m in front of it (duplicated walls); its stored depth stays its own (render._mesh_layer)
        out["bias"] = np.full(len(out["T"]), -0.25)
        out["open_kind"] = np.array(kind, np.int8)
        out["frame"] = np.array(frame, float).reshape(-1, 9)
        out["open_bld"] = np.array(bld, np.int64)
        return out

    # ------------------------------------------------------------------ shading
    def walls_rgb(self, bi, wi, P, px, py, cls_out=None):
        """Wall pixels: facade colour, plinth, floor cornices, eave cornice, quoins. `cls_out` (array of the pixels'
        classes) receives CLASS["trim"] where the pixel is stone trim (plinth, cornices, quoins), a material of its own."""
        n = len(bi)
        rgb = np.zeros((n, 3))
        base = np.array([self.styles[b].wall for b in bi]) if n else np.zeros((0, 3))
        rgb[:] = base
        has = wi >= 0
        if has.any():
            w = wi[has]
            rel = P[has, :2] - self.w_base[w, :2]
            u = (rel * self.w_u[w]).sum(1)
            v = P[has, 2] - self.w_base[w, 2]
            H = np.maximum(self.w_h[w], 0.1)
            L = self.w_len[w]
            c = rgb[has]
            if self.materials:
                names = np.array([("wall_stone" if self.styles[b].stone else
                                   "wall_" + self.styles[b].facade.split("_", 1)[1]) for b in bi[has]])
                for nm in np.unique(names):
                    mm = names == nm
                    t = self.tex(nm, u[mm], v[mm])
                    if t is not None:
                        c[mm] = t
            trim = B("trim")
            sty = [self.styles[b] for b in bi[has]]
            # the wall's own surface: coursed ashlar on stone buildings; on render a faint mottle and, on some
            # buildings, a banded ground floor
            stone_w = np.array([x.stone for x in sty], bool)
            t, j = slabs(u[stone_w], v[stone_w], 0.8, 0.36, joint=0.05, tone=0.05, seed=31)
            c[stone_w] *= (t * (1 - 0.16 * j))[:, None]
            rend = ~stone_w
            c[rend] *= (1 + (vnoise(u[rend] + 13.0 * w[rend], v[rend], 1.6, 33) - 0.5) * 0.05)[:, None]
            rus = np.array([x.rustic for x in sty], bool) & (v > 0.82) & (v < 3.42)
            c[rus] *= (1 - 0.16 * soft_band(v[rus], 0.45, 0.07))[:, None]
            plinth = v < 0.7
            c[plinth] = mix(c[plinth], B("plinth"), 0.75)
            c[(v >= 0.7) & (v < 0.82)] *= 0.86                               # the plinth's top edge
            # a cornice line at each floor line of the layout (3.6 m, then every 3.0 m) below the eave
            fl = (v > 3.0) & (v < H - 0.6) & band(v - 3.6, 3.0, 0.16)
            c[fl] = mix(c[fl], trim, 0.55) * 0.97
            c[(v > 3.0) & (v < H - 0.6) & band(v - 3.6 + 0.14, 3.0, 0.08)] *= 0.86   # its shadowless underside line
            eave = (v > H - 0.42) & (v <= H + 0.02) & (H > 2.5)
            c[eave] = trim
            c[(v > H - 0.52) & (v <= H - 0.42) & (H > 2.5)] *= 0.82
            q = np.array([self.styles[b].quoins for b in bi[has]])
            corner = q & ((u < 0.5) | (u > L - 0.5)) & (np.floor(v / 0.4) % 2 == 0) & (v > 0.7) & (v < H - 0.45)
            c[corner] = mix(c[corner], trim, 0.8)
            # stone round the openings: jambs, a lintel with a keystone and a sill at every window; jambs and a
            # lintel at every door (the opening itself is drawn over it by its own quad)
            sur = np.zeros(len(w), bool)
            shade = np.ones(len(w))
            order = np.argsort(w, kind="stable")
            cuts = np.flatnonzero(np.diff(w[order])) + 1
            for g in np.split(order, cuts):
                wn, dr = self.w_win[w[g[0]]], self.w_door[w[g[0]]]
                if not len(wn) and not len(dr):
                    continue
                uu, vv = u[g][:, None], v[g][:, None]
                hit = np.zeros(len(g), bool)
                sh = np.ones(len(g))
                if len(wn):
                    u0, v0, u1, v1 = wn[:, 0][None], wn[:, 1][None], wn[:, 2][None], wn[:, 3][None]
                    box = (uu > u0 - 0.15) & (uu < u1 + 0.15) & (vv > v0 - 0.05) & (vv < v1 + 0.24)
                    sill = (uu > u0 - 0.24) & (uu < u1 + 0.24) & (vv > v0 - 0.17) & (vv <= v0 - 0.03)
                    key = box & (np.abs(uu - (u0 + u1) / 2) < 0.11) & (vv > v1)
                    under = sill & (vv < v0 - 0.12)
                    hit |= (box | sill).any(1)
                    sh = np.where(key.any(1) | under.any(1), 0.88, sh)
                if len(dr):
                    u0, v0, u1, v1 = dr[:, 0][None], dr[:, 1][None], dr[:, 2][None], dr[:, 3][None]
                    box = (uu > u0 - 0.2) & (uu < u1 + 0.2) & (vv < v1 + 0.3)
                    top = box & (vv > v1 + 0.2)
                    hit |= box.any(1)
                    sh = np.where(top.any(1), 0.88, sh)
                sur[g] = hit
                shade[g] = sh
            sur &= (v > 0.82) & (v < H - 0.52) & ~corner
            c[sur] = np.array([x.surround for x in sty]).reshape(-1, 3)[sur] * shade[sur, None]
            rgb[has] = c
            if cls_out is not None:
                stone = (v < 0.82) | ((v > 3.0) & (v < H - 0.6) & band(v - 3.6 + 0.04, 3.0, 0.3)) | \
                    ((v > H - 0.52) & (v <= H + 0.02) & (H > 2.5)) | corner | sur
                sub = cls_out[has]
                sub[stone] = CLASS["trim"]
                cls_out[has] = sub
        return rgb * gp(px, py, 0.02, 11)[:, None] if n else rgb

    def roofs_rgb(self, bi, P, nrm, px, py):
        n = len(bi)
        rgb = np.zeros((n, 3))
        if not n:
            return rgb
        base = np.array([self.styles[b].roof for b in bi])
        kind = np.array([{None: 0, "slate": 1, "tile": 2}[self.styles[b].courses] for b in bi])
        h = np.linalg.norm(nrm[:, :2], axis=1)
        slope_ok = (h > 0.09) & (kind > 0)                                # pitched (over ~5 degrees)
        s = np.where(h[:, None] > 1e-6, nrm[:, :2] / np.maximum(h, 1e-6)[:, None], 0)   # downhill, horizontal
        e = np.column_stack([-s[:, 1], s[:, 0]])                            # along the eave
        along = (P[:, :2] * e).sum(1)
        sinA = np.clip(h, 1e-3, 1)
        down = -P[:, 2] / sinA                                              # distance down the slope
        # courses of 0.45 m (tile) and 0.5 m (slate): larger than life, as a drawing's are, so that at 0.125 m a pixel
        # the lines are a minority of a roof face's pixels and the face's median stays the slate's own colour
        course = np.where(kind == 2, 0.45, 0.5)
        width = np.where(kind == 2, 0.34, 0.4)
        row = np.floor(down / course)
        col = np.floor((along + (row % 2) * width / 2) / width)
        tone = 1 + (ihash(row, col, bi) - 0.5) * np.where(kind == 2, 0.09, 0.06)
        rgb = base * np.where(slope_ok, tone, 1.0)[:, None]
        # courses and joints by coverage, at the spacing the camera samples this roof face with (one map pixel
        # across or up the screen, measured on the face). They fade out before a line and its pixel fill half a
        # course: a face seen at a grazing angle cannot hold the lines and would show their average darkening in
        # most pixels, a tone that a face seen square on (clean slates between lines) does not have. So no face is
        # darker or lighter than another of the same roof (L5.1)
        n3 = nrm / np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
        vn = n3 @ VIEW
        vn = np.where(np.abs(vn) < 0.05, -0.05, vn)
        t_down = np.column_stack([s * n3[:, 2:3], -h])
        t_along = np.column_stack([e, np.zeros(n)])
        px_down, px_along = np.zeros(n), np.zeros(n)
        for axis in (RIGHT, UP):
            d = 0.125 * (axis[None, :] - VIEW[None, :] * ((n3 @ axis) / vn)[:, None])
            px_down = np.maximum(px_down, np.abs((d * t_down).sum(1)))
            px_along = np.maximum(px_along, np.abs((d * t_along).sum(1)))
        px_down, px_along = np.maximum(px_down, 0.125), np.maximum(px_along, 0.125)
        keep_c = np.clip((0.4 * course - px_down) / (0.1 * course), 0, 1) * slope_ok
        keep_j = np.clip((0.4 * width - px_along) / (0.1 * width), 0, 1) * keep_c
        lines = 1 - 0.26 * keep_c * soft_band(down, course, 0.10 * course, px_down)
        lines *= 1 - 0.12 * keep_j * soft_band(along + (row % 2) * width / 2, width, 0.08 * width, px_along)
        rgb *= lines[:, None]
        if self.materials:
            names = np.array([self.styles[b].roof_name for b in bi])
            for nm in np.unique(names):
                mm = names == nm
                t = self.tex(nm, along[mm], down[mm])
                if t is not None:
                    rgb[mm] = t
        flat = ~slope_ok
        rgb[flat] = base[flat] * gp(px[flat], py[flat], 0.09, 13)[:, None] if flat.any() else rgb[flat]   # gravel
        return rgb

    def openings_rgb(self, O, ti, P, bi):
        """Opening pixels from their local (s, t) across and up the rectangle (metres): (albedo, class). Each part is
        a material of its own for the shadow detector (L5.1): glass "window", frames, bars and sills "trim", door
        panels "door", shutters "shutter", awnings "shopfront"."""
        k = O["open_kind"][ti]
        F = O["frame"][ti]
        o, au, av = F[:, 0:3], F[:, 3:6], F[:, 6:9]
        W = np.linalg.norm(au, axis=1)
        H = np.linalg.norm(av, axis=1)
        rel = P - o
        s = (rel * au).sum(1) / np.maximum(W ** 2, 1e-9) * W               # metres across
        t = (rel * av).sum(1) / np.maximum(H ** 2, 1e-9) * H               # metres up
        rgb = np.zeros((len(k), 3))
        cls = np.select([k == OPEN_KIND["shutter"], np.isin(k, (OPEN_KIND["door"], OPEN_KIND["garage"])),
                         k == OPEN_KIND["shopfront"]], [CLASS["shutter"], CLASS["door"], CLASS["shopfront"]],
                        CLASS["window"]).astype(np.int64)
        trim, glass = B("trim"), B("window")
        done = np.zeros(len(k), bool)
        st = [self.styles[b] for b in bi]
        door = np.array([x.door for x in st]).reshape(-1, 3)
        shut = np.array([x.shutter for x in st]).reshape(-1, 3)
        awn = np.array([x.awning for x in st]).reshape(-1, 3)
        fr = 0.09
        edge = (s < fr) | (s > W - fr) | (t < fr) | (t > H - fr)
        # windows: frame, glass, a central glazing bar and a transom, a sill line at the bottom
        m = k == OPEN_KIND["window"]
        # each window's glass its own tone (curtains, blinds: a hash of the window), the same all over the window
        gl = glass * (0.86 + 0.3 * ihash(ti // 2, 51))[:, None]
        c = np.where(edge[:, None], trim, gl)
        six = np.array([x.panes == "six" for x in st], bool)
        bar = (np.abs(s - W / 2) < 0.04) | np.where(six, (np.abs(t - H / 3) < 0.035) | (np.abs(t - 2 * H / 3) < 0.035),
                                                     np.abs(t - H * 0.68) < 0.04)
        c = np.where((bar & ~edge)[:, None], trim, c)
        c = np.where((t < 0.05)[:, None], trim * 0.85, c)
        rgb[m] = c[m]
        cls[m & (edge | bar | (t < 0.05))] = CLASS["trim"]
        # shutters: slats
        m = k == OPEN_KIND["shutter"]
        c = shut * np.where(band(t, 0.14, 0.03), 0.78, 1.0)[:, None]
        c = np.where(edge[:, None], shut * 0.8, c)
        rgb[m] = c[m]
        # doors: frame, two panels, a fanlight
        m = k == OPEN_KIND["door"]
        fan = t > H - 0.42
        c = np.where(fan[:, None], glass, door)
        panel = (~fan) & ((np.abs(s - W / 2) < 0.03) | band(t, 0.9, 0.05, phase=0.2))
        c = np.where(panel[:, None], door * 0.8, c)
        dtrim = edge | (np.abs(t - (H - 0.44)) < 0.04)
        c = np.where(dtrim[:, None], trim, c)
        rgb[m] = c[m]
        cls[m & fan & ~dtrim] = CLASS["window"]
        cls[m & dtrim] = CLASS["trim"]
        # garage doors: horizontal panels
        m = k == OPEN_KIND["garage"]
        c = door * np.where(band(t, 0.5, 0.05), 0.75, 1.0)[:, None]
        c = np.where(edge[:, None], trim, c)
        rgb[m] = c[m]
        cls[m & edge] = CLASS["trim"]
        # shop fronts: a striped awning band on top, glazing bars, a dark frame
        if self.materials:
            for kk, nm in ((OPEN_KIND["window"], "window_casement"), (OPEN_KIND["door"], "door_panel"),
                           (OPEN_KIND["garage"], "door_garage"), (OPEN_KIND["shopfront"], "window_shop")):
                mm = k == kk
                if mm.any() and nm in self.materials:
                    img = self.materials[nm][0]
                    hh, ww = img.shape[:2]
                    x = (s[mm] / np.maximum(W[mm], 1e-6) * ww).astype(int).clip(0, ww - 1)
                    y = ((1 - t[mm] / np.maximum(H[mm], 1e-6)) * hh).astype(int).clip(0, hh - 1)
                    rgb[mm] = img[y, x]
            done = np.isin(k, [OPEN_KIND[x] for x in ("window", "door", "garage", "shopfront")])
        else:
            done = np.zeros(len(k), bool)
        m = (k == OPEN_KIND["shopfront"]) & ~done
        aw = t > H - 0.5
        stripe = np.floor(s / 0.3) % 2 == 0
        ca = np.where(stripe[:, None], awn, mix(awn, trim, 0.85))
        ca = np.where((t > H - 0.08)[:, None], awn * 0.75, ca)
        bars = band(s, 1.25, 0.08) | (np.abs(t - 0.45) < 0.05) | edge
        cg = np.where(bars[:, None], door * 0.9, glass)
        c = np.where(aw[:, None], ca, cg)
        rgb[m] = c[m]
        cls[m & ~aw & bars] = CLASS["door"]                  # the shop's painted frame
        cls[m & ~aw & ~bars] = CLASS["window"]
        return rgb, cls

    # ------------------------------------------------------------------ structures and trees
    @staticmethod
    def stone_rgb(base, P, nrm, px, py, cls):
        """Ashlar: courses every 0.5 m, joints every 0.9 m (staggered) along the face; railings as bars."""
        rgb = base.copy()
        h = np.linalg.norm(nrm[:, :2], axis=1)
        vertical = h > 0.7
        d = np.where(h[:, None] > 1e-6, nrm[:, :2] / np.maximum(h, 1e-6)[:, None], 0)
        along = P[:, 0] * -d[:, 1] + P[:, 1] * d[:, 0]
        row = np.floor(P[:, 2] / 0.5)
        stone = vertical & (cls != CLASS["parapet"]) & (cls != CLASS["lift"])
        tone = 1 + (ihash(row, np.floor((along + (row % 2) * 0.45) / 0.9)) - 0.5) * 0.08
        rgb[stone] *= tone[stone, None]
        joint = stone & (band(P[:, 2], 0.5, 0.06) | band(along + (row % 2) * 0.45, 0.9, 0.06))
        rgb[joint] *= 0.8
        bars = vertical & ((cls == CLASS["parapet"]) | (cls == CLASS["lift"])) & band(along, 0.25, 0.06)
        rgb[bars] *= 0.72
        return rgb * gp(px, py, 0.02, 17)[:, None]

    @staticmethod
    def crown_rgb(col, P, tree_id, px, py):
        """Leaf clumps: a 3D cell pattern (0.8 m cells) on the crown's surface, lighter and darker clumps and dark
        gaps between them. No light: the pattern does not depend on the sun or the view."""
        q = P / 0.8
        cell = np.floor(q)
        f = q - cell - 0.5
        r = np.sqrt((f ** 2).sum(1))
        tone = 1 + (ihash(cell[:, 0], cell[:, 1], cell[:, 2], tree_id) - 0.5) * 0.22
        out = col * tone[:, None]
        gap = r > 0.62
        out[gap] *= 0.72
        return out * gp(px, py, 0.04, 7)[:, None]
