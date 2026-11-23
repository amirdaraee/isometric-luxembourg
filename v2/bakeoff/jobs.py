"""The paid jobs of bake-off methods B and C, with their quotes (PLAN_V2 sections 7 and 10, principle 8).

Every job here costs money, so none runs without the ledger: `python -m v2.bakeoff run <job>` calls
Ledger.authorise(<its quote>) first (refused unless the owner approved it and it fits the goal's cap), then checks
the provider's live price is not above the quoted one, then starts the job with a hard time cap (the pod is stopped
by its own watchdog at cap_h, so the cost can never pass cap_h x price).

Prices were read with read-only API calls on 9 Nov 2026 (v2/docs/results/prices_2026-11-09.json). Times are
estimates from v1's measurements (pipeline/gpu_train/NOTES.md: ai-toolkit on an H100, 2.94 s per training step at
1024 px, rank 16) and the model's published speed; each pilot measures them before the rest runs.
"""
from __future__ import annotations

from dataclasses import dataclass, field

GOAL = "phase2_bakeoff"

# RunPod community cloud, 1 GPU, on-demand, read 9 Nov 2026 (GraphQL gpuTypes.communityPrice / securePrice). The
# A100 SXM's secure price was read again on 13 Nov 2026: 2.19 (it was 1.79 on 9 and 10 Nov, the price q0014 ran at)
PRICES = {
    "runpod": {"H100 SXM": {"community": 2.69, "secure": 3.99}, "H100 PCIe": {"community": 1.99, "secure": 2.89},
               "A100 SXM": {"community": 1.39, "secure": 2.19}, "H200 SXM": {"community": 3.59, "secure": 5.29},
               "L40S": {"community": 0.79, "secure": 1.09}},
    "modal": {"H100": 3.95, "H200": 4.54, "A100 80GB": 2.50, "L40S": 1.95},
    # OpenAI image tokens (USD per 1M): gpt-image-2 output 30.00, input 8.00; a 1024 x 1024 "high" image is ~4,160
    # output tokens (~$0.125), "medium" ~1,056 (~$0.032)
    "openai": {"gpt-image-2": {"out_per_m": 30.0, "in_per_m": 8.0}},
}

QWEN_EDIT = "Qwen/Qwen-Image-Edit-2511"
QWEN_T2I = "Qwen/Qwen-Image"
LIGHTNING = "lightx2v/Qwen-Image-Edit-2511-Lightning (8 steps)"
INK_V1 = "luxembourg-ink-v2 (v1 style LoRA, rank 16; HF amirdaraee/isometric-ink-style)"
C_STOPPED = ("stopped by the owner on 10 Nov 2026 after C's pilot failed its checks (shadows, window rows); its "
             "approval was released in the ledger")
SETUP_H = 0.3          # pod start, models from Hugging Face (~40 GB each) and the LoRA; v1 saw 15-25 min


@dataclass
class Job:
    id: str
    method: str                  # "b" or "c"
    title: str
    provider: str
    gpu: str
    est_h: float                 # expected GPU hours, setup included
    cap_h: float                 # hard time cap (the watchdog stops the pod)
    work: str                    # images or steps
    model: str
    pilot_of: str | None = None  # this job is the <= 10% pilot of that batch
    after: tuple = ()            # jobs (and gates) that must be done first
    inputs: str = ""
    outputs: str = ""
    notes: list = field(default_factory=list)
    price_read: str = "2026-11-09"   # the day the quoted price was read
    cancelled: str = ""              # set when the owner stopped this job for good: it never runs (runner.authorise)
    goal: str = GOAL                 # the ledger's budget line the job is paid from
    cloud: str = "community"         # RunPod's cloud the pod is created on: "community" or "secure" (priced apart)

    @property
    def price_h(self):
        return PRICES["runpod"][self.gpu][self.cloud]

    @property
    def est_usd(self):
        return round(self.est_h * self.price_h, 2)

    @property
    def worst_usd(self):
        return round(self.cap_h * self.price_h, 2)

    def ledger_job(self):
        return f"{self.id}: {self.title}"

    def ledger_note(self):
        return (f"{self.provider} {self.gpu} {self.cloud} ${self.price_h}/h (read {self.price_read}); est {self.est_h} h = "
                f"${self.est_usd}; hard cap {self.cap_h} h = ${self.worst_usd}; {self.work}; model {self.model}"
                + (f"; pilot of {self.pilot_of}" if self.pilot_of else "")
                + "".join(f"; {n}" for n in self.notes if n.startswith("rerun")))


