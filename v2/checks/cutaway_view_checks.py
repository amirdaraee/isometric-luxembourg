"""The landmark cutaways in the viewer: the browser's part of checks K2, K5 and K6 (spec:
v2/docs/specs/landmark-cutaways.md), on the built release, with a headless browser (v2/web/scripts/cutaway_checks.mjs).

What the viewer must show is worked out here from the release's tiles alone: per map pixel the nearest surface of the
colour layers (ties to the later layer), with layer 5's pixels of the replaced buildings left out and the cutaway's
tiles in their place. The frames are read at one screen pixel per map pixel, so they compare pixel for pixel.

KV0   page errors: 0
K6    off means off: a view that never had the cutaway on, the cutaway turned on and off again: 0 pixels differ, by
      day and by night, per landmark and at the far zoom (where the merged far tiles give way while a cutaway is on);
      on, the frame does differ. With layer 5 off the cutaway is off: 0 pixels of layer 5. With the tunnel view the
      cut building is part of the faded city: it shows through the fade, and both off is the plain frame again
K2    every interior pixel drawn (layer 5, class cut, inside wall, inside roof, floor or slab) lies in the opening
      mask of the tiles: 0 outside. And the whole frame is the tiles': 0 pixels where the layer or the class differs
      from the expected nearest surface, 0 where layer 5's colour differs (nothing drawn twice, nothing lost)
K5    depth: probe vehicles (cars on a grid at the floor's level, through and round the landmark) are drawn exactly
      where their boxes are not behind the expected nearest surface (the viewer's rule: depth - eps <= the surface;
      pixels on a silhouette, within 1 px of a depth step or of the box's outline, are counted apart, as C4 does); label
      points on and 3 m behind the cutaway's surfaces are hidden or shown as that surface says
The opening's own cast shadow (K3's ?hour part) is not built: the shadow height map still holds the whole building.
"""
from __future__ import annotations

import json
import subprocess
import zlib
from pathlib import Path

import numpy as np
from scipy import ndimage

from v2.checks.framework import Report
from v2.checks.g1_checks import WEB, box_pixels, box_tris, viewer_server
from v2.layers.common import TILE, read_tile

VIEW_W, VIEW_H = 1600, 1200
DATE = "2026-06-21"
HOURS = (13, 23)
LAYER_ID = {"ground": 1, "relief": 2, "water": 3, "transport": 4, "buildings": 5, "structures": 6, "trees": 7}
CAR = (4.4, 1.8, 1.45)


def frame(folder: Path, name: str, W=VIEW_W, H=VIEW_H):
    return np.frombuffer(zlib.decompress((folder / f"{name}.rgb.z").read_bytes()), np.uint8).reshape(H, W, 3)


