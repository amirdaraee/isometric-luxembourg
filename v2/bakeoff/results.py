"""Checking what the paid jobs made, and turning it into layers (all local, $0).

    check(job)        C1p, C1: every painting through flat light, the detector and the line score (paintcheck.py);
                      C2p: the step-200 samples through flat light, and the measured seconds per step.
                      A pilot also projects the full job's time from its measured speed. A failed check writes
                      <data>/v2/test/bakeoff/stopped/<job>.json, and the runner then refuses the jobs after it.
    pick_b()          B: every material through its checks, one picked per material; every portrait through the
                      painting checks, the better passing candidate picked; writes b/picked.json and b/painted.json
    mark_painted(m)   C: writes c/painted.json once every window is painted

The rules were fixed before any job ran (v2/docs/PHASE2_QUOTE.md, dataset.py); no threshold is changed here.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import numpy as np
from PIL import Image

from v2.bakeoff import bundle as B
from v2.bakeoff import paintcheck as PC
from v2.bakeoff.jobs import BY_ID
from v2.bakeoff.runner import cap_seconds, stop_file

MIN_PAIRS = 60


def _scene():
    from v2.build.stages import graph
    return graph().folder("scene", B.AREA)


def _stop(job, reason, detail):
    f = stop_file(job)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"job": job, "reason": reason, "detail": detail, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}, indent=1))
    print(f"STOP {job}: {reason}")
    return 1


def _table(res):
    for r in res:
        print(f"  {r['file']:28} flat worst {r['flat_worst']:.3f} ({r['flat_failing_buildings']:3d} buildings over 5%)  "
              f"edges {r['line_edges']}  windows {r['line_windows']}  vehicles {r['vehicles']}  {'KEEP' if r['keep'] else 'drop'}")


def check(job: str) -> int:
    c = B.base() / "c"
    out = c / "checks"
    out.mkdir(parents=True, exist_ok=True)
    if job in ("C1p", "C1"):
        wj = json.loads((c / "windows.json").read_text())
        pilot = [f"{x}_{y}" for x, y in wj["pilot_crops"]]
        names = pilot if job == "C1p" else [f"{x}_{y}" for x, y in wj["train_crops"]]
        files = [(n, f"{n}_{k}.png") for n in names for k in (0, 1) if (c / "targets" / f"{n}_{k}.png").exists()]
        if not files:
            return _stop(job, "no paintings came back", {})
        res = PC.check_set(_scene(), c / "inputs", c / "targets", files, out / job)
        _table(res)
        kept = [r for r in res if r["keep"]]
        timing = json.loads((c / "targets" / "timing.json").read_text()) if (c / "targets" / "timing.json").exists() else {}
        summ = {"job": job, "paintings": len(res), "kept": len(kept),
                "fail_flat": sum(not r["flat_ok"] for r in res), "fail_lines": sum(not r["lines_ok"] for r in res),
                "fail_cars": sum(not r["cars_ok"] for r in res), "timing": timing}
        # For the record (the verdict above is the rule's): the same measure on each window's unlit input, the
        # scores pooled over the set, and how many paintings would pass under the kindest fair reading of the line
        # rule (window rows at 95%, building edges no worse than the code render's own score in that window: in some
        # windows the code render itself is under 95% on edges).
        base, pool = {}, {}
        for n in sorted({n for n, _ in files}):
            x0, y0 = (int(v) for v in n.split("_"))
            g = PC.geom(c / "inputs", n)
            ls = PC.line_score(_scene(), x0, y0, np.asarray(Image.open(c / "inputs" / f"{n}.unlit.png").convert("RGB")), g)
            base[n] = {k: (round(v[1] / v[0], 4) if v[0] else None) for k, v in ls.items()}
            for k, v in ls.items():
                t = pool.setdefault(("input", k), [0, 0]); t[0] += v[0]; t[1] += v[1]
        for r in res:
            for k in ("edges", "windows"):
                sh = r[f"line_{k}"]
                if sh is not None:
                    t = pool.setdefault(("painting", k), [0, 0]); t[0] += r["line_seen"][k]; t[1] += sh * r["line_seen"][k]
            b = base[r["window"]]
            r["input_edges"], r["input_windows"] = b["edges"], b["windows"]
            r["keep_kindest_reading"] = bool(
                r["flat_ok"] and r["cars_ok"] and (r["line_windows"] is None or r["line_windows"] >= 0.95)
                and (r["line_edges"] is None or r["line_edges"] >= min(0.95, b["edges"] or 0)))
        summ["pooled_line_score"] = {f"{a}_{k}": round(v[1] / max(v[0], 1), 4) for (a, k), v in sorted(pool.items())}
        summ["kept_kindest_reading"] = sum(r["keep_kindest_reading"] for r in res)
        (out / f"{job}.json").write_text(json.dumps({"summary": summ, "results": res}, indent=1))
        print(json.dumps(summ))
        if job == "C1p":
            projected = len(kept) / len(res) * 160
            full = BY_ID["C1"]
            secs = timing.get("load_s", 120) + 144 * timing.get("s_per_painting", 10)
            summ.update(projected_pairs=round(projected), projected_c1_seconds=round(secs), c1_cap_seconds=cap_seconds(full))
            (out / f"{job}.json").write_text(json.dumps({"summary": summ, "results": res}, indent=1))
            if projected < MIN_PAIRS:
                return _stop(job, f"the pilot kept {len(kept)} of {len(res)} paintings: {projected:.0f} pairs projected for "
                             f"the full set, {MIN_PAIRS} are needed", summ)
            if secs > cap_seconds(full):
                return _stop(job, f"C1 would take {secs:.0f} s at the pilot's speed, over its cap {cap_seconds(full)} s", summ)
            print(f"C1p passes: {projected:.0f} pairs projected (>= {MIN_PAIRS}); C1 about {secs / 60:.0f} min at the measured speed")
            return 0
        (c / "dataset").mkdir(exist_ok=True)
        (c / "dataset" / "kept.json").write_text(json.dumps({"kept": [{"window": r["window"], "file": r["file"]} for r in kept]}, indent=1))
        if len(kept) < MIN_PAIRS:
            return _stop(job, f"{len(kept)} paintings passed the checks, {MIN_PAIRS} pairs are needed: C2 does not start", summ)
        print(f"C1 passes: {len(kept)} pairs kept")
        return 0
    if job == "C2p":
        d = c / "train_pilot"
        tests = json.loads((c / "dataset" / "tests.json").read_text())["tests"]
        rows = []
        for p in sorted((d / "samples").glob("*")):
            m = re.search(r"_(\d{9})_(\d+)\.(jpg|png)$", p.name)
            if not m or int(m.group(1)) != 200:
                continue
            name = tests[int(m.group(2))]
            x0, y0 = (int(v) for v in name.split("_"))
            rows.append({"window": name, **PC.check_painting(_scene(), p, PC.geom(c / "inputs", name), x0, y0)})
        _table([{**r, "vehicles": "-", "keep": r["flat_ok"]} for r in rows])
        s_step = None
        log = d / "logs" / "C2p.log"
        if log.exists():
            its = re.findall(r"(\d+\.\d+)\s*s/it", log.read_text(errors="ignore")) or []
            ips = re.findall(r"(\d+\.\d+)\s*it/s", log.read_text(errors="ignore")) or []
            if its:
                s_step = float(np.median([float(x) for x in its[-50:]]))
            elif ips:
                s_step = 1 / float(np.median([float(x) for x in ips[-50:]]))
        if s_step is None and (d / "train_start").exists() and (d / "train_end").exists():
            s_step = (int((d / "train_end").read_text()) - int((d / "train_start").read_text())) / 200      # an upper bound
        full = BY_ID["C2"]
        secs = None if s_step is None else 1800 * s_step + 420            # + the model load and three sample rounds
        summ = {"job": job, "samples_at_200": len(rows), "flat_ok": [r["flat_ok"] for r in rows],
                "flat_worst": [r["flat_worst"] for r in rows], "s_per_step": s_step,
                "projected_c2_seconds": None if secs is None else round(secs), "c2_cap_seconds": cap_seconds(full)}
        (out / f"{job}.json").write_text(json.dumps({"summary": summ, "results": rows}, indent=1))
        print(json.dumps(summ))
        if not rows:
            return _stop(job, "no step-200 samples came back", summ)
        if not all(r["flat_ok"] for r in rows):
            return _stop(job, "a step-200 sample has a baked shadow (flat light over 5% on a building)", summ)
        if secs is None or secs > cap_seconds(full):
            return _stop(job, f"C2 would take {secs} s at the pilot's speed, over its cap {cap_seconds(full)} s", summ)
        print(f"C2p passes: no shadow in the step-200 samples; C2 about {secs / 60:.0f} min at {s_step:.2f} s/step")
        return 0
    raise SystemExit(f"no check for {job}")


# ------------------------------------------------------------------------------------------------ B
# A surface material is used only if it is the palette colour it was asked for ("Colour close to RGB ...",
# prompts.MATERIAL_BRIEF): its median colour within this distance of the palette's (RGB, 0-441). Added on 10 Nov
# 2026 when the first library came back: without it the nearest of three candidates was taken however far it was,
# and a wall asked for as soft blue came back cyan. An opening (a window, a door) is a drawing of several colours
# and is not held to one.
MAX_COLOUR_DISTANCE = 45.0
OBJECTS = ("window_casement", "window_shuttered", "window_shop", "door_panel", "door_double", "door_garage")


def material_check(img: np.ndarray, target_rgb, is_object: bool) -> dict:
    """A material swatch's own flat-light check: no light direction across it. The median luminance of the left
    and right halves (and, for a surface material, of the top and bottom halves) within 5%; for a surface also how
    well it tiles (the step across the wrap, against the step between neighbouring columns and rows inside)."""
    from v2.layers.common import lum
    L = lum(img.astype(float))
    h, w = L.shape
    def rel(a, b):
        return abs(np.median(a) - np.median(b)) / max(np.median(a), np.median(b), 1e-6)
    lr = rel(L[:, : w // 2], L[:, w // 2:])
    tb = 0.0 if is_object else rel(L[: h // 2], L[h // 2:])
    wrap = (np.abs(L[:, 0] - L[:, -1]).mean() + np.abs(L[0] - L[-1]).mean()) / 2
    inner = (np.abs(np.diff(L, axis=1)).mean() + np.abs(np.diff(L, axis=0)).mean()) / 2
    colour = float(np.linalg.norm(np.median(img.reshape(-1, 3), 0) - np.asarray(target_rgb, float)))
    return {"light_lr": round(float(lr), 4), "light_tb": round(float(tb), 4), "flat_ok": bool(max(lr, tb) <= 0.05),
            "wrap_step": round(float(wrap), 2), "inner_step": round(float(inner), 2), "colour_distance": round(colour, 1)}


def object_crop(img: np.ndarray):
    """An opening's swatch cut to the opening itself: the box of the pixels that differ from the border's colour
    (the wall the model drew round it). Returns (x0, y0, x1, y1); the whole image if nothing stands out."""
    border = np.concatenate([img[:8].reshape(-1, 3), img[-8:].reshape(-1, 3), img[:, :8].reshape(-1, 3), img[:, -8:].reshape(-1, 3)])
    bg = np.median(border, 0)
    diff = np.abs(img.astype(float) - bg).sum(-1) > 60
    rows, cols = np.flatnonzero(diff.mean(1) > 0.25), np.flatnonzero(diff.mean(0) > 0.25)
    if len(rows) < img.shape[0] // 10 or len(cols) < img.shape[1] // 10:
        return 0, 0, img.shape[1], img.shape[0]
    return int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1


def pick_b() -> int:
    from v2.bakeoff.prompts import MATERIALS
    from v2.layers.common import pal
    b = B.base() / "b"
    out = b / "checks"
    out.mkdir(parents=True, exist_ok=True)
    picked = {"materials": {}, "landmarks": {}}
    report = {"materials": {}, "landmarks": {}}
    mfiles = sorted((b / "materials").glob("*_[0-9].png"))
    det = PC.owl(mfiles, out / "materials", mpp=1 / 64) if mfiles else {"by_file": {}}
    for name, (what, key, size) in MATERIALS.items():
        rows = []
        for p in sorted((b / "materials").glob(f"{name}_[0-9].png")):
            img = np.asarray(Image.open(p).convert("RGB"))
            r = {"file": p.name, **material_check(img, pal(*key.split(".")), name in OBJECTS),
                 "vehicles": len(det["by_file"].get(p.name, []))}
            r["colour_ok"] = bool(name in OBJECTS or r["colour_distance"] <= MAX_COLOUR_DISTANCE)
            r["ok"] = bool(r["flat_ok"] and not r["vehicles"] and r["colour_ok"])
            if name in OBJECTS:
                r["crop"] = object_crop(img)
            rows.append(r)
        report["materials"][name] = rows
        good = [r for r in rows if r["ok"]]
        if good:
            # the candidate nearest the palette colour; for a surface, ties broken by how well it tiles
            best = min(good, key=lambda r: (round(r["colour_distance"] / 10), r["wrap_step"] / max(r["inner_step"], 1e-6)))
            picked["materials"][name] = {"file": best["file"], "size_m": list(size), **({"crop": best["crop"]} if "crop" in best else {})}
        print(f"  {name:18} " + "  ".join(f"{r['file'][-5]}:{'ok' if r['ok'] else 'no'} lr {r['light_lr']:.3f} tb {r['light_tb']:.3f} dc {r['colour_distance']:.0f}" for r in rows)
              + f"  -> {picked['materials'].get(name, {}).get('file', 'none passes: A pattern stays')}")
    # landmark portraits
    lm = {x["building"]: x for x in json.loads((b / "landmarks.json").read_text()) if x.get("building")}
    files = []
    for bid in sorted(lm):
        for k in (0, 1):
            if (b / "landmarks" / f"{bid}_{k}.png").exists():
                files.append((bid, f"{bid}_{k}.png"))
    if files:
        res = []
        for bid, fn in files:
            meta = json.loads((b / "landmark_inputs" / f"{bid}.json").read_text())
            g = PC.geom(b / "landmark_inputs", bid)
            # the portrait is judged on its own building only
            own = (g["ids"] >> 8) == meta["building_index"]
            g = {**g, "which": np.where(own, g["which"], 0)}
            res.append({"window": bid, "x0": meta["x0"], "y0": meta["y0"], "building_index": meta["building_index"],
                        **PC.check_painting(_scene(), b / "landmarks" / fn, g, meta["x0"], meta["y0"])})
        det = PC.owl([b / "landmarks" / fn for _, fn in files], out / "landmarks")
        for r in res:
            r["vehicles"] = len(det["by_file"].get(r["file"], []))
            r["cars_ok"] = not r["vehicles"]
            r["keep"] = bool(r["flat_ok"] and r["lines_ok"] and r["cars_ok"])
        _table(res)
        for bid in sorted(lm):
            good = [r for r in res if r["window"] == bid and r["keep"]]
            report["landmarks"][bid] = [r for r in res if r["window"] == bid]
            if good:
                best = max(good, key=lambda r: (r["line_edges"] or 0) + (r["line_windows"] or 0))
                picked["landmarks"][bid] = {"file": best["file"], "x0": best["x0"], "y0": best["y0"],
                                            "building_index": best["building_index"], "name": lm[bid]["name"]}
    summ = {"materials": len(report["materials"]), "materials_picked": len(picked["materials"]),
            "landmarks_painted": len(report["landmarks"]), "landmarks_used": len(picked["landmarks"])}
    (out / "pick.json").write_text(json.dumps({"summary": summ, "report": report}, indent=1, default=int))
    (b / "picked.json").write_text(json.dumps(picked, indent=1, default=int))
    print(json.dumps(summ))
    if picked["materials"] or picked["landmarks"]:
        (b / "painted.json").write_text(json.dumps({"method": "b", **summ, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}))
    return 0


def mark_painted(method: str) -> int:
    if method == "b":
        return pick_b()
    c = B.base() / "c"
    wj = json.loads((c / "windows.json").read_text())
    missing = [f"{x}_{y}" for x, y in wj["windows"] if not (c / "painted" / f"{x}_{y}.png").exists()]
    if missing:
        print(f"C: {len(missing)} of {len(wj['windows'])} windows are not painted: {missing[:6]}")
        return 1
    (c / "painted.json").write_text(json.dumps({"method": "c", "windows": len(wj["windows"]), "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}))
    print(f"C: {len(wj['windows'])} windows painted")
    return 0


def pilot_gates() -> int:
    """C was stopped at its pilot, so only the pilot's windows are painted. This measures the built layers there,
    like for like: the gate's own line score (L5.2, line_checks.score on the release's layer-5 tiles) of every
    registered method inside the painted windows only, and each used painting's flat-light and detector results.
    Written to c/checks/pilot_gates.json and v2/docs/results/bakeoff_c_pilot.json."""
    from v2.checks import line_checks as lc
    from v2.checks.layer_checks import TileCache
    from v2.config import V2, params
    P = params()["g1"]
    c = B.base() / "c"
    rels = json.loads((B.base() / "releases.json").read_text())
    wins = sorted(p.stem for p in (c / "painted").glob("*.png"))
    lines = PC.model_lines(str(_scene()))
    out = {"windows": wins, "line_score": {}}
    for m, info in sorted(rels.items()):
        cache = TileCache(Path(info["release"]), "buildings", maxn=64)
        row = {}
        for k, (Ps, Ds, Os, px, py) in lines.items():
            inside = np.zeros(len(px), bool)
            for w in wins:
                x0, y0 = (int(v) for v in w.split("_"))
                inside |= (px >= x0 + 4) & (px < x0 + 1020) & (py >= y0 + 4) & (py < y0 + 1020)
            seen, on = lc.score(cache, Ps[inside], Ds[inside], P["line_score_px"], P["line_min_step"], obj=Os[inside])
            row[k] = {"seen": int(seen.sum()), "share": round(float(on.sum() / max(seen.sum(), 1)), 4)}
        row["pass"] = bool(row["edges"]["share"] >= P["line_score_share"] and row["windows"]["share"] >= P["line_score_share"])
        out["line_score"][m] = row
        print(m, row)
    pil = json.loads((c / "checks" / "C1p.json").read_text())
    used = {w: None for w in wins}
    for r in pil["results"]:
        src = c / "targets" / r["file"]
        dst = c / "painted" / f"{r['window']}.png"
        if dst.exists() and src.read_bytes() == dst.read_bytes():
            used[r["window"]] = {k: r[k] for k in ("file", "flat_worst", "flat_failing_buildings", "flat_ok", "line_edges",
                                                    "line_windows", "vehicles", "keep")}
    out["paintings_used"] = used
    out["pilot_summary"] = pil["summary"]
    (c / "checks" / "pilot_gates.json").write_text(json.dumps(out, indent=1))
    (V2 / "docs" / "results" / "bakeoff_c_pilot.json").write_text(json.dumps(out, indent=1))
    return 0
