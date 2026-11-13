"""The bake-off (PLAN_V2 section 7): methods B and C up to the point of spending, and the viewer's registry.

    python -m v2.bakeoff status                 every paid job, its quote in the ledger and whether it may run
    python -m v2.bakeoff quote [--record] [--again JOB]
                                                the quote table; --record writes each job's quote to the ledger once
                                                (quote events only: approving is the owner's); --again writes a new
                                                quote for a job whose last one is spent or released
    python -m v2.bakeoff inputs c [--limit N]   C's unlit inputs: every 1024 px window with buildings (unlit render,
                                                layout, mask, ids and normals), and the 80 training crops' list
    python -m v2.bakeoff inputs b               B's landmark list and each landmark's unlit crop; the material list
    python -m v2.bakeoff inputs facades         C4: ten buildings' camera-facing walls drawn front-on
    python -m v2.bakeoff inputs cutaway         K1 (Phase 3): the cathedral's cut render as the painter's two control
                                                images, as built and with its opening cleared (cutaway_paint.py)
    python -m v2.bakeoff trial [--no-build]     C4's result: on the ten trial buildings, method A against the facades
                                                painted front-on and projected onto their walls (line score, flat
                                                light, cars), a preview sheet, and the small C4 build registered as
                                                its own column of the bake-off viewer
    python -m v2.bakeoff pilot-gates            C (stopped at its pilot): the line score of every method inside the
                                                pilot's painted windows, and the used paintings' checks
    python -m v2.bakeoff previews [--url U]     the fixed views of every registered method from the running bake-off
                                                viewer, and the comparison sheet (v2/docs/img)
    python -m v2.bakeoff smoke c                local $0 smoke test: an identity "painting" through compose and the
                                                checks on one window (no model runs; see PHASE2_QUOTE.md)
    python -m v2.bakeoff run <job> [--go] [--keep] [--on SESSION]
                                                the whole job: ledger authorise + live price, the pod with its
                                                watchdog, the bundle up, the results down, the spend recorded, the
                                                pod terminated. Without --go it only prints what it would start.
                                                --keep leaves the pod up for the next job; --on runs on that pod
    python -m v2.bakeoff check <job>            the checks of a job's results (flat light, no cars, line score; a
                                                pilot's measured speed against the full job's cap); a failure stops
                                                the jobs after it. K1: the cutaway candidates through K1-K4
    python -m v2.bakeoff adopt K1 [--candidate L]   the candidate the owner accepted by eye (K7, recorded in
                                                v2/data/structures/cutaway_acceptances.json) to the cutaway layer;
                                                refused if it fails a gate or has no such record ($0, cutaway_paint.py)
    python -m v2.bakeoff end <session>|--all    terminate a session's pod and record its spend (the owner's pause)
    python -m v2.bakeoff pods                   read-only: none of the pods created here is left on RunPod
    python -m v2.bakeoff reconcile [--record]   the ledger against RunPod's billing (read-only API)
    python -m v2.bakeoff pick b                 B: check every material and portrait, pick one each (picked.json)
    python -m v2.bakeoff painted <method>       mark a method's paintings complete, so its layers can be built
    python -m v2.bakeoff register <method>      the current release (built with V2_ART=<method>) into the bake-off
                                                viewer (python -m v2.view test --bakeoff)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from v2.config import v2_data


def _scene(area):
    from v2.build.stages import graph
    from v2.layers.common import Scene
    g = graph()
    return Scene(g.folder("scene", area)), g


def _renderer(area, art):
    from v2.layers.render import Renderer
    sc, g = _scene(area)
    return Renderer(sc, g.folder("fetch_osm_ground", area) / "ground.json",
                    g.folder("fetch_osm_transport", area) / "transport.json", art=art), g


def cmd_status(a):
    from v2.bakeoff.jobs import JOBS, totals
    from v2.bakeoff.runner import quote_of
    from v2.ledger.ledger import Ledger
    L = Ledger()
    ap = L.approved()
    for j in JOBS:
        q = quote_of(j, L)
        sp = [e["usd"] for e in L.events if e["type"] == "spend" and e["quote"] == q]
        from v2.bakeoff.runner import stopped
        qw = L.quotes()[q]["worst_usd"] if q else j.worst_usd
        state = "RELEASED" if q in L.released() else "APPROVED" if q in ap else "not approved"
        print(f"{j.id:4} {j.title[:60]:60} quote {q or '-':6} {state:12} "
              f"est ${j.est_usd:5.2f} cap ${qw:5.2f}  " + (f"spent ${sp[0]:.2f}" if sp else "not run")
              + ("  CHECKS FAILED: branch stopped" if stopped(j.id) else "")
              + ("  STOPPED BY THE OWNER" if j.cancelled else ""))
    used = [e for e in L.events if e["type"] == "spend" and e["goal"] == "phase2_bakeoff"
            and e["quote"] not in {quote_of(j, L) for j in JOBS}]
    for e in used:
        print(f"     earlier run: {e['job'][:50]:50} quote {e['quote']} spent ${e['usd']:.2f}")
    est, worst = totals()
    print(f"total: est ${est}, worst case ${worst}; goal phase2_bakeoff: {L.status()['goals']['phase2_bakeoff']}")


def cmd_quote(a):
    from v2.bakeoff.jobs import JOBS, batch_ok, totals
    from v2.bakeoff.runner import record_quotes
    for j in JOBS:
        print(f"{j.id:4} {j.provider} {j.gpu} ${j.price_h}/h est {j.est_h} h ${j.est_usd} cap {j.cap_h} h ${j.worst_usd}  {j.work}")
    print("totals (est, worst):", totals(), " batches over $5 without a pilot:", batch_ok() or "none")
    if a.record:
        for e in record_quotes():
            print("recorded", e["id"], e["job"], e["worst_usd"])
    if a.again:
        from v2.bakeoff.jobs import BY_ID
        from v2.bakeoff.runner import live_price, requote
        from v2.ledger.ledger import LedgerRefusal
        j = BY_ID[a.again]
        try:
            p = live_price(j)
            if p > j.price_h + 1e-9:
                raise LedgerRefusal(f"{j.id}: {j.gpu} costs ${p}/h now, jobs.py has ${j.price_h}/h: update the price first")
            e = requote(j)
        except LedgerRefusal as ex:
            print("REFUSED:", ex, file=sys.stderr)
            return 2
        print("recorded", e["id"], e["job"], e["worst_usd"], f"(live price ${p}/h)")


def cmd_inputs(a):
    if a.method == "cutaway":
        from v2.bakeoff import cutaway_paint as CP
        print(json.dumps(CP.make_inputs(), indent=1))
        return 0
    from v2.bakeoff import inputs as I
    from v2.bakeoff.dataset import pick_crops
    R, g = _renderer(a.area, "plain")
    if a.method == "facades":
        from v2.bakeoff import facade_trial as F
        meta = F.make_inputs(R.scene, v2_data() / a.area / "bakeoff" / "c" / "facade_inputs")
        print(f"{len(meta['buildings'])} buildings, {len(meta['facades'])} camera-facing facades with windows (C4)")
        return 0
    out = v2_data() / a.area / "bakeoff" / a.method
    if a.method == "c":
        rel = Path(a.release) if a.release else g.folder("release", a.area)
        idx = json.loads((rel / "index.json").read_text())
        wins = I.windows(R.scene, list(idx["layers"]["buildings"]["tiles"]["0"]))
        crops = pick_crops(wins, 80)
        (out).mkdir(parents=True, exist_ok=True)
        (out / "windows.json").write_text(json.dumps({"windows": wins, "train_crops": crops, "pilot_crops": crops[:8],
                                                      "win_px": I.WIN, "stride_px": I.STRIDE, "release": str(rel)}, indent=0))
        print(f"{len(wins)} windows to paint (C3), {len(crops)} training crops (C1), 8 in the pilot (C1p)")
        todo = wins[: a.limit] if a.limit else wins
        for x0, y0 in todo:
            name = f"{x0}_{y0}"
            if (out / "inputs" / f"{name}.unlit.png").exists():
                continue
            rgb, layout, mask, extra = I.render_window(R, x0, y0, rel=rel)
            I.write_window(out / "inputs", name, rgb, layout, mask, {"x0": x0, "y0": y0, "px": I.WIN, "m_per_px": 0.125},
                           extra)
            print("wrote", name, flush=True)
    else:
        from v2.bakeoff.prompts import MATERIALS
        lm = I.landmarks(R.scene)
        out.mkdir(parents=True, exist_ok=True)
        (out / "landmarks.json").write_text(json.dumps(lm, indent=1, ensure_ascii=False))
        (out / "materials.json").write_text(json.dumps({k: {"what": v[0], "colour": v[1], "size_m": v[2]} for k, v in MATERIALS.items()}, indent=1))
        print(f"{len(lm)} landmarks ({sum(1 for x in lm if x['building'])} on a building), {len(MATERIALS)} materials")
        if a.crops:
            from v2.layers.common import project
            for x in lm:
                if not x["building"]:
                    continue
                b = R.scene.buildings[x["building_index"]]
                px, py, _ = project(x["e"], x["n"], b.get("eave_z", b.get("ground_z", 300)))
                x0, y0 = int(px) - 512, int(py) - 640
                rgb, layout, mask, extra = I.render_window(R, x0, y0)
                I.write_window(out / "landmark_inputs", x["building"], rgb, layout, mask, {**x, "x0": x0, "y0": y0}, extra)
                print("wrote", x["name"], flush=True)


def cmd_smoke(a):
    """C end to end with an identity painter: the unlit input stands in for a painting; compose must cut it to the
    mesh exactly, and flat_light must find no shadow in it (the unlit render has none)."""
    import numpy as np
    from PIL import Image
    from v2.bakeoff import inputs as I
    from v2.bakeoff.compose import painted_rgb
    from v2.bakeoff.dataset import flat_light
    R, g = _renderer(a.area, "plain")
    wj = json.loads((v2_data() / a.area / "bakeoff" / "c" / "windows.json").read_text())
    w = wj["windows"]
    x0, y0 = w[len(w) // 2]
    rgb, layout, mask, extra = I.render_window(R, x0, y0, size=1024, rel=Path(wj["release"]) if wj.get("release") else None)
    tmp = v2_data() / a.area / "bakeoff" / "c" / "smoke"
    (tmp / "painted").mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb).save(tmp / "painted" / f"{x0}_{y0}.png")
    got, has = painted_rgb(tmp / "painted", x0 + 256, y0 + 256, 512, 512)
    same = float((np.abs(got[has] - rgb[256:768, 256:768][has]) < 1).mean())
    worst, bad = flat_light(rgb, extra["ids"], extra["normal"])
    res = {"window": [x0, y0], "identity_roundtrip_share": round(same, 4), "flat_light_worst": worst,
           "flat_light_failures": len(bad), "mask_px": int(mask.sum())}
    (tmp / "smoke.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res))
    return 0 if same > 0.999 and not bad else 1


def cmd_run(a):
    from v2.bakeoff import runner
    from v2.ledger.ledger import LedgerRefusal
    try:
        res = runner.run(a.job, go=a.go, keep=a.keep, on=a.on, session=a.session, wait_min=a.wait)
    except LedgerRefusal as ex:
        print("REFUSED:", ex, file=sys.stderr)
        return 2
    if res.get("dry_run"):
        res["pod"]["env"] = [e if e["key"] != "PUBLIC_KEY" else {"key": "PUBLIC_KEY", "value": "(this laptop's public key)"} for e in res["pod"]["env"]]
        res["pod"]["dockerArgs"] = res["pod"]["dockerArgs"][:60] + "... (pod/watchdog.sh)"
    print(json.dumps(res, indent=1))
    return 0 if res.get("dry_run") or res.get("ok") else 1


def cmd_end(a):
    from v2.bakeoff import runner
    if a.all:
        runner.end_all(a.note)
    else:
        runner.end(a.session, a.note)
    print(json.dumps(runner.verify_none_left(), indent=1))


def cmd_pods(a):
    from v2.bakeoff import runner
    v = runner.verify_none_left()
    print(json.dumps(v, indent=1))
    return 1 if v["still_listed"] else 0


def cmd_reconcile(a):
    from v2.bakeoff import billing
    return billing.reconcile(record=a.record)


def cmd_adopt(a):
    from v2.bakeoff import cutaway_paint as CP
    print(json.dumps(CP.adopt(a.job, label=a.candidate), indent=1))
    print("now: python -m v2.build test check_cutaways check_cutaways_view   (the gates on the painted tiles)")
    return 0


def cmd_check(a):
    if a.job == "K1":
        from v2.bakeoff import cutaway_paint as CP
        res = CP.check(a.job, run=a.run or "")
        for c in res["candidates"]:
            print(json.dumps(c))
        print(json.dumps({k: res[k] for k in ("passing", "accepted", "K4_inputs_ok", "K1a_of_the_render_as_built", "timing")}))
        return 0 if res["candidates"] else 1
    from v2.bakeoff import results
    return results.check(a.job)


def cmd_pick(a):
    from v2.bakeoff import results
    return results.pick_b()


def cmd_trial(a):
    """C4's result (facade_trial.evaluate), written to v2/docs/results/bakeoff_c4.json and v2/docs/img, and the
    small C4 build (facade_trial.build_view) registered as "c4" for the bake-off viewer."""
    from v2.bakeoff import facade_trial as F
    from v2.bakeoff import previews as PV
    from v2.config import V2
    Ra, g = _renderer(a.area, "a")
    base = v2_data() / a.area / "bakeoff"
    c = base / "c"
    res = F.evaluate(Ra, c, c / "checks")
    if not res["painted"]:
        print("C4: no painted facade yet (python -m v2.bakeoff run C4 --go, after the owner's approval)")
        return 1
    A, best = res["scores"]["A"], res["scores"][f"C4 seed {res['best_seed']}"]
    res["answer"] = {
        "straight_lines_survived": bool(best["lines_pass"]),
        "window_rows": {"c4": best["windows"]["share"], "a": A["windows"]["share"]},
        "building_edges": {"c4": best["edges"]["share"], "a": A["edges"]["share"]},
        "no_baked_shadow": bool(best["flat_pass"]), "flat_light_worst": {"c4": best["flat_light"]["worst"], "a": A["flat_light"]["worst"]},
        "flat_light_worst_between_painted_walls": best["flat_light_painted_walls"]["worst"],
        "paintings_with_light_across_them": res.get("light_within_paintings", {}).get("over_5_percent"),
        "no_cars": res.get("cars", {}).get("detections") == 0}
    if not a.no_build:
        rels = json.loads((base / "releases.json").read_text())
        out = F.build_view(Ra, Path(rels["a"]["release"]), c, base / "c4" / "release", seed_k=res["best_seed"])
        res["build"] = out
        ok = res["answer"]["straight_lines_survived"] and res["answer"]["no_baked_shadow"]
        rels["c4"] = {"release": out["folder"], "art": "c4",
                      "note": (f"Facade trial, {'passing' if ok else 'failing'}: {out['facades']} facades of {len(res['buildings'])} "
                               f"buildings painted front-on and put on their walls (views: C4 facade trial). Window rows "
                               f"{best['windows']['share']:.1%}, edges {best['edges']['share']:.1%}, flat light worst "
                               f"{best['flat_light']['worst']:.1%}. Everywhere else this column is method A.")}
        (base / "releases.json").write_text(json.dumps(rels, indent=1))
    (V2 / "docs" / "results" / "bakeoff_c4.json").write_text(json.dumps(res, indent=1))
    if (c / "checks" / "c4_trial.png").exists():
        PV.jpeg(c / "checks" / "c4_trial.png", PV.IMG / "test_c4_trial_buildings.jpg", max_px=2400)
    print(json.dumps({k: v for k, v in res.items() if k != "buildings"}, indent=1))
    return 0


def cmd_previews(a):
    """The fixed views of every registered method (v2/docs/img/test_<method>_<view>.jpg) and the sheets: A beside B
    at the brief's views (test_bakeoff_compare.jpg), A beside the C4 trial at its buildings (test_c4_trial.jpg)."""
    import shutil
    from v2.bakeoff import previews as PV
    res = PV.shoot(a.url)
    notes = {m: v.get("note", "").split(":")[0] for m, v in json.loads((v2_data() / a.area / "bakeoff" / "releases.json").read_text()).items()}
    main = {**res, "methods": [m for m in res["methods"] if m in ("a", "b")],
            "made": {k: v for k, v in res["made"].items() if k[1] in PV.BRIEF}}
    dst = PV.sheet(main, PV.IMG / "test_bakeoff_compare.jpg", notes=notes)
    print(dst.name, dst.stat().st_size // 1024, "KB")
    if "c4" in res["methods"]:
        trial = {**res, "methods": ["a", "c4"], "made": {k: v for k, v in res["made"].items() if k[1].startswith("c4-")}}
        dst = PV.sheet(trial, PV.IMG / "test_c4_trial.jpg", notes={"c4": notes.get("c4", "")})
        print(dst.name, dst.stat().st_size // 1024, "KB")
    if a.before:
        dst = PV.before_after(Path(a.before), res, PV.IMG / "test_lighting_before_after.jpg")
        print(dst.name, dst.stat().st_size // 1024, "KB")
    shutil.rmtree(res["tmp"])
    return 0


def cmd_painted(a):
    from v2.bakeoff import results
    return results.mark_painted(a.method)


def cmd_register(a):
    from v2.config.art import art_method
    rel_dir = v2_data() / a.area / "release"
    cur = json.loads((rel_dir / "current.json").read_text())
    folder = rel_dir / (a.folder or cur["folder"])
    m = json.loads((folder / "manifest.json").read_text())
    built = m["params"].get("art") if isinstance(m.get("params"), dict) else None
    dep_art = json.loads((Path(m["deps"]["layer_buildings"]["folder"]) / "manifest.json").read_text())["params"].get("art")
    if (built or dep_art) != a.method:
        raise SystemExit(f"release {folder.name} was built with art {built or dep_art!r}, not {a.method!r}: "
                         f"V2_ART={a.method} python -m v2.build {a.area} release")
    p = v2_data() / a.area / "bakeoff" / "releases.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    idx = json.loads(p.read_text()) if p.exists() else {}
    idx[a.method] = {"release": str(folder), "art": a.method, **({"note": a.note} if a.note else {})}
    p.write_text(json.dumps(idx, indent=1))
    print(f"registered {a.method}: {folder}  (current art method: {art_method()})")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m v2.bakeoff", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--area", default="test")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    q = sub.add_parser("quote"); q.add_argument("--record", action="store_true"); q.add_argument("--again", metavar="JOB")
    i = sub.add_parser("inputs"); i.add_argument("method", choices=["b", "c", "facades", "cutaway"]); i.add_argument("--limit", type=int, default=0)
    i.add_argument("--crops", action="store_true", help="b: also each landmark's unlit crop")
    i.add_argument("--release", help="c: the built release whose layers 1-4 are used (default: this checkout's)")
    s = sub.add_parser("smoke"); s.add_argument("method", choices=["c"])
    r = sub.add_parser("run"); r.add_argument("job"); r.add_argument("--go", action="store_true",
                                                                       help="really start it (needs the owner's approval in the ledger)")
    r.add_argument("--keep", action="store_true", help="leave the pod up for the next job of the session")
    r.add_argument("--on", help="run on this open session's pod (the job before it is closed first)")
    r.add_argument("--session", help="name of a new session (default: the job's id)")
    r.add_argument("--wait", type=float, default=0, help="minutes to keep trying when RunPod has no free machine")
    e = sub.add_parser("end"); e.add_argument("session", nargs="?"); e.add_argument("--all", action="store_true")
    e.add_argument("--note", default="ended by hand")
    sub.add_parser("pods")
    rc = sub.add_parser("reconcile"); rc.add_argument("--record", action="store_true")
    c = sub.add_parser("check"); c.add_argument("job"); c.add_argument("--run", help="K1: run1 = the first run's paintings again")
    ad = sub.add_parser("adopt"); ad.add_argument("job", choices=["K1"]); ad.add_argument("--candidate")
    pk = sub.add_parser("pick"); pk.add_argument("method", choices=["b"])
    pt = sub.add_parser("painted"); pt.add_argument("method", choices=["b", "c"])
    tr = sub.add_parser("trial"); tr.add_argument("--no-build", action="store_true", help="measure only, no C4 build")
    sub.add_parser("pilot-gates")
    pv = sub.add_parser("previews"); pv.add_argument("--url", default="http://localhost:5175/")
    pv.add_argument("--before", help="a folder with the earlier test_a_grund_golden_hour.jpg and test_a_grund_night.jpg: "
                                     "also writes the lighting before/after sheet")
    g = sub.add_parser("register"); g.add_argument("method", choices=["a", "b", "c"]); g.add_argument("--folder")
    g.add_argument("--note", help="shown over the method's column in the bake-off viewer (what its checks found)")
    a = ap.parse_args(argv)
    return {"status": cmd_status, "quote": cmd_quote, "inputs": cmd_inputs, "smoke": cmd_smoke, "run": cmd_run,
            "register": cmd_register, "end": cmd_end, "pods": cmd_pods, "reconcile": cmd_reconcile, "check": cmd_check, "adopt": cmd_adopt,
            "pick": cmd_pick, "painted": cmd_painted, "trial": cmd_trial, "previews": cmd_previews,
            "pilot-gates": lambda a: __import__("v2.bakeoff.results", fromlist=["x"]).pilot_gates()}[a.cmd](a) or 0


if __name__ == "__main__":
    sys.exit(main())