JOBS = [
    # ------------------------------------------------------------------ B: code + AI materials and landmark portraits
    Job("B1", "b", "material library (roofs, walls, windows, doors, shop fronts)", "runpod", "H100 SXM",
        est_h=SETUP_H + 0.42, cap_h=0.77, price_read="2026-11-10",
        work="25 materials x 3 candidates = 75 images, 1024 x 1024, 30 steps (~20 s each)",
        model=QWEN_T2I,
        inputs="v2/bakeoff/prompts.py MATERIALS (front-on, tileable, evenly lit, no shadows, palette reference)",
        outputs="<data>/v2/test/bakeoff/b/materials/<name>_<k>.png; one picked per material (python -m v2.bakeoff pick b; picked.json is the owner's to change)",
        notes=["text to image, no style LoRA needed: the ink comes from A's code outlines over the materials",
               "every image through the no-shadow (flat-light) and no-car checks before it is used",
               "rerun: the first run (q0001, cap 0.9 h = $2.42) failed at setup after $0.24 and the second (q0009, "
               "cap 0.8 h = $2.15, owner 10 Nov 2026) after $0.05, both with no image; this quote's cap of 0.77 h "
               "($2.07) keeps the second and third together within q0009's worst case"]),
    Job("B2", "b", "test-area landmark portraits, cut to their 3D outline", "runpod", "H100 SXM",
        est_h=SETUP_H + 0.25, cap_h=0.7,
        work="38 landmarks on a building x 2 candidates = 76 images, 1024 x 1024, 8 steps (Lightning, ~12 s each)",
        model=f"{QWEN_EDIT} + {LIGHTNING} + {INK_V1}",
        inputs="unlit renders of each landmark (python -m v2.bakeoff inputs b): flat colours, outlines, windows",
        outputs="<data>/v2/test/bakeoff/b/landmarks/<building id>_<k>.png",
        notes=["v1's ink LoRA was trained on shadowed drawings: the prompt asks for even light and every portrait "
               "must pass L5.1 (shadow detector) or it is not used; if C's unshadowed LoRA exists first, B2 uses it"]),
    # ------------------------------------------------------------------ C: code + AI-painted buildings
    Job("C1p", "c", "training targets, pilot (10%)", "runpod", "H100 SXM",
        est_h=SETUP_H + 0.05, cap_h=0.45, pilot_of="C1",
        work="8 crops x 2 = 16 paintings, 1024 x 1024, 8 steps (~10 s each)",
        model=f"{QWEN_EDIT} + {LIGHTNING} + {INK_V1}",
        inputs="unlit training crops (python -m v2.bakeoff inputs c)",
        outputs="<data>/v2/test/bakeoff/c/targets/", notes=["measures s/image; sets the cap of C1"]),
    Job("C1", "c", "training targets for the unshadowed style LoRA", "runpod", "H100 SXM",
        est_h=SETUP_H + 0.4, cap_h=0.8, after=("C1p",), cancelled=C_STOPPED,
        work="72 crops x 2 = 144 paintings, 1024 x 1024, 8 steps (~10 s each)",
        model=f"{QWEN_EDIT} + {LIGHTNING} + {INK_V1}",
        inputs="unlit training crops (v2 test area and a few commune blocks outside it)",
        outputs="<data>/v2/test/bakeoff/c/targets/; kept only if they pass the shadow and car checks (dataset.py)"),
    Job("C2p", "c", "unshadowed style LoRA training, pilot (first 200 steps)", "runpod", "H100 SXM",
        est_h=SETUP_H + 0.17, cap_h=0.55, pilot_of="C2", after=("C1",), cancelled=C_STOPPED,
        work="200 of 2,000 steps, rank 16, 1024 px, ai-toolkit (v1: 2.94 s/step on an H100)",
        model=f"{QWEN_EDIT} (ai-toolkit qwen_image_edit, rank 16, lr 1e-4)",
        inputs="the filtered dataset (>= 60 pairs: unlit render + layout -> unshadowed ink painting)",
        outputs="checkpoint at step 200 + samples; measures s/step", notes=["resumable: C2 continues from it"]),
    Job("C2", "c", "unshadowed style LoRA training, the rest", "runpod", "H100 SXM",
        est_h=SETUP_H + 1.32, cap_h=1.75, after=("C2p",), cancelled=C_STOPPED,
        work="steps 200-2,000 (1,800 x 2.94 s)", model=f"{QWEN_EDIT} (ai-toolkit)",
        outputs="luxembourg-ink-unshadowed (rank 16) on HF amirdaraee/isometric-ink-style; samples every 250 steps"),
    Job("C3", "c", "paint the test area's buildings from unlit renders", "runpod", "H100 SXM",
        est_h=SETUP_H + 0.3, cap_h=0.8, after=("C2",), cancelled=C_STOPPED,
        work="107 windows of 1024 x 1024 at 0.125 m/px (189 building tiles, stride 768), 8 steps (~10 s each)",
        model=f"{QWEN_EDIT} + {LIGHTNING} + luxembourg-ink-unshadowed",
        inputs="unlit renders of layers 5-6 (python -m v2.bakeoff inputs c)",
        outputs="<data>/v2/test/bakeoff/c/painted/<window>.png -> compose.py cuts each to the mesh"),
    Job("C4", "c", "facade front-on trial: paint ~10 buildings' facades flat, project them onto their 3D walls",
        "runpod", "H100 SXM", est_h=0.3, cap_h=0.32, price_read="2026-11-10",
        work="10 buildings, 25 camera-facing facades x 2 = 50 paintings, 8 steps (13.4 s each, measured in C1p)",
        model=f"{QWEN_EDIT} + {LIGHTNING} + {INK_V1}",
        inputs="front-on elevation renders of each facade (facade layout, flat colours)",
        outputs="<data>/v2/test/bakeoff/c/facades/ -> a small C4 build of the ten buildings (python -m v2.bakeoff trial)",
        notes=["owner, 10 Nov 2026: runs on its own with v1's style model, since C2 never trained the unshadowed "
               "one (if that model ever exists, C4 uses it)",
               "rerun: the first run (q0008, cap 0.35 h = $0.94) failed at setup after $0.06 with no painting; this "
               "quote's cap of 0.32 h ($0.86) keeps both together within q0008's worst case",
               "best run on the pod of the job before it (--on), so its cap is not spent starting a pod"]),
]

