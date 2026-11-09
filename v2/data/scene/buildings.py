"""Scene: buildings from the ACT LoD2.2 3D city model (spec: v2/docs/specs/scene.md, "Buildings").

Streams the commune's CityGML (data/raw/bati3d, ACT 2023 v2, CC0) and keeps the buildings whose footprint centre lies
in the area. Per building (buildings.json):
  id (the ACT gml:id), measured height, ground, eave and ridge heights, footprint rings (E, N), roof planes (normal,
  slope, azimuth, area), roof shape (flat, shed, gable, hip, mansard-or-complex, mixed), walls (3D rings with their
  ACT surface id), parts (the BuildingInstallations: dormers, chimneys, ...), and terrain under the footprint.
mesh.npz: every surface triangulated (local E, N relative to the camera origin, z), with kind (0 ground, 1 roof,
2 wall, 3 installation) and building index, for the code renders in Phase 1.
The CityGML has no BuildingPart elements and no roofType attribute, so the roof shape is derived from the roof
planes (rule in the spec).
"""
from __future__ import annotations

import json
import time
import zipfile

import mapbox_earcut as earcut
import numpy as np
from lxml import etree
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from v2.config import raw_dir
from v2.config.camera import camera
from v2.data.geo import area_polygon
from v2.data.scene.grid import Grid

GML = "{http://www.opengis.net/gml}"
BLDG = "{http://www.opengis.net/citygml/building/2.0}"
KIND = {BLDG + "GroundSurface": 0, BLDG + "RoofSurface": 1, BLDG + "WallSurface": 2}
BATI = "bati3d/act2023v2-bati3d-luxembourg.zip"


def ring_pts(ring):
    v = np.array(ring.findtext(GML + "posList").split(), dtype=np.float64).reshape(-1, 3)
    return np.column_stack((v[:, 1], v[:, 0], v[:, 2]))  # the file stores northing, easting, height


def plane(pts):
    c = pts[:-1] if len(pts) > 3 and np.allclose(pts[0], pts[-1]) else pts
    centred = c - c.mean(axis=0)
    try:
        nrm = np.linalg.svd(centred, full_matrices=False)[2][2]
    except np.linalg.LinAlgError:
        return None
    if nrm[2] < 0:
        nrm = -nrm
    return nrm


def area3d(pts):
    p = pts[:-1] if np.allclose(pts[0], pts[-1]) else pts
    s = np.zeros(3)
    for a, b in zip(p, np.roll(p, -1, axis=0)):
        s += np.cross(a, b)
    return 0.5 * float(np.linalg.norm(s))


def roof_shape(planes, flat_max):
    """flat / shed / gable / hip / mixed / complex from the roof planes (slope, azimuth, area)."""
    tot = sum(p["area"] for p in planes) or 1.0
    sloped = [p for p in planes if p["slope"] > flat_max]
    s_area = sum(p["area"] for p in sloped)
    if s_area < 0.15 * tot:
        return "flat"
    # orientation histogram of the sloped area in 4 quadrants around the main azimuth
    az = np.array([p["azimuth"] for p in sloped]); w = np.array([p["area"] for p in sloped])
    main = az[np.argmax(w)]
    q = np.round(((az - main) % 360) / 90).astype(int) % 4
    share = np.bincount(q, weights=w, minlength=4) / s_area
    kind = "complex"
    big = share > 0.08
    if big.sum() == 1:
        kind = "shed"
    elif big.sum() == 2 and big[0] and big[2]:
        kind = "gable"
    elif big.sum() >= 3:
        # mansard: two slope bands on the same sides
        sl = np.array([p["slope"] for p in sloped])
        kind = "mansard" if ((sl > 55).any() and (sl < 45).any() and big.sum() == 4) else "hip"
    if s_area < 0.8 * tot:
        kind = "mixed:" + kind
    return kind


