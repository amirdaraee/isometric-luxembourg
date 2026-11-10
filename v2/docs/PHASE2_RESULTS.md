# v2 Phase 2 results: the bake-off (A, B, C4)

10 November 2026, second round. Branch `v2-bakeoff2`, into `v2`. The first round (A, a thin B, C's failed pilot) is
in git history; its numbers that still hold are repeated here.

## 1. The short version

- **Spent on the bake-off: $3.72** of the $17 cap. Reconciled with RunPod: its balance fell by $3.7142, the ledger
  has $3.7160. Nothing is committed any more.
- **A (all code)** is rebuilt with the new lighting and passes every gate (50 of 50 stages).
- **B (code + AI)** now has its AI materials, and it **fails the no-baked-shadows gate** (48 of 50 stages). It also
  looks worse than A: the AI roof and wall swatches repeat as visible grids.
- **C4 (facades painted front-on): straight lines survived. It does not look richer than A; it looks plainer.**
- **Lighting:** golden hour and night are fixed in the viewer's light pass. Day is unchanged, pixel for pixel.
- C1, C2p, C2 and C3 stay stopped. Their approvals are released in the ledger.
- No pod is left. The pod `luxembourgish-asr-pilot` was not touched.

## 2. What ran and what it cost

All jobs ran through `python -m v2.bakeoff run <job> --go`. Every pod was an H100 NVL at **$2.59 an hour**, under
the quoted $2.69 (the same chip, cheaper listing, as the owner allowed).

| Job | Quote | Worst case | Spent | Time | Result |
|---|---|---|---|---|---|
| B1 materials | q0001 | $2.42 | $0.24 | 5.5 min | 9 Nov. Failed at setup (driver too old for the pinned torch). No image. |
| C1p pilot | q0003 | $1.21 | $0.80 | 18.3 min | 9 Nov. 16 paintings, 2 pass. **C stopped.** |
| B2 landmark portraits | q0002 | $1.88 | $0.76 | 17.5 min | 9 Nov. 74 portraits; 13 landmarks have one that passes. |
| B1 materials, rerun | q0009 | $2.15 | $0.05 | 1.3 min | 10 Nov. Failed at setup (see below). No image. |
| C4 facade trial | q0008 | $0.94 | $0.06 | 1.5 min | 10 Nov. Same pod, same fault. No painting. |
| **B1 materials, second rerun** | q0010 | $2.07 | **$1.16** | 26.5 min | 10 Nov. **75 images** (25 materials × 3), 18.9 s each. |
| **C4 facade trial, rerun** | q0011 | $0.86 | **$0.64** | 14.8 min | 10 Nov. **50 paintings** (25 facades × 2), 12.9 s each. |
| C1, C2p, C2, C3 | q0004–q0007 | $10.49 | $0 | | Released by the owner. They cannot run. |
| **Total** | | | **$3.72** | | |

- **Measured:** each job's seconds on its pod × (the pod's price + its disk, $0.02 an hour), on the laptop's clock.
- **Reconciled:** RunPod's balance was $18.9778 before the first pod and $15.2637 after the last: $3.7142, against
  the ledger's $3.7160. RunPod's per-pod billing lines listed $3.38 when I checked and were still being published,
  so the balance is the figure used. `python -m v2.bakeoff reconcile` shows the lines later.
- **Pods:** four were created here (`7hmguf56fayepx`, `xqxfvi0ljnfl0o`, `yjvb0l3v6a142q`, `ae85o8cf3q1dyo`). All are
  terminated and RunPod lists none of them (`python -m v2.bakeoff pods`).

**The two failed starts of 10 November ($0.12).**
- The new first-minute check passed. One step later the pod's Python environment failed to build: the setup
  script tested one package (torchvision) before another it needs (numpy) was installed. Yesterday's fix had only
  run on a pod that already had numpy.
- My driver script then started C4 on the same pod, which hit the same fault. That was my mistake: stopping after
  B1 would have let me fix the script and restart B1 on its own quote.
- Both quotes were used up, so I asked the owner. Two new quotes (q0010, q0011) were approved: "Approve both".
- Fixed for good: the setup script installs numpy first, and the runner now holds a pod for 7 minutes when a job
  fails with nothing made, so the same job can restart in place on the same quote.

## 3. Gates

Thresholds are the build's own. None was changed.

| Brief | A | B | C4 (the ten trial buildings) |
|---|---|---|---|
| G1 suite | **pass**, 50 of 50 stages | **fail**, 48 of 50 (the shadow check; the G1 report is skipped after it) | not a full build: A's release with the trial buildings' tiles drawn again |
| #5 No baked shadows | **pass**, 0 materials over 5%; worst 4.97% | **fail**: 11 of 244 materials over 5% | see below |
| #6 Line score, building edges (95%) | **98.05%** | **98.49%** | **98.98%** (A on the same buildings: 98.96%) |
| #6 Line score, window rows (95%) | **99.30%** | **99.44%** | **100%** (A: 99.82%) |
| #9 No cars | **pass**, 0 detections | **pass**, 0 detections | **pass**, 0 on the 50 paintings |
| Seams | **pass**, 0.0 on layers 5–7 | **pass**, 0.0 on layers 5–7 | not measured |

- A: `v2/docs/results/g1_test_a.json`. B: `v2/docs/results/bakeoff_b_gates.json` (from the build's check stages;
  there is no `g1_test_b.json` because the G1 report did not run). C4: `v2/docs/results/bakeoff_c4.json`.

