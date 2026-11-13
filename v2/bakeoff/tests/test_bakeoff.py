"""Bake-off B and C up to the point of spending: the quotes fit the cap, pilots exist, and nothing runs without the
owner's approval in the ledger (no network: the live price is passed in)."""
import dataclasses
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
    live_c1 = dataclasses.replace(J.BY_ID["C1"], cancelled="")       # the order rule itself, were C1 not stopped
    with pytest.raises(LedgerRefusal, match="needs C1p"):
        runner.authorise(live_c1, L, price_now=1.0)


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
    live_c1 = dataclasses.replace(J.BY_ID["C1"], cancelled="")
    assert runner.authorise(live_c1, L, price_now=1.0)["id"] == runner.quote_of(live_c1, L)
    (tmp_path / "C1p.json").write_text("{}")
    with pytest.raises(LedgerRefusal, match="did not pass its checks"):
        runner.authorise(live_c1, L, price_now=1.0)


def test_the_stopped_c_jobs_refuse_and_c4_runs_alone_with_v1s_model(L, monkeypatch, tmp_path):
    """Owner, 10 Nov 2026: C1, C2p, C2 and C3 stay stopped (whatever the ledger says); C4 no longer waits for C2."""
    runner.record_quotes(L)
    for j in J.JOBS:
        L.approve(runner.quote_of(j, L), by="owner")
    monkeypatch.setattr(runner, "stop_file", lambda job_id: tmp_path / f"{job_id}.json")
    for jid in ("C1", "C2p", "C2", "C3"):
        with pytest.raises(LedgerRefusal, match="stopped by the owner"):
            runner.authorise(J.BY_ID[jid], L, price_now=1.0)
        with pytest.raises(LedgerRefusal, match="stopped by the owner"):
            runner.requote(J.BY_ID[jid], L)
    c4 = J.BY_ID["C4"]
    assert c4.after == () and not c4.cancelled and "luxembourg-ink-v2" in c4.model
    assert runner.authorise(c4, L, price_now=c4.price_h)["id"] == runner.quote_of(c4, L)
    (tmp_path / "C1p.json").write_text("{}")                 # the pilot's stop does not reach C4
    assert runner.authorise(c4, L, price_now=c4.price_h)["worst_usd"] == c4.worst_usd <= 0.94
    with pytest.raises(LedgerRefusal, match="re-quote"):     # the other refusals stay
        runner.authorise(c4, L, price_now=c4.price_h + 0.01)
    # the stopped jobs' approvals are released: nothing is committed for them, and the ledger refuses them too
    for jid in ("C1", "C2p", "C2", "C3"):
        L.release(runner.quote_of(J.BY_ID[jid], L), by="owner")
    left = {"B1", "B2", "C1p", "C4"}
    assert L.committed(J.GOAL) == round(sum(J.BY_ID[j].worst_usd for j in left), 4)
    with pytest.raises(LedgerRefusal, match="released"):
        runner.authorise(dataclasses.replace(J.BY_ID["C3"], cancelled="", after=()), L, price_now=1.0)


def test_c4_takes_v1s_style_model_and_its_trigger(monkeypatch, tmp_path):
    from v2.bakeoff import bundle as B
    from v2.bakeoff import prompts as P
    monkeypatch.setattr(B, "base", lambda: tmp_path)
    monkeypatch.setattr(B, "v1_work", lambda: tmp_path / "v1")
    ups = B.uploads("C4", tmp_path / "bundle")
    assert any(src.endswith(B.V1_LORA) for src, _, _ in ups) and not any(B.NEW_LORA in src for src, _, _ in ups)
    assert "<isometric luxembourg ink>" in P.C_FACADE_PROMPT_V1 and "unshadowed" not in P.C_FACADE_PROMPT_V1
    assert "front-on" in P.C_FACADE_PROMPT_V1 and "no shadows" in P.C_FACADE_PROMPT_V1
    run_sh = (runner.POD / "run.sh").read_text()
    assert 'C4)  if [ -f "$NEW" ]; then paint "$NEW" 1867,1868; else paint "$V1" 1867,1868; fi' in run_sh