class Window:
    """A window of the release's zoom-0 tiles: map pixels x0.. x0 + W, y0.. y0 + H."""

    def __init__(self, rel: Path, idx: dict, x0: int, y0: int, W=VIEW_W, H=VIEW_H):
        self.rel, self.idx, self.x0, self.y0, self.W, self.H = rel, idx, x0, y0, W, H

    def layer(self, folder: Path, tiles: dict):
        """A tile set in the window: dict depth (inf where nothing), rgb, k, ids."""
        out = {"depth": np.full((self.H, self.W), np.inf), "rgb": np.zeros((self.H, self.W, 3), np.uint8),
               "k": np.zeros((self.H, self.W), np.uint8), "ids": np.zeros((self.H, self.W), np.uint32)}
        for ty in range(self.y0 // TILE, (self.y0 + self.H - 1) // TILE + 1):
            for tx in range(self.x0 // TILE, (self.x0 + self.W - 1) // TILE + 1):
                name = f"{tx}_{ty}"
                if name not in tiles:
                    continue
                t = read_tile(folder / "0", name, tiles[name])
                a0, b0 = max(self.x0, tx * TILE), max(self.y0, ty * TILE)
                a1, b1 = min(self.x0 + self.W, (tx + 1) * TILE), min(self.y0 + self.H, (ty + 1) * TILE)
                src = (slice(b0 - ty * TILE, b1 - ty * TILE), slice(a0 - tx * TILE, a1 - tx * TILE))
                dst = (slice(b0 - self.y0, b1 - self.y0), slice(a0 - self.x0, a1 - self.x0))
                for key in out:
                    if key in t:
                        out[key][dst] = t[key][src]
        return out

    def expected(self, cut: list):
        """What the viewer shows with the cutaways `cut` on: per pixel the depth, the layer and class of the nearest
        surface, layer 5's colour, and whether it comes from a cutaway's tiles."""
        L = self.idx["layers"]
        g = self.layer(self.rel / "ground", L["ground"]["tiles"]["0"])
        r = self.layer(self.rel / "relief", L["relief"]["tiles"]["0"])
        wall = np.isfinite(r["depth"]) & (r["k"] == 3) & (~np.isfinite(g["depth"]) | (r["depth"] <= g["depth"]))
        depth = np.where(wall, r["depth"], np.where(np.isfinite(g["depth"]), g["depth"], r["depth"]))
        layer = np.where(np.isfinite(depth), np.where(wall | ~np.isfinite(g["depth"]), 2, 1), 0).astype(np.uint8)
        k = np.where(wall, 0, g["k"]).astype(np.uint8)
        rgb = np.zeros((self.H, self.W, 3), np.uint8)
        from_cut = np.zeros((self.H, self.W), bool)
        replaced = [i for n in cut for i in self.idx["cutaways"]["landmarks"][n]["replaces_index"]]

        def put(t, lid, is_cut=False):
            nonlocal depth
            m = t["depth"] <= depth                       # ties go to the later layer
            depth = np.where(m, t["depth"], depth)
            layer[m] = lid
            k[m] = t["k"][m]
            from_cut[m] = is_cut
            if lid == 5:
                rgb[m] = t["rgb"][m]
        for name in ("water", "transport", "buildings", "structures", "trees"):
            t = self.layer(self.rel / name, L[name]["tiles"]["0"])
            if name == "buildings" and replaced:
                t["depth"] = np.where(np.isin(t["ids"] >> 8, replaced), np.inf, t["depth"])
            put(t, LAYER_ID[name])
            if name == "buildings":
                for n in cut:
                    put(self.layer(self.rel / "cutaways" / n, self.idx["cutaways"]["landmarks"][n]["tiles"]["0"]), 5, True)
        return {"depth": depth, "layer": layer, "k": k, "rgb": rgb, "from_cut": from_cut}


def probe_grid(lm: dict, sc_buildings: list, step=4.0, margin=6.0):
    """Probe cars on a grid at the floor's level over the landmark's footprint and a margin: (E, N, z, heading)."""
    pts = np.array([p for i in lm["replaces_index"] for poly in sc_buildings[i]["footprint"] for p in poly[0]], float)
    x0, y0, x1, y1 = pts[:, 0].min() - margin, pts[:, 1].min() - margin, pts[:, 0].max() + margin, pts[:, 1].max() + margin
    E, N = np.meshgrid(np.arange(x0, x1, step), np.arange(y0, y1, step))
    return [(float(e), float(n), float(lm["floor_z"]), 0.5) for e, n in zip(E.ravel(), N.ravel())]


def check_cutaways_view(ctx):
    from v2.config.camera import camera
    from v2.layers.common import Scene
    P = ctx.params["g3"]
    rel = ctx.dep("release")
    rep = Report("cutaways_view")
    idx = json.loads((rel / "index.json").read_text())
    cuts = idx.get("cutaways", {}).get("landmarks", {})
    if not cuts:
        rep.info("KV", "cutaways in the release: none; nothing to check", 0)
        return rep.result()
    sc = Scene(ctx.dep("scene"))
    oe, on = camera()["origin_en"]
    eps = float(idx["config"]["vehicles"]["depth_eps_m"])
    opening_k = idx["cutaways"]["opening_k"]
    out = ctx.out
    jobs = {"size": [VIEW_W, VIEW_H], "date": DATE, "hours": list(HOURS), "landmarks": {}}
    ex0, ey0, ex1, ey1 = idx["extent_px"]
    jobs["whole"] = [(ex0 + ex1) // 2, (ey0 + ey1) // 2, round(min(VIEW_W / (ex1 - ex0), VIEW_H / (ey1 - ey0)) * 0.95, 4)]
    work = {}
    for name, lm in cuts.items():
        bx0, by0, bx1, by1 = lm["bbox_px"]
        cx, cy = (bx0 + bx1) // 2, (by0 + by1) // 2
        win = Window(rel, idx, cx - VIEW_W // 2, cy - VIEW_H // 2)
        exp = win.expected([name])
        probes = probe_grid(lm, sc.buildings)
        inst = [v for e, n, z, h in probes for v in (e - oe, n - on, z, h)]
        size = [v for _ in probes for v in CAR + (0,)]
        # label points: on the cutaway's surfaces (0.5 m behind: shown unless something stands in front) and 3 m behind
        r, c = np.nonzero(exp["from_cut"][::9, ::9])
        r, c = r * 9, c * 9
        d = exp["depth"][r, c]
        labels = [[float(win.x0 + cc + 0.5), float(win.y0 + rr + 0.5), float(dd + off)] for rr, cc, dd in zip(r, c, d)
                  for off in (0.5, 3.0)]
        jobs["landmarks"][name] = {"view": [cx, cy], "probes": {"inst": inst, "size": size}, "labels": labels}
        work[name] = (win, exp, probes, labels)
    (out / "jobs.json").write_text(json.dumps(jobs))
    with viewer_server(rel) as base:
        run = subprocess.run(["node", str(WEB / "scripts" / "cutaway_checks.mjs"), base, str(out)], cwd=WEB,
                             capture_output=True, text=True, timeout=3600)
    if run.returncode:
        raise RuntimeError("the cutaways' viewer checks failed to run: " + (run.stderr or run.stdout)[-3000:])
    R = json.loads((out / "view.json").read_text())
    rep.info("KV0a", "browser GPU; views at 1 px per map px", {**R["gpu"], "size": [VIEW_W, VIEW_H], "hours": list(HOURS)})
    rep.at_most("KV0", "page errors", len(R["errors"]), 0, R["errors"])
    for name, lm in cuts.items():
        win, exp, probes, labels = work[name]
        V = R["landmarks"][name]
        nm = lm["name"]
        # ---------------------------------------------------------------- K6
        for h in HOURS:
            rep.at_most(f"K6v-off-{name}-{h:02d}", f"{nm}, {h:02d}:00: pixels that differ between a view that never had the "
                        "cutaway on and the same view after on and off again", V["off_differs_px"][str(h)], P["cutview_off_differs_px"])
            rep.at_least(f"K6v-on-{name}-{h:02d}", f"{nm}, {h:02d}:00: pixels the cutaway changes when on",
                         V["on_differs_px"][str(h)], P["cutview_on_min_px"])
        rep.at_most(f"K6v-layer5-{name}", f"{nm}: layer 5 pixels drawn with layer 5 off and the cutaway on",
                    V["buildings_off_layer5_px"], 0)
        if "xray_on_differs_px" in V:
            rep.at_least(f"K6v-xray-on-{name}", f"{nm}: in tunnel view, pixels the cutaway changes when on (it shows "
                         "through the fade)", V["xray_on_differs_px"], 1)
            rep.at_most(f"K6v-xray-off-{name}", f"{nm}: in tunnel view, pixels that differ after the cutaway is on and off "
                        "again; and after the tunnel view is off too, from the plain frame",
                        V["xray_off_differs_px"] + V["xray_then_off_differs_px"], P["cutview_off_differs_px"])
        # ---------------------------------------------------------------- K2 and the whole frame
        F = frame(out, f"{name}_layer")
        f_layer = np.round(F[..., 0] / 255 * 8).astype(np.uint8)
        f_k = np.round(F[..., 1] / 255 * 16).astype(np.uint8)
        drawn_in = (f_layer == 5) & np.isin(f_k, opening_k)
        mask = exp["from_cut"] & np.isin(exp["k"], opening_k)
        tile_mask = np.isin(win.layer(rel / "cutaways" / name, lm["tiles"]["0"])["k"], opening_k)
        rep.at_most(f"K2v-{name}", f"{nm}: interior pixels drawn by the viewer outside the tiles' opening mask (of "
                    f"{int(drawn_in.sum())} drawn; the mask holds {int(tile_mask.sum())} px in the view)",
                    int((drawn_in & ~tile_mask).sum()), 0)
        five = exp["layer"] == 5
        wrong = (f_layer != exp["layer"]) | (five & (f_k != exp["k"]))
        rr, cc = np.nonzero(wrong)
        rep.at_most(f"K2v-frame-{name}", f"{nm}: pixels of the view whose layer, or class in layer 5, is not the tiles' "
                    f"nearest surface with the cutaway in place (of {wrong.size}; {int(mask.sum())} of the opening seen)",
                    int(wrong.sum()), P["cutview_frame_px"],
                    [{"px": [int(win.x0 + c), int(win.y0 + r)], "viewer": [int(f_layer[r, c]), int(f_k[r, c])],
                      "tiles": [int(exp["layer"][r, c]), int(exp["k"][r, c])]} for r, c in zip(rr[:8], cc[:8])])
        A = frame(out, f"{name}_albedo")
        dc = np.abs(A.astype(int) - exp["rgb"].astype(int)).max(-1)
        rep.at_most(f"K2v-colour-{name}", f"{nm}: layer 5 pixels (the cutaway's and the other buildings', "
                    f"{int(five.sum())}) whose colour is not the tiles'", int((five & (dc > 0)).sum()), P["cutview_frame_px"])
        # ---------------------------------------------------------------- K5: probe vehicles
        Fp = frame(out, f"{name}_probes")
        seen = np.round(Fp[..., 0] / 255 * 8).astype(np.uint8) == 8
        want = np.zeros(seen.shape, bool)
        covered = np.zeros(seen.shape, bool)
        near_eq = np.zeros(seen.shape, bool)
        hidden_by_cut = 0
        for e, n, z, h in probes:
            Vb, Tb = box_tris(e, n, z, h, *CAR)
            bx, by, bd = box_pixels(Vb, Tb)
            c_, r_ = bx - win.x0, by - win.y0
            ok = (c_ >= 0) & (c_ < VIEW_W) & (r_ >= 0) & (r_ < VIEW_H)
            c_, r_, bd = c_[ok], r_[ok], bd[ok]
            D = exp["depth"][r_, c_]
            vis = bd - eps <= D
            want[r_[vis], c_[vis]] = True
            covered[r_, c_] = True
            near_eq[r_, c_] |= np.abs(bd - eps - D) < 0.02
            hidden_by_cut += int((~vis & exp["from_cut"][r_, c_]).sum())
        diff = seen != want
        dd = np.where(np.isfinite(exp["depth"]), exp["depth"], 1e6)
        step = (ndimage.maximum_filter(dd, 3) - ndimage.minimum_filter(dd, 3)) > 1.0
        outline = ndimage.binary_dilation(covered) & ~ndimage.binary_erosion(covered)
        outline |= ndimage.binary_dilation(want) & ~ndimage.binary_erosion(want)
        sil = diff & (step | outline | near_eq)
        mism = diff & ~sil
        rr, cc = np.nonzero(mism)
        rep.at_most(f"K5v-vehicles-{name}", f"{nm}: probe vehicle pixels where the viewer's depth test against the cut "
                    f"building disagrees with the tiles (of {int(covered.sum())} px of {len(probes)} cars; "
                    f"{int(sil.sum())} more on silhouettes)", int(mism.sum()), P["cutview_probe_px"],
                    [{"px": [int(win.x0 + c), int(win.y0 + r)]} for r, c in zip(rr[:8], cc[:8])])
        rep.at_most(f"K5v-silhouette-{name}", f"{nm}: share of probe pixels on silhouettes (edge rounding)",
                    round(float(sil.sum() / max(int(covered.sum()), 1)), 5), P["cutview_silhouette_share"])
        rep.info(f"K5v-probes-{name}", f"{nm}: probe pixels drawn; hidden behind the cutaway's own surfaces",
                 [int(want.sum()), hidden_by_cut])
        # ---------------------------------------------------------------- K5: labels
        got = np.array(V["labels_hidden"])
        L = np.array(labels)
        D = exp["depth"][(L[:, 1] - 0.5 - win.y0).astype(int), (L[:, 0] - 0.5 - win.x0).astype(int)]
        truth = np.isfinite(D) & (D < L[:, 2] - 1.5)
        bad = (got != truth.astype(int))
        rep.at_most(f"K5v-labels-{name}", f"{nm}: label points (on and 3 m behind the cutaway's surfaces, {len(L)}) that "
                    f"the viewer hides or shows against what the tiles say ({int(truth.sum())} hidden)", int(bad.sum()),
                    P["cutview_label_points"], [{"px": L[i, :2].tolist(), "viewer": int(got[i]), "tiles": bool(truth[i])}
                                                 for i in np.flatnonzero(bad)[:8]])
    rep.at_most("K6v-far-off", "far zoom (the whole area): pixels that differ after the cutaways are on and off again",
                R["far"]["off_differs_px"], P["cutview_off_differs_px"])
    rep.at_least("K6v-far-on", "far zoom: pixels the cutaways change when on", R["far"]["on_differs_px"], 1)
    rep.info("K3v", "the opening's own cast shadow moving with ?hour: not built (the shadow height map holds the whole "
             "building, so the opening is lit as if roofed)", "not done")
    return rep.result()
