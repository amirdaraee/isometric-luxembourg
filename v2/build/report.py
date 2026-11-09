"""Report stages: preview images of the scene, and the gate G0 summary.

previews: plan views (buildings by height, the transport graph by height with bridges, tunnels and portals, trees
over the relief), the rail line's height profile through the viaducts, and an isometric view of the buildings and
their windows through the v2 camera. Images are JPEGs under 1 MB.
g0: every check's result, the scene's counts and sizes; published (with the previews) into v2/docs so the owner can
review the gate in the pull request: v2/docs/img/<area>_*.jpg and v2/docs/results/g0_<area>.json.
"""
from __future__ import annotations

import io
import json
import shutil

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.collections import LineCollection, PolyCollection  # noqa: E402
from PIL import Image  # noqa: E402

from v2.config import V2, v2_data  # noqa: E402
from v2.config.camera import depth, en_to_px  # noqa: E402
from v2.data.geo import area_polygon  # noqa: E402
from v2.data.scene.scene import part  # noqa: E402

INK = "#2e2824"


def save(fig, path, quality=85, max_px=2400):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=fig.dpi, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    im = Image.open(buf).convert("RGB")
    im.thumbnail((max_px, max_px), Image.LANCZOS)
    q = quality
    while True:
        im.save(path, "JPEG", quality=q, optimize=True)
        if path.stat().st_size < 950_000 or q <= 40:
            break
        q -= 10


def hillshade(z, step):
    gy, gx = np.gradient(z, step)
    az, alt = np.radians(315), np.radians(45)
    slope = np.arctan(np.hypot(gx, gy)); aspect = np.arctan2(-gx, gy)
    return np.clip(np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect), 0, 1)


def base(ax, T, poly, alpha=0.55):
    step = float(T["step"]); k = max(1, int(round(1.0 / step)))
    z = T["mnt"][::k, ::k]
    hs = hillshade(z, step * k)
    ext = (float(T["e0"]), float(T["e0"]) + T["mnt"].shape[1] * step, float(T["n0"]), float(T["n0"]) + T["mnt"].shape[0] * step)
    ax.imshow(hs, origin="lower", extent=ext, cmap="gray", alpha=alpha, vmin=0, vmax=1)
    x, y = poly.exterior.xy
    ax.plot(x, y, color="#c0392b", lw=1.2, ls="--")
    pad = 40
    b = poly.bounds
    ax.set_xlim(b[0] - pad, b[2] + pad); ax.set_ylim(b[1] - pad, b[3] + pad)
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])