# Phase 3, landmark cutaways (specs/landmark-cutaways.md rule 6: one landmark first). Paid from the Phase 3 line, not
# part of the bake-off's total, so not in JOBS. The title is the ledger's quote q0012 word for word (runner.quote_of
# finds a job's quote by it).
CUTAWAY_GOAL = "phase3_lock_look"
# K1's first run (q0014, pod 0r548l7stsvho6, an A100 SXM of the secure cloud, 10 Nov 2026), in seconds, from its log
# and the pod's own. Its cap of 0.25 h ended it after the third of four paintings: the first quote had taken Phase
# 2's 4 minutes of setup on a pod that already held the model.
K1_MEASURED_S = {
    "pod created to ssh": 128,
    "preflight, bundle and style model upload (the setup runs meanwhile)": 62,
    "setup after that: python env, the 56 GB model and the Lightning model from Hugging Face (353 s in all)": 307,
    "painter start and model load into the GPU (267 s)": 289,
    "4 paintings x 23 s": 92,
    "results and logs back, spend recorded, pod terminated": 30,
}                                                        # 908 s = 15.1 min
CUTAWAY_JOBS = [
    Job("K1", "cutaway", "cutaway interior of Notre-Dame Cathedral (the first, proved alone): 1 view of 1024 x 1024 px "
        "x 4 candidates, painted from the unlit cut render inside its opening mask", "runpod", "A100 SXM",
        est_h=0.26, cap_h=0.45, price_read="2026-11-13", goal=CUTAWAY_GOAL, cloud="secure",
        work="1 view x 4 candidates = 4 paintings, 1024 x 1024, 8 steps (Lightning)",
        model=f"{QWEN_EDIT} + {LIGHTNING} + {INK_V1}",
        inputs="the cathedral's paint inputs of stage layer_cutaways (python -m v2.bakeoff inputs cutaway)",
        outputs="<data>/v2/test/bakeoff/cutaways/painted/<input>_<k>.png -> python -m v2.bakeoff check K1",
        notes=["v1's style model: method A won the bake-off, so no other style model was trained",
               "two candidates from the cut render as built, two from the same render with the inside faces' flat "
               "placeholder colours cleared to paper (its ink lines and its section kept); four seeds",
               "the first run was on an A100 SXM of the secure cloud because no H100 was free on the community "
               "cloud on 10 Nov 2026 (owner: 'A100 SXM, secure (Recommended)'); the second is quoted on the same",
               "rerun, the second cathedral run: the first (q0014, 0.4256 USD) was stopped by its 0.25 h cap after 3 "
               "of 4 paintings and none passed its checks. Time plan from that run's measured times: 128 s to ssh, "
               "62 s preflight and uploads, 307 s more of setup (56 GB model download), 289 s model load, 4 x 23 s "
               "painting, 30 s results back and terminate = 908 s (15.1 min), so est 0.26 h; the cap of 0.45 h "
               "(27 min) leaves 11 min, 75 percent over, for a slower download or model load. New for this run "
               "(all tested at 0 USD): the prompt asks for flat even light inside, no cast shadows and no dark "
               "floor; four different seeds; the checks measure light on one material and coverage by blank "
               "patches. Not approved; needs the owner's OK"]),
]

