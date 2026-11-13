"""A landmark cutaway's painted interior (specs/landmark-cutaways.md, "the painted step"): the inputs the paid job
takes, the checks of what it brings back, and the step that hands a passing painting to the cutaway layer. All
local, $0. The job itself is K1 in jobs.py.

    make_inputs()       from stage layer_cutaways' paint inputs: per candidate kind the control image and the layout
                        (v1's second control image: black outlines, dark windows, on white)
    compose()           a painting cut to the opening mask over the cut render (rule 2: the painting never covers the
                        outside of the building or the map round it)
    check_candidate()   K1-K3 on one painting with the gate's own functions and thresholds (cutaway_checks.py,
                        params.json g3 cutaway_*), light across each kind of face, the interior's lines, and whether
                        an interior was painted at all
    check()             every candidate of a job, K4 (the detector, vehicles and people) on inputs, paintings and
                        composites, the sheets for v2/docs/img, the numbers for v2/docs/results
    adopt()             the best passing candidate, cut to the mask, into v2/data/structures/cutaway_paintings: the
                        build's cutaway layer then draws it in place of the placeholder (layers/cutaways.py)

Two kinds of candidate, two seeds each (four seeds in all: in the first run the same seed gave nearly the same
painting from both kinds, so the kinds no longer share their seeds):
    <name>         the cut render exactly as the build wrote it (flat placeholder colours inside the opening)
    <name>-open    the same render with the inside faces' flat colours cleared to paper, the ink lines and the
                   section (the cut faces, the opening's rim) kept: the style model was trained to "fill in the
                   missing pixels", and in Phase 2 it returned flat colour as given

What the first run (10 Nov 2026, three paintings) taught the checks, each measured on those paintings:
    K2b   "covered" asked for a colour away from paper, and the painter's pale floor slabs are paper's colour: 819
          of cathedral_0's 900 "uncovered" pixels were light squares of its floor, half of them over 23 px from the
          mask's edge. A blank is now a patch, not a pixel (BLANK_MIN_PX), and the painter's own background counts
          as blank too (two of the three paintings came back on white, not on paper).
    light the plane fitted to a face's luminance read a chequered floor, pews on one side and windows as light.
          Light is now measured on one material (light_across).
    lines the lines that went missing are the placeholder's own (the floor against the wall behind the pews, wall
          corners behind columns), not the section's: reported apart (interior_lines).
    K3    the median luminance of a painted wall is its windows' (over half of each wall was glass or ink; the
          median pixel was about 90 of 255, the stone about 200), so K3 compared how much glass each wall had.

The owner's rule for both (13 Nov 2026, "Correct both, free"), in place before the second run:
    K3    on a painting is measured on each face's own material only (the stone of a wall: cutaway_checks.
          face_material), not its glass and not its ink. The 5% limit is K3's own, unchanged. A side with too little
          stone to measure fails.
    lines the gate is the cut's outline: the section's lines (K1's subject) at the gate's own share. The
          placeholder's own construction lines are reported, not gated.

K5 and K6 are of the geometry (depth, ids, the toggle): a painting changes colour only, inside the mask, so they
hold as built; they run again as gates when a painting is composed into the layer.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np
from PIL import Image

from v2.bakeoff.prompts import C_TARGET_PROMPT
from v2.config import V2, params, v2_data

AREA = "test"
KINDS = ("", "-open")
SEEDS = (1867, 1868)                      # pod/run.sh K1: the first kind's; the second kind's are these + SEED_STEP
SEED_STEP = 2                             # pod/paint.py --seed-step
PAPER_TOL = 8                             # K2b: within this RGB distance of paper (or of the painting's own
                                          # background) a mask pixel may be blank
BLANK_MIN_PX = 7                          # K2b: ... and is, if a 7 x 7 px square (0.9 m) of such pixels holds it.
                                          # A paler patch narrower than that is a detail of the drawing (a floor slab)
# light across one kind of face (light_across)
LIGHT_BLOCK = 16                          # px (2 m): larger than a floor pattern's repeat
LIGHT_STEP = 4                            # px between blocks: a shade that holds a 20 px square (2.5 m) holds a block
LIGHT_CHROMA = 0.03                       # the same material: r and g shares of r + g + b within this of the face's
                                          # (K3's own is the same number: cutaway_checks.MATERIAL_CHROMA)
LIGHT_SHARE = 0.4                         # a block is measured if this share of its face pixels are that material
LIGHT_PCT = 90                            # the material's lit level in a block: this percentile of its luminance
CHANGE_LUM = 12                           # "changed": the build's own line step (params g3 cutaway_line_min_step)
PROMPTS = {
    "cathedral": C_TARGET_PROMPT + (
        " The building is cut open like an architectural model. Inside the opening draw the interior of a gothic "
        "cathedral as a flat colour drawing: the nave with a pale chequered stone floor, rows of sandstone columns, "
        "pointed arches, a ribbed vault, narrow stained-glass windows and wooden pews. The interior is lit evenly "
        "from every side, like a diagram: every wall the same pale sandstone, the whole floor the same pale tone "
        "from edge to edge, also under and beside the pews and the columns. No cast shadows, no dark floor, no dark "
        "corners, no beams of light, no people."),
}
# the first run's (10 Nov 2026), kept with its results: it asked for even light in the style's own sentence only
PROMPT_RUN1 = C_TARGET_PROMPT + (
    " The building is cut open like an architectural model. Inside the opening draw the interior of a gothic "
    "cathedral: the nave with a chequered stone floor, rows of sandstone columns, pointed arches, a ribbed vault, "
    "tall stained-glass windows and wooden pews. No people.")


def base() -> Path:
    return v2_data() / AREA / "bakeoff" / "cutaways"


def input_names(name: str) -> list:
    return [name + k for k in KINDS]


def seed_of(kind: str, k: int, step: int = SEED_STEP) -> int:
    """The seed of candidate k of a kind, as pod/paint.py numbers them (inputs in name order, --seed-step)."""
    return SEEDS[k] + sorted(KINDS).index(kind) * step


def source() -> Path:
    """Stage layer_cutaways' folder of this checkout's build."""
    from v2.build.stages import graph
    return graph().folder("layer_cutaways", AREA)


def load(src: Path, name: str) -> dict:
    """One landmark's paint inputs: unlit (h, w, 3), mask and outline (bool), k, ids, normal, depth (inf where
    nothing is drawn), meta."""
    g = np.load(src / f"{name}.geom.npz")
    depth = g["depth"].astype(np.float64)
    return {"unlit": np.asarray(Image.open(src / f"{name}.unlit.png").convert("RGB")),
            "mask": np.asarray(Image.open(src / f"{name}.mask.png")) > 127,
            "outline": np.asarray(Image.open(src / f"{name}.outline.png")) > 127,
            "k": g["k"], "ids": g["ids"], "normal": g["normal"].astype(np.float64),
            "depth": np.where(depth > 1e8, np.inf, depth), "meta": json.loads((src / f"{name}.json").read_text())}


def paper() -> np.ndarray:
    from v2.layers.common import pal
    return np.round(pal("ink", "paper")).astype(np.uint8)


def lum(rgb):
    from v2.layers.common import lum as L
    return L(np.asarray(rgb, float))


def geometry_edges(d: dict, reach=0) -> np.ndarray:
    """Pixels on either side of a change of kind, object, facing or depth, grown by `reach` px
    (cutaway_checks.edges_of, which cannot grow by 0)."""
    from v2.checks.cutaway_checks import edges_of
    e = edges_of({"depth": d["depth"], "ids": d["ids"], "k": d["k"], "normal": d["normal"]}, reach=max(reach, 1))
    if reach >= 1:
        return e
    from scipy import ndimage
    # grown by 1 with the cross-shaped element: a pixel of the ungrown set is one whose change is its own
    ok = np.isfinite(d["depth"])
    key = d["ids"].astype(np.int64) * 16 + d["k"]
    dd = np.where(ok, d["depth"], 1e9)
    nz = np.round(d["normal"] * 20)
    own = np.zeros(ok.shape, bool)
    for u, v in (((slice(None), slice(None, -1)), (slice(None), slice(1, None))),
                 ((slice(None, -1), slice(None)), (slice(1, None), slice(None)))):
        ch = (key[u] != key[v]) | (np.abs(dd[u] - dd[v]) > 0.5) | (nz[u] != nz[v]).any(-1) | (ok[u] != ok[v])
        own[u] |= ch
        own[v] |= ch
    assert (ndimage.binary_dilation(own, iterations=1) == e).all()
    return own


def layout_of(d: dict) -> np.ndarray:
    """v1's second control image for the cut model: black where the geometry or the drawing has a line, the
    outside's windows dark, white elsewhere (inputs.render_window's recipe)."""
    edge = geometry_edges(d)
    L = d["unlit"].astype(float).mean(-1)
    edge |= np.abs(np.diff(L, axis=1, prepend=L[:, :1])) > 40
    edge |= np.abs(np.diff(L, axis=0, prepend=L[:1, :])) > 40
    out = np.full(L.shape, 255, np.uint8)
    out[np.isin(d["ids"] & 255, (12, 13, 14)) & np.isfinite(d["depth"])] = 90
    out[edge] = 0
    return out


def opened(d: dict) -> np.ndarray:
    """The cut render with the inside faces' flat placeholder colours cleared to paper. Its ink lines stay, and so
    does the section (the cut faces): the opening's rim is given to the painter, not left to it."""
    from v2.layers.cutaways import KIND
    out = d["unlit"].copy()
    out[d["mask"] & ~geometry_edges(d) & (d["k"] != KIND["cut"])] = paper()
    return out