def previews(ctx):
    sc = ctx.dep("scene")
    poly = area_polygon(ctx.area)
    T = np.load(part(sc, "terrain") / "terrain.npz")
    img = ctx.out / "img"; img.mkdir()
    blds = json.loads((part(sc, "buildings") / "buildings.json").read_text())["buildings"]
    g = json.loads((part(sc, "transport") / "graph.json").read_text())
    st = json.loads((part(sc, "structures") / "structures.json").read_text())
    water = json.loads((part(sc, "water") / "water.json").read_text())
    big = ctx.area != "test"
    figsize = (14, 14) if big else (12, 13)
    dpi = 220 if big else 170
    made = []

    def water_patches(ax):
        polys = [np.array(r[0]) for a in water["areas"] for r in a["rings"]]
        ax.add_collection(PolyCollection(polys, facecolor="#8fb8cc", edgecolor="none", alpha=0.9))

    # 1. buildings by height
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    base(ax, T, poly); water_patches(ax)
    polys = [np.array(b["footprint"][0][0]) for b in blds]
    hs = np.array([b["height"] for b in blds])
    pc = PolyCollection(polys, array=hs, cmap="viridis", edgecolor=INK, linewidth=0.15 if big else 0.3)
    pc.set_clim(0, np.percentile(hs, 99) if len(hs) else 1)
    ax.add_collection(pc)
    fig.colorbar(pc, ax=ax, fraction=0.03, pad=0.01, label="building height (m, ACT measured height)")
    ax.set_title(f"{ctx.area}: {len(blds)} ACT LoD2 buildings coloured by height")
    save(fig, img / "buildings_height.jpg"); made.append("buildings_height.jpg")

    # 2. transport graph by height
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    base(ax, T, poly, alpha=0.45); water_patches(ax)
    segs, zs, widths = [], [], []
    for e in g["edges"]:
        en = np.array(e["en"]); z = np.array([np.nan if v is None else v for v in e["z"]])
        if len(en) < 2:
            continue
        s = np.stack([en[:-1], en[1:]], axis=1)
        segs += list(s); zs += list((z[:-1] + z[1:]) / 2)
        w = {"road": 1.6, "rail": 2.2, "tram": 2.0, "funicular": 1.8}.get(e["mode"], 0.6)
        widths += [w * (0.6 if big else 1)] * len(s)
    lc = LineCollection(segs, array=np.array(zs), cmap="turbo", linewidths=widths)
    ax.add_collection(lc)
    fig.colorbar(lc, ax=ax, fraction=0.03, pad=0.01, label="height of the road / track (m)")
    for e in g["edges"]:
        en = np.array(e["en"])
        if e["structure"] == "bridge" and e["mode"] in ("road", "rail", "tram"):
            ax.plot(en[:, 0], en[:, 1], color="black", lw=4.5 if not big else 2.5, alpha=0.35, zorder=1, solid_capstyle="butt")
        if e["structure"] == "tunnel":
            ax.plot(en[:, 0], en[:, 1], color="white", lw=1.0, ls=(0, (2, 2)), zorder=3)
    pts = [(p["e"], p["n"]) for p in g["portals"] if p["found"] and p["mode"] in ("road", "rail", "tram", "funicular")]
    if pts:
        ax.scatter(*np.array(pts).T, s=30 if not big else 8, marker="s", facecolor="none", edgecolor="black", zorder=4, label="tunnel portal")
    for v in st["viaducts"]:
        for p in v.get("piers", []):
            ax.plot(p["e"], p["n"], "o", ms=3, color="#7b3f00", zorder=5)
    ax.plot([], [], color="black", lw=4, alpha=0.35, label="bridge deck (grey casing)")
    ax.plot([], [], color="grey", lw=1, ls=(0, (2, 2)), label="tunnel (dashed)")
    ax.plot([], [], "o", ms=3, color="#7b3f00", label="modelled viaduct pier")
    ax.legend(loc="lower right")
    ax.set_title(f"{ctx.area}: transport graph ({len(g['edges'])} edges) coloured by profile height")
    save(fig, img / "transport_height.jpg"); made.append("transport_height.jpg")

    # 3. trees over the relief, cliffs in red
    t = np.load(part(sc, "trees") / "trees.npz")
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    base(ax, T, poly, alpha=0.7); water_patches(ax)
    step = float(T["step"]); k = max(1, int(round(1.0 / step)))
    cl = (T["cls"][::k, ::k] == 2).astype(float)
    ext = (float(T["e0"]), float(T["e0"]) + T["mnt"].shape[1] * step, float(T["n0"]), float(T["n0"]) + T["mnt"].shape[0] * step)
    ax.imshow(np.ma.masked_where(cl == 0, cl), origin="lower", extent=ext, cmap="autumn", alpha=0.6)
    ax.add_collection(PolyCollection(polys, facecolor="#d8cfc4", edgecolor=INK, linewidth=0.2))
    cols = np.array(["#3c7d32", "#a33a3a", "#1f5a4a", "#b58a2b"])[t["type"].astype(int)]
    from matplotlib.collections import EllipseCollection
    ec = EllipseCollection(2 * t["crown_r"], 2 * t["crown_r"], np.zeros(len(t["e"])), units="xy",
                           offsets=np.column_stack((t["e"], t["n"])), offset_transform=ax.transData,
                           facecolors=cols, edgecolors="none", alpha=0.55)
    ax.add_collection(ec)
    ax.set_title(f"{ctx.area}: {len(t['e'])} LiDAR 2024 trees (crown x0.85; green deciduous, red red-leaved, teal conifer), cliffs in orange")
    save(fig, img / "trees_relief.jpg"); made.append("trees_relief.jpg")

    # 4. the rail line's height profile through the viaducts
    rail = [e for e in g["edges"] if e["mode"] == "rail" and e["structure"] in ("bridge", "ground", "tunnel")]
    if rail and not big:
        fig, ax = plt.subplots(figsize=(14, 5.5), dpi=150)
        # order the rail samples along the line's main direction (south-east to north-west here)
        allp = np.concatenate([np.array(e["en"]) for e in rail])
        c = allp.mean(axis=0); u = np.linalg.svd(allp - c, full_matrices=False)[2][0]
        for e in rail:
            en = np.array(e["en"]); tt = (en - c) @ u
            z = np.array([np.nan if v is None else v for v in e["z"]]); gr = np.array([np.nan if v is None else v for v in e["ground"]])
            col = {"bridge": "#1f77b4", "tunnel": "#d62728", "ground": "#555555"}[e["structure"]]
            ax.plot(tt, z, color=col, lw=1.2)
            ax.plot(tt, gr, color="#8c6d46", lw=0.6, alpha=0.6)
        for v in st["viaducts"]:
            for p in v.get("piers", []):
                tp = (np.array([p["e"], p["n"]]) - c) @ u
                ax.add_patch(plt.Rectangle((tp - p["thickness_m"] / 2, p["foot_z"]), p["thickness_m"], p["top_z"] - p["foot_z"],
                                           color="#7b3f00", alpha=0.7))
            for a in v.get("arches", []):
                if a.get("abutment"):
                    continue
                ta, tb = (np.array(a["from"]) - c) @ u, (np.array(a["to"]) - c) @ u
                th = np.linspace(0, np.pi, 30); mid = (ta + tb) / 2; rad = abs(tb - ta) / 2
                ax.plot(mid + rad * np.cos(th), a["spring_z"] + (a["crown_z"] - a["spring_z"]) * np.sin(th), color="#7b3f00", lw=0.8)
            if v.get("deck"):
                d = np.array(v["deck"]); tt = (d[:, :2] - c) @ u
                ax.text(tt.mean(), d[:, 2].max() + 3, v["id"], ha="center", fontsize=9)
        ax.plot([], [], color="#1f77b4", label="track on a bridge (LiDAR surface)")
        ax.plot([], [], color="#d62728", label="track in a tunnel")
        ax.plot([], [], color="#555555", label="track on the ground (LiDAR terrain)")
        ax.plot([], [], color="#8c6d46", label="terrain under the track")
        ax.plot([], [], color="#7b3f00", label="modelled piers and arches")
        ax.legend(loc="lower left", fontsize=8)
        ax.set_xlabel("metres along the line (south-east to north-west)"); ax.set_ylabel("height (m)")
        ax.set_title(f"{ctx.area}: rail profiles (all tracks) with the modelled viaducts")
        save(fig, img / "rail_profile.jpg"); made.append("rail_profile.jpg")

    # 5. isometric view through the v2 camera: buildings (and their windows), around the Grund
    if not big:
        m = np.load(part(sc, "buildings") / "mesh.npz")
        V = m["verts"].astype(float) + np.r_[m["origin_en"], 0]
        tri = m["tris"]; kind = m["tri_kind"]
        P = V[tri]                                           # (T, 3, 3)
        px, py = en_to_px(P[..., 0], P[..., 1], P[..., 2])
        dep = depth(P[..., 0].mean(1), P[..., 1].mean(1), P[..., 2].mean(1))
        nrm = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
        nrm /= np.maximum(np.linalg.norm(nrm, axis=1), 1e-9)[:, None]
        sun = np.array([-0.5, 0.35, 0.8]); sun /= np.linalg.norm(sun)
        shade = 0.55 + 0.45 * np.abs(nrm @ sun)
        basec = np.where(kind[:, None] == 1, np.array([0.62, 0.36, 0.3]), np.array([0.86, 0.8, 0.7]))
        col = np.clip(basec * shade[:, None], 0, 1)
        order = np.argsort(-dep)
        fig, ax = plt.subplots(figsize=(16, 11), dpi=150)
        ax.set_facecolor("#efe8dc")
        ax.add_collection(PolyCollection(np.stack([px, py], -1)[order], facecolors=col[order], edgecolors=(0.18, 0.15, 0.13, 0.5),
                                         linewidths=0.08))
        fac = json.loads((part(sc, "facades") / "facades.json").read_text())["walls"]
        from v2.data.scene.facades import window_world
        wins = [window_world(w, x) for w in fac for x in w["windows"] if w["normal"][1] < 0.2 or w["normal"][0] > -0.2]
        if wins:
            W = np.array(wins)
            wx, wy = en_to_px(W[..., 0], W[..., 1], W[..., 2])
            ax.add_collection(PolyCollection(np.stack([wx, wy], -1), facecolors="#3b4a5a", edgecolors="none", alpha=0.85))
        ax.set_xlim(px.min(), px.max()); ax.set_ylim(py.max(), py.min())
        ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
        ax.set_title(f"{ctx.area}: buildings through the v2 camera (south-east view, 30 degrees, v2 map pixels) "
                     f"with the facade layout's windows; no lighting from the art, flat test shading only")
        save(fig, img / "iso_buildings.jpg"); made.append("iso_buildings.jpg")
        # a close-up of the Grund
        cx, cy = en_to_px(np.array([77840.0]), np.array([75380.0]), np.array([250.0]))
        ax_lim = (cx[0] - 2400, cx[0] + 2400, cy[0] + 1700, cy[0] - 1700)
        fig, ax = plt.subplots(figsize=(14, 10), dpi=150)
        ax.set_facecolor("#efe8dc")
        ax.add_collection(PolyCollection(np.stack([px, py], -1)[order], facecolors=col[order], edgecolors=(0.18, 0.15, 0.13, 0.7),
                                         linewidths=0.25))
        if wins:
            ax.add_collection(PolyCollection(np.stack([wx, wy], -1), facecolors="#3b4a5a", edgecolors="none", alpha=0.9))
        ax.set_xlim(ax_lim[0], ax_lim[1]); ax.set_ylim(ax_lim[2], ax_lim[3])
        ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
        ax.set_title("the Grund and Neumünster Abbey: windows placed by the facade rule (straight rows by construction)")
        save(fig, img / "iso_grund_windows.jpg"); made.append("iso_grund_windows.jpg")
    return {"images": made, "bytes": {f: (img / f).stat().st_size for f in made}}


