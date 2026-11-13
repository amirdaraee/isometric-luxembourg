"""Landmark cutaways on a tiny building: a 12 x 8 m box with a gable roof (eave 6 m, ridge 10 m over the ground),
cut across by one plane. Section, mask, depth; then the checks' own model of it (v2/checks/cutaway_checks.py)."""
from types import SimpleNamespace

import numpy as np
import pytest
from shapely.geometry import Polygon

from v2.checks import cutaway_checks as cc
from v2.layers import cutaways as cw
from v2.layers import geometry as G
from v2.layers.common import CLASS, TILE, Tile, project, unproject

E0, N0, Z0 = 77000.0, 75000.0, 300.0
P = {"cutaway_wall_m": 0.5, "cutaway_roof_m": 0.4, "cutaway_slab_m": 0.3, "cutaway_min_storey_m": 2.4,
     "cutaway_solid_roof_deg": 80.0, "ground_floor_m": 3.6, "floor_m": 3.0}
FLOOR = Z0 + 0.5
PLANE = {"origin": [E0 + 6.0, N0 + 4.0], "normal": [1.0, 0.0], "extent": [-50.0, 50.0]}   # takes the east half


def p(x, y, z):
    return [E0 + x, N0 + y, Z0 + z]


def house():
    """(footprint, shell mesh with "kind", the scene the checks read)."""
    M = G.Mesh()
    kind = []

    def add(pts, k):
        n = len(pts) - 2
        M.add(pts, [[0, i + 1, i + 2] for i in range(n)], CLASS["roof"] if k == 1 else CLASS["building"], 0,
              "buildings.roof_slate" if k == 1 else "buildings.wall_render")
        kind.extend([k] * n)
    add([p(0, 0, 6), p(12, 0, 6), p(12, 4, 10), p(0, 4, 10)], 1)            # south slope
    add([p(0, 8, 6), p(0, 4, 10), p(12, 4, 10), p(12, 8, 6)], 1)            # north slope
    add([p(0, 0, 0), p(12, 0, 0), p(12, 0, 6), p(0, 0, 6)], 2)              # south wall
    add([p(0, 8, 0), p(0, 8, 6), p(12, 8, 6), p(12, 8, 0)], 2)              # north wall
    add([p(0, 0, 0), p(0, 0, 6), p(0, 4, 10), p(0, 8, 6), p(0, 8, 0)], 2)   # west gable
    add([p(12, 0, 0), p(12, 8, 0), p(12, 8, 6), p(12, 4, 10), p(12, 0, 6)], 2)
    shell = M.done()
    shell["kind"] = np.array(kind, np.int8)
    ring = [[E0, N0], [E0 + 12, N0], [E0 + 12, N0 + 8], [E0, N0 + 8], [E0, N0]]
    scene = SimpleNamespace(
        buildings=[{"id": "house", "footprint": [[ring]], "ground_z": Z0}],
        mesh={"verts": (shell["V"] - [E0, N0, 0.0]).astype(np.float32), "tris": shell["T"].astype(np.int32),
              "tri_kind": shell["kind"], "tri_bld": np.zeros(len(shell["T"]), np.int32), "origin_en": np.array([E0, N0])})
    return Polygon(ring), shell, scene


def model(floors=False):
    F, shell, scene = house()
    solid = cw.Solid(F, shell["V"][shell["T"][shell["kind"] == 1]], Z0)
    region = cw.Region([PLANE], FLOOR)
    return cw.cut_model({0: solid}, shell, None, region, P, floors=floors), shell, scene, region


def frame_of(shell):
    px, py, _ = project(shell["V"][:, 0], shell["V"][:, 1], shell["V"][:, 2])
    return cw.Frame(int(px.min()) - 8, int(py.min()) - 8, int(max(np.ptp(px), np.ptp(py))) + 16)


def drawn(m, frame):
    L = cw.draw([m["shell"], m["faces"]], frame)
    return L, cw.kinds_of(L.ids, L.depth, m["own"])


def test_clipping_keeps_what_is_outside_the_slice():
    tri = np.array([[[0.0, 0, 0], [4, 0, 0], [0, 4, 0]]])
    H = np.array([[1.0, 0, 0, 1.0]])                                         # the slice: x > 1
    out, par = cw.clip_outside(tri, H)
    area = np.linalg.norm(np.cross(out[:, 1] - out[:, 0], out[:, 2] - out[:, 0]), axis=1).sum() / 2
    assert par.tolist() == [0] * len(out) and out[..., 0].max() <= 1 + 1e-9
    assert area == pytest.approx(8 - 4.5)                                    # the triangle less its part beyond x = 1
    whole, _ = cw.clip_outside(tri - [5, 0, 0], H)
    assert len(whole) == 1 and len(cw.clip_outside(tri + [2, 0, 0], H)[0]) == 0


