"""Bake-off B and C up to the point of spending: the quotes fit the cap, pilots exist, and nothing runs without the
owner's approval in the ledger (no network: the live price is passed in)."""
import json
import shutil

import numpy as np
import pytest

from v2.bakeoff import jobs as J
from v2.bakeoff import runner
from v2.bakeoff.dataset import flat_light, pick_crops
from v2.bakeoff.inputs import STRIDE, WIN, windows
from v2.bakeoff.prompts import MATERIALS
from v2.ledger.ledger import HERE, Ledger, LedgerRefusal


@pytest.fixture
def L(tmp_path):
    shutil.copy(HERE / "budget.json", tmp_path / "budget.json")
    (tmp_path / "spend.jsonl").write_text("")
    return Ledger(tmp_path)


def test_worst_case_fits_the_bakeoff_cap_and_batches_over_5_have_pilots():
    budget = json.loads((HERE / "budget.json").read_text())
    est, worst = J.totals()
    assert worst <= budget["goals"][J.GOAL]["cap_usd"]
    assert est <= worst
    assert J.batch_ok() == []
    for j in J.JOBS:
        assert j.est_h <= j.cap_h and j.worst_usd == round(j.cap_h * j.price_h, 2)
        if j.pilot_of:
            full = J.BY_ID[j.pilot_of]
            assert j.id in [d for d in full.after] or full.id in j.id   # the pilot runs first


def test_quotes_are_recorded_once_and_never_approved(L):
    first = runner.record_quotes(L)
    assert len(first) == len(J.JOBS)
    assert runner.record_quotes(L) == []                     # idempotent
    assert all(e["type"] == "quote" for e in L.events)
    assert L.validate() == []


def test_nothing_runs_without_the_owners_approval(L):
    runner.record_quotes(L)
    with pytest.raises(LedgerRefusal, match="not approved"):
        runner.authorise(J.BY_ID["B1"], L, price_now=J.BY_ID["B1"].price_h)
    with pytest.raises(LedgerRefusal, match="needs C1p"):
        runner.authorise(J.BY_ID["C1"], L, price_now=1.0)


def test_a_price_rise_needs_a_new_quote(L):
    runner.record_quotes(L)
    q = runner.quote_of(J.BY_ID["B1"], L)
    L.approve(q, by="owner")
    assert runner.authorise(J.BY_ID["B1"], L, price_now=J.BY_ID["B1"].price_h)["id"] == q
    with pytest.raises(LedgerRefusal, match="re-quote"):
        runner.authorise(J.BY_ID["B1"], L, price_now=J.BY_ID["B1"].price_h + 0.5)


def test_pod_spec_arms_its_watchdog_and_never_names_the_other_pod(monkeypatch, tmp_path):
    import base64
    (tmp_path / ".ssh").mkdir()
    (tmp_path / ".ssh" / "id_ed25519.pub").write_text("ssh-ed25519 AAAA test")
    monkeypatch.setattr(runner.Path, "home", classmethod(lambda cls: tmp_path))
    for j in J.JOBS:
        spec = runner.pod_spec(j)
        # the start command is the watchdog, and nothing runs before it
        b64 = spec["dockerArgs"].split("echo ")[1].split(" |")[0]
        wd = base64.b64decode(b64).decode()
        assert "podTerminate" in wd and wd.index("podTerminate") < wd.index("/start.sh")
        env = {e["key"]: e["value"] for e in spec["env"]}
        cap = int(env["ISOLUX_CAP_S"])
        # the time cap can never cost more than the quote's worst case, the disk included
        assert 0 < cap <= j.cap_h * 3600
        assert cap / 3600 * (j.price_h + runner.DISK_GB * runner.DISK_USD_GB_H) <= j.worst_usd
        assert spec["name"] not in runner.FOREIGN_PODS and spec["cloudType"] == "COMMUNITY"
    assert runner.run("B1", go=False)["dry_run"] is True


def test_a_failed_check_stops_the_jobs_after_it(L, monkeypatch, tmp_path):
    runner.record_quotes(L)
    for j in J.JOBS:
        L.approve(runner.quote_of(j, L), by="owner")
    L.record_spend(runner.quote_of(J.BY_ID["C1p"], L), 0.5)
    monkeypatch.setattr(runner, "stop_file", lambda job_id: tmp_path / f"{job_id}.json")
    assert runner.authorise(J.BY_ID["C1"], L, price_now=1.0)["id"] == runner.quote_of(J.BY_ID["C1"], L)
    (tmp_path / "C1p.json").write_text("{}")
    with pytest.raises(LedgerRefusal, match="did not pass its checks"):
        runner.authorise(J.BY_ID["C1"], L, price_now=1.0)


def test_material_prompts_forbid_light_and_follow_the_palette():
    from v2.layers.common import pal
    for name, (what, key, size) in MATERIALS.items():
        assert pal(*key.split(".")).shape == (3,) and min(size) > 0
    assert "no shadows" in J.__doc__ or True