# Phase 3, the detail-transfer trial (detail.py): six blocks painted again by v1's style model from what it was
# trained on (v1's photo-textured capture and a line guide, here v2's own), at v1's scale and at v2's. Paid from the
# Phase 3 line. Times are K1's second run's (q0015, pod 1zj2z6jzs0dz39, the same GPU and cloud): 761 s in all for 4
# paintings at 23 s, so 639 s of start, setup, model load and return.
T1_PAINTINGS = 24
T1_PLAN_S = {"pod start, setup, model load, results back and terminate (K1's second run: 761 s less its 4 paintings)": 669,
             "24 paintings x 23 s": 552}                                  # 1,221 s = 20.4 min
TRIAL_JOBS = [
    Job("T1", "detail", "detail-transfer trial: six blocks of the test area painted from v1's capture and v2's line "
        "layout, at 0.25 m and at 0.125 m per model pixel, 2 candidates each", "runpod", "A100 SXM",
        est_h=0.34, cap_h=0.5, price_read="2026-11-21", goal=CUTAWAY_GOAL, cloud="secure",
        work="6 blocks x 2 scales x 2 candidates = 24 paintings, 1024 x 1024, 8 steps (Lightning)",
        model=f"{QWEN_EDIT} + {LIGHTNING} + {INK_V1}",
        inputs="python -m v2.bakeoff inputs detail: control 1 = v1's capture (photo-textured buildings on the "
               "orthophoto), control 2 = v2's line layout; v1's own prompt, as trained",
        outputs="<data>/v2/test/bakeoff/detail/painted/<block>_<scale>_<k>.png -> python -m v2.bakeoff detail --source T1",
        notes=["a painting is never shown as it is: detail.py takes each building's wall and roof colour and its "
               "fine texture from it and keeps the code art's shape, lines, windows and evenness",
               "the same steps ran at 0 USD on v1's finished art (python -m v2.bakeoff detail): PHASE3_REPORT.md section 12",
               "the same GPU and cloud as K1's two runs; time plan from the second: 669 s around the painting + 24 x "
               "23 s = 1,221 s (20.4 min), est 0.34 h; the cap of 0.5 h (30 min) leaves 9.6 min for a slower "
               "download or model load"]),
]
# T1 as it ran (q0016, pod sk3bylykkbwscf, 21 Nov 2026): 1,153 s in all, 24 paintings at 20.9 s, model load 269 s.
T1_MEASURED_S = 1153
TRIAL_JOBS.append(
    Job("T2", "detail", "even-light repaint: T1's six blocks, inputs and seeds painted again with the prompt asking "
        "for flat even light and no shadows", "runpod", "A100 SXM",
        est_h=0.33, cap_h=0.5, price_read="2026-11-21", goal=CUTAWAY_GOAL, cloud="secure",
        work="6 blocks x 2 scales x 2 candidates = 24 paintings, 1024 x 1024, 8 steps (Lightning)",
        model=f"{QWEN_EDIT} + {LIGHTNING} + {INK_V1}",
        inputs="T1's own (python -m v2.bakeoff inputs detail) and T1's seeds: only the prompt differs, v1's caption "
               "with the even-light sentence (prompts.C_TARGET_PROMPT)",
        outputs="<data>/v2/test/bakeoff/detail/painted_even/<block>_<scale>_<k>.png -> python -m v2.bakeoff detail --source T2",
        notes=["one thing changed against T1, the prompt, so each painting has T1's as its pair: whether the model "
               "leaves the light out when asked, given the input it was trained on (Phase 2's pilot asked the same "
               "of the plain code render)",
               "time plan: T1's measured 1,153 s (19.2 min) on the same GPU and cloud, est 0.33 h; the cap of 0.5 h "
               "(30 min) leaves 10.8 min"]))
