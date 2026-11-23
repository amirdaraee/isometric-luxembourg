"""Detail transfer (Phase 3 trial T1, detail.py): the two steps on a small made-up scene, and the paid job up to
the point of spending (no network, no model)."""
import json

import numpy as np

from v2.bakeoff import bundle as B
from v2.bakeoff import detail as D
from v2.bakeoff import jobs as J
from v2.bakeoff import runner
from v2.ledger.ledger import HERE


def scene(n=240):
    """Two buildings on bare ground: each a wall (with a window) under a roof. Returns (code art, geometry)."""
    ids = np.zeros((n, n), np.uint32); which = np.ones((n, n), np.uint8)
    normal = np.zeros((n, n, 3)); normal[..., 1] = 1.0
    code = np.full((n, n, 3), 200, np.uint8)
    for k, (r0, c0) in enumerate(((40, 30), (120, 130)), start=1):
        roof = (slice(r0, r0 + 30), slice(c0, c0 + 70)); wall = (slice(r0 + 30, r0 + 70), slice(c0, c0 + 70))
        win = (slice(r0 + 42, r0 + 54), slice(c0 + 20, c0 + 30))
        ids[roof] = k << 8 | 23; ids[wall] = k << 8 | 11; ids[win] = k << 8 | 12
        which[roof] = which[wall] = 5
        normal[roof] = (0.0, 0.8, 0.6); normal[wall] = (0.6, 0.0, 0.8)
        code[roof] = (70, 74, 90); code[wall] = (220, 200, 170); code[win] = (40, 50, 80)
        code[r0 + 30, c0:c0 + 70] = 20                                   # the eaves line, inked
    depth = np.where(which == 5, 5.0, 50.0)
    return code, {"ids": ids, "which": which, "normal": normal, "depth": depth}


def painting_of(code, g, dx=0, dy=0, shade=False):
    """A 'painting' of the scene: other colours, a hatch on the roofs, optionally the walls' left half in shadow,
    then moved by (dx, dy)."""
    cls = g["ids"] & 255
    p = np.full(code.shape, 150, float)
    rr, cc = np.indices(cls.shape)
    p[cls == 23] = (60, 80, 120); p[cls == 11] = (240, 210, 150); p[cls == 12] = (30, 40, 70)
    p[(cls == 23) & ((rr + cc) % 6 == 0)] *= 0.6
    if shade:
        for b in (1, 2):
            m = (cls == 11) & ((g["ids"] >> 8) == b)
            cols = np.flatnonzero(m.any(0))
            p[m & (cc < cols.mean())] *= 0.5
    p = np.roll(p, (dy, dx), axis=(0, 1))                                # reading at (y + dy, x + dx) undoes it
    return np.clip(p, 0, 255).astype(np.uint8)


def test_a_v2_window_in_v1_pixels_is_the_cameras_conversion():
    from v2.config.camera import v2_to_v1_px
    for name in D.input_names():
        x0, y0, size, step = D.window_of(name)
        a, b, n = D.v1_box(x0, y0, size)
        ex, ey = v2_to_v1_px(x0, y0)
        assert (a, b) == (ex, ey) and n * 2 == size and size == D.WIN * step