**Why B fails #5.** The check compares each material's brightness inside and outside where a shadow would fall.
A's patterns are even, so the two agree. The AI swatches have large light and dark patches (pale joints between
dark slates, grid lines on walls), so parts of one roof or wall differ by far more than 5%. It is uneven tone
rather than a painted shadow, but the gate is right to fail it: such a surface cannot be lit cleanly by code.

**C4 and shadows, three ways.**
- Light across each painting (left half against right, top against bottom): 47 of 50 are within 5%. 3 are not
  (two seeds of one facade, and one other).
- Between the painted walls of one building: worst 0.4%. Pass.
- Over each whole building: 1 of 10 is over 5% (19.8%). This is the trial's own doing, not a shadow: its drawings
  gave every wall the same cream, and that building's unpainted walls keep A's colour.

## 4. How they look

Previews are in `v2/docs/img/`: `test_<a|b>_<view>.jpg`, the sheet `test_bakeoff_compare.jpg` (A beside B at six
views), `test_c4_trial.jpg` and `test_c4_trial_buildings.jpg` (A beside C4), `test_lighting_before_after.jpg`.

**A, all code.** Pastel facades, slate and tile roofs, framed windows, shutters, shop awnings, rounded trees. Still
the most detailed and the cleanest of the three.

**B, code + AI materials.** Worse than A as built.
- 15 of the 25 materials passed their checks. The code draws 11 of them: one roof (dark slate), six wall colours,
  the casement window, the panel door, the garage door and the shop front.
- **Roofs:** the picked dark slate swatch has a pale border, so every dark-slate roof shows a white grid. See
  `test_b_facades.jpg`. The other four roof swatches were the wrong colour and were not used, so those roofs are A's.
- **Walls:** the model answered "lime-rendered wall" with tiled grids in strong colours (cyan, lime, hot pink).
  The ones near the palette were used, and they read as tinted graph paper. Blue, yellow and stone walls are A's.
- **Windows and doors:** the swatches are good drawings on their own, but at map scale a window is about 9 pixels
  wide and they add little.
- The 13 landmark portraits are as before: plainer than A's version of the same building.
- B's trees are now A's leaf-clump crowns.
- I added one rule before picking, and it is stricter, not looser: a surface swatch must be within 45 (RGB
  distance) of the palette colour it was asked for. Without it the cyan wall would have been used for blue houses.

**C4, facades painted front-on.**
- The model returned each facade almost as it was given: a cream wall with dark windows, sometimes with a window
  frame or glazing bars added. Nothing like v1's texture.
- On the map the trial buildings lose what A draws (wall colour, shutters, window frames, plinth, cornices) and
  gain nothing. See `test_c4_trial.jpg`.
- So the method works mechanically, and v1's style model gives it nothing to project.

**Lighting, before and after** (`test_lighting_before_after.jpg`).
- **Golden hour:** was dim and grey-green. Now warm and bright: an orange sun, warm sky light at 1.5 times day's,
  a fill light from the sky opposite the sun so shaded walls keep their shape, and shadows that fade with distance
  from what casts them.
- **Night:** was near black with dots of light. Now a deep blue with every building readable: moonlight from one
  side with soft cast shadows, a warm halo round each lit window, larger and stronger lamps.
- **Day:** unchanged. I rendered the Grund view at 09:00, 13:00 and 16:00 with the old and the new code: at most 3
  pixels of 1.2 million differ, by 1 of 255.
- Nothing is baked: the layers are the same evenly lit art, and the change is in `v2/config/light.json` and the
  viewer's light pass. Specs: `layer-09-light.md` rules 3–7, `layer-10-night.md` rule 4.

## 5. Strengths and weaknesses

| | Strengths | Weaknesses |
|---|---|---|
| **A** | Passes everything. Costs $0, also for the whole city. Lines are exact. The most detail. | Looks generated: every house follows the same rules. |
| **B** | Lines stay exact. Windows and doors as swatches are attractive up close. | Fails #5. Roof and wall swatches repeat as grids and miss the palette. Needs a different material recipe, not just a rerun. |
| **C4** | Lines are straight by construction: 100% of window rows. No cars. | Adds no richness with v1's model. Each wall is painted alone, so a building's walls need a shared colour. |

A short note, not a pitch: on this evidence A is still ahead. Both AI routes now run end to end and pass the line
score, and neither made the map richer.

## 6. Open questions

1. **B's materials.** Should I try another recipe (a prompt that names the exact colour and forbids borders, and a
   check that a swatch tiles without a seam), or stop B here? A rerun would need a new quote of about $2.
2. **C4.** It needs a model that adds detail to a flat facade. The untrained unshadowed model was meant for that,
   and C2 is stopped. Leave C4 here?
3. **The colour rule for materials** (within 45 of the palette colour). I added it on seeing the first library. Keep
   it, or set another limit?
4. **`current.json`.** A build of B or C moves `release/current.json` to its own release, and a later A build that
   is already up to date does not move it back. I set it back to A by hand. Should the build do that itself?
5. **Night's moon** is drawn at a fixed place in the sky (south-south-west, 40° up), not the real moon's. Fine?

## 7. How to look

```sh
ISOLUX_DATA=/Users/amirdaraee/00/projects/isometric-luxembourg/data \
  .venv/bin/python -m v2.view test --bakeoff --port 5175
# open http://localhost:5175/bakeoff.html   (Ctrl-C stops it)
```

- The page shows A, B, C (pilot) and C4 side by side at the same view, hour and season.
- Four views named "C4 facade trial" show its buildings. Outside them the C4 column is method A.
- `data/v2/test/release/current.json` points at A's final build (`2163b3d26525`).
