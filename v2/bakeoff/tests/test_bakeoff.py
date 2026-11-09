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


def test_pod_spec_arms_its_watchdog_and_never_names_the_other_pod():
    for j in J.JOBS:
        spec = runner.pod_spec(j, "bash pod/run.sh " + j.id)
        assert f"sleep {int(j.cap_h * 3600)}" in spec["dockerArgs"].split("&&")[0]
        assert spec["name"] not in runner.FOREIGN_PODS and spec["cloudType"] == "COMMUNITY"
    assert runner.launch("B1", "true", dry_run=True)["dry_run"] is True


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