def make_inputs(names=("cathedral",), src: Path | None = None, dst: Path | None = None) -> dict:
    src = Path(src) if src else source() / "paint"
    dst = Path(dst) if dst else base() / "inputs"
    dst.mkdir(parents=True, exist_ok=True)
    made = {}
    for name in names:
        d = load(src, name)
        assert d["unlit"].shape[:2] == (1024, 1024), "one model pass is 1024 x 1024 (pod/paint.py)"
        lay = layout_of(d)
        for kind, img in (("", d["unlit"]), ("-open", opened(d))):
            Image.fromarray(img).save(dst / f"{name}{kind}.unlit.png")
            Image.fromarray(lay).save(dst / f"{name}{kind}.layout.png")
        made[name] = {"source": str(src), "frame_px": d["meta"]["frame_px"], "opening_px": int(d["mask"].sum()),
                      "line_px_in_opening": int((d["mask"] & geometry_edges(d)).sum()), "inputs": input_names(name)}
    (dst / "inputs.json").write_text(json.dumps(made, indent=1))
    return made


# ------------------------------------------------------------------------------------------------ one painting
def compose(unlit, painting, mask) -> np.ndarray:
    """The painting inside the opening mask, the cut render everywhere else."""
    out = np.asarray(unlit, np.uint8).copy()
    out[mask] = np.asarray(painting, np.uint8)[mask]
    return out


