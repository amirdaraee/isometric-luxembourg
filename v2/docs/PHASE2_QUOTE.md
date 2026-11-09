# Phase 2 quote: bake-off methods B and C

9 November 2026. Nothing here has been spent: every line below is a `quote` event in the ledger
(`v2/ledger/spend.jsonl`, goal `phase2_bakeoff`, cap $17) and none is approved. Each job runs only after you approve
its quote; `python -m v2.bakeoff run <job> --go` refuses otherwise (`Ledger.authorise`). It also refuses if the GPU's
price has gone up since this quote, or if the job before it has not finished. Method A cost $0 and is built.

## The short version

- **Expected cost: $14.14. Worst case: $16.94**, which fits the $17 bake-off cap. Every job has a hard time cap, and
  the pod stops itself at that cap.
- **B** (AI materials and landmark portraits): about **$3.42** expected, **$4.30** worst case.
- **C** (AI-painted buildings, with a new style model trained without shadows): about **$10.72** expected,
  **$12.64** worst case.
- Every job runs on **RunPod, community cloud, one H100 SXM at $2.69 an hour**. I read this price from RunPod's API
  today, read-only.
  - RunPod is the cheapest place for this work:
    - Modal's H100 costs $3.95 an hour.
    - OpenAI's gpt-image-2 costs about $0.125 per high-quality image. B's 75 material images alone would cost about
      $9.40 there, against $2.02 on RunPod. So the OpenAI key is not used.
  - Prices are recorded in `v2/docs/results/prices_2026-11-09.json`.
- **Pilots run first**, even though no single batch is over $5:
  - C's training pictures: 8 of the 80 crops first (C1p).
  - C's training: the first 200 of 2,000 steps first (C2p).
  - Each pilot measures the real speed before the rest is approved.

## The table

Price: RunPod community H100 SXM, **$2.69 an hour** (read 9 Nov 2026). "Setup" means starting the pod and
downloading the models, about 0.3 h, included in each job's time.

| Job | What it makes | Model | Work | Est. time | Est. cost | Hard cap | Worst case |
|---|---|---|---|---|---|---|---|
| **B1** | The material library: roof slates and tiles, 8 wall renders, sandstone, plinth, 3 windows, 3 doors, cornice, quoins, viaduct stone, railing | Qwen-Image (text to image) | 25 materials × 3 candidates = 75 images, 1024 px, 30 steps (about 20 s each) | 0.72 h | $1.94 | 0.9 h | $2.42 |
| **B2** | Portraits of the test area's landmarks, cut to their 3D outline | Qwen-Image-Edit-2511 + Lightning + v1's ink LoRA | 38 landmarks × 2 = 76 images, 8 steps (about 12 s each) | 0.55 h | $1.48 | 0.7 h | $1.88 |
| **C1p** | Pilot: training pictures for C's new style model | as B2 | 8 crops × 2 = 16 paintings | 0.35 h | $0.94 | 0.45 h | $1.21 |
| **C1** | The other training pictures | as B2 | 72 crops × 2 = 144 paintings, about 10 s each | 0.70 h | $1.88 | 0.8 h | $2.15 |
| **C2p** | Pilot: train the new style model without shadows, first 200 steps | ai-toolkit, Qwen-Image-Edit-2511, rank 16 | 200 of 2,000 steps (v1 measured 2.94 s per step on an H100) | 0.47 h | $1.26 | 0.55 h | $1.48 |
| **C2** | The rest of the training | as C2p | steps 200 to 2,000 | 1.62 h | $4.36 | 1.75 h | $4.71 |
| **C3** | Paint the test area's buildings from unlit renders | Qwen-Image-Edit-2511 + Lightning + the new LoRA | 107 windows of 1024 px at 0.125 m/px, 8 steps | 0.60 h | $1.61 | 0.8 h | $2.15 |
| **C4** | Trial: paint about 10 buildings' facades front-on, then project each onto its 3D wall | as C3 | about 40 facades × 2 = 80 paintings (in C3's session) | 0.25 h | $0.67 | 0.35 h | $0.94 |
| | **Total** | | | **5.26 h** | **$14.14** | **6.3 h** | **$16.94** |

I measured the work counts from the data:
- 25 materials (`v2/bakeoff/prompts.py`).
- 38 landmarks that stand on a building in the test area, out of v1's 62 landmark cards there
  (`python -m v2.bakeoff inputs b`).