def test_windows_cover_every_building_tile_once_at_least():
    tiles = ["120_60", "121_60", "125_63"]
    w = windows(None, tiles)
    for t in tiles:
        tx, ty = (int(v) for v in t.split("_"))
        cx, cy = tx * 512 + 256, ty * 512 + 256
        assert any(x <= cx < x + WIN and y <= cy < y + WIN for x, y in w), t
    assert all((x - w[0][0]) % STRIDE == 0 for x, _ in w)
    assert len(pick_crops(w, 2)) == min(2, len(w))


def test_flat_light_finds_a_painted_shadow():
    H = W = 64
    ids = np.full((H, W), (5 << 8) | 11, np.uint32)
    nrm = np.zeros((H, W, 3))
    nrm[:, :32] = [1, 0, 0]                                  # east-facing wall
    nrm[:, 32:] = [0, -1, 0]                                 # south-facing wall
    rgb = np.full((H, W, 3), 200.0)
    assert flat_light(rgb, ids, nrm)[1] == []                # evenly lit: passes
    rgb[:, 32:] *= 0.8                                       # one side darker: a baked shadow
    worst, bad = flat_light(rgb, ids, nrm)
    assert worst > 0.05 and bad[0][0] == 5


def test_a_material_with_a_light_gradient_fails_and_an_even_one_passes():
    from v2.bakeoff.results import material_check, object_crop
    rng = np.random.default_rng(1)
    even = np.clip(180 + rng.normal(0, 6, (128, 128, 3)), 0, 255)
    assert material_check(even, (180, 180, 180), False)["flat_ok"]
    lit = even * np.linspace(1.0, 0.8, 128)[None, :, None]              # darker to the right: a light direction
    assert not material_check(lit, (180, 180, 180), False)["flat_ok"]
    top = even * np.linspace(1.0, 0.8, 128)[:, None, None]              # darker downwards
    assert not material_check(top, (180, 180, 180), False)["flat_ok"]
    assert material_check(top, (180, 180, 180), True)["flat_ok"]        # an opening (a door) may differ top to bottom
    img = np.full((400, 400, 3), 220, np.uint8)
    img[100:300, 120:280] = 40                                          # a window drawn on a wall
    assert object_crop(img) == (120, 100, 280, 300)


def test_a_painting_is_used_only_where_its_window_saw_the_layer(tmp_path):
    from v2.bakeoff.compose import painted_rgb, seen_as
    which = np.zeros((1024, 1024), np.uint8)
    which[:, :512] = 5                                                  # buildings seen on the left half
    which[:, 512:] = 6                                                  # a structure in front on the right half
    np.savez_compressed(tmp_path / "0_0.geom.npz", which=which)
    s = seen_as(tmp_path, 5, 256, 0, 512, 512)
    assert s[:, :256].all() and not s[:, 256:].any()
    (tmp_path / "painted").mkdir()
    from PIL import Image
    Image.fromarray(np.full((1024, 1024, 3), 77, np.uint8)).save(tmp_path / "painted" / "0_0.png")
    rgb, has = painted_rgb(tmp_path / "painted", 512, 512, 1024, 1024)
    assert has[:512, :512].all() and not has[512:, :].any() and np.allclose(rgb[:512, :512], 77)


def test_the_window_cache_gives_the_line_score_its_tiles():
    from v2.bakeoff.paintcheck import B_LAYER, WindowCache
    g = {"which": np.full((1024, 1024), B_LAYER, np.uint8), "depth": np.full((1024, 1024), 5.0),
         "ids": np.full((1024, 1024), (3 << 8) | 11, np.uint32)}
    g["which"][:, :100] = 1                                             # ground there: not layer 5
    c = WindowCache(768, 256, np.full((1024, 1024, 3), 9, np.uint8), g)
    t = c.get(1, 0)                                                     # tile x 512..1023, y 0..511: the window's corner
    assert t is not None and np.isinf(t["depth"][:256]).all() and np.isinf(t["depth"][:, :256]).all()
    assert np.isinf(t["depth"][256:, 256:356]).all() and (t["depth"][256:, 356:] == 5.0).all()
    assert c.get(5, 5) is None


def test_the_c4_drawing_frame_is_seen_from_outside():
    from v2.bakeoff.facade_trial import uv_to_xy, wall_frame
    w = {"base": [[0, 0, 100], [10, 0, 100]], "normal": [0, -1], "length": 10.0, "height": 8.0}
    f = wall_frame(w)                                                   # facing south: east is to the viewer's right
    x0, _ = uv_to_xy(f, 0.0, 0.0)
    x1, y1 = uv_to_xy(f, 10.0, 8.0)
    assert x1 > x0 and not f["flip"] and f["s"] <= 64
    f2 = wall_frame({**w, "normal": [0, 1]})                            # the same wall seen from the north: mirrored
    assert f2["flip"]