def blank(painting, mask, outline=None) -> np.ndarray:
    """Mask pixels the painter left blank: the colour of paper, or of the painting's own background (the median of
    what it returned outside the building's outline, where nothing is to be drawn), in a patch that holds a
    BLANK_MIN_PX square. What lies outside the mask counts as blank for the patch, so a blank strip along the
    opening's edge is found whatever its width."""
    from scipy import ndimage
    p = np.asarray(painting, int)
    refs = [paper().astype(int)]
    if outline is not None and (~outline).any():
        refs.append(np.median(p[~outline], axis=0).astype(int))
    near = np.zeros(mask.shape, bool)
    for r in refs:
        near |= np.abs(p - r).max(-1) <= PAPER_TOL
    sq = np.ones((BLANK_MIN_PX, BLANK_MIN_PX), bool)
    room = near | ~mask
    patch = ndimage.binary_dilation(ndimage.binary_erosion(room, sq, border_value=1), sq)
    return patch & near & mask


def covered(painting, mask, outline=None) -> np.ndarray:
    """K2b: mask pixels the painting drew on (not left blank)."""
    return mask & ~blank(painting, mask, outline)


def steps(rgb) -> np.ndarray:
    """Pixels at a luminance step of the build's line size or more (to the next pixel right or down)."""
    L = lum(rgb)
    s = np.zeros(L.shape, bool)
    s[:, :-1] |= np.abs(np.diff(L, axis=1)) >= CHANGE_LUM
    s[:-1, :] |= np.abs(np.diff(L, axis=0)) >= CHANGE_LUM
    return s


def chroma(rgb) -> np.ndarray:
    """A colour without its brightness (cutaway_checks.chroma)."""
    from v2.checks.cutaway_checks import chroma as c
    return c(rgb)