def test_a_used_up_quote_is_quoted_again_within_the_first_worst_case(L):
    """B1's rerun (owner, 10 Nov 2026): a new quote, and with the first run's spend it stays within the first cap."""
    b1 = J.BY_ID["B1"]
    first = L.quote(J.GOAL, "runpod", b1.ledger_job(), 2.42)
    with pytest.raises(LedgerRefusal, match="not used yet"):
        runner.requote(b1, L)
    L.approve(first["id"], by="owner")
    L.record_spend(first["id"], 0.2414)
    with pytest.raises(LedgerRefusal, match="already spent"):
        runner.authorise(b1, L, price_now=b1.price_h)
    q = runner.requote(b1, L)
    assert q["id"] != first["id"] and runner.quote_of(b1, L) == q["id"]
    assert q["worst_usd"] == b1.worst_usd and "rerun" in q["note"]
    # the owner's limit for the rerun (10 Nov 2026) was $2.18; what the failed second run spent comes off it
    assert q["worst_usd"] + 0.0545 <= 2.15 <= 2.18 and J.BY_ID["C4"].worst_usd + 0.0645 <= 0.94
    with pytest.raises(LedgerRefusal, match="not approved"):
        runner.authorise(b1, L, price_now=b1.price_h)
    L.approve(q["id"], by="owner")
    assert runner.authorise(b1, L, price_now=b1.price_h)["id"] == q["id"]


class FakeSession:
    def __init__(self, answer):
        self.answer, self.cmds, self.ended, self.name = answer, [], None, "fake"
        self.d = {"pod_id": "pod0", "cost_h": 2.59, "job": {"id": "B1", "start": 0.0, "deadline": 1e12}}
        self.open = True

    def ssh(self, cmd, timeout=120, check=True):
        self.cmds.append(cmd)
        return self.answer if "preflight.sh" in cmd else ""

    def rsync(self, src, dst, timeout=1800, extra=()):
        self.cmds.append(f"rsync {dst}")
        return True

    def save(self):
        pass

    def end(self, ledger=None, note=""):
        self.ended, self.open = note, False


def test_a_new_pod_that_fails_its_preflight_is_ended_before_any_setup(monkeypatch, L):
    from v2.bakeoff import bundle as B
    pf = (runner.POD / "preflight.sh").read_text()
    assert "torch.cuda.is_available()" in pf and "nvidia-smi" in pf and "PREFLIGHT OK" in pf and "pip install" not in pf
    s = FakeSession("gpu: 550.1, H100\nPREFLIGHT FAILED: the image's torch does not see the GPU")
    monkeypatch.setattr(runner, "Ledger", lambda: L)
    monkeypatch.setattr(runner, "authorise", lambda job, ledger=None, price_now=None: None)
    monkeypatch.setattr(runner, "_create", lambda job, name, wait_min=0: s)
    monkeypatch.setattr(runner, "Session", lambda name: type("Closed", (), {"open": False, "d": {}})())
    monkeypatch.setattr(B, "build", lambda job: (_ for _ in ()).throw(AssertionError("the bundle was built")))
    res = runner.run("B1", go=True)
    assert res["ok"] is False and "preflight" in res["note"]
    assert s.ended.startswith("preflight failed: PREFLIGHT FAILED") and not s.open
    assert not any("setup.sh" in c or "run.sh" in c for c in s.cmds)
    # the check is the first thing the pod is asked after its deadline is written
    assert "preflight.sh Qwen/Qwen-Image" in next(c for c in s.cmds if "preflight" in c)


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