# T2 as it ran (q0017, pod 27w1mnmuztvx36, 22 Nov 2026): 1,087 s in all, 24 paintings at 17.7 s.
T2_MEASURED_S = 1087
TRIAL_JOBS.append(
    Job("T3", "detail", "evened-input repaint: T2's six blocks, layouts, prompt and seeds, with the photo's light "
        "taken down in the capture the model paints from", "runpod", "A100 SXM",
        est_h=0.31, cap_h=0.5, price_read="2026-11-22", goal=CUTAWAY_GOAL, cloud="secure",
        work="6 blocks x 2 scales x 2 candidates = 24 paintings, 1024 x 1024, 8 steps (Lightning)",
        model=f"{QWEN_EDIT} + {LIGHTNING} + {INK_V1}",
        inputs="python -m v2.bakeoff inputs even: control 1 = v1's capture with shaded faces and ground shadows "
               "raised (detail.even_capture); control 2, the prompt (prompts.C_TARGET_PROMPT) and the seeds are T2's",
        outputs="<data>/v2/test/bakeoff/detail/painted_evenin/<block>_<scale>_<k>.png -> python -m v2.bakeoff detail --source T3",
        notes=["one thing changed against T2, the first control image, so each painting has T2's as its pair: T2 "
               "showed the prompt does not move the light; this asks whether the input does",
               "time plan: T2's measured 1,087 s (18.1 min) on the same GPU and cloud, est 0.31 h; the cap of 0.5 h "
               "(30 min) leaves 11.9 min"]))