def triangulate(rings):
    verts = np.vstack([r[:-1] for r in rings])
    if len(verts) < 3:
        return None
    nrm = plane(verts)
    if nrm is None:
        return None
    axis = int(np.argmax(np.abs(nrm)))
    p2 = np.delete(verts, axis, axis=1)
    ends = np.cumsum([len(r) - 1 for r in rings]).astype(np.uint32)
    idx = earcut.triangulate_float64(p2, ends)
    return verts, idx.astype(np.int64)


def parse(path, keep, log=print):
    """Yields (building dict, list of (kind, rings, surface id)) for kept buildings."""
    z = zipfile.ZipFile(path)
    gml = next(i for i in z.infolist() if i.filename.endswith(".gml"))
    t0, n = time.time(), 0
    with z.open(gml) as f:
        for _, el in etree.iterparse(f, events=("end",), huge_tree=True, tag=BLDG + "Building"):
            n += 1
            polys = []
            for poly in el.iter(GML + "Polygon"):
                kind, sid, inst = 3, None, None
                for anc in poly.iterancestors():
                    if anc.tag in KIND and kind == 3 and inst is None:
                        kind, sid = KIND[anc.tag], anc.get(GML + "id")
                    if anc.tag == BLDG + "BuildingInstallation":
                        inst = anc.get(GML + "id")
                    if anc.tag == BLDG + "Building":
                        break
                ext = poly.find(f"{GML}exterior/{GML}LinearRing")
                if ext is None:
                    continue
                rings = [ring_pts(ext)] + [ring_pts(r) for r in poly.findall(f"{GML}interior/{GML}LinearRing")]
                polys.append((3 if inst else kind, rings, sid or poly.get(GML + "id"), inst))
            meta = {"id": el.get(GML + "id"), "measured_height": el.findtext(BLDG + "measuredHeight"),
                    "created": el.findtext("{http://www.opengis.net/citygml/2.0}creationDate")}
            if keep(polys):
                yield meta, polys
            el.clear()
            while el.getprevious() is not None:
                del el.getparent()[0]
            if n % 5000 == 0:
                log(f"{n} buildings read, {time.time() - t0:.0f}s")


def footprint(polys):
    gs = [Polygon(r[0][:, :2], [h[:, :2] for h in r[1:]]) for k, r, _, _ in polys if k == 0]
    gs = [g if g.is_valid else g.buffer(0) for g in gs]
    gs = [g for g in gs if not g.is_empty]
    if not gs:
        return None
    return unary_union(gs)