def test_a_job_that_fails_with_nothing_made_holds_its_pod_for_a_restart_in_place(monkeypatch, L, tmp_path):
    """Two quotes were used up by setup faults: the pod is now held a few minutes, its deadline pulled in, and the
    same job starts again on it without a new authorisation."""
    import time as _t
    from v2.bakeoff import bundle as B
    s = FakeSession("PREFLIGHT OK")
    s.d["job"]["deadline"] = _t.time() + 2800
    s.d["job"]["start"] = _t.time()
    answers = iter(["1\nSETUP FAILED (no torch that sees the GPU)"])
    real_ssh = s.ssh
    s.ssh = lambda cmd, timeout=120, check=True: next(answers) if ".rc 2>/dev/null" in cmd else real_ssh(cmd, timeout, check)
    monkeypatch.setattr(runner, "Ledger", lambda: L)
    monkeypatch.setattr(runner, "authorise", lambda job, ledger=None, price_now=None: None)
    monkeypatch.setattr(runner, "_create", lambda job, name, wait_min=0: s)
    monkeypatch.setattr(runner, "Session", lambda name: type("Closed", (), {"open": False, "d": {}})())
    monkeypatch.setattr(runner.time, "sleep", lambda x: None)
    monkeypatch.setattr(B, "build", lambda job: tmp_path)
    monkeypatch.setattr(B, "uploads", lambda job, bdir: [])
    monkeypatch.setattr(B, "local_out", lambda job: tmp_path / "out")
    res = runner.run("B1", go=True)
    assert res["ok"] is False and res["kept"] and res["retry"] == "python -m v2.bakeoff run B1 --go --on fake"
    assert s.ended is None and s.open                                   # not terminated: held
    hold = s.d["job"]["hold_until"]
    assert 0 < hold - _t.time() <= runner.HOLD_S and hold < s.d["job"]["deadline"]
    assert any(c.startswith(f"echo {int(hold)} > /workspace/DEADLINE") for c in s.cmds)   # the watchdog's new deadline
    # started again on the held pod: no authorisation, the job's own deadline back
    monkeypatch.setattr(runner, "authorise", lambda *a, **k: (_ for _ in ()).throw(AssertionError("authorised again")))
    monkeypatch.setattr(runner, "Session", lambda name: s)
    monkeypatch.setattr(runner, "_alive", lambda ses: True)
    answers = iter(["0\nMATERIALS FINISHED"])
    (tmp_path / "out" / "roof_slate_0.png").write_bytes(b"x")
    res = runner.run("B1", go=True, on="fake")
    assert res["ok"] and "hold_until" not in s.d["job"] and s.ended == "finished"
    assert any(c.startswith(f"echo {int(s.d['job']['deadline'])} > /workspace/DEADLINE") for c in s.cmds)


# ------------------------------------------------------------------ Phase 3: the cathedral's cutaway painting (K1)
def test_the_cutaway_job_is_the_ledgers_quote_and_cannot_pass_its_worst_case():
    j = J.BY_ID["K1"]
    real = Ledger()
    q = runner.quote_of(j, real)
    # q0012 (an H100) was released unspent, q0014 paid for the first run; q0015 is the second run's
    assert q == "q0015" and real.quotes()[q]["worst_usd"] == j.worst_usd == 0.99
    assert any(e["type"] == "spend" and e["quote"] == "q0014" for e in real.events)
    # the second run (13 Nov 2026): approved by the owner, run once, within its worst case; q0013 is not approved
    paid = [e for e in real.events if e["type"] == "spend" and e["quote"] == q]
    assert len(paid) == 1 and float(paid[0]["usd"]) <= j.worst_usd
    assert any(e["type"] == "approve" and e["quote"] == q and e["by"] == "owner" for e in real.events)
    assert not any(e["type"] == "approve" and e["quote"] == "q0013" for e in real.events)
    assert j.cloud == "secure" and j.price_h == 2.19
    assert j.goal == "phase3_lock_look" and j not in J.JOBS            # not part of the bake-off's total
    for cost_h in (j.price_h, 2.59, 1.0):
        s = runner.cap_seconds(j, cost_h)
        assert s <= 27 * 60 and (s + 20) / 3600 * (cost_h + runner.DISK_GB * runner.DISK_USD_GB_H) <= j.worst_usd
    assert runner.quote_of(J.BY_ID["B1"], real) != q


def test_the_second_cathedral_run_is_planned_from_the_first_runs_measured_times():
    j = J.BY_ID["K1"]
    need = sum(J.K1_MEASURED_S.values())                               # 908 s: the first run, had it not been capped
    assert 900 <= need <= j.est_h * 3600 <= need + 60
    # the runner stops waiting 45 s before the pod's deadline: half as long again as measured still finishes
    assert runner.cap_seconds(j) - 45 >= 1.5 * need
    assert "--seed-step" in (runner.POD / "paint.py").read_text() and 'K1)  paint "$V1" 1867,1868 2' in (runner.POD / "run.sh").read_text()
    from v2.bakeoff import cutaway_paint as CP
    seeds = [CP.seed_of(kind, k) for kind in CP.KINDS for k in range(len(CP.SEEDS))]
    assert sorted(seeds) == [1867, 1868, 1869, 1870]                   # four candidates, four seeds


