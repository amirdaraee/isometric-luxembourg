"""The bake-off (PLAN_V2 section 7): methods B and C up to the point of spending, and the viewer's registry.

    python -m v2.bakeoff status                 every paid job, its quote in the ledger and whether it may run
    python -m v2.bakeoff quote [--record]       the quote table; --record writes each job's quote to the ledger once
                                                (quote events only: approving is the owner's)
    python -m v2.bakeoff inputs c [--limit N]   C's unlit inputs: every 1024 px window with buildings (unlit render,
                                                layout, mask, ids and normals), and the 80 training crops' list
    python -m v2.bakeoff inputs b               B's landmark list and each landmark's unlit crop; the material list
    python -m v2.bakeoff smoke c                local $0 smoke test: an identity "painting" through compose and the
                                                checks on one window (no model runs; see PHASE2_QUOTE.md)
    python -m v2.bakeoff run <job> [--go]       ledger authorise + live price + pod with its watchdog; without --go
                                                only prints what it would start (the default)
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
        print(f"{j.id:4} {j.title[:60]:60} quote {q or '-':6} {'APPROVED' if q in ap else 'not approved':12} "
              f"est ${j.est_usd:5.2f} cap ${j.worst_usd:5.2f}")
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


def cmd_inputs(a):
    from v2.bakeoff import inputs as I
    from v2.bakeoff.dataset import pick_crops
    R, g = _renderer(a.area, "plain")
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
    from v2.bakeoff.runner import launch
    print(json.dumps(launch(a.job, f"bash pod/run.sh {a.job}", dry_run=not a.go), indent=1))


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
    idx[a.method] = {"release": str(folder), "art": a.method}
    p.write_text(json.dumps(idx, indent=1))
    print(f"registered {a.method}: {folder}  (current art method: {art_method()})")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m v2.bakeoff", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--area", default="test")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    q = sub.add_parser("quote"); q.add_argument("--record", action="store_true")
    i = sub.add_parser("inputs"); i.add_argument("method", choices=["b", "c"]); i.add_argument("--limit", type=int, default=0)
    i.add_argument("--crops", action="store_true", help="b: also each landmark's unlit crop")
    i.add_argument("--release", help="c: the built release whose layers 1-4 are used (default: this checkout's)")
    s = sub.add_parser("smoke"); s.add_argument("method", choices=["c"])
    r = sub.add_parser("run"); r.add_argument("job"); r.add_argument("--go", action="store_true",
                                                                       help="really start it (needs the owner's approval in the ledger)")
    g = sub.add_parser("register"); g.add_argument("method", choices=["a", "b", "c"]); g.add_argument("--folder")
    a = ap.parse_args(argv)
    return {"status": cmd_status, "quote": cmd_quote, "inputs": cmd_inputs, "smoke": cmd_smoke, "run": cmd_run,
            "register": cmd_register}[a.cmd](a) or 0


if __name__ == "__main__":
    sys.exit(main())