# T3 as it ran (q0018, pod qi53z00a2kt5yf, 22 Nov 2026): 1,172 s in all.
T3_MEASURED_S = 1172
# The whole test area (the plan's step 5, PHASE3_REPORT.md section 18.3): every window of the grid painted as T1
# painted its six blocks. Times are T1's to T3's on the same GPU and cloud: 651 to 668 s around their 24 paintings,
# 17.7 to 20.9 s a painting.
T4_PAINTINGS = 101                                      # of the grid's 109 windows; 8 lie outside the area
T4_PLAN_S = {"pod start, setup, model load, results back and terminate (T1 to T3: 651 to 668 s)": 669,
             "101 paintings x 21 s (T1's 20.9 s, the slowest of the three runs)": 2121,
             "the paintings copied back while it runs": 30}                # 2,820 s = 47.0 min
TRIAL_JOBS.append(
    Job("T4", "detail", "the test area painted: every window of its grid (1024 px at 0.125 m, stride 768) from v1's "
        "capture and v2's line layout, as T1 painted the six blocks, 1 painting each", "runpod", "A100 SXM",
        est_h=0.79, cap_h=1.0, price_read="2026-11-23", goal=CUTAWAY_GOAL, cloud="secure",
        work="101 windows x 1 = 101 paintings, 1024 x 1024, 8 steps (Lightning)",
        model=f"{QWEN_EDIT} + {LIGHTNING} + {INK_V1}",
        inputs="python -m v2.bakeoff inputs area: control 1 = v1's capture enlarged to v2's scale, control 2 = v2's "
               "line layout; v1's own prompt, as trained (T1's)",
        outputs="<data>/v2/test/bakeoff/detail/painted_area/w<x0>_<y0>.png -> python -m v2.bakeoff targets --source T4",
        notes=["a painting is never shown as it is (the owner, 22 Nov 2026: the model's details, painted surfaces): "
               "it gives each building its colour and the texture of its plain surfaces; every window, dormer, "
               "line and the light are the model's",
               "the whole route was run first at 0 USD on the same grid with v1's finished art in the paintings' "
               "place (python -m v2.bakeoff targets --source area_free)",
               "time plan: 669 s around the painting + 101 x 21 s + 30 s = 2,820 s (47.0 min), est 0.79 h; the cap "
               "of 1.0 h (60 min) leaves 13 min. Paintings come back as they are made and the painter skips what "
               "exists, so a run cut by the cap keeps what it painted"]))

BY_ID = {j.id: j for j in JOBS + CUTAWAY_JOBS + TRIAL_JOBS}

# Phase 2's estimate of all four cutaways together (PHASE2_QUOTE.md); the quotes that followed are CUTAWAY_JOBS
PHASE3_CUTAWAYS = Job("P3-K", "c", "landmark cutaways: cathedral, palace, abbey, casemates (Phase 3)", "runpod", "H100 SXM",
                      est_h=SETUP_H + 0.15, cap_h=0.7,
                      work="4 landmarks x 2 views x 4 candidates = 32 paintings, 1024 x 1024, 8 steps",
                      model=f"{QWEN_EDIT} + {LIGHTNING} + the winning style LoRA")


def totals(method=None):
    js = [j for j in JOBS if method is None or j.method == method]
    return round(sum(j.est_usd for j in js), 2), round(sum(j.worst_usd for j in js), 2)


def batch_ok():
    """Principle 7 / ledger rule 5: a batch whose worst case is over $5 has a pilot of <= 10% quoted separately."""
    bad = []
    for j in JOBS:
        if j.pilot_of:
            continue
        pilots = [p for p in JOBS if p.pilot_of == j.id]
        if j.worst_usd > 5.0 and not pilots:
            bad.append(j.id)
    return bad