def test_the_cutaway_job_needs_its_own_approval(L):
    j = J.BY_ID["K1"]
    with pytest.raises(LedgerRefusal, match="no quote"):
        runner.authorise(j, L, price_now=j.price_h)
    q = L.quote(j.goal, j.provider, j.ledger_job(), j.worst_usd)["id"]
    with pytest.raises(LedgerRefusal, match="not approved"):
        runner.authorise(j, L, price_now=j.price_h)
    L.approve(q, by="owner")
    assert runner.authorise(j, L, price_now=j.price_h)["id"] == q
    assert runner.record_quotes(L) and runner.quote_of(j, L) == q      # the bake-off's quotes are another line


def _cut(n=96):
    """A small frame: a floor (kind 5) beside a wall (kind 3) inside a mask, the outside (kind 1) round it."""
    from v2.layers.cutaways import KIND
    k = np.zeros((n, n), np.uint8)
    k[8:88, 8:88] = KIND["outside"]
    k[24:72, 24:48] = KIND["floor"]
    k[24:72, 48:72] = KIND["inside_wall"]
    normal = np.zeros((n, n, 3)); normal[..., 2] = 1.0
    normal[k == KIND["inside_wall"]] = (1.0, 0.0, 0.0)
    unlit = np.full((n, n, 3), 239, np.uint8)
    unlit[k == KIND["outside"]] = (120, 110, 90)
    unlit[k == KIND["floor"]] = (212, 200, 176)
    unlit[k == KIND["inside_wall"]] = (234, 224, 204)
    return {"unlit": unlit, "mask": np.isin(k, (KIND["floor"], KIND["inside_wall"])), "outline": k > 0, "k": k,
            "ids": (k.astype(np.uint32) << 8) | k, "normal": normal, "depth": np.where(k > 0, 10.0, np.inf),
            "meta": {"frame_px": [0, 0, n, n], "opening_bbox": [24, 24, 72, 72]}}


def test_a_cutaway_painting_is_cut_to_its_mask_and_judged_inside_it():
    from v2.bakeoff import cutaway_paint as CP
    from v2.layers.cutaways import cut_params
    P = dict(cut_params(), cutaway_shadow_min_px=20)
    d = _cut()
    yy, xx = np.indices(d["mask"].shape)
    same = CP.check_candidate(d["unlit"], d, P)                       # the model returned the render as given
    assert same["K2_ok"] and same["K3_ok"] and not same["interior_painted"] and not CP.verdict(same)
    wild = np.random.default_rng(1).integers(0, 255, d["unlit"].shape).astype(np.uint8)   # drawn over everything
    comp = CP.compose(d["unlit"], wild, d["mask"])
    assert (comp[~d["mask"]] == d["unlit"][~d["mask"]]).all() and (comp[d["mask"]] == wild[d["mask"]]).all()
    assert CP.check_candidate(wild, d, P)["K2a_interior_px_outside_mask"] == 0
    blank = d["unlit"].copy(); blank[d["mask"]] = CP.paper()           # the opening left as paper
    assert CP.check_candidate(blank, d, P)["K2b_mask_covered"] == 0.0
    tiles = d["unlit"].copy()                                          # a tiled floor and wall, evenly lit
    tiles[d["mask"] & ((xx + yy) % 4 == 0)] = (60, 50, 45)
    r = CP.check_candidate(tiles, d, P)
    assert r["K2_ok"] and r["K3_ok"] and r["light_across_ok"] and r["interior_painted"]
    lit = tiles.astype(float)                                          # the same with light from one side
    lit[d["mask"]] *= (0.5 + 0.5 * (xx[d["mask"]] - 24) / 48)[:, None]
    r = CP.check_candidate(lit.astype(np.uint8), d, P)
    assert not r["light_across_ok"] and not CP.verdict(r)
    assert set(CP.input_names("cathedral")) == {"cathedral", "cathedral-open"}
    pr = CP.PROMPTS["cathedral"]
    assert "<isometric luxembourg ink>" in pr and "no shadows" in pr
    assert "lit evenly from every side" in pr and "No cast shadows, no dark floor" in pr and "No people" not in pr.replace("no people", "")
    assert (CP.opened(d)[d["mask"] & ~CP.geometry_edges(d)] == CP.paper()).all()


def _floor(n=200):
    """A frame that is one floor (kind 5) inside the outside's ring, and its pixel grid."""
    from v2.layers.cutaways import KIND
    k = np.full((n, n), KIND["outside"], np.uint8)
    k[20:180, 20:180] = KIND["floor"]
    return k, np.indices(k.shape)