def test_the_slice_is_in_front_of_the_plane_within_its_extent_above_the_floor():
    r = cw.Region([dict(PLANE, extent=[-2.0, 3.0])], FLOOR)
    e, n = np.array([E0 + 7, E0 + 5, E0 + 7, E0 + 7]), np.array([N0 + 4, N0 + 4, N0 + 7.5, N0 + 1.5])
    assert r.inside(e, n).tolist() == [True, False, False, False]            # behind the plane; past each end
    assert not r.inside(e[:1], n[:1], np.array([FLOOR - 0.1]))[0]
    faces = r.faces((E0 - 20, N0 - 20, E0 + 32, N0 + 28))
    assert len(faces) == 3                                                   # the plane and the two ends of its extent
    assert sorted(round(float(np.linalg.norm(q - p_)), 3) for p_, q, _ in faces)[0] == 5.0


def test_section_of_the_gable_house():
    m, *_ = model()
    st = m["stats"][0]
    # outer profile above the floor (8 x 5.5 + the gable 16) less the hollow (7 wide, walls 0.5, roof 0.4 down)
    assert st["section_m2"] == pytest.approx(60 - (7 * 5.6 + 0.5 * 7 * 3.5), abs=0.01)
    assert st["slab_levels"] == [] and st["inner_footprint_m2"] == pytest.approx(11 * 7)
    m2, *_ = model(floors=True)
    st2 = m2["stats"][0]
    assert st2["slab_levels"] == [303.6, 306.6, 309.6]                       # the facade layout's floor lines
    assert st2["section_m2"] == pytest.approx(8.55 + 2.1 + 1.89 + 0.09, abs=0.02)
    # nothing of the kept shell or of the inside is left inside the slice
    for mesh in (m2["shell"], m2["faces"]):
        V = mesh["V"][mesh["T"]].reshape(-1, 3)
        assert not (V[:, 0] > E0 + 6 + 1e-6)[V[:, 2] > FLOOR + 1e-6].any()
    assert (m2["faces"]["V"][:, 2] >= FLOOR - 1e-6).all()                    # the inside starts at the floor


def test_cut_faces_lie_on_the_plane_and_the_opening_stays_in_the_outline():
    m, shell, scene, region = model(floors=True)
    f = frame_of(shell)
    L, k = drawn(m, f)
    whole = np.isfinite(cw.draw([shell], f, outline=False).depth)
    opening = np.isin(k, cw.OPENING)
    assert opening.sum() > 2000 and not (opening & ~whole).any()             # K1b: inside the whole model's outline
    assert not (np.isfinite(L.depth) & ~whole).any()
    X, Y = np.meshgrid(*f.centres)
    cut = k == cw.KIND["cut"]
    e, n, z = unproject(X[cut], Y[cut], L.depth[cut])
    on_plane = np.abs(e - (E0 + 6)) < 1e-6
    on_floor = np.abs(z - FLOOR) < 1e-6                                      # the walls' trace on the floor, in the slice
    assert (on_plane | on_floor).all() and on_plane.sum() > 300 and on_floor.sum() > 50
    fl = k == cw.KIND["floor"]
    assert np.allclose(unproject(X[fl], Y[fl], L.depth[fl])[2], FLOOR)
    assert {int(v) for v in np.unique(k)} >= {cw.KIND[x] for x in ("outside", "cut", "inside_wall", "floor", "slab")}
    # the section's area, seen on its plane (normal east): pixels x pixel area / the cosine to the view
    area = on_plane.sum() * 0.125 ** 2 / abs(float(np.array([1.0, 0, 0]) @ cw.TO_CAMERA))
    assert area == pytest.approx(m["stats"][0]["section_m2"], rel=0.06)