def build(ctx):
    p = ctx.params["buildings"]
    poly = area_polygon(ctx.area)
    pre = poly.buffer(30)
    terrain = Grid.load(ctx.dep("scene_terrain") / "terrain.npz", "mnt")
    oe, on = camera()["origin_en"]

    def keep(polys):
        g = [r[0] for k, r, _, _ in polys if k == 0]
        pts = np.vstack(g) if g else np.vstack([r[0] for _, r, _, _ in polys])
        c = pts[:, :2].mean(axis=0)
        return pre.contains(Point(c))

    out, V, T, TK, TB = [], [], [], [], []
    nv = 0
    for meta, polys in parse(raw_dir() / BATI, keep, log=ctx.log):
        fp = footprint(polys)
        if fp is None or fp.area < p["min_footprint_m2"]:
            continue
        if not poly.contains(fp.representative_point()):
            continue
        bi = len(out)
        zs_ground = [r[0][:, 2].min() for k, r, _, _ in polys if k == 0]
        roofs, walls, parts = [], [], {}
        for k, rings, sid, inst in polys:
            if k == 1:
                nrm = plane(rings[0])
                if nrm is None:
                    continue
                roofs.append({"id": sid, "slope": round(float(np.degrees(np.arccos(min(1.0, abs(nrm[2]))))), 1),
                              "azimuth": round(float(np.degrees(np.arctan2(nrm[0], nrm[1])) % 360), 1),
                              "area": round(area3d(rings[0]), 2), "z": [round(float(rings[0][:, 2].min()), 2),
                                                                       round(float(rings[0][:, 2].max()), 2)]})
            elif k == 2:
                walls.append({"id": sid, "ring": [[round(x, 3), round(y, 3), round(z, 3)] for x, y, z in rings[0]]})
            elif k == 3 and inst:
                q = parts.setdefault(inst, {"id": inst, "kind": "installation", "zmin": 1e9, "zmax": -1e9, "surfaces": 0})
                q["zmin"] = min(q["zmin"], float(rings[0][:, 2].min())); q["zmax"] = max(q["zmax"], float(rings[0][:, 2].max()))
                q["surfaces"] += 1
            tri = triangulate(rings)
            if tri is None or len(tri[1]) == 0:
                continue
            verts, idx = tri
            V.append(np.column_stack((verts[:, 0] - oe, verts[:, 1] - on, verts[:, 2])).astype(np.float32))
            T.append(idx.reshape(-1, 3) + nv); nv += len(verts)
            TK.append(np.full(len(idx) // 3, k, np.int8)); TB.append(np.full(len(idx) // 3, bi, np.int32))
        ground_z = float(min(zs_ground)) if zs_ground else float(min(r[0][:, 2].min() for _, r, _, _ in polys))
        ridge = max((r["z"][1] for r in roofs), default=ground_z)
        eave = min((r["z"][0] for r in roofs), default=ridge)
        rings = [fp] if fp.geom_type == "Polygon" else list(fp.geoms)
        # the terrain under the footprint: does the building sit on the ground model?
        c = fp.representative_point()
        tz = terrain.sample(np.array([c.x]), np.array([c.y]))[0]
        out.append({
            "id": meta["id"], "created": meta["created"],
            "measured_height": float(meta["measured_height"]) if meta["measured_height"] else None,
            "ground_z": round(ground_z, 2), "eave_z": round(eave, 2), "ridge_z": round(ridge, 2),
            "height": round(float(meta["measured_height"]) if meta["measured_height"] else ridge - ground_z, 2),
            "roof_shape": roof_shape(roofs, p["flat_roof_max_slope_deg"]) if roofs else "none",
            "footprint": [[[[round(x, 3), round(y, 3)] for x, y in g.exterior.coords]]
                          + [[[round(x, 3), round(y, 3)] for x, y in h.coords] for h in g.interiors] for g in rings],
            "footprint_m2": round(fp.area, 2), "centre": [round(c.x, 2), round(c.y, 2)],
            "terrain_z": round(float(tz), 2) if np.isfinite(tz) else None,
            "roofs": roofs, "walls": walls,
            "parts": [{**q, "zmin": round(q["zmin"], 2), "zmax": round(q["zmax"], 2)} for q in parts.values()],
        })
    ctx.write_json("buildings.json", {"buildings": out})
    np.savez_compressed(ctx.out / "mesh.npz", verts=np.vstack(V), tris=np.vstack(T).astype(np.int32),
                        tri_kind=np.concatenate(TK), tri_bld=np.concatenate(TB), origin_en=np.array([oe, on]))
    shapes = {}
    for b in out:
        k = b["roof_shape"].split(":")[-1]
        shapes[k] = shapes.get(k, 0) + 1
    return {"buildings": len(out), "triangles": int(sum(len(t) for t in T)), "roof_shapes": shapes,
            "walls": sum(len(b["walls"]) for b in out), "parts": sum(len(b["parts"]) for b in out),
            "height_max_m": max((b["height"] for b in out), default=0)}


def load(path):
    return json.loads((path / "buildings.json").read_text())["buildings"]


def footprints(buildings):
    out = []
    for b in buildings:
        ps = [Polygon(r[0], r[1:]) for r in b["footprint"]]
        out.append(unary_union(ps) if len(ps) > 1 else ps[0])
    return out