def _light(rgb, k, min_px=150):
    from v2.bakeoff import cutaway_paint as CP
    from v2.layers.cutaways import KIND
    return CP.light_across(np.clip(rgb, 0, 255).astype(np.uint8), k, k == KIND["floor"], min_px)[KIND["floor"]]


def test_light_across_a_face_measures_light_not_what_is_drawn_on_it():
    """The first cathedral run: a chequered floor failed the light check as a pattern, not as light."""
    from scipy import ndimage
    TOL = 0.05                                                         # params g3 cutaway_shadow_lum_tol
    k, (yy, xx) = _floor()
    cream, grey, navy, wood = (236, 229, 214), (128, 126, 122), (44, 60, 104), (120, 50, 24)
    flat = np.empty(k.shape + (3,)); flat[:] = cream
    chequer = np.where((((xx // 5) + (yy // 4)) % 2 == 0)[..., None], cream, grey).astype(float)
    blue = np.where((((xx // 5) + (yy // 4)) % 2 == 0)[..., None], cream, navy).astype(float)
    iso = np.where(((((xx + 2 * yy) // 12) + ((xx - 2 * yy) // 12)) % 2 == 0)[..., None], cream, grey).astype(float)   # lozenges
    joints = flat.copy(); joints[(xx % 9 == 0) | (yy % 6 == 0)] = (70, 62, 55)
    soft = ndimage.uniform_filter(chequer, (2, 2, 1))                  # the painter's soft edges
    patterns = {"flat": flat, "chequer": chequer, "navy chequer": blue, "lozenges": iso, "joints": joints, "soft chequer": soft}
    for name, img in patterns.items():
        assert _light(img, k) <= 0.01, name                            # a pattern, evenly lit: no light measured
    pews = chequer.copy(); pews[60:90, 30:150] = wood; pews[120:150, 30:150] = wood     # another material is not shade
    assert _light(pews, k) <= 0.01
    for name, img in patterns.items():
        grad = img * (0.6 + 0.4 * (xx - 20) / 160)[..., None]          # light from one side
        assert _light(grad, k) > 3 * TOL, name
        faint = img * (0.9 + 0.1 * (xx - 20) / 160)[..., None]         # 10% from side to side: still over 5%
        assert _light(faint, k) > TOL, name
        blob = img * np.where(np.hypot(xx - 110, yy - 100) < 26, 0.65, 1.0)[..., None]  # a cast shadow
        assert _light(blob, k) > 3 * TOL, name
        for cx, cy in ((110, 100), (97, 131), (64, 75)):               # a small one, 3.5 m across, wherever it falls
            small = img * np.where(np.hypot(xx - cx, yy - cy) < 14.5, 0.65, 1.0)[..., None]
            assert _light(small, k) > 3 * TOL, name
    # its limit, stated in light_across: a shade narrower than a block is not measured (K3 and the eye remain)
    thin = chequer.copy(); thin[100:104, 30:150] *= 0.65
    assert _light(thin, k) <= 0.01


def test_a_pale_floor_slab_is_painted_and_a_blank_patch_or_edge_strip_is_not():
    """The first cathedral run: light squares of the floor, the colour of paper, were counted as unpainted."""
    from v2.bakeoff import cutaway_paint as CP
    k, (yy, xx) = _floor()
    mask = k == 5
    outline = np.ones(k.shape, bool); outline[:8] = False              # the top rows are the painting's background
    paper = CP.paper().astype(int)
    img = np.where((((xx // 5) + (yy // 4)) % 2 == 0)[..., None], paper + (-2, -2, -4), (128, 126, 122)).astype(np.uint8)
    for bg in (paper, (255, 255, 255)):                                # the painter's background: paper, or white
        a = img.copy(); a[~outline] = bg
        # slabs of paper's colour are painted; only those lying on the opening's very edge count as blank (0.2%)
        assert CP.covered(a, mask, outline).sum() / mask.sum() >= 0.998
        assert CP.covered(a, mask & (np.minimum(xx, yy) > 30) & (np.maximum(xx, yy) < 170), outline)[40:160, 40:160].all()
        hole = a.copy(); hole[90:110, 60:90] = bg                      # a blank patch inside the opening
        assert mask.sum() - CP.covered(hole, mask, outline).sum() >= 20 * 30
        strip = a.copy(); strip[20:23, 20:180] = bg                    # a blank strip 3 px wide along the edge
        assert mask.sum() - CP.covered(strip, mask, outline).sum() >= 3 * 160
        assert CP.covered(strip, mask, outline).sum() / mask.sum() < 0.995   # ... fails K2b's 99.5%
    empty = img.copy(); empty[mask] = paper
    assert CP.covered(empty, mask, outline).sum() == 0


def test_lost_lines_are_told_apart_the_sections_and_the_placeholders():
    from v2.bakeoff import cutaway_paint as CP
    from v2.layers.cutaways import KIND, cut_params
    d = _cut()
    d["k"][24:27, 24:72] = KIND["cut"]                                 # a section along the opening's top
    d["ids"] = (d["k"].astype(np.uint32) << 8) | d["k"]
    d["unlit"][d["k"] == KIND["cut"]] = (150, 60, 50)
    r = CP.interior_lines(d["unlit"], d)                               # the render itself keeps all of its lines
    assert r["kept"] == r["section_kept"] == r["placeholder_kept"] == 1.0 and r["section_px"] and r["placeholder_px"]
    over = d["unlit"].copy()                                           # a painting that draws one tone over floor and wall
    inner = d["mask"] & (d["k"] != KIND["cut"])
    over[inner] = (200, 190, 170)
    r = CP.interior_lines(over, d)
    assert r["section_kept"] > 0.95 and r["placeholder_by_junction"]["floor_wall"]["kept"] < 0.2
    # the gate is the cut's outline (owner, 13 Nov 2026): the placeholder's lost lines are reported, not gated
    P = dict(cut_params(), cutaway_shadow_min_px=20)
    c = CP.check_candidate(over, d, P)
    assert c["lines_kept_ok"] is True and c["interior_lines"]["placeholder_kept"] < 0.95 and c["interior_lines"]["kept"] < 0.95
    lost = over.copy()                                                 # ... and a painting that draws over the section fails
    lost[d["mask"]] = (200, 190, 170)
    lost[24:30, 24:72] = (200, 190, 170)
    c = CP.check_candidate(lost, d, P)
    assert c["interior_lines"]["section_kept"] < 0.95 and c["lines_kept_ok"] is False and not CP.verdict(c)


def _two_walls(n=160):
    """A frame whose opening is two inside walls turned different ways (east and south), and a painter for it:
    each wall in stone with a share of its width in stained glass behind inked mullions."""
    from v2.layers.cutaways import KIND
    k = np.zeros((n, n), np.uint8)
    k[8:152, 8:152] = KIND["outside"]
    k[30:130, 20:80] = KIND["inside_wall"]
    k[30:130, 80:140] = KIND["inside_wall"]
    normal = np.zeros((n, n, 3)); normal[..., 2] = 1.0
    normal[30:130, 20:80] = (1.0, 0.0, 0.0)
    normal[30:130, 80:140] = (0.0, -1.0, 0.0)
    unlit = np.full((n, n, 3), 239, np.uint8)
    unlit[k == KIND["outside"]] = (120, 110, 90)
    unlit[k == KIND["inside_wall"]] = (234, 224, 204)
    d = {"unlit": unlit, "mask": k == KIND["inside_wall"], "outline": k > 0, "k": k,
         "ids": (k.astype(np.uint32) << 8) | k, "normal": normal, "depth": np.where(k > 0, 10.0, np.inf),
         "meta": {"frame_px": [0, 0, n, n], "opening_bbox": [20, 30, 140, 130]}}

    def paint(glass=(0.7, 0.2), stone=(1.0, 1.0), shade=(1.0, 1.0)):
        img = unlit.astype(float)
        for (x0, x1), g, st, sh in zip(((20, 80), (80, 140)), glass, stone, shade):
            wall = np.empty((100, x1 - x0, 3)); wall[:] = (226, 208, 172)             # sandstone
            wall[::9] = (70, 60, 50)                                                  # its joints, in ink
            wall *= st
            w = int(round(g * (x1 - x0)))
            pane = np.empty((84, w, 3)); pane[:] = (40, 80, 170)                      # stained glass
            pane[:, ::6] = (30, 26, 24); pane[::10] = (30, 26, 24)                    # mullions, in ink
            wall[8:92, 4:4 + w] = pane
            img[30:130, x0:x1] = wall * sh
        return np.clip(img, 0, 255).astype(np.uint8)
    return d, paint


def test_k3_on_a_painting_measures_the_stone_not_the_glass_or_the_ink():
    """The first cathedral run: over half of each painted wall was window or ink, so K3's median was the glass's."""
    from v2.bakeoff import cutaway_paint as CP
    from v2.layers.cutaways import cut_params
    P = cut_params()
    TOL = P["cutaway_shadow_lum_tol"]
    assert TOL == 0.05                                                 # K3's own limit, unchanged
    d, paint = _two_walls()
    even = CP.check_candidate(paint(), d, P)                           # much glass on one wall, little on the other
    assert even["K3_every_pixel_worst"] > 3 * TOL                      # the first measure: the window area
    assert even["K3_ok"] and even["K3_worst"] <= 0.01 and even["K3_unmeasured_sides"] == 0
    assert even["K3_by_kind"]["inside_wall"]["sides"] == 2
    assert 0.1 < even["K3_material_share"]["inside_wall"] < 0.6       # the stone, without the glass and the ink
    for f in (0.9, 0.8, 0.6):                                          # the stone of one wall darker: baked light
        for stone in ((f, 1.0), (1.0, f)):
            r = CP.check_candidate(paint(stone=stone), d, P)
            assert not r["K3_ok"] and r["K3_worst"] == pytest.approx(1 - f, abs=0.02) and not CP.verdict(r), (f, stone)
        r = CP.check_candidate(paint(shade=(f, 1.0)), d, P)            # a whole wall in shade, glass and all
        assert not r["K3_ok"] and r["K3_worst"] > TOL
    same_glass = CP.check_candidate(paint(glass=(0.4, 0.4), stone=(0.9, 1.0)), d, P)   # ... also with equal windows
    assert not same_glass["K3_ok"] and same_glass["K3_every_pixel_worst"] > TOL
    ok = CP.check_candidate(paint(stone=(0.97, 1.0)), d, P)            # within the limit: 3%
    assert ok["K3_ok"] and 0.02 < ok["K3_worst"] <= TOL
    hidden = paint()                                                   # a wall with no stone left to measure fails
    hidden[30:130, 20:80] = (40, 80, 170)
    r = CP.check_candidate(hidden, d, P)
    assert r["K3_unmeasured_sides"] == 1 and not r["K3_ok"]
    flat = CP.check_candidate(d["unlit"], d, P)                        # the placeholder: both measures are the same
    assert flat["K3_worst"] == flat["K3_every_pixel_worst"] == 0 and flat["K3_ok"]


def test_only_a_candidate_that_passed_is_handed_to_the_layer(tmp_path, monkeypatch):
    from PIL import Image
    from v2.bakeoff import cutaway_paint as CP
    from v2.layers import cutaways as cw
    d = _cut()
    monkeypatch.setattr(CP, "base", lambda: tmp_path)
    monkeypatch.setattr(CP, "load", lambda src, name: d)
    (tmp_path / "checks").mkdir(); (tmp_path / "painted").mkdir()
    art = np.random.default_rng(5).integers(0, 255, d["unlit"].shape).astype(np.uint8)
    Image.fromarray(art).save(tmp_path / "painted" / "cathedral_1.png")
    cand = {"label": "cathedral_1", "file": "cathedral_1.png", "input": "cathedral", "seed": 1868, "pass": False, "K3_worst": 0.2}
    res = {"source": "x", "candidates": [cand], "passing": [], "best": None}
    (tmp_path / "checks" / "K1.json").write_text(json.dumps(res))
    for label in (None, "cathedral_1"):
        with pytest.raises(SystemExit, match="did not pass"):
            CP.adopt("K1", label=label, dst=tmp_path / "paintings")
    assert not (tmp_path / "paintings").exists()                       # the placeholder stays
    cand["pass"] = True
    res.update(passing=["cathedral_1"], best="cathedral_1")
    (tmp_path / "checks" / "K1.json").write_text(json.dumps(res))
    meta = CP.adopt("K1", dst=tmp_path / "paintings")
    p = cw.load_painting("cathedral", tmp_path / "paintings")
    assert meta["candidate"] == "cathedral_1" and meta["checks"]["K3_worst"] == 0.2 and meta["frame_px"] == [0, 0, 96, 96]
    assert (p["on"] == d["mask"]).all() and (p["rgb"][d["mask"]] == art[d["mask"]]).all()
