"""Stream the commune's CityGML out of the zip into flat textured triangles.

Output: data/work/buildings.npz
  tris     float32 [T,3,5]  local E, local N, z, u, v
  tri_tex  int32   [T]      texture index, -1 when untextured
  tri_kind int8    [T]      0 ground, 1 roof, 2 wall, 3 installation/other
  tri_bld  int32   [T]      building index
  textures str     [K]      archive member names
  bld_ground float32 [B,3] local E, local N, ground z (for terrain fitting)
"""
import time
import zipfile
import numpy as np
import mapbox_earcut as earcut
from lxml import etree
from common import BATI_ZIP, WORK, ORIGIN_E, ORIGIN_N

GML = "{http://www.opengis.net/gml}"
BLDG = "{http://www.opengis.net/citygml/building/2.0}"
APP = "{http://www.opengis.net/citygml/appearance/2.0}"
KIND = {BLDG + "GroundSurface": 0, BLDG + "RoofSurface": 1, BLDG + "WallSurface": 2}


def ring_pts(ring):
    vals = np.array(ring.findtext(GML + "posList").split(), dtype=np.float64)
    pts = vals.reshape(-1, 3)
    # posList order is northing, easting, height.
    return np.column_stack((pts[:, 1] - ORIGIN_E, pts[:, 0] - ORIGIN_N, pts[:, 2]))


def triangulate(rings):
    """Earcut in the polygon's own plane. Returns flat vertex + index arrays."""
    verts = np.vstack([r[:-1] for r in rings])
    if len(verts) < 3:
        return None
    centred = verts - verts.mean(axis=0)
    try:
        normal = np.linalg.svd(centred, full_matrices=False)[2][2]
    except np.linalg.LinAlgError:
        return None
    axis = int(np.argmax(np.abs(normal)))
    p2 = np.delete(verts, axis, axis=1)
    ends = np.cumsum([len(r) - 1 for r in rings]).astype(np.uint32)
    idx = earcut.triangulate_float64(p2, ends)
    return verts, idx.astype(np.int64)


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    z = zipfile.ZipFile(BATI_ZIP)
    gml = next(i for i in z.infolist() if i.filename.endswith(".gml"))
    t0 = time.time()

    polys = []          # (bld, kind, [ring_ids], [ring arrays])
    ring_index = {}     # ring id -> (poly index, ring position)
    ring_uv = {}        # ring id -> (tex index, uv array)
    textures, tex_idx = [], {}
    grounds = []
    bld = 0

    with z.open(gml) as f:
        ctx = etree.iterparse(f, events=("end",), huge_tree=True, tag=(
            BLDG + "Building", APP + "ParameterizedTexture"))
        for _, el in ctx:
            if el.tag == BLDG + "Building":
                gpts = []
                for poly in el.iter(GML + "Polygon"):
                    kind = 3
                    for anc in poly.iterancestors():
                        if anc.tag in KIND:
                            kind = KIND[anc.tag]
                            break
                        if anc.tag == BLDG + "Building":
                            break
                    ids, arrs = [], []
                    ext = poly.find(f"{GML}exterior/{GML}LinearRing")
                    if ext is None:
                        continue
                    rings = [ext] + poly.findall(f"{GML}interior/{GML}LinearRing")
                    for r in rings:
                        ids.append(r.get(GML + "id"))
                        arrs.append(ring_pts(r))
                    pi = len(polys)
                    polys.append((bld, kind, ids, arrs))
                    for pos, rid in enumerate(ids):
                        if rid:
                            ring_index[rid] = (pi, pos)
                    if kind == 0:
                        gpts.append(arrs[0])
                if gpts:
                    g = np.vstack(gpts)
                    grounds.append((g[:, 0].mean(), g[:, 1].mean(), g[:, 2].min()))
                else:
                    grounds.append((np.nan, np.nan, np.nan))
                bld += 1
                if bld % 4000 == 0:
                    print(f"{bld} buildings, {time.time() - t0:.0f}s", flush=True)
            else:
                name = el.findtext(APP + "imageURI").replace("/", "\\")
                ti = tex_idx.setdefault(name, len(textures))
                if ti == len(textures):
                    textures.append(name)
                for tc in el.iter(APP + "textureCoordinates"):
                    rid = tc.get("ring", "").lstrip("#")
                    ring_uv[rid] = (ti, np.array(tc.text.split(), dtype=np.float32).reshape(-1, 2))
            el.clear()
            while el.getprevious() is not None:
                del el.getparent()[0]

    print(f"parsed {bld} buildings, {len(polys)} polygons, {len(ring_uv)} textured rings, {time.time() - t0:.0f}s", flush=True)

    tris, tex, kinds, blds = [], [], [], []
    failed = 0
    for b, kind, ids, arrs in polys:
        out = triangulate(arrs)
        if out is None:
            failed += 1
            continue
        verts, idx = out
        if len(idx) == 0:
            failed += 1
            continue
        uvs = []
        ti = -1
        ok = True
        for rid, arr in zip(ids, arrs):
            u = ring_uv.get(rid)
            if u is None or len(u[1]) != len(arr):
                ok = False
                break
            ti = u[0]
            uvs.append(u[1][:-1])
        if ok and uvs:
            uv = np.vstack(uvs)
        else:
            uv = np.zeros((len(verts), 2), np.float32)
            ti = -1
        v5 = np.column_stack((verts, uv)).astype(np.float32)
        tris.append(v5[idx])
        n = len(idx) // 3
        tex.append(np.full(n, ti, np.int32))
        kinds.append(np.full(n, kind, np.int8))
        blds.append(np.full(n, b, np.int32))

    tris = np.vstack(tris).reshape(-1, 3, 5)
    tex = np.concatenate(tex)
    kinds = np.concatenate(kinds)
    blds = np.concatenate(blds)
    print("triangles", len(tris), "untextured", int((tex < 0).sum()), "failed polygons", failed)
    print("by kind", np.bincount(kinds))
    print("local E range", tris[..., 0].min(), tris[..., 0].max(), "local N range", tris[..., 1].min(), tris[..., 1].max(), "z", tris[..., 2].min(), tris[..., 2].max())
    np.savez(WORK / "buildings.npz", tris=tris, tri_tex=tex, tri_kind=kinds, tri_bld=blds,
             textures=np.array(textures), bld_ground=np.array(grounds, np.float32))
    print(f"done {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