def g0(ctx):
    checks = {}
    for name, folder in ctx.deps.items():
        m = json.loads((folder / "manifest.json").read_text())
        if m["kind"] == "check":
            s = m["summary"]
            checks[name] = {"passed": s.get("passed"), "lines": s.get("lines", [])}
    sc = json.loads((ctx.deps["scene"] / "manifest.json").read_text())["summary"]
    prev = ctx.deps["previews"]
    res = {"area": ctx.area, "passed": all(c["passed"] for c in checks.values()), "checks": checks, "scene": sc,
           "on_disk_bytes_all_versions": {p.name: sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
                          for p in sorted((v2_data() / ctx.area).iterdir()) if p.is_dir()}}
    ctx.write_json("g0.json", res, indent=1)
    out_img = V2 / "docs" / "img"; out_res = V2 / "docs" / "results"
    out_img.mkdir(parents=True, exist_ok=True); out_res.mkdir(parents=True, exist_ok=True)
    for f in sorted((prev / "img").glob("*.jpg")):
        shutil.copy(f, out_img / f"{ctx.area}_{f.name}")
    (out_res / f"g0_{ctx.area}.json").write_text(json.dumps(res, indent=1))
    return {"passed": res["passed"], "checks": {k: v["passed"] for k, v in checks.items()}}