- 107 windows covering the 189 building tiles (`v2/bakeoff/inputs.py`).

The times are estimates:
- v1's measured training speed (`pipeline/gpu_train/NOTES.md`).
- v1's painting rate with the 8-step Lightning LoRA.
- 15 to 25 minutes of setup, as v1 saw.

The pilots replace these estimates with measured numbers before the larger jobs are approved.

## Order and gates

1. **B1 and B2.** They can run at once or one after the other. You then pick one material per kind, and
   `picked.json` records your choice. Every portrait must pass:
   - the shadow check (L5.1);
   - the car check (OWLv2);
   - the line score.
2. **C1p, then C1.** Each painting is kept only if it passes:
   - the flat-light check (`v2/bakeoff/dataset.py`);
   - the car check;
   - the line score.

   At least 60 pairs must pass, or C2 does not start.
3. **C2p, then C2.** The pilot's samples at step 200 are checked for shadows before the rest runs.
4. **C3 and C4.** Each window is cut to the 3D model (`v2/bakeoff/compose.py`). C must then pass every G1 check
   plus the line score, as A did. If C4's facade projection fails its line score, C falls back to C3's painting
   alone, as PLAN_V2 section 7 says.

## The training dataset for C's style model, without shadows

- **Starting point.**
  - v1's style LoRA, `luxembourg-ink-v2` (HF `amirdaraee/isometric-ink-style`, rank 16, on Qwen-Image-Edit-2511),
    is the teacher.
  - Its training drawings all had painted shadows. So C1 asks it for even light, and every result is filtered.
- **Crops.** 80 windows spread over the test area (`windows.json` → `train_crops`). Each has two control images, the
  same two that v1's style v2 used (`pipeline/gpu_train/v2/v2.yaml`):
  - the unlit render;
  - the layout image.
- **Filter.**
  - Flat light: the same material on faces turned different ways must be within 5%.
  - No vehicles: OWLv2 at 0.1.
  - Line score: at least 95% within 1 px.
- **Training.** Config `v2/bakeoff/pod/c2_train.yaml`:
  - v1's recipe;
  - new trigger: `<isometric luxembourg ink unshadowed>`;
  - 2,000 steps, a checkpoint every 200.
- **Where it goes.** The trained LoRA joins v1's on HF `amirdaraee/isometric-ink-style`.

## Phase 3 estimate (not part of this total)

**Landmark cutaways**, the first four: the cathedral, the palace, the abbey and the Bock casemates. All four are
inside the test area.
- Work: 4 × 2 views × 4 candidates = 32 paintings, plus setup.
- Same pod type: about 0.45 h, **about $1.21 expected, $1.88 worst case** (cap 0.7 h).
- This is paid from the Phase 3 line ($8 cap) and quoted in the ledger when Phase 3 starts.

**Tunnel view** is code only, so it costs $0.

## What is ready to run once you approve

Everything up to the paid call:
- the job scripts (`v2/bakeoff/pod/`);
- the prompts and lists;
- the inputs: B's landmark list, and C's 107 windows with their unlit render, layout, mask, ids and normals;
- the dataset filter;
- the composer that turns paintings into layers 5 to 7 with the 3D model's depth;
- the bake-off viewer.

To start a job:

```sh
python -m v2.bakeoff status          # each job, its quote and whether it is approved
python -m v2.ledger.ledger approve <quote id> --by owner --note "..."   # yours only
python -m v2.bakeoff run B1          # prints the pod it would start, with its watchdog
python -m v2.bakeoff run B1 --go     # authorises against the ledger and live price, then starts it
```

## Not tested

- **I could not test the paid models on this Mac.** It has 16 GB of memory and 17 GB of free disk, and
  Qwen-Image-Edit-2511 is about 40 GB. Instead, the local smoke test (`python -m v2.bakeoff smoke c`) sends a
  stand-in painting through:
  - the inputs;
  - the composer;
  - the flat-light check;
  - the cut.

  Its result is in the Phase 2 report. The first real run of the model is pilot C1p.
- **Modal's free credit.** Modal includes $30 of free compute a month on its Starter plan. If your Modal account still
  has this month's credit, running there would cost you nothing, even at Modal's higher list price. Should I move
  the quote to Modal?
