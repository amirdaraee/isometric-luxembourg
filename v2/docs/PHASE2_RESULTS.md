# v2 Phase 2 results: the bake-off (A, B, C)

10 November 2026. Branch `v2-bakeoff`, into `v2`. Paid part resumed by the owner on 9 November.

## 1. The short version

- **Spent: $1.80** of the $16.94 approved (cap $17). Reconciled with RunPod: its balance fell by $1.7969, the ledger
  has $1.7973.
- **A (all code)** is rebuilt with rounder trees and passes every gate (50 of 50 stages).
- **B (code + AI)** is built and passes every gate, but it is a thin B: 13 landmark portraits and no AI materials.
  - B1 (the material library) stopped at setup after $0.24. Its quote is used up, so it needs a new one to run again.
  - B2 painted 37 landmarks twice. 13 have a portrait that passes all three checks; the other 24 keep A's code art.
- **C (AI-painted buildings) was stopped at its pilot**, as the rules say. Only 2 of the pilot's 16 paintings passed
  the checks, and 60 pairs were needed from the full set. Jobs C1, C2p, C2, C3 and C4 did not run.
  - The pilot's 8 windows are composed into a C build so you can see what the paintings look like. It is marked
    failing in the viewer. Outside those windows that build is method A.
- **C4, the facade front-on trial, did not run.** It needs the style model that C2 would have trained. So there is
  no answer yet to "did straight lines survive?".
- No pod is left. The pod `luxembourgish-asr-pilot` was not touched.

## 2. What ran and what it cost

All jobs ran through `python -m v2.bakeoff run <job> --go`. RunPod had no free H100 SXM on its community cloud, so
both pods were H100 NVL at **$2.59 an hour**, under the quoted $2.69. It is the same chip in another listing.

| Job | Quote, worst case | Spent | Time | Result |
|---|---|---|---|---|
| B1 materials | $2.42 | **$0.24** | 5.5 min | Failed at setup: the pod's driver was too old for the pinned torch. No image was made. |
| B2 landmark portraits | $1.88 | **$0.76** | 17.5 min | 74 portraits (37 landmarks × 2). 13 landmarks have one that passes. |
| C1p pilot | $1.21 | **$0.80** | 18.3 min | 16 paintings. 2 pass the checks. **Branch stopped.** |
| C1, C2p, C2, C3, C4 | $11.43 | $0 | | Not run. |
| **Total** | **$16.94** | **$1.80** | | |

- **Measured:** each job's seconds on its pod × (the pod's price + its disk, $0.02 an hour), on the laptop's clock.
- **Reconciled:** RunPod's own balance was $18.9778 before the first pod and $17.1809 after the last, a drop of
  $1.7969 against the ledger's $1.7973.
  - RunPod publishes a pod's billing lines over some hours. An hour after the last pod ended they listed $1.68 and
    were still growing, so the balance is the figure used.
  - The ledger holds two reconcile events. The first compared the half-published lines ($1.46) and is marked not
    ok. The second, by the balance, is ok and is the one the ledger now goes by.
  - Run `python -m v2.bakeoff reconcile` again later to see the complete per-pod lines.
- **Pods:** two were created (`7hmguf56fayepx`, `xqxfvi0ljnfl0o`). Both were terminated, and RunPod lists neither
  (`python -m v2.bakeoff pods`).
- C1p's time includes two failed starts on the same pod (the driver, then a missing torchvision). They were fixed in
  place, inside the pilot's own time cap. B2 then ran on that pod, so the model was downloaded once.

## 3. What each method looks like

Previews are in `v2/docs/img/`: `test_<a|b|c>_<view>.jpg` and the sheet `test_bakeoff_compare.jpg`.

**A, all code.** Pastel facades, slate and tile roofs, framed windows, shutters, shop awnings, ashlar viaducts.
Trees are now rounded crowns of leaf clumps at the measured height. It is the most detailed of the three at every
view.

**B, code + AI.** It is A with 13 landmark buildings replaced by their AI portrait.
- The portraits are plainer than A's version of the same building: cream walls, a slate or red roof, dark windows.
  The model mostly inked the plain input it was given and added little. See the museum in the middle of
  `test_b_grund_day.jpg`.
- B's trees are flat crowns without leaf clumps. That is how layer 7 was specified for B.
- No AI material is in it, because B1 failed.

**C, pilot only.** Look at `test_c_pilot_windows.jpg` beside `test_a_pilot_windows.jpg`.
- Houses are simple boxes with ochre and cream walls and small dark windows. Several have one wall darker than the
  other, which is the baked shading the brief forbids.
- The red bridge's deck is painted too, with lane lines and soft rails.
- It is clean and inked, but not richer than A in these windows.
- These paintings come from v1's style model asked for even light. The new unshadowed model was never trained.

## 4. Gates

Thresholds are the build's own. None was changed.

