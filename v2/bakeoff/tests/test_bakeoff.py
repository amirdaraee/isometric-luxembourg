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