def test_the_layout_has_v1s_three_values_and_keeps_its_lines_at_half_scale():
    code, g = scene()
    lay = D.layout_of(g)
    assert set(np.unique(lay)) == {0, 120, 255}
    half = D.layout_of(g, 2)
    assert half.shape == (120, 120)
    # every line pixel of the full layout has a black pixel in its 2 x 2 cell
    assert (half[np.nonzero(lay == 0)[0] // 2, np.nonzero(lay == 0)[1] // 2] == 0).all()


def test_register_finds_a_paintings_drift():
    code, g = scene()
    for dx, dy in ((0, 0), (9, -14), (-17, 6)):
        reg, shifts = D.register(code, painting_of(code, g, dx, dy), g)
        # to the pixel, or one off: the code inks the eaves on the wall's first row, the painting has no such line
        assert all(abs(v[0] - dx) <= 1 and abs(v[1] - dy) <= 1 for v in shifts.values()) and len(shifts) == 2, (dx, dy, shifts)
        cls = g["ids"] & 255
        # each roof reads the painting's roof again
        assert np.abs(reg[cls == 23].astype(int).mean(0) - painting_of(code, g)[cls == 23].mean(0)).max() < 6


def test_transfer_takes_colour_and_texture_and_leaves_lines_windows_and_ground():
    code, g = scene()
    out, st = D.transfer(code, painting_of(code, g), g)
    cls = g["ids"] & 255
    assert st["parts"] == 4 and st["skipped"] == 0
    wall = (cls == 11) & (D.lum(code.astype(float)) > 100)
    assert np.abs(np.median(out[wall], axis=0) - (240, 210, 150)).max() <= 6           # the painting's wall colour
    roof_in = np.zeros(cls.shape, bool); roof_in[48:62, 40:90] = True
    assert out[roof_in].std() > code[roof_in].std() + 2                                # the hatch came across
    assert D.ink_changed(code, out) == 0                                               # the code's lines
    assert (out[cls == 12] == code[cls == 12]).all()                                   # the code's windows
    assert (out[g["which"] == 1] == code[g["which"] == 1]).all()                       # the ground


def test_a_painted_shadow_does_not_come_through():
    code, g = scene()
    lit_p = painting_of(code, g, shade=True)
    out, _ = D.transfer(code, lit_p, g)
    cls = g["ids"] & 255; cc = np.indices(cls.shape)[1]
    for b in (1, 2):
        m = (cls == 11) & ((g["ids"] >> 8) == b)
        cols = np.flatnonzero(m.any(0)); mid = cols.mean()
        inner = m & (np.abs(cc - mid) > 8) & (D.lum(code.astype(float)) > 100)
        left, right = D.lum(out[inner & (cc < mid)].astype(float)), D.lum(out[inner & (cc > mid)].astype(float))
        painted = D.lum(lit_p[inner & (cc < mid)].astype(float)).mean() / D.lum(lit_p[inner & (cc > mid)].astype(float)).mean()
        assert painted < 0.6                                                           # the painting is half as bright
        assert abs(left.mean() / right.mean() - 1) < 0.03                              # the result is even
        # and its colour is the lit side's, not the mean of the two
        assert np.abs(np.median(out[inner], axis=0) - (240, 210, 150)).max() <= 8


def test_the_trial_job_is_quoted_from_the_last_runs_times_and_fits_the_phase():
    j = J.BY_ID["T1"]
    assert j in J.TRIAL_JOBS and j not in J.JOBS and j.goal == "phase3_lock_look"
    assert len(D.input_names()) * len(D.SEEDS) == J.T1_PAINTINGS == 24
    need = sum(J.T1_PLAN_S.values())
    assert need <= j.est_h * 3600 <= need + 60
    assert runner.cap_seconds(j) - 45 >= 1.4 * need                    # 40 percent over the plan still finishes
    assert j.est_usd <= j.worst_usd <= 1.10
    budget = json.loads((HERE / "budget.json").read_text())
    assert j.worst_usd <= budget["goals"][j.goal]["cap_usd"]
    assert 'T1|T2|T3)  paint "$V1" 1867,1868 ;;' in (runner.POD / "run.sh").read_text()
    assert B.SETUP["T1"] == "paint" and B.OUT["T1"] == "detail/painted"
    assert any(str(u[0]).endswith(B.V1_LORA) for u in B.uploads("T1", HERE))


def test_the_even_light_repaint_differs_from_t1_by_its_prompt_only(tmp_path, monkeypatch):
    from v2.bakeoff import prompts as PR
    t1, t2 = J.BY_ID["T1"], J.BY_ID["T2"]
    assert (t2.gpu, t2.cloud, t2.goal, t2.work, t2.model) == (t1.gpu, t1.cloud, t1.goal, t1.work, t1.model)
    assert J.T1_MEASURED_S <= t2.est_h * 3600 <= J.T1_MEASURED_S + 60 and t2.worst_usd <= 1.10
    assert runner.cap_seconds(t2) - 45 >= 1.4 * J.T1_MEASURED_S
    assert B.OUT["T2"] == "detail/painted_even" != B.OUT["T1"] and D.PAINTED["T2"] == "painted_even"
    # the bundles: the same control images, the prompts apart by the even-light sentence alone
    monkeypatch.setattr(B, "base", lambda: tmp_path)
    monkeypatch.setattr(D, "base", lambda: tmp_path / "detail")
    src = tmp_path / "detail" / "inputs"; src.mkdir(parents=True)
    for n in D.input_names():
        for ext in ("unlit.png", "layout.png"):
            (src / f"{n}.{ext}").write_bytes(f"{n}.{ext}".encode())
    b1, b2 = B.build("T1"), B.build("T2")
    files = lambda d: {p.name: p.read_bytes() for p in (d / "inputs").iterdir()}          # noqa: E731
    assert files(b1) == files(b2) and len(files(b1)) == 24
    assert (b1 / "prompt.txt").read_text() == PR.V1_CAPTION
    assert (b2 / "prompt.txt").read_text() == PR.V1_CAPTION + PR.EVEN


def test_the_trial_job_cannot_run_without_its_own_approval(tmp_path):
    import shutil

    from v2.ledger.ledger import Ledger, LedgerRefusal
    shutil.copy(HERE / "budget.json", tmp_path / "budget.json")
    (tmp_path / "spend.jsonl").write_text("")
    L = Ledger(tmp_path)
    j = J.BY_ID["T1"]
    import pytest
    with pytest.raises(LedgerRefusal):
        runner.authorise(j, L, price_now=j.price_h)                    # no quote
    q = L.quote(j.goal, j.provider, j.ledger_job(), j.worst_usd, j.ledger_note())
    with pytest.raises(LedgerRefusal):
        runner.authorise(j, L, price_now=j.price_h)                    # quoted, not approved
    L.approve(q["id"], by="owner", note="test")
    with pytest.raises(LedgerRefusal):
        runner.authorise(j, L, price_now=j.price_h + 0.5)              # dearer than quoted
    assert runner.authorise(j, L, price_now=j.price_h)["id"] == q["id"]


def test_delit_keeps_the_paintings_own_drawing_and_the_codes_border_ink():
    code, g = scene()
    painting = painting_of(code, g)
    cls = g["ids"] & 255
    out = D.delit(code, painting, g)
    # the painted window (dark on the wall) is still there, where the light transfer keeps the code's
    win = cls == 12; wall = (cls == 11) & (D.lum(code.astype(float)) > 100)
    assert D.lum(out[win].astype(float)).mean() < 0.5 * D.lum(out[wall].astype(float)).mean()
    assert not (out[win] == code[win]).all()
    # the eaves line the code inked between roof and wall stays the code's; the ground is untouched
    for r0, c0 in ((40, 30), (120, 130)):
        assert (out[r0 + 30, c0 + 2:c0 + 68] == code[r0 + 30, c0 + 2:c0 + 68]).all()
    assert (out[g["which"] == 1] == code[g["which"] == 1]).all()


def test_delit_gives_a_shaded_wall_its_lit_neighbours_colour():
    code, g = scene()
    # a second wall face on each building (the right 30 columns turn the corner), which the painting shades
    cls = g["ids"] & 255; cc = np.indices(cls.shape)[1]
    side = np.zeros(cls.shape, bool)
    for b, c0 in ((1, 30), (2, 130)):
        side |= (cls == 11) & ((g["ids"] >> 8) == b) & (cc >= c0 + 40)
    g["normal"][side] = (-0.6, 0.0, 0.8)
    painting = painting_of(code, g).astype(float)
    painting[side] *= 0.45
    out = D.delit(code, painting.astype(np.uint8), g)
    for b in (1, 2):
        w = (cls == 11) & ((g["ids"] >> 8) == b)
        front, shaded = D.lum(out[w & ~side].astype(float)), D.lum(out[w & side].astype(float))
        assert abs(np.median(shaded) / np.median(front) - 1) < 0.03
    assert D.flat_by_part(out, g, min_px=200)["worst"] < 0.03 < D.flat_by_part(painting, g, min_px=200)["worst"]


def test_pairs_set_two_runs_side_by_side_painting_by_painting(tmp_path, monkeypatch):
    from PIL import Image
    code, g = scene()
    n = code.shape[0]
    monkeypatch.setattr(D, "base", lambda: tmp_path)
    monkeypatch.setattr(D, "WIN", n)
    monkeypatch.setattr(D, "input_names", lambda: ["x_p125"])
    monkeypatch.setattr(D, "window_of", lambda name: (0, 0, n, 1))
    monkeypatch.setattr(D, "photo_shadow", lambda g, meta, rel=None: None)
    src = tmp_path / "inputs"; src.mkdir()
    Image.fromarray(code).save(src / "x_p125.code.png")
    np.savez_compressed(src / "x_p125.geom.npz", **g)
    (src / "x_p125.json").write_text(json.dumps({"x0": 0, "y0": 0}))
    for run, shade in (("T1", True), ("T2", False)):
        d = tmp_path / D.PAINTED[run]; d.mkdir()
        for k in range(len(D.SEEDS)):
            Image.fromarray(painting_of(code, g, shade=shade)).save(d / f"x_p125_{k}.png")
    out = D.pairs("T1", "T2", img=tmp_path / "img")
    assert set(out["inputs"]) == {"x_p125_0", "x_p125_1"}
    for v in out["inputs"].values():
        assert v["differ_mean"] > 0 and v["luminance"]["T2"] > v["luminance"]["T1"]
    assert json.loads((tmp_path / "checks" / "pairs_T1_T2.json").read_text())["inputs"] == out["inputs"]
    assert (tmp_path / "img" / "test_detail_t1_t2_close_1.jpg").exists()


SUN = np.array([0.2, 0.36, 0.91])                                       # behind the viewer, to the right, as the photo's


def two_faced(g):
    """The scene's walls with a second face each: the right 30 columns turn the corner, away from SUN."""
    cls = g["ids"] & 255; cc = np.indices(cls.shape)[1]
    side = np.zeros(cls.shape, bool)
    for b, c0 in ((1, 30), (2, 130)):
        side |= np.isin(cls, (11, 12)) & ((g["ids"] >> 8) == b) & (cc >= c0 + 40)
    g["normal"][side] = (-0.6, 0.0, 0.8)
    return side


def test_the_evened_capture_raises_a_face_the_sun_left_and_leaves_a_dark_material_alone():
    code, g = scene()
    side = two_faced(g)
    cls = g["ids"] & 255; bid = g["ids"] >> 8
    photo = painting_of(code, g).astype(float)
    photo[side & (bid == 1)] *= 0.7                                     # building 1: the far face in shade
    front2 = (cls == 11) & (bid == 2) & ~side
    photo[front2] *= 0.5                                                # building 2: a dark front, facing the sun
    photo = photo.astype(np.uint8)
    out, st = D.even_capture(photo, g, None, SUN)
    y0, y1 = D.lum(photo.astype(float)), D.lum(out.astype(float))
    w1 = (cls == 11) & (bid == 1)
    assert np.median(y0[w1 & side]) / np.median(y0[w1 & ~side]) < 0.75
    assert abs(np.median(y1[w1 & side]) / np.median(y1[w1 & ~side]) - 1) < 0.03
    assert (out[bid == 2] == photo[bid == 2]).all()                     # nothing the sun explains: left as it is
    assert (y1 + 1 >= y0).all()                                         # nothing is ever darkened
    assert (out[g["which"] == 1] == photo[g["which"] == 1]).all() and st["raised"] == 1


def test_the_evened_capture_lifts_a_ground_shadow_to_the_ground_beside_it():
    code, g = scene()
    photo = painting_of(code, g).astype(float)
    cast = np.zeros(g["which"].shape, bool); cast[195:225, 20:100] = True      # on bare ground
    photo[cast] *= (0.45, 0.5, 0.6)                                             # dark and blue
    photo = photo.astype(np.uint8)
    out, st = D.even_capture(photo, g, cast, SUN)
    inner = np.zeros_like(cast); inner[199:221, 24:96] = True
    assert np.abs(np.median(out[inner], axis=0) - 150).max() <= 4 and st["ground_patches"] == 1
    far = np.zeros_like(cast); far[230:, :] = True
    assert (out[far] == photo[far]).all()


def test_t3_differs_from_t2_by_its_first_control_image_only(tmp_path, monkeypatch):
    t2, t3 = J.BY_ID["T2"], J.BY_ID["T3"]
    assert (t3.gpu, t3.cloud, t3.goal, t3.work, t3.model) == (t2.gpu, t2.cloud, t2.goal, t2.work, t2.model)
    assert J.T2_MEASURED_S <= t3.est_h * 3600 <= J.T2_MEASURED_S + 60 and t3.worst_usd <= 1.10
    assert runner.cap_seconds(t3) - 45 >= 1.4 * J.T2_MEASURED_S
    assert B.OUT["T3"] == "detail/painted_evenin" and D.PAINTED["T3"] == "painted_evenin" and B.SETUP["T3"] == "paint"
    assert any(str(u[0]).endswith(B.V1_LORA) for u in B.uploads("T3", HERE))
    monkeypatch.setattr(B, "base", lambda: tmp_path)
    monkeypatch.setattr(D, "base", lambda: tmp_path / "detail")
    src = tmp_path / "detail" / "inputs"; src.mkdir(parents=True)
    even = tmp_path / "detail" / "inputs_even"; even.mkdir()
    for n in D.input_names():
        for ext in ("unlit.png", "layout.png"):
            (src / f"{n}.{ext}").write_bytes(f"{n}.{ext}".encode())
        (even / f"{n}.unlit.png").write_bytes(f"{n}.evened".encode())
    b2, b3 = B.build("T2"), B.build("T3")
    files = lambda d: {p.name: p.read_bytes() for p in (d / "inputs").iterdir()}          # noqa: E731
    f2, f3 = files(b2), files(b3)
    assert set(f2) == set(f3) and len(f3) == 24
    assert all((f2[k] == f3[k]) == k.endswith("layout.png") for k in f2)
    assert (b2 / "prompt.txt").read_text() == (b3 / "prompt.txt").read_text()


def test_level_brings_a_buildings_sides_to_one_brightness_and_the_target_has_the_codes_windows(monkeypatch):
    from v2.bakeoff.dataset import flat_light
    code, g = scene()
    side = np.zeros(g["ids"].shape, bool)
    cls = g["ids"] & 255; cc = np.indices(cls.shape)[1]
    for b, c0 in ((1, 30), (2, 130)):
        side |= np.isin(cls, (11, 12)) & ((g["ids"] >> 8) == b) & (cc >= c0 + 40)
    g["normal"][np.isin(cls, (11, 12))] = (1.0, 0.0, 0.0)               # walls face east ...
    g["normal"][side] = (0.0, -1.0, 0.0)                                # ... and the far 30 columns south
    painting = painting_of(code, g).astype(float)
    painting[side] *= 0.6
    painting = painting.astype(np.uint8)
    ids = np.where(g["which"] == 5, g["ids"], 0)
    assert flat_light(painting, ids, g["normal"])[1]                    # the check fails it as painted
    lv = D.level(painting, g)
    worst, bad = flat_light(lv, ids, g["normal"])
    assert not bad and worst < 0.02
    assert (lv[g["which"] == 1] == painting[g["which"] == 1]).all()     # the ground is not touched
    monkeypatch.setattr(D, "photo_shadow", lambda g, meta, rel=None: None)
    t = D.target(code, painting, g, {})
    assert (t["target"][cls == 12] == code[cls == 12]).all()
    assert not flat_light(t["target"], ids, g["normal"])[1]


def test_the_viewers_variant_rewrites_only_the_painted_layers_colour_and_leaves_the_release_alone(tmp_path, monkeypatch):
    from PIL import Image

    from v2.layers.common import TILE, read_tile, write_tile
    n = 2 * TILE
    monkeypatch.setattr(D, "BLOCK", n); monkeypatch.setattr(D, "WIN", TILE)
    monkeypatch.setattr(D, "BLOCKS", {"x": (0, 0)})
    monkeypatch.setattr(D, "base", lambda: tmp_path / "detail")
    monkeypatch.setattr(D, "v2_data", lambda: tmp_path)
    # a release of one block: buildings are what is seen on its left three quarters, ground on the rest
    rel = tmp_path / "test" / "release" / "r1"; store = tmp_path / "store"
    which = np.ones((n, n), np.uint8); which[:, : 3 * n // 4] = 5
    tiles = {"0": {}, "1": {}}
    for layer in ("buildings", "structures", "ground"):
        for z, names in (("0", ("0_0", "1_0", "0_1", "1_1")), ("1", ("0_0",))):
            for nm in names:
                depth = np.full((TILE, TILE), np.inf)
                if layer != "structures":
                    depth[:] = 10.0
                dm = write_tile(store / layer / z, nm, rgb=np.full((TILE, TILE, 3), 50, np.uint8), depth=depth,
                                normal=np.tile([0.0, 0.0, 1.0], (TILE, TILE, 1)), q=101, z=int(z))
                tiles[z][nm] = dm
        (rel).mkdir(parents=True, exist_ok=True)
        (rel / layer).symlink_to(store / layer)
    (rel / "index.json").write_text(json.dumps({"layers": {L: {"tiles": tiles} for L in ("buildings", "structures", "ground")}}))
    (rel.parent / "current.json").write_text(json.dumps({"folder": "r1"}))
    before = {p: p.read_bytes() for p in store.rglob("*") if p.is_file()}
    # the block's geometry and its targets: all 200
    src = tmp_path / "detail" / "inputs"; src.mkdir(parents=True)
    np.savez_compressed(src / "x_p250.geom.npz", ids=np.zeros((n, n), np.uint32), which=which,
                        normal=np.zeros((n, n, 3), np.float16), depth=np.full((n, n), 10.0, np.float32))
    Image.fromarray(np.zeros((n, n, 3), np.uint8)).save(src / "x_p250.code.png")
    (src / "x_p250.json").write_text("{}")
    tg = tmp_path / "detail" / "targets" / "T1"; tg.mkdir(parents=True)
    Image.fromarray(np.full((n, n, 3), 200, np.uint8)).save(tg / "x_p250_0.png")
    out = D.variant_release("T1", 0, area="painted")
    assert out.parent == tmp_path / "painted" / "release"
    assert json.loads((out.parent / "current.json").read_text())["folder"] == out.name
    assert {p: p.read_bytes() for p in store.rglob("*") if p.is_file()} == before      # the release is as it was
    t = read_tile(out / "buildings" / "0", "1_1", tiles["0"]["1_1"], z=0)["rgb"]
    left = which[TILE:, TILE:] == 5
    assert left.any() and not left.all()
    assert (t[left] == 200).all() and (t[~left] == 50).all()                            # only where it is seen
    assert (read_tile(out / "buildings" / "0", "0_0", tiles["0"]["0_0"], z=0)["rgb"] == 200).all()
    up = read_tile(out / "buildings" / "1", "0_0", tiles["1"]["0_0"], z=1)["rgb"]       # the next zoom follows
    assert (up[:, : 3 * TILE // 4] == 200).all() and (up[:, 3 * TILE // 4:] == 50).all()
    assert (out / "ground").resolve() == (store / "ground").resolve()                  # the other layers: linked
    assert (read_tile(out / "structures" / "0", "0_0", tiles["0"]["0_0"], z=0)["rgb"] == 50).all()


def test_seams_measure_one_buildings_colour_between_two_paintings_of_it(tmp_path, monkeypatch):
    from PIL import Image
    code, g = scene()
    n = code.shape[0]
    monkeypatch.setattr(D, "base", lambda: tmp_path)
    monkeypatch.setattr(D, "input_names", lambda: ["x_p250"])
    src = tmp_path / "inputs"; src.mkdir()
    Image.fromarray(code).save(src / "x_p250.code.png")
    np.savez_compressed(src / "x_p250.geom.npz", **g)
    (src / "x_p250.json").write_text("{}")
    (tmp_path / "checks").mkdir(); tg = tmp_path / "targets" / "T1"; tg.mkdir(parents=True)
    a = painting_of(code, g); b = a.copy()
    wall1 = ((g["ids"] & 255) == 11) & ((g["ids"] >> 8) == 1)
    b[wall1] = (b[wall1] * 0.8).astype(np.uint8)                        # one building's walls 20% darker in the second
    Image.fromarray(a).save(tg / "x_p250_0.png"); Image.fromarray(b).save(tg / "x_p250_1.png")
    out = D.seams("T1", min_px=200)["two_candidates"]
    assert out["parts"] == 4 and out["median"] < 0.01 and 0.2 < out["p90"] * 1.5 and out["over_5_percent"] == 0.25


def test_one_colour_a_building_makes_two_paintings_of_it_alike(monkeypatch):
    code, g = scene()
    cls = g["ids"] & 255; bid = g["ids"] >> 8
    g["normal"][np.isin(cls, (11, 12))] = (1.0, 0.0, 0.0)               # walls a flat_light side can measure
    a = painting_of(code, g).astype(float); b = a.copy()
    wall1 = (cls == 11) & (bid == 1)
    b[wall1] *= (0.75, 0.8, 0.95)                                        # the second painting: building 1 darker, bluer
    a, b = a.astype(np.uint8), b.astype(np.uint8)
    ta, tb = D.part_colours(a, g), D.part_colours(b, g)
    assert set(ta) == {(1, "wall"), (1, "roof"), (2, "wall"), (2, "roof")}
    assert np.abs(ta[(1, "wall")][0] - (240, 210, 150)).max() < 4 and np.abs(tb[(1, "wall")][0] - (180, 168, 142)).max() < 4
    # the painting at v2's scale decides when both show the building alike; more of it shown decides otherwise
    col = D.one_colour({"x_p250_0": ta, "x_p125_0": tb})
    assert np.allclose(col[(1, "wall")], tb[(1, "wall")][0])
    few = {k: (v[0], v[1] // 2) for k, v in tb.items()}
    assert np.allclose(D.one_colour({"x_p250_0": ta, "x_p125_0": few})[(1, "wall")], ta[(1, "wall")][0])
    monkeypatch.setattr(D, "photo_shadow", lambda g, meta, rel=None: None)
    col = D.one_colour({"x_p250_0": ta, "x_p250_1": tb})                 # the same scale: the first
    out = [D.target(code, None, g, {}, colours=col, reg=r)["target"] for r in (a, b)]
    own = [D.target(code, None, g, {}, reg=r)["target"] for r in (a, b)]
    inner = wall1 & (D.lum(code.astype(float)) > 100)
    med = lambda im: np.median(im[inner].astype(float), axis=0)          # noqa: E731
    assert np.abs(med(own[0]) - med(own[1])).max() > 25                  # each painting's own colour: apart
    assert np.abs(med(out[0]) - med(out[1])).max() <= 3                  # one colour: alike
    assert np.abs(med(out[0]) - (240, 210, 150)).max() <= 8


def test_in_the_viewer_a_building_is_never_split_between_two_paintings(tmp_path, monkeypatch):
    from PIL import Image

    from v2.layers.common import TILE, read_tile, write_tile
    n = 2 * TILE
    monkeypatch.setattr(D, "BLOCK", n); monkeypatch.setattr(D, "WIN", TILE)
    monkeypatch.setattr(D, "BLOCKS", {"x": (0, 0)})
    monkeypatch.setattr(D, "base", lambda: tmp_path / "detail")
    monkeypatch.setattr(D, "v2_data", lambda: tmp_path)
    q = n // 4
    which = np.ones((n, n), np.uint8); ids = np.zeros((n, n), np.uint32)
    which[q + 50:q + 150, q + 50:q + 150] = 5; ids[q + 50:q + 150, q + 50:q + 150] = 1 << 8 | 11      # whole in the centre
    which[q + 300:q + 400, q + 400:q + TILE + 80] = 5; ids[q + 300:q + 400, q + 400:q + TILE + 80] = 2 << 8 | 11   # crosses its edge
    rel = tmp_path / "test" / "release" / "r1"; store = tmp_path / "store"
    tiles = {"0": {}}
    for layer in ("buildings", "structures"):
        for nm in ("0_0", "1_0", "0_1", "1_1"):
            tx, ty = (int(v) for v in nm.split("_"))
            seen = which[ty * TILE:(ty + 1) * TILE, tx * TILE:(tx + 1) * TILE] == (5 if layer == "buildings" else 6)
            tiles["0"][nm] = write_tile(store / layer / "0", nm, rgb=np.full((TILE, TILE, 3), 50, np.uint8),
                                        depth=np.where(seen, 10.0, np.inf), normal=np.tile([0.0, 0.0, 1.0], (TILE, TILE, 1)), q=101)
        rel.mkdir(parents=True, exist_ok=True)
        (rel / layer).symlink_to(store / layer)
    (rel / "index.json").write_text(json.dumps({"layers": {L: {"tiles": tiles} for L in ("buildings", "structures")}}))
    (rel.parent / "current.json").write_text(json.dumps({"folder": "r1"}))
    src = tmp_path / "detail" / "inputs"; src.mkdir(parents=True)
    np.savez_compressed(src / "x_p250.geom.npz", ids=ids, which=which, normal=np.zeros((n, n, 3), np.float16),
                        depth=np.full((n, n), 10.0, np.float32))
    Image.fromarray(np.zeros((n, n, 3), np.uint8)).save(src / "x_p250.code.png")
    (src / "x_p250.json").write_text("{}")
    tg = tmp_path / "detail" / "targets" / "T1"; tg.mkdir(parents=True)
    Image.fromarray(np.full((n, n, 3), 200, np.uint8)).save(tg / "x_p250_0.png")       # the block's painting: 200
    Image.fromarray(np.full((TILE, TILE, 3), 90, np.uint8)).save(tg / "x_p125_0.png")  # the close up: 90
    out = D.variant_release("T1", 0, area="painted")
    got = np.zeros((n, n, 3), np.uint8)
    for nm in tiles["0"]:
        tx, ty = (int(v) for v in nm.split("_"))
        got[ty * TILE:(ty + 1) * TILE, tx * TILE:(tx + 1) * TILE] = read_tile(out / "buildings" / "0", nm, tiles["0"][nm])["rgb"]
    assert (got[(ids >> 8) == 1] == 90).all()                           # whole inside: from the close up
    assert (got[(ids >> 8) == 2] == 200).all()                          # across its edge: all of it from the block's


def test_a_face_the_painting_shows_in_two_tones_is_not_taken_from_it():
    code, g = scene()
    cls = g["ids"] & 255; bid = g["ids"] >> 8; cc = np.indices(cls.shape)[1]
    painting = painting_of(code, g).astype(float)
    roof1 = (cls == 23) & (bid == 1)
    painting[roof1 & (cc < 65)] *= 0.45                                 # a shadow's edge across building 1's roof
    painting = painting.astype(np.uint8)
    under = D.transfer(code, painting, g)[0]
    st = {}
    out = D.delit(code, painting, g, base=under, two_tone=D.TWO_TONE, stats=st)
    free = D.delit(code, painting, g, base=under)
    inner = roof1.copy(); inner[:42] = False; inner[66:] = False; inner[:, :34] = False; inner[:, 96:] = False
    assert (out[inner] == under[inner]).all() and st["left_out"] == 1   # that roof: the base, whole
    assert not (free[inner] == under[inner]).all()
    roof2 = (cls == 23) & (bid == 2)
    assert (out[roof2] == free[roof2]).all()                            # the other roof: the painting, as before
    assert st["faces"] == 4 and st["left_out_px"] == int(roof1.sum())


def test_where_two_blocks_overlap_a_building_comes_from_the_block_that_shows_the_most_of_it(tmp_path, monkeypatch):
    from PIL import Image

    from v2.layers.common import TILE, read_tile, write_tile
    n = 2 * TILE
    monkeypatch.setattr(D, "BLOCK", n); monkeypatch.setattr(D, "WIN", TILE)
    monkeypatch.setattr(D, "BLOCKS", {"a": (0, 0), "b": (TILE, 0)})     # b starts half a block to the right of a
    monkeypatch.setattr(D, "base", lambda: tmp_path / "detail")
    monkeypatch.setattr(D, "v2_data", lambda: tmp_path)
    W = 3 * TILE
    which = np.ones((n, W), np.uint8); ids = np.zeros((n, W), np.uint32)
    which[100:200, TILE - 300:TILE + 100] = 5; ids[100:200, TILE - 300:TILE + 100] = 1 << 8 | 11   # mostly in a alone
    which[400:500, TILE + 50:TILE + 700] = 5; ids[400:500, TILE + 50:TILE + 700] = 2 << 8 | 11     # whole in b, part in a
    rel = tmp_path / "test" / "release" / "r1"; store = tmp_path / "store"
    tiles = {"0": {}}
    for layer in ("buildings", "structures"):
        for tx in range(3):
            for ty in range(2):
                seen = which[ty * TILE:(ty + 1) * TILE, tx * TILE:(tx + 1) * TILE] == (5 if layer == "buildings" else 6)
                tiles["0"][f"{tx}_{ty}"] = write_tile(store / layer / "0", f"{tx}_{ty}", rgb=np.full((TILE, TILE, 3), 50, np.uint8),
                                                      depth=np.where(seen, 10.0, np.inf), normal=np.tile([0.0, 0.0, 1.0], (TILE, TILE, 1)), q=101)
        rel.mkdir(parents=True, exist_ok=True)
        (rel / layer).symlink_to(store / layer)
    (rel / "index.json").write_text(json.dumps({"layers": {L: {"tiles": tiles} for L in ("buildings", "structures")}}))
    (rel.parent / "current.json").write_text(json.dumps({"folder": "r1"}))
    src = tmp_path / "detail" / "inputs"; src.mkdir(parents=True)
    tg = tmp_path / "detail" / "targets" / "T1"; tg.mkdir(parents=True)
    for name, x0, value in (("a", 0, 200), ("b", TILE, 90)):
        np.savez_compressed(src / f"{name}_p250.geom.npz", ids=ids[:, x0:x0 + n], which=which[:, x0:x0 + n],
                            normal=np.zeros((n, n, 3), np.float16), depth=np.full((n, n), 10.0, np.float32))
        Image.fromarray(np.zeros((n, n, 3), np.uint8)).save(src / f"{name}_p250.code.png")
        (src / f"{name}_p250.json").write_text("{}")
        Image.fromarray(np.full((n, n, 3), value, np.uint8)).save(tg / f"{name}_p250_0.png")
    out = D.variant_release("T1", 0, area="painted")
    got = np.zeros((n, W, 3), np.uint8)
    for nm in tiles["0"]:
        tx, ty = (int(v) for v in nm.split("_"))
        got[ty * TILE:(ty + 1) * TILE, tx * TILE:(tx + 1) * TILE] = read_tile(out / "buildings" / "0", nm, tiles["0"][nm])["rgb"]
    assert (got[(ids >> 8) == 1] == 200).all()                          # a shows all of it, b a quarter: all from a
    assert (got[(ids >> 8) == 2] == 90).all()                           # b shows all of it: all from b, also inside a


def test_surface_mode_takes_the_paintings_colour_and_plain_texture_and_none_of_its_things(monkeypatch):
    code, g = scene()
    cls = g["ids"] & 255; bid = g["ids"] >> 8
    rr, cc = np.indices(cls.shape)
    painting = painting_of(code, g).astype(float)                       # roofs hatched; a painted window on each wall
    wall1 = (cls == 11) & (bid == 1)
    thing = wall1 & (rr >= 78) & (rr < 100) & (cc >= 60) & (cc < 84)    # a window of the painting's own, elsewhere
    painting[thing] = (30, 40, 70)
    painting = painting.astype(np.uint8)
    monkeypatch.setattr(D, "photo_shadow", lambda g, meta, rel=None: None)
    t = D.target(code, None, g, {}, reg=painting, mode="surface")["target"]
    inner = wall1 & (D.lum(code.astype(float)) > 100)
    assert np.abs(np.median(t[inner], axis=0) - (240, 210, 150)).max() <= 8          # the painting's wall colour
    core = np.zeros_like(thing); core[82:96, 64:80] = True
    plain = np.zeros_like(thing); plain[82:96, 34:44] = True
    a, b = D.lum(t[core].astype(float)).mean(), D.lum(t[plain & inner].astype(float)).mean()
    assert abs(a / b - 1) < 0.03                                         # its own window: gone, no patch, no outline
    assert (t[cls == 12] == code[cls == 12]).all() and D.ink_changed(code, t) == 0    # the code's windows and ink
    roof_in = np.zeros(cls.shape, bool); roof_in[48:62, 40:90] = True
    assert t[roof_in].std() > code[roof_in].std() + 1                    # the roof's hatch: a plain surface, kept
    d = D.target(code, None, g, {}, reg=painting, mode="drawing")["target"]
    assert not (d[cls == 11] == t[cls == 11]).all()


# ------------------------------------------------------------------------------------------------ the whole test area (T4)
def test_the_test_areas_job_is_quoted_from_the_trials_times_and_fits_the_phase():
    j, t1 = J.BY_ID["T4"], J.BY_ID["T1"]
    assert j in J.TRIAL_JOBS and j not in J.JOBS and j.goal == "phase3_lock_look"
    assert (j.gpu, j.cloud, j.model) == (t1.gpu, t1.cloud, t1.model)       # the machine and the model the times are from
    need = sum(J.T4_PLAN_S.values())
    assert need <= j.est_h * 3600 <= need + 60
    assert runner.cap_seconds(j) - 45 >= 1.2 * need                      # a fifth over the plan still finishes
    assert f"{J.T4_PAINTINGS} windows x 1 = {J.T4_PAINTINGS} paintings" in j.work and len(D.AREA_SEEDS) == 1
    assert f"{J.T4_PAINTINGS} paintings x 21 s" in " ".join(J.T4_PLAN_S)
    budget = json.loads((HERE / "budget.json").read_text())
    assert j.est_usd <= j.worst_usd <= 2.19 <= budget["goals"][j.goal]["cap_usd"]
    assert 'T4)  paint "$V1" 1867 ;;' in (runner.POD / "run.sh").read_text()
    assert B.SETUP["T4"] == "paint" and B.OUT["T4"] == "detail/" + D.PAINTED["T4"] == "detail/painted_area"
    assert any(str(u[0]).endswith(B.V1_LORA) for u in B.uploads("T4", HERE))


def test_the_test_areas_grid_covers_every_tile_with_a_building_or_a_structure(tmp_path):
    from v2.layers.common import TILE
    tiles = {"buildings": ["10_10", "11_10", "13_12"], "structures": ["16_11"]}
    (tmp_path / "index.json").write_text(json.dumps({"layers": {L: {"tiles": {"0": {n: 1.0 for n in v}}} for L, v in tiles.items()}}))
    grid = D.area_grid(tmp_path)
    assert all(x % 2 == 0 and y % 2 == 0 for x, y in grid)               # v1's pixels are whole
    assert all((x - grid[0][0]) % D.STRIDE == 0 and (y - grid[0][1]) % D.STRIDE == 0 for x, y in grid)
    for n in sum(tiles.values(), []):
        tx, ty = (int(v) for v in n.split("_"))
        seen = np.zeros((TILE, TILE), bool)
        for x, y in grid:
            a0, b0, a1, b1 = max(x, tx * TILE), max(y, ty * TILE), min(x + D.WIN, (tx + 1) * TILE), min(y + D.WIN, (ty + 1) * TILE)
            if a1 > a0 and b1 > b0:
                seen[b0 - ty * TILE:b1 - ty * TILE, a0 - tx * TILE:a1 - tx * TILE] = True
        assert seen.all(), n
    x0, y0 = grid[0]
    assert D.window_of(D.area_name(x0, y0)) == (x0, y0, D.WIN, 1)
    assert D.window_of("cathedral_p125") == (D.BLOCKS["cathedral"][0] + D.BLOCK // 4, D.BLOCKS["cathedral"][1] + D.BLOCK // 4, D.WIN, 1)


def test_the_test_areas_bundle_is_its_grids_windows_with_t1s_prompt(tmp_path, monkeypatch):
    from v2.bakeoff import prompts as PR
    monkeypatch.setattr(B, "base", lambda: tmp_path)
    monkeypatch.setattr(D, "base", lambda: tmp_path / "detail")
    src = tmp_path / "detail" / "inputs_area"; src.mkdir(parents=True)
    names = ["w0_0", "w768_0", "w0_768"]
    (tmp_path / "detail" / "inputs_area.json").write_text(json.dumps({"inputs": {n: {} for n in names}}))
    for n in names + ["w9999_0"]:                                        # a file of an earlier grid is not taken
        for ext in ("unlit.png", "layout.png"):
            (src / f"{n}.{ext}").write_bytes(f"{n}.{ext}".encode())
    b = B.build("T4")
    assert sorted(p.name for p in (b / "inputs").iterdir()) == sorted(f"{n}.{e}" for n in names for e in ("unlit.png", "layout.png"))
    assert (b / "prompt.txt").read_text() == PR.V1_CAPTION               # as T1 was painted
    assert D.names_of("T4") == names == D.names_of("area_free") and D.names_of("T1") == D.input_names()
    # the painter gives one seed's painting no number (pod/paint.py); two seeds' have one
    assert D.painted_file("w0_0", "T4") == tmp_path / "detail" / "painted_area" / "w0_0.png"
    assert D.painted_file("cathedral_p125", "T1", 1).name == "cathedral_p125_1.png"


def _grid_scene(tmp_path, monkeypatch, source, grey=0, hidden=None):
    """Two windows of a made-up grid, the second half a window to the right, over three tiles by two; a release
    r1 with empty tiles; targets of one grey each (200 and 90). Returns (ids, which, tiles, W). With `grey`, the
    code art and the tiles are that grey and the tiles carry their ids; `hidden` (a slice pair) is a part of the
    buildings' layer that the windows see another layer in front of."""
    from PIL import Image

    from v2.layers.common import TILE, write_tile
    n = 2 * TILE
    monkeypatch.setattr(D, "WIN", n); monkeypatch.setattr(D, "STRIDE", TILE)
    monkeypatch.setattr(D, "base", lambda: tmp_path / "detail")
    monkeypatch.setattr(D, "v2_data", lambda: tmp_path)
    W = 3 * TILE
    which = np.ones((n, W), np.uint8); ids = np.zeros((n, W), np.uint32)
    which[100:200, TILE - 300:TILE + 100] = 5; ids[100:200, TILE - 300:TILE + 100] = 1 << 8 | 11   # mostly in the first alone
    which[400:500, TILE + 50:TILE + 700] = 5; ids[400:500, TILE + 50:TILE + 700] = 2 << 8 | 11     # whole in the second
    rel = tmp_path / "test" / "release" / "r1"; store = tmp_path / "store"
    tiles = {"0": {}}
    for layer in ("buildings", "structures"):
        for tx in range(3):
            for ty in range(2):
                tl = (slice(ty * TILE, (ty + 1) * TILE), slice(tx * TILE, (tx + 1) * TILE))
                seen = which[tl] == (5 if layer == "buildings" else 6)
                tiles["0"][f"{tx}_{ty}"] = write_tile(store / layer / "0", f"{tx}_{ty}", rgb=np.full((TILE, TILE, 3), grey or 50, np.uint8),
                                                      depth=np.where(seen, 10.0, np.inf), normal=np.tile([0.0, 0.0, 1.0], (TILE, TILE, 1)), q=101,
                                                      ids=ids[tl] if grey and layer == "buildings" else None)
        rel.mkdir(parents=True, exist_ok=True)
        (rel / layer).symlink_to(store / layer)
    (rel / "index.json").write_text(json.dumps({"layers": {L: {"tiles": tiles} for L in ("buildings", "structures")}}))
    (rel.parent / "current.json").write_text(json.dumps({"folder": "r1"}))
    if hidden is not None:                                               # the windows see another layer there
        which = which.copy(); which[hidden] = 2
    src = tmp_path / "detail" / "inputs_area"; src.mkdir(parents=True)
    tg = tmp_path / "detail" / "targets" / source; tg.mkdir(parents=True)
    (tmp_path / "detail" / "checks").mkdir()
    metas = {}
    for x0, value in ((0, 200), (TILE, 90)):
        name = D.area_name(x0, 0)
        np.savez_compressed(src / f"{name}.geom.npz", ids=ids[:, x0:x0 + n], which=which[:, x0:x0 + n],
                            normal=np.zeros((n, n, 3), np.float16), depth=np.full((n, n), 10.0, np.float32))
        Image.fromarray(np.full((n, n, 3), grey, np.uint8)).save(src / f"{name}.code.png")
        metas[name] = {"x0": x0, "y0": 0, "size": n, "release": "r1", "paint_share": 0.1}
        (src / f"{name}.json").write_text(json.dumps(metas[name]))
        Image.fromarray(np.full((n, n, 3), value, np.uint8)).save(tg / f"{name}_0.png")
    (tmp_path / "detail" / "inputs_area.json").write_text(json.dumps({"inputs": metas}))
    return ids, which, tiles, W


def test_on_the_grid_a_building_two_windows_show_comes_from_the_one_that_shows_the_most_of_it(tmp_path, monkeypatch):
    import pytest

    from v2.layers.common import TILE, read_tile
    ids, _which, tiles, W = _grid_scene(tmp_path, monkeypatch, "T4")
    out = D.variant_release("T4", 0, area="painted")
    got = np.zeros((2 * TILE, W, 3), np.uint8)
    for nm in tiles["0"]:
        tx, ty = (int(v) for v in nm.split("_"))
        got[ty * TILE:(ty + 1) * TILE, tx * TILE:(tx + 1) * TILE] = read_tile(out / "buildings" / "0", nm, tiles["0"][nm])["rgb"]
    assert (got[(ids >> 8) == 1] == 200).all()                          # the first shows all of it: all from the first
    assert (got[(ids >> 8) == 2] == 90).all()                           # the second shows all of it, the first a part
    assert (got[ids == 0] == 50).all()                                  # nothing else is touched
    # inputs made for another release are refused: their geometry is not this release's
    src = tmp_path / "detail" / "inputs_area"
    (src / "w0_0.json").write_text(json.dumps({"x0": 0, "y0": 0, "release": "r0"}))
    with pytest.raises(SystemExit):
        D.variant_release("T4", 0, area="painted")


def test_seams_on_the_grid_compare_two_neighbours_on_the_ground_they_share(tmp_path, monkeypatch):
    _grid_scene(tmp_path, monkeypatch, "area_free")
    s = D.seams("area_free", min_px=600)["two_windows"]
    # building 2 lies whole in both windows' shared half; building 1's part there is 100 x 100 px: two walls
    assert s["parts"] == 2 and abs(s["median"] - (200 - 90) / 145) < 0.01 and s["over_5_percent"] == 1.0


def test_a_far_zoom_tile_takes_a_layers_new_colour_only_where_that_layer_is_its_nearest_surface():
    k = np.zeros((4, 4), np.uint8); k[0] = 1 * 16 + 2; k[1] = 5 * 16 + 11; k[2] = 6 * 16; k[3] = 7 * 16 + 1
    rgb = np.full((4, 4, 3), 10, np.uint8)
    out = D.far_colour(rgb, k, {5: np.full((4, 4, 3), 200, np.uint8), 6: np.full((4, 4, 3), 90, np.uint8)})
    assert (out[0] == 10).all() and (out[1] == 200).all() and (out[2] == 90).all() and (out[3] == 10).all()   # ground, trees stay
    assert (D.far_colour(rgb, k, {5: np.full((4, 4, 3), 200, np.uint8)})[2] == 10).all()   # a layer with no tile there
    assert (rgb == 10).all()                                              # the tile read is not changed


def test_what_a_layer_holds_behind_another_layer_takes_its_materials_painted_colour(tmp_path, monkeypatch):
    """A target shows the nearest surface only. The part of a wall behind a cliff is in the buildings' tile all
    the same: it takes the colour change the wall has where a target shows it, not the code art's colour."""
    from v2.layers.common import TILE, read_tile
    hid = (slice(400, 500), slice(TILE + 600, TILE + 700))               # a part of building 2's wall
    ids, _which, tiles, W = _grid_scene(tmp_path, monkeypatch, "T4", grey=100, hidden=hid)
    out = D.variant_release("T4", 0, area="painted")
    got = np.zeros((2 * TILE, W, 3), np.uint8)
    for nm in tiles["0"]:
        tx, ty = (int(v) for v in nm.split("_"))
        got[ty * TILE:(ty + 1) * TILE, tx * TILE:(tx + 1) * TILE] = read_tile(out / "buildings" / "0", nm, tiles["0"][nm])["rgb"]
    assert (got[(ids >> 8) == 2] == 90).all() and (got[hid] == 90).all()   # shown and hidden alike: 100 x 90 / 100
    assert (got[(ids >> 8) == 1] == 200).all() and (got[ids == 0] == 100).all()
    assert json.loads((out.parent / "current.json").read_text())["hidden_px_tinted"] == 100 * 100


def _roof_rows(g, b=1):
    roof = ((g["ids"] & 255) == 23) & ((g["ids"] >> 8) == b)
    return roof, np.flatnonzero(roof.any(1)), np.flatnonzero(roof.any(0))


def test_a_narrow_painted_shadow_on_the_models_shadow_line_is_no_part_of_the_texture():
    """A shadow the painting kept as a band along a roof's foot, narrower than the texture's own reach: with the
    3D model's shadow given (cast), the texture is read on each side of its line apart and the band is gone;
    without it the band comes through as a darker strip."""
    code, g = scene()
    roof, rows, cols = _roof_rows(g)
    band = roof.copy(); band[: rows[-1] - 7] = False                    # the roof's lowest 8 rows
    paint = painting_of(code, g).astype(float); paint[band] *= 0.87
    paint = paint.astype(np.uint8)
    inside = np.zeros(roof.shape, bool); inside[:, cols[0] + 6:cols[-1] - 5] = True
    low = band & inside; low[rows[-1] - 1:] = False; low[: rows[-1] - 5] = False        # the band's middle rows
    high = roof & inside & ~band; high[: rows[-1] - 16] = False; high[rows[-1] - 9:] = False
    def ratio(out):
        L = D.lum(out.astype(float))
        return float(np.median(L[low]) / np.median(L[high]))
    assert ratio(paint) < 0.9                                            # the painting has it
    assert ratio(D.transfer(code, paint, g, p=D.SURFACE)[0]) < 0.96      # and so had the picture
    assert abs(ratio(D.transfer(code, paint, g, p=D.SURFACE, cast=band)[0]) - 1) < 0.02
    # a cast shadow where the painting has none changes nothing but the grain's own mean
    flat = painting_of(code, g)
    a, b = D.transfer(code, flat, g, p=D.SURFACE)[0], D.transfer(code, flat, g, p=D.SURFACE, cast=band)[0]
    assert abs(ratio(a) - 1) < 0.02 and abs(ratio(b) - 1) < 0.02