| Brief | A | B | C (pilot windows only) |
|---|---|---|---|
| G1 suite | **pass**, 50 of 50 stages | **pass**, 50 of 50 stages | not run on the whole area: the build is method A outside 8 windows |
| #6 Line score, building edges (95%) | **98.1%** | **98.0%** | 95.8% in the pilot windows (A there: 95.9%) |
| #6 Line score, window rows (95%) | **99.3%** | **99.3%** | **93.8%: fail** (A there: 99.9%) |
| #5 No baked shadows | **pass**, worst 4.97% (limit 5%) | **pass**, worst 4.97% | **fail**: 6 of 16 pilot paintings have a building over 5%, worst 12.3% |
| #9 No cars | **pass**, 0 detections | **pass**, 0 detections | pass: 0 detections on the 16 paintings |
| Seams | **pass**, 0.0 on layers 5–7 | **pass**, 0.0 on layers 5–7 | not measured |

- A's and B's numbers are from `v2/docs/results/g1_test_a.json` and `g1_test_b.json`.
- C's are from `v2/docs/results/bakeoff_c_pilot.json` (`python -m v2.bakeoff pilot-gates`): the gate's own line
  score on the built layer 5, inside the 8 painted windows, with the better of two seeds per window.

**The pilot's own check (the one that stopped C).** Each painting had to pass flat light, the car detector and the
line score to be kept as a training picture.

| | Paintings | Pass |
|---|---|---|
| All three checks | 16 | **2** |
| Flat light | 16 | 10 |
| Line score | 16 | 2 |
| No cars | 16 | 16 |

- 2 of 16 projects to 20 pairs from the full set. 60 were needed.
- Window rows within 1 px, all 16 paintings together: **81.8%**. The unlit inputs score 96.0%.
- One thing I found while checking: on building edges, the code render itself is under 95% in some windows (A
  scores 80% and 89% in two of them). So I also counted the kindest fair reading: window rows at 95%, edges no worse
  than the input's. That keeps 3 of 16, which projects to 30 pairs. The pilot fails either way.
- Speed: 13.4 s per painting, against the 10 s estimated. C1 would still have fitted its cap.

## 5. Strengths and weaknesses

| | Strengths | Weaknesses |
|---|---|---|
| **A** | Passes everything. Costs $0, also for the whole city. Lines are exact. The most detail today. | Looks generated: every house follows the same rules. |
| **B** | Lines stay exact where code draws. A portrait is used only if it passes. | As run, it adds almost nothing over A and its portraits are plainer. 24 of 37 landmarks failed, mostly on window rows. No materials yet. |
| **C** | Inked, hand-drawn feel. No cars. Edges hold. | Window rows drift (93.8%). Some baked shading. From an unlit input the model adds little detail. Whole city would cost $40–60. |

A short note, not a pitch: on this evidence A is ahead, and the AI paintings did not show the richness that was the
reason to try them. The untested idea that could change this is C4, painting facades front-on.

## 6. Rounder trees in A

- Height is the survey's, unchanged. Width now follows the tree's shape: height × a ratio that grows from young to
  mature trees, by type, capped by the room its neighbours leave, never under the survey's width.
- Median height over width on the test area: **5.05 before, 2.19 now**.
- Spec: `v2/docs/specs/layer-07-trees.md` rule 1. New gates TE6 and TE7, and TE8 reports the ratio.
- A was rebuilt and all 50 stages pass.

## 7. Open questions

1. **Run B1 again?** It needs a new quote, about $2.00. A cap of $2.18 would keep B1 inside its first worst case.
   The setup fault is fixed and was proven on the second pod.
2. **Run C4 on its own?** It could use v1's style model instead of the one C2 never trained. Its quote ($0.94 worst
   case) is approved, but the runner refuses it because C2 did not run. It is the only test of whether front-on
   painting keeps windows straight.
3. **Go on with C at all?** The pilot failed the rule it was given. On the built layer the window rows are at 93.8%,
   not far from 95%. Going on would need a new quote and a decision on the rule for training pictures.
4. **B's trees.** Should B use A's leaf-clump crowns? Today it draws flat crowns.
5. **The edges score per window.** The code render is under 95% in some windows. The area-wide gate passes, so
   this only matters if single paintings are judged again.
6. **GPU supply.** RunPod had no H100 SXM on the community cloud. I took the H100 NVL at a lower price. Say if you
   want the runner to wait for the exact listing instead.
7. **The unspent approvals.** Quotes q0004 to q0008 ($11.43) are still approved in the ledger and count as
   committed. The runner refuses them while C1p's stop is in place.

## 8. How to look

```sh
ISOLUX_DATA=/Users/amirdaraee/00/projects/isometric-luxembourg/data \
  .venv/bin/python -m v2.view test --bakeoff --port 5175
# open http://localhost:5175/bakeoff.html   (Ctrl-C stops it)
```

- The page shows A, B and C side by side at the same view, hour and season.
- Two new views, "C's pilot windows", show the only part C painted.
- `data/v2/test/release/current.json` points at A's final build (`c7fae38fc58f`).