def tiles_of(m, shell):
    """The cut drawn into tiles, as a cache line_checks.score and the checks read."""
    px, py, _ = project(shell["V"][:, 0], shell["V"][:, 1], shell["V"][:, 2])
    out = {}
    for ty in range(int(py.min()) // TILE, int(py.max()) // TILE + 1):
        for tx in range(int(px.min()) // TILE, int(px.max()) // TILE + 1):
            t = Tile(tx, ty, apron=0)
            L, k = drawn(m, t)
            out[(tx, ty)] = {"rgb": L.rgb, "depth": L.depth, "ids": L.ids, "k": k, "normal": L.normal}
    return SimpleNamespace(get=lambda tx, ty: out.get((tx, ty)), tiles=out)


def pixels(cache):
    px = {k: [] for k in ("px", "py", "depth", "k", "ids", "normal")}
    for (tx, ty), t in cache.tiles.items():
        r, c = np.nonzero(np.isfinite(t["depth"]))
        px["px"].append(tx * TILE + c + 0.5)
        px["py"].append(ty * TILE + r + 0.5)
        for a in ("depth", "k", "ids", "normal"):
            px[a].append(t[a][r, c])
    return {a: np.concatenate(v) for a, v in px.items()}


def test_the_checks_own_model_agrees_with_the_drawing_and_catches_a_wrong_depth():
    from v2.checks import line_checks as lic
    m, shell, scene, region = model(floors=True)
    lm = {"buildings": ["house"], "floor_z": FLOOR, "floors": True, "planes": [PLANE]}
    M = cc.Model(scene, lm, P)
    # K1: the model's section, from the raw triangles: two walls above the floor and the two roof slopes
    A, B, O = M.section_lines()
    assert np.linalg.norm(B - A, axis=1).sum() == pytest.approx(2 * 5.5 + 2 * np.hypot(4, 4), abs=1e-6)
    cache = tiles_of(m, shell)
    Ps, Ds, Os = lic.samples(A, B, O)
    seen, on = lic.score(cache, Ps, Ds, 1.0, 12, obj=Os)
    assert seen.sum() > 40 and on.sum() / seen.sum() >= 0.95
    # K2 and K5 at every drawn pixel
    px = pixels(cache)
    interior = np.isin(px["k"], cw.OPENING)
    surf = np.column_stack(unproject(px["px"], px["py"], px["depth"]))
    near = M.near(surf, px["normal"])
    possible, sure = M.opening(px["px"], px["py"], px["depth"], surf, px["normal"], near)
    assert cc.interior_in_mask(interior, possible)[0] == 0
    assert cc.interior_in_mask(interior, sure)[1] >= 0.995
    assert (near["kept"] & near["free"])[interior].all()                     # on the model's surface within 1 cm
    cut = px["k"] == cw.KIND["cut"]
    assert M.face_depth_error(px["px"][cut], px["py"][cut], px["depth"][cut]).max() < 1e-6
    # a drawing 5 cm too deep is not on the model's surface
    deep = np.column_stack(unproject(px["px"], px["py"], px["depth"] + 0.05))
    near2 = M.near(deep, px["normal"])
    assert (~(near2["kept"] & near2["free"]))[interior].mean() > 0.9
    assert M.face_depth_error(px["px"][cut], px["py"][cut], px["depth"][cut] + 0.05).min() > 0.01
    # an interior that spills one pixel over the mask is counted
    grown = interior.copy()
    grown[np.flatnonzero(~possible)[:7]] = True
    assert cc.interior_in_mask(grown, possible)[0] == 7


def test_flat_interior_finds_a_darker_side():
    n = 400
    normal = np.r_[np.tile([1.0, 0, 0], (n, 1)), np.tile([0, -1.0, 0], (n, 1))]
    material = np.full(2 * n, 3)
    rgb = np.full((2 * n, 3), 200.0)
    sun = np.array([0.0, -0.8, 0.6])
    flat = cc.flat_interior(rgb, material, normal, sun, min_px=150)[3]
    assert flat["sides"] == 2 and flat["worst"] == 0
    rgb[:n] *= 0.9                                                           # the east-facing side painted darker
    assert cc.flat_interior(rgb, material, normal, sun, min_px=150)[3]["worst"] == pytest.approx(0.1)
    rgb[:] = 200.0
    rgb[n:] *= 1.08                                                          # the sunlit side painted lighter
    assert cc.flat_interior(rgb, material, np.r_[np.tile([0, 1.0, 0], (n, 1)), normal[n:]], sun, 150)[3]["sun"] > 0.05


def test_the_cuts_file_is_well_formed():
    cuts = cw.load_cuts()
    assert set(cuts["landmarks"]) == {"cathedral", "palace", "abbey"}
    for lm in cuts["landmarks"].values():
        assert 1 <= len(lm["planes"]) <= 2 and lm["buildings"] and lm["why"]
        for pl in lm["planes"]:
            assert np.linalg.norm(pl["normal"]) == pytest.approx(1, abs=1e-3) and pl["extent"][0] < pl["extent"][1]
            assert np.array(pl["normal"]) @ cw.TO_CAMERA[:2] > 0             # the cut face looks at the camera
    assert max(cw.CUT_CLASS.values()) < 256 and not set(cw.CUT_CLASS.values()) & set(CLASS.values())
    assert set(cw.cut_params()) >= set(P)


def test_the_stages_are_in_the_graph():
    from v2.build.stages import graph
    g = graph()
    assert g.stages["check_cutaways"].kind == "check" and "layer_cutaways" in g.stages["check_cutaways"].deps
    assert "layer_cutaways" in g.order(["check_cutaways"])


# ------------------------------------------------------------------ a painted interior in place of the placeholder
def test_a_painting_that_passed_replaces_the_placeholder_inside_the_opening_and_nothing_else(tmp_path):
    m, shell, _, _ = model(floors=True)
    f = frame_of(shell)
    L, k = drawn(m, f)
    mask = np.isin(k, cw.OPENING)
    rng = np.random.default_rng(3)
    art = rng.integers(0, 255, (f.size, f.size, 3)).astype(np.uint8)          # "a painting": drawn all over its frame
    frame_px = [f.px0, f.py0, f.size, f.size]
    with pytest.raises(ValueError, match="passed"):
        cw.write_painting(tmp_path, "house", art, mask, frame_px, {"pass": False})
    assert cw.load_painting("house", tmp_path) is None                         # none yet: the placeholder is drawn
    meta = cw.write_painting(tmp_path, "house", art, mask, frame_px, {"pass": True, "candidate": "house_0"})
    p = cw.load_painting("house", tmp_path)
    assert meta["opening_px"] == mask.sum() and (p["on"] == mask).all() and (p["rgb"][mask] == art[mask]).all()
    assert not p["rgb"][~mask].any()                                           # what it drew outside the mask is gone
    # in tiles (with and without an apron) and in the frame: the opening is the painting, the rest is untouched
    px, py, _ = project(shell["V"][:, 0], shell["V"][:, 1], shell["V"][:, 2])
    frames = [f] + [Tile(tx, ty, apron=a) for a in (0, 8) for ty in range(int(py.min()) // TILE, int(py.max()) // TILE + 1)
                    for tx in range(int(px.min()) // TILE, int(px.max()) // TILE + 1)]
    seen = 0
    for fr in frames:
        Lf, kf = drawn(m, fr)
        c = {"rgb": Lf.rgb.copy(), "k": kf, "depth": Lf.depth.copy()}
        on = cw.paint_into(c, fr, p)
        opening = np.isin(kf, cw.OPENING)
        assert (on == opening).all()                                           # all of the opening, only the opening
        assert (c["rgb"][~on] == Lf.rgb[~on]).all() and (c["depth"] == Lf.depth).all()
        r, q = np.nonzero(on)
        gx, gy = np.floor(fr.centres[0]).astype(int)[q] - f.px0, np.floor(fr.centres[1]).astype(int)[r] - f.py0
        assert (c["rgb"][r, q] == art[gy, gx]).all()                           # each pixel from its own map pixel
        seen += len(r)
    assert seen > 3 * mask.sum() * 0.99
    # a record that does not say "passed", or a file that is not the recorded one, stops the build
    rec = tmp_path / "house.json"
    rec.write_text(rec.read_text().replace('"pass": true', '"pass": false'))
    with pytest.raises(RuntimeError, match="passed"):
        cw.load_painting("house", tmp_path)
    rec.write_text(rec.read_text().replace('"pass": false', '"pass": true'))
    from PIL import Image
    Image.fromarray(np.dstack([art, np.full(art.shape[:2], 255, np.uint8)]), "RGBA").save(tmp_path / "house.png")
    with pytest.raises(RuntimeError, match="sha256"):
        cw.load_painting("house", tmp_path)


def test_no_painting_is_in_the_repo_until_one_passes_and_the_stage_would_see_it():
    from v2.build.stages import graph
    assert not cw.PAINTINGS.is_dir() or all(cw.load_painting(p.stem) for p in cw.PAINTINGS.glob("*.json"))
    raw = graph().stages["layer_cutaways"].raw("test")
    assert cw.CUTS in raw and all(p in raw for p in (cw.PAINTINGS.iterdir() if cw.PAINTINGS.is_dir() else []))
