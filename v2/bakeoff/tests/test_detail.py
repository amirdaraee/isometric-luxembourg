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
    assert 'T1)  paint "$V1" 1867,1868 ;;' in (runner.POD / "run.sh").read_text()
    assert B.SETUP["T1"] == "paint" and B.OUT["T1"] == "detail/painted"
    assert any(str(u[0]).endswith(B.V1_LORA) for u in B.uploads("T1", HERE))


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
    out = D.delit(code, painting, g, sigma=8.0)
    # the painted window (dark on the wall) is still there, where the light transfer keeps the code's
    win = cls == 12; wall = (cls == 11) & (D.lum(code.astype(float)) > 100)
    assert D.lum(out[win].astype(float)).mean() < 0.5 * D.lum(out[wall].astype(float)).mean()
    assert not (out[win] == code[win]).all()
    # the eaves line the code inked between roof and wall stays the code's; the ground is untouched
    for r0, c0 in ((40, 30), (120, 130)):
        assert (out[r0 + 30, c0 + 2:c0 + 68] == code[r0 + 30, c0 + 2:c0 + 68]).all()
    assert (out[g["which"] == 1] == code[g["which"] == 1]).all()