def light_across(rgb, material, ok, min_px) -> dict:
    """Light and shade inside one kind of face, apart from what is drawn on it. K3's own notion ("sides of the same
    material"), within a face: the face's material is the colour of its light pixels (chroma of those between the
    75th and 97th percentile of its luminance); in every LIGHT_BLOCK square that holds enough of that material, the
    material's lit level is the LIGHT_PCT percentile of its luminance there; the result is the largest fall of that
    level between two blocks, as a share. A pattern (a chequer, tiles, joints) shows the material at its lit level
    in every block, so it measures 0; a gradient or a cast shadow darkens the material itself and is measured.
    Another material (a pew, a window, a slab of another stone) is not compared with it: K3 and the eye judge those.
    Its limits: a shade is seen once it darkens nine tenths of the material in one block, so surely when it holds a
    square of LIGHT_BLOCK + LIGHT_STEP px (2.5 m; a round one 3.5 m across), not when it is a thin line beside a
    pew; a shade drawn in another colour than the material's (a blue shadow on cream stone) is another material."""
    L = lum(rgb)
    ch = chroma(rgb)
    out = {}
    for m in np.unique(material[ok & (material > 0)]):
        sel = ok & (material == m)
        if sel.sum() < 4 * min_px:
            continue
        lo, hi = np.percentile(L[sel], (75, 97))
        ref = np.median(ch[sel & (L >= lo) & (L <= hi)], axis=0)
        same = sel & (np.abs(ch - ref).max(-1) <= LIGHT_CHROMA)
        yy, xx = np.nonzero(sel)
        lit = []
        for y in range(yy.min() // LIGHT_STEP * LIGHT_STEP, yy.max() + 1, LIGHT_STEP):
            for x in range(xx.min() // LIGHT_STEP * LIGHT_STEP, xx.max() + 1, LIGHT_STEP):
                w = (slice(y, y + LIGHT_BLOCK), slice(x, x + LIGHT_BLOCK))
                n, q = int(sel[w].sum()), same[w]
                if n >= LIGHT_BLOCK * LIGHT_BLOCK // 2 and q.sum() >= LIGHT_SHARE * n:
                    lit.append(float(np.percentile(L[w][q], LIGHT_PCT)))
        out[int(m)] = float((max(lit) - min(lit)) / max(max(lit), 1e-6)) if len(lit) > 1 else 0.0
    return out


def painted_at_all(painting, d: dict) -> dict:
    """Did the model paint an interior, or return the flat render? Inside the opening, away from the model's own
    lines: the share of pixels whose luminance moved by a line step or more from the placeholder, and the drawn
    detail (pixels at a luminance step) against the placeholder's."""
    inner = d["mask"] & ~geometry_edges(d, reach=2)
    n = max(int(inner.sum()), 1)
    moved = np.abs(lum(painting) - lum(d["unlit"])) >= CHANGE_LUM
    det, det0 = int((steps(painting) & inner).sum()), int((steps(d["unlit"]) & inner).sum())
    share, detail = float((moved & inner).sum() / n), float(det / n)
    return {"changed_share": round(share, 4), "detail_share": round(detail, 4), "placeholder_detail_share": round(det0 / n, 4),
            "pixels": n, "interior_painted": bool(share >= 0.25 and detail >= 0.05)}


def interior_lines(painting, d: dict) -> dict:
    """The model's own lines inside the opening (where faces meet): the share with a drawn step within 1 px. Apart:
    the section's lines (a cut face on either side: the opening's rim, K1's subject), which are the gate, and the
    placeholder's (where two inside faces of the nominal shell meet: a painted interior may stand a pew or a column
    in front of them), which are reported."""
    from scipy import ndimage
    from v2.layers.cutaways import KIND
    line = d["mask"] & geometry_edges(d)
    near = ndimage.binary_dilation(steps(painting), iterations=1)
    sq = np.ones((3, 3), bool)
    at = {n: ndimage.binary_dilation(d["k"] == KIND[n], sq) for n in ("cut", "inside_wall", "inside_roof", "floor", "slab")}
    share = lambda s: round(float((s & near).sum() / max(int(s.sum()), 1)), 4)                               # noqa: E731
    section = line & at["cut"]
    inner = line & ~at["cut"]
    by = {"floor_wall": inner & at["floor"] & at["inside_wall"], "roof_wall": inner & at["inside_roof"] & at["inside_wall"]}
    by["wall_wall"] = inner & at["inside_wall"] & ~by["floor_wall"] & ~by["roof_wall"]
    return {"line_px": int(line.sum()), "kept": share(line),
            "section_px": int(section.sum()), "section_kept": share(section),
            "placeholder_px": int(inner.sum()), "placeholder_kept": share(inner),
            "placeholder_by_junction": {k: {"px": int(v.sum()), "kept": share(v)} for k, v in by.items() if v.any()}}


class Frame:
    """A frame of map pixels as the tile cache line_checks.score reads (colour, depth, ids)."""

    def __init__(self, x0, y0, rgb, depth, ids):
        from v2.bakeoff.paintcheck import B_LAYER, WindowCache
        self.c = WindowCache(x0, y0, rgb, {"which": np.where(np.isfinite(depth), B_LAYER, 0), "depth": depth, "ids": ids})

    def get(self, tx, ty):
        return self.c.get(tx, ty)


def section_score(rgb, d: dict, model, P) -> dict:
    """K1a on an image: the line score of the model's section (cutaway_checks.Model.section_lines)."""
    from v2.checks import line_checks as lic
    A, B, O = model.section_lines()
    Ps, Ds, Os = lic.samples(A, B, O)
    fx, fy = d["meta"]["frame_px"][:2]
    seen, on = lic.score(Frame(fx, fy, rgb, d["depth"], d["ids"]), Ps, Ds, P["cutaway_line_px"],
                         P["cutaway_line_min_step"], obj=Os)
    return {"seen": int(seen.sum()), "share": round(float(on.sum() / max(int(seen.sum()), 1)), 4)}


def check_candidate(painting, d: dict, P: dict, sun=None, model=None) -> dict:
    """One painting against K1-K3 and the rest. `d`: load(); P: cutaways.cut_params()."""
    from v2.checks.cutaway_checks import face_material, flat_interior, ink, interior_in_mask
    from v2.layers.cutaways import KIND
    painting = np.asarray(painting, np.uint8)
    mask = d["mask"]
    comp = compose(d["unlit"], painting, mask)
    names = {v: k for k, v in KIND.items()}
    # K2: what the composite changed is the interior; what the painting drew on is what covers the mask
    interior = (comp != d["unlit"]).any(-1) | mask
    out_px, _ = interior_in_mask(interior, mask)
    _, cover = interior_in_mask(covered(painting, mask, d["outline"]), mask)
    # K3: the gate's shadow detector on the painted interior, on each face's own material (a wall's stone, not its
    # glass or ink); the same over every pixel of the face is kept as a reported number (the first run's measure)
    edge = geometry_edges(d, reach=2)
    kinds = np.where(mask, d["k"], 0)
    stone = face_material(comp, kinds, mask & ~edge, ink(comp, P["cutaway_line_min_step"]))
    flat = lambda only: flat_interior(comp[mask], kinds[mask], d["normal"][mask], sun, P["cutaway_shadow_min_px"],   # noqa: E731
                                      edge[mask], None if only is None else only[mask])
    worst = lambda f: max([max(v["worst"], v["sun"] or 0.0) for v in f.values()] or [0.0])                   # noqa: E731
    fl, fl_all = flat(stone), flat(None)
    k3, unmeasured = worst(fl), sum(v["unmeasured"] for v in fl.values())
    share = {names[int(m)]: round(float((stone & (kinds == m)).sum() / max(int((mask & ~edge & (kinds == m)).sum()), 1)), 4)
             for m in np.unique(kinds[mask & ~edge])}
    across = light_across(comp, kinds, mask & ~edge, P["cutaway_shadow_min_px"])
    res = {
        "K2a_interior_px_outside_mask": out_px, "K2b_mask_covered": round(cover, 5),
        "K2_ok": bool(out_px == 0 and cover >= P["cutaway_mask_cover"]),
        "K3_worst": round(float(k3), 4), "K3_unmeasured_sides": int(unmeasured),
        "K3_ok": bool(k3 <= P["cutaway_shadow_lum_tol"] and unmeasured == 0),
        "K3_material_share": share, "K3_every_pixel_worst": round(float(worst(fl_all)), 4),
        "K3_by_kind": {names[m]: {a: (round(b, 4) if isinstance(b, float) else b) for a, b in v.items()} for m, v in fl.items()},
        "light_across_kind": {names[m]: round(v, 4) for m, v in across.items()},
        "light_across_worst": round(max(across.values() or [0.0]), 4),
        "interior_lines": interior_lines(painting, d), **painted_at_all(painting, d),
        # how the model treated what it was not asked to change (the composite does not use it)
        "raw_outside_changed_share": round(float(((np.abs(lum(painting) - lum(d["unlit"])) >= CHANGE_LUM) & d["outline"] & ~mask).sum()
                                                 / max(int((d["outline"] & ~mask).sum()), 1)), 4),
        "raw_drawn_outside_outline_px": int((covered(painting, ~d["outline"], d["outline"])).sum()),
    }
    res["light_across_ok"] = bool(res["light_across_worst"] <= P["cutaway_shadow_lum_tol"])
    # the gate is the cut's outline: the section's lines. The placeholder's own lines are reported (interior_lines)
    res["lines_kept_ok"] = bool(res["interior_lines"]["section_kept"] >= P["cutaway_line_share"])
    if model is not None:
        s = section_score(comp, d, model, P)
        res.update(K1a_section_line_share=s["share"], K1a_seen=s["seen"], K1_ok=bool(s["share"] >= P["cutaway_line_share"]))
    return res


def verdict(r: dict) -> bool:
    """A candidate may replace the placeholder: every check passes and an interior was painted."""
    return bool(r.get("K1_ok", True) and r["K2_ok"] and r["K3_ok"] and r["light_across_ok"] and r["lines_kept_ok"]
                and r.get("K4_ok", True) and r["interior_painted"])


# ------------------------------------------------------------------------------------------------ a job's results
def _model(name):
    from v2.build.stages import graph
    from v2.checks.cutaway_checks import Model
    from v2.layers import cutaways as cw
    from v2.layers.common import Scene
    P = cw.cut_params()
    return Model(Scene(graph().folder("scene", AREA)), cw.load_cuts()["landmarks"][name], P), P


def _sun():
    from v2.layers.light import sun_vector
    return sun_vector(dt.datetime.fromisoformat(params()["g1"]["shadow_photo_sun"]))[2]


def detector(files: dict, out: Path) -> dict:
    """K4 on every image of `files` ({label: path}): vehicles, then people, with the gate's queries and scores."""
    from v2.checks.cutaway_checks import run_detector
    g1, g3 = params()["g1"], params()["g3"]
    jobs = [{"layer": "cutaway-paint", "path": str(p), "tile": lab} for lab, p in files.items()]
    res = {lab: {"vehicles": 0, "people": 0} for lab in files}
    top = {}
    for tag, queries, thr, box_m in (("vehicles", g1["detector_queries"], g1["detector_score"], g1["detector_box_m"]),
                                     ("people", g3["cutaway_person_queries"], g3["cutaway_detector_score"], g3["cutaway_person_box_m"])):
        r = run_detector(jobs, out, f"paint_{tag}", queries, thr, box_m)
        top[tag] = {"images": r["images"], "max_score": r["max_score"], "detections": r["detections"]}
        for det in r["detections"]:
            res[det["tile"]][tag] += 1
    return {"by_image": res, **top}


def crop_box(d: dict, pad=40):
    x0, y0, x1, y1 = d["meta"]["opening_bbox"]
    n = d["mask"].shape[0]
    return max(x0 - pad, 0), max(y0 - pad, 0), min(x1 + pad, n), min(y1 + pad, n)


def _label(im: Image.Image, text: str) -> Image.Image:
    from PIL import ImageDraw
    out = Image.new("RGB", (im.width, im.height + 26), (255, 255, 255))
    out.paste(im, (0, 26))
    ImageDraw.Draw(out).text((6, 6), text, fill=(20, 20, 20))
    return out


def _row(ims, gap=8):
    h = max(i.height for i in ims)
    out = Image.new("RGB", (sum(i.width for i in ims) + gap * (len(ims) - 1), h), (255, 255, 255))
    x = 0
    for i in ims:
        out.paste(i, (x, 0))
        x += i.width + gap
    return out


def _stack(rows, gap=8):
    out = Image.new("RGB", (max(r.width for r in rows), sum(r.height for r in rows) + gap * (len(rows) - 1)), (255, 255, 255))
    y = 0
    for r in rows:
        out.paste(r, (0, y))
        y += r.height + gap
    return out


def _save(im: Image.Image, dst: Path, max_bytes=950_000):
    dst.parent.mkdir(parents=True, exist_ok=True)
    for q in (90, 86, 82, 76, 70, 60, 50):
        im.save(dst, "JPEG", quality=q, optimize=True)
        if dst.stat().st_size <= max_bytes:
            break
    return dst


def sheets(name: str, d: dict, inputs: Path, cands: list, img: Path, run: str = "") -> dict:
    """The input sheet (both control images, the layout, the mask) and the candidates side by side: each whole
    painting as the model returned it, and under it the opening at twice the size, cut to the mask over the render.
    An earlier run's sheets carry its name (..._run1.jpg)."""
    tag = f"_{run}" if run else ""
    box = crop_box(d)
    half = lambda a: Image.fromarray(a).resize((512, 512), Image.LANCZOS)                                    # noqa: E731
    zoom = lambda a: Image.fromarray(a).crop(box).resize(((box[2] - box[0]) * 2, (box[3] - box[1]) * 2), Image.LANCZOS)  # noqa: E731
    rd = lambda f: np.asarray(Image.open(inputs / f).convert("RGB"))                                         # noqa: E731
    a = _row([_label(half(rd(f"{name}.unlit.png")), "input: the cut render as built"),
              _label(half(rd(f"{name}-open.unlit.png")), "input: the opening cleared to paper"),
              _label(half(rd(f"{name}.layout.png")), "layout (second control image)"),
              _label(half(np.repeat((d["mask"] * 255).astype(np.uint8)[..., None], 3, -1)), "opening mask")])
    b = _row([_label(zoom(rd(f"{name}.unlit.png")), "the opening, as built (2x)"),
              _label(zoom(rd(f"{name}-open.unlit.png")), "the opening, cleared (2x)")])
    out = {"input": _save(_stack([a, b]), img / f"test_cutaway_{name}_paint_input{tag}.jpg").name}
    if cands:
        top = _row([_label(half(c["raw"]), c["label"]) for c in cands])
        w = (top.width - 8 * (len(cands) - 1)) // len(cands)
        fit = lambda a: (lambda z: z.resize((w, round(z.height * w / z.width)), Image.LANCZOS))(zoom(a))       # noqa: E731
        bot = _row([_label(fit(c["comp"]), ("PASS" if c["pass"] else "fail") + ": cut to the mask, in the render") for c in cands])
        out["candidates"] = _save(_stack([top, bot]), img / f"test_cutaway_{name}_candidates{tag}.jpg").name
    return out


def check(job: str = "K1", name: str = "cathedral", painted: Path | None = None, write_docs=True, run: str = "") -> dict:
    """Every candidate of the job through the checks; results to <data>/.../cutaways/checks and, with write_docs,
    v2/docs/results/cutaway_<job>.json and the sheets in v2/docs/img. run="run1": the first run's paintings
    (<data>/.../cutaways/painted_run1, both kinds on the same two seeds, its own prompt), to cutaway_<job>_run1.json."""
    src = source() / "paint"
    d = load(src, name)
    painted = Path(painted) if painted else base() / ("painted" + (f"_{run}" if run else ""))
    out = base() / ("checks" + (f"_{run}" if run else ""))
    tag = job + (f"_{run}" if run else "")
    out.mkdir(parents=True, exist_ok=True)
    model, P = _model(name)
    sun = _sun()
    inputs = base() / ("inputs" + (f"_{run}" if run else ""))
    files = {f"input {n}": inputs / f"{n}.unlit.png" for n in input_names(name)}
    base_line = section_score(d["unlit"], d, model, P)
    cands = []
    for kind in KINDS:
        for k in range(len(SEEDS)):
            seed = seed_of(kind, k, 0 if run == "run1" else SEED_STEP)
            p = painted / f"{name}{kind}_{k}.png"
            if not p.exists():
                continue
            raw = np.asarray(Image.open(p).convert("RGB"))
            if raw.shape != d["unlit"].shape:
                raise SystemExit(f"{p.name}: {raw.shape}, the frame is {d['unlit'].shape}")
            comp = compose(d["unlit"], raw, d["mask"])
            Image.fromarray(comp).save(out / f"{name}{kind}_{k}.composite.png")
            label = f"{name}{kind}_{k}"
            files[f"painting {label}"] = p
            files[f"composite {label}"] = out / f"{label}.composite.png"
            cands.append({"label": label, "file": p.name, "input": name + kind, "seed": seed, "raw": raw, "comp": comp,
                          **check_candidate(raw, d, P, sun, model)})
    det = detector(files, out)
    for c in cands:
        hits = {t: sum(det["by_image"][f"{w} {c['label']}"][t] for w in ("painting", "composite")) for t in ("vehicles", "people")}
        c.update(K4_vehicles=hits["vehicles"], K4_people=hits["people"], K4_ok=not any(hits.values()))
        c["pass"] = verdict(c)
    passing = [c for c in cands if c["pass"]]
    best = max(passing, key=lambda c: (c["detail_share"], -c["K3_worst"]))["label"] if passing else None
    timing = json.loads((painted / "timing.json").read_text()) if (painted / "timing.json").exists() else {}
    res = {"job": job, "run": run or "current", "landmark": name, "source": str(src), "frame_px": d["meta"]["frame_px"],
           "opening_px": int(d["mask"].sum()),
           "prompt": PROMPT_RUN1 if run == "run1" else PROMPTS[name], "thresholds": {k: P[k] for k in ("cutaway_mask_cover", "cutaway_shadow_lum_tol", "cutaway_shadow_min_px",
                                                                     "cutaway_line_px", "cutaway_line_share", "cutaway_line_min_step")},
           "own_tolerances": {"paper_rgb": PAPER_TOL, "blank_patch_px": BLANK_MIN_PX, "changed_lum": CHANGE_LUM,
                              "interior_painted": "changed_share >= 0.25 and detail_share >= 0.05",
                              "light_block_px": LIGHT_BLOCK, "light_block_step_px": LIGHT_STEP, "light_same_material_chroma": LIGHT_CHROMA,
                              "light_block_material_share": LIGHT_SHARE, "light_lit_level_percentile": LIGHT_PCT,
                              "K3_measured_on": "each face's own material: chroma within 0.03 of the face's light pixels, "
                                                "not ink (darker than a neighbour by cutaway_line_min_step)",
                              "lines_kept_gate": "the section's lines (interior_lines.section_kept); the placeholder's are reported"},
           "K1a_of_the_render_as_built": base_line,
           "K4": {t: {"images": det[t]["images"], "max_score": det[t]["max_score"], "detections": det[t]["detections"]} for t in ("vehicles", "people")},
           "K4_inputs_ok": not any(v for lab, hit in det["by_image"].items() if lab.startswith("input") for v in hit.values()),
           "candidates": [{k: v for k, v in c.items() if k not in ("raw", "comp")} for c in cands],
           "passing": [c["label"] for c in passing], "best": best, "timing": timing}
    (out / f"{job}.json").write_text(json.dumps(res, indent=1))
    if write_docs:
        res["images"] = sheets(name, d, inputs, cands, V2 / "docs" / "img", run)
        (V2 / "docs" / "results" / f"cutaway_{tag}.json").write_text(json.dumps(res, indent=1))
    return res


def adopt(job: str = "K1", name: str = "cathedral", label: str | None = None, dst: Path | None = None) -> dict:
    """Hand a candidate that passed to the cutaway layer: the painting cut to the opening mask, with its checks,
    into v2/data/structures/cutaway_paintings (layers/cutaways.py reads it at the next build of layer_cutaways, whose
    gates K1-K6 then run on the painted tiles). Refused unless the job's last check lists the candidate as passing:
    the placeholder stays until a painting passes."""
    from v2.layers import cutaways as cw
    f = base() / "checks" / f"{job}.json"
    if not f.exists():
        raise SystemExit(f"{job}: not checked yet (python -m v2.bakeoff check {job})")
    res = json.loads(f.read_text())
    label = label or res["best"]
    if label is None or label not in res["passing"]:
        raise SystemExit(f"{job}: {label or 'no candidate'} did not pass its checks; the placeholder stays "
                         f"(passing: {res['passing'] or 'none'})")
    c = next(c for c in res["candidates"] if c["label"] == label)
    d = load(Path(res["source"]), name)
    raw = np.asarray(Image.open(base() / "painted" / c["file"]).convert("RGB"))
    return cw.write_painting(Path(dst) if dst else cw.PAINTINGS, name, raw, d["mask"], d["meta"]["frame_px"],
                             {"job": job, "candidate": label, "seed": c["seed"], "input": c["input"], "pass": c["pass"],
                              "checks": {k: v for k, v in c.items() if k not in ("label", "file", "input", "seed", "pass")}})
