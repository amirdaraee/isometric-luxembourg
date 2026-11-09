# v2 Phase 2 report: the bake-off (A built, B and C ready)

9 November 2026. Branch `v2-phase2`, into `v2`. Spend: **$0**. No pod was started, and no paid API was called. The
only network calls were read-only price queries to RunPod's API and the Modal and OpenAI price pages.

## 1. What this phase did

| Part | Where | What |
|---|---|---|
| **Method A, layers 5–7** | `v2/layers/art_a.py`, `render.py` | Inked code render with more detail. Each building gets a facade colour from 8 palette colours (or sandstone) and a roof: slate, dark slate, tile or old tile; flat roofs are gravel. **Walls** have a sandstone plinth, a cornice at every floor line of the facade layout and an eave cornice; some buildings have quoins. **Roofs** have courses parallel to the eave with staggered joints, and a tone per tile. **Windows** have a white frame, glazing bars and a sill. Some buildings have **shutters**, placed only where they fit the wall. **Doors** have panels and a fanlight; there are also garage doors. **Shop fronts** have glazing bars and a striped awning band. **Viaducts and walls** are drawn as ashlar, **railings** as bars. **Trees** are drawn as leaf clumps, and each crown now fills its tree's measured height above a trunk a quarter as tall (its width is still the survey's). Every detail is computed from the pixel's place on its 3D surface. It is albedo only, with no light. |
| Art method switch | `v2/config/art.py`, `params.json` art | `a` (default), `b`, `c`, `plain` (Phase 1's placeholder). `V2_ART=b` builds another option into its own stage folders. |
| **Red bridge fix** | `geometry.deck_mask`, `render.py` | Section 2. |
| **Line score L5.2** (brief #6) | `v2/checks/line_checks.py`, stage `check_lines` | Every crease and outline of the 3D model and the top and bottom of every window, sampled every 0.25 m. The nearest drawn line (a luminance step of at least 12/255 across the projected line) must lie within 1 px. Each of the two sets needs at least 95%. |
| **Check L4.6**, bridge ends | `layer_checks.abutment_continuity` | Section 2. |
| B and C up to the paid step | `v2/bakeoff/`, `v2/layers/bakeoff.py` | Jobs, prompts, inputs, dataset filter, composer, runner with the ledger gate and the pod watchdog (section 4). |
| Quote | `v2/docs/PHASE2_QUOTE.md`, ledger `q0001`–`q0008` | Section 5. |
| Bake-off viewer | `v2/web/bakeoff.html`, `src/bakeoff.ts`, `vite.config.ts` | Each registered method's release side by side, at 9 fixed views and the same hour and season. Methods not yet painted show what they are waiting for. |
| Owner decisions recorded | `research/v2/DECISIONS.md`, `PLAN_V2.md` 9.1 and section 10, `docs/specs/tunnel-view.md`, `docs/specs/landmark-cutaways.md` | Tunnel view (X1–X8) and landmark cutaways (K1–K7), both for Phase 3. |

## 2. "The red bridge is not connected to the road"

**Cause.** The transport graph was right: the bridge's ends and the roads meet at the same heights. The fault was in
how layer 4 drew the roads.
- **Ground ways were draped on the terrain model.** ACT cuts a bridge out of the terrain past the point where OSM ends
  its bridge tag. So for the last 10–15 m before each abutment, the terrain model drops into the valley. At the red
  bridge's Kirchberg end it drops 11 m (309.4 m becomes 298.5 m).
- The road was drawn down there, while its profile (and the cars on it) stayed at 309.4 m. **The deck ended in the
  air**, and the city end had a 5 m step.
- Phase 1's rule, "approaches drawn as decks", looked at the median of a whole edge. These edges are mostly on the
  ground, so it never caught them.

**Fix, in the renderer** (`geometry.deck_mask`, `pieces`, `densify`; layer 4 rule 1 in `layer-04-transport.md`):
- A ground way is now a deck on **every stretch** where its profile stands more than 1 m over the drawn terrain.
- The stretch continues, every 0.5 m along the way, until the profile is back within 0.1 m of the terrain. It also
  starts at any bridge end it leaves.
- Layer 6 draws the abutment's sides under such stretches, down into the terrain.

Two more defects the new check found at bridge ends:
- **Tunnel mouths facing away from the camera were drawn.** One stood over a road bridge in Pfaffenthal. Now they are
  not drawn.
- **A portal under a deck** is cut to the deck's underside.

**Every other bridge.** The new gate **L4.6** (layer-04 spec) checks every bridge end in the area: 121 nodes and about
5,700 centre-line samples within 6 m of each end. It finds a gap when nothing is drawn at the way's profile or on the
terrain, and a step when the drawn height changes faster than both by more than 2 px.

| | Bridge ends with a problem | Samples failing | Largest step |
|---|---|---|---|
| Before (Phase 1's release) | 54 of 121 | 382 (145 gaps, 237 steps) | 96.6 px (the red bridge's Kirchberg end) |
| After (this release) | 0 of 120 (1 way excepted, below) | 0 | 1.19 px (under the 2 px limit) |

**One exception** (`v2/data/exceptions.json`): the Stierchen footbridge's first graph edge. It is 1.26 m long and
climbs 1.7 m, because the abutment's steps are mapped as the bridge. Seen almost edge-on, one of its samples falls
on a pixel the deck does not cover.

**Preview.** `v2/docs/img/test_red_bridge_before_after.jpg` shows both ends, before and after. These are unlit
composites of the layers: the before images show Phase 1's placeholder art, the after images show method A.

## 3. Method A's checks (build gates, test area)

Command: `python -m v2.build test g1`. Result: **50 of 50 stages ok**, exit 0. Full results:
`v2/docs/results/g1_test_a.json`. Phase 1's file for the placeholder art is kept as it was.

| Brief | Check | Result |
|---|---|---|
| #4 Layers independent | C1a: 504 re-renders, each without one other layer's inputs, identical. C1c: built tiles vs the renderer, 2.68 (limit 3). Every layer turned off in the viewer leaves 0 pixels and no shadow. | **pass** |
| #5 No baked shadows (on A's art) | L5.1: 0 of 236 materials differ by more than 5% in the photo-sun's shadow. Worst by layer: buildings 4.97%, structures 2.7%. Shadow direction error 7.7°, 9.8° and 7.6° (limit 10°). The viewer's shadows match the reference on 99.6% of pixels. | **pass** |
| #6 Straight lines and windows (line score L5.2) | Building edges (creases of 20° or more, and outlines): 98.1% of 723,358 seen samples within 1 px. Window rows: 99.3% of 76,718. Limit 95% each. | **pass** |
| #7 Roads and rails | L4.1: 100% of centre lines inside the drawn surface. Cars on drawn road 99.97%. Trams and trains on track 100%. **L4.6, bridge ends: 0 failing** (section 2). | **pass** |
| #8 Tunnels and bridges | 0 vehicle pixels in tunnels. 0 disagreements in 12.5 million probe pixels. Largest height step between frames 0.33 m. | **pass** |
| #9 No painted cars (on A's art) | OWLv2: 0 detections at 0.1 or above on every colour tile of all 7 layers. The highest score of any box was 0.14, outside the vehicle size range. | **pass** |
| Seams | Buildings, structures and trees: 0.0 ΔE (lossless). Every layer is at or under 3. | **pass** |
| Speed (desktop) | First view 0.11 s. Panning 83 fps at 1:1, 120 fps over the whole area. | **pass** |

**Exceptions:** one, for L4.6 (section 2). No threshold was changed.

**New thresholds:**
- L4.6: 2 px, 6 m, 0.25 m sampling.
- L5.2: a step of 12/255 counts as a line.

**What it took for A to pass.** Each of these was fixed at its cause:
- **Layers 5–7 are now coded lossless.** Their detail lost up to 6.5/255 in lossy WebP q90, over C1c's 3. This
  costs about twice the bytes: buildings 40 MB and trees 81 MB for the test area.
- **Doors, windows and shop fronts are drawn as decals over their own wall.** ACT duplicates some walls just in front
  of others, and that hid about 6% of the windows.
- **Stone trim, shutters, glass, frames, door panels and awnings each have their own material class** in the ids.
  The shadow detector compares one material lit and in shadow. Frame and glass mixed in one class made a window's
  median depend on how squarely it is seen.
- **Ink lines go only at creases of 20° or more.** ACT models round towers as flat facets a few degrees apart. A line
  between each pair, plus lines along every steep depth step of a facet seen edge-on, darkened the towers toward
  their outline, which reads like shading. C's flat-light check caught this on 3 of the 107 unlit windows. A wall
  and its windows are always kept apart.
- **The line score looks for the drawn line nearest the model's line.** A window frame beside a line is a second
  line, not a moved one. It also counts a sample only where layer 5 shows that building.

**How A looks** (section 7):
- Colourful facades, slate and tile roofs, framed windows with shutters, shop awnings, ashlar viaducts, and the Red
  Bridge in red.
- Crowns now fill each tree's measured height; their width is still the survey's. With narrow LiDAR crowns this
  makes tall, poplar-like trees, which you may want to judge.

## 4. B and C, ready to run

Everything up to the paid call is built and tested at $0:

- **Jobs and quotes** (`v2/bakeoff/jobs.py`). Each job has a provider, a GPU, a time cap and a worst case. The
  quotes are in the ledger as `q0001`–`q0008`, as quote events only.
- **The runner** (`v2/bakeoff/runner.py`, `python -m v2.bakeoff run <job> [--go]`). It checks four things before
  anything starts:
  - `Ledger.authorise` passes (the owner has approved the quote and it fits the cap);
  - the live price is no higher than the quoted one;
  - the jobs before it are done.

  Then it starts a RunPod pod whose first act is a watchdog that stops it at the job's cap. Without `--go`, the
  runner only prints the pod it would start. Unit tests show it refuses without approval, refuses after a price rise,
  and refuses out of order.
- **Prompts and lists** (`prompts.py`).
  - 25 materials, each following a palette colour.
  - 38 test-area landmarks on a building (`inputs b`).
  - The C prompts.

  Every prompt forbids light, shadows and anything that moves.
- **C's inputs** (`python -m v2.bakeoff inputs c`). 107 windows of 1024 px at 0.125 m/px over the 189 building tiles.
  Each window has:
  - an unlit render: Phase 1's plain buildings over the code ground, with no light at all;
  - a layout image: black outlines, dark windows;
  - a mask;
  - ids and normals.

  The 80 training crops and the 8 pilot crops are listed in `windows.json`.
- **C's training dataset plan** (`dataset.py`, `pod/c2_train.yaml`).
  - v1's `luxembourg-ink-v2` is the teacher.
  - A painting is kept only if it passes: flat light (the same material on faces turned different ways within 5%),
    OWLv2 no cars, and the line score.
  - At least 60 pairs, or training does not start.
  - ai-toolkit, rank 16, 2,000 steps, a checkpoint every 200 (the pilot stops at 200).
- **Pod scripts** (`pod/`). These reuse v1's whole-canvas painter (`pipeline/gpu_train/tiles/mdpaint.py`:
  MultiDiffusion with hold and repair) with Qwen-Image-Edit-2511, the 8-step Lightning LoRA and a style LoRA.
- **The composer** (`compose.py`, `v2/layers/bakeoff.py`).
  - C: each painting is cut to the mesh. Overlapping windows are blended by a tent weight. Depth, normals and ids
    always come from the scene.
  - B: A's render with the picked materials sampled in place of A's patterns, and each landmark's portrait cut to its
    building.
  - Until the paintings exist, a B or C layer stage stops with a message naming the job to run.
- **Local smoke test** (`python -m v2.bakeoff smoke c`). A stand-in "painting" (the unlit input itself) went through
  the composer and came back pixel-exact (100%). The flat-light filter found no false shadow on any of the 107 unlit
  windows, and a unit test shows it does catch one.

  A real model run does not fit this Mac: it has 16 GB of memory and 17 GB of free disk, and
  Qwen-Image-Edit-2511 is about 40 GB. The first real run is pilot C1p.

## 5. The quote (details in `v2/docs/PHASE2_QUOTE.md`)

Every job runs on RunPod community cloud, one H100 SXM at $2.69 an hour, read from the API today. Modal is $3.95 an
hour, and OpenAI's gpt-image-2 is about $0.125 per high-quality image, so both cost more.

| Job | What | Est. | Worst case |
|---|---|---|---|
| B1 | 25 materials × 3 (Qwen-Image) | $1.94 | $2.42 |
| B2 | 38 landmark portraits × 2 | $1.48 | $1.88 |
| C1p | Training targets, pilot (16) | $0.94 | $1.21 |
| C1 | Training targets (144) | $1.88 | $2.15 |
| C2p | Style LoRA without shadows, pilot (200 steps) | $1.26 | $1.48 |
| C2 | The rest of the training (1,800 steps) | $4.36 | $4.71 |
| C3 | Paint the test area (107 windows) | $1.61 | $2.15 |
| C4 | Facade front-on trial (about 10 buildings) | $0.67 | $0.94 |
| **Total** | | **$14.14** | **$16.94** (cap $17) |

**Phase 3 estimate, not in this total:** the four landmark cutaways, about $1.21 ($1.88 worst case). The tunnel view
is $0.

## 6. The bake-off viewer

```sh
.venv/bin/python -m v2.bakeoff register a          # once per built method (done for A)
.venv/bin/python -m v2.view test --bakeoff --port 5175
# open http://localhost:5175/bakeoff.html
```

The page has one column per method, each the real viewer (code light, night, seasons) on that method's release. It
offers 9 fixed views: the Grund by day, at golden hour and at night; the abbey at 1:1; the Bock; facades at 2:1; the
red bridge; Pfaffenthal; and the whole area. All columns share the hour and season. B and C show what they are waiting
for until `python -m v2.bakeoff register b` (or `c`) is run after their paint. Port 5174 is left to your own viewer.

## 7. Previews of A (`v2/docs/img/`, screenshots of the viewer, each under 1 MB)

| Image | Shows |
|---|---|
| `test_a_grund_day.jpg` | The Grund at 13:00 on 24 June: the abbey, the Alzette, the Bock above |
| `test_a_grund_golden_hour.jpg` | The same view at 21:18 |
| `test_a_grund_night.jpg` | The same view at 23:15: lit windows and street lamps |
| `test_a_bock.jpg` | The Bock close up: the casemates' walls, Castle Bridge, the cliffs |
| `test_a_facades.jpg` | Facades at 2:1: frames, glazing bars, shutters and dormers, all straight |
| `test_a_abbey.jpg` | Neumünster Abbey at 1:1 |
| `test_a_red_bridge.jpg` | The Red Bridge's east end, now joined to the road |
| `test_bakeoff_viewer.jpg` | The bake-off page: A at the Grund view; B and C waiting for approval |
| `test_red_bridge_before_after.jpg` | Both ends of the Red Bridge, before and after the fix (unlit composites) |
| `test_a_g1_*.jpg` | Gate G1's own previews for A: the whole area by day, at golden hour and at night; shadows at 10:00 and 16:00; trains at a portal and on the viaduct; the layer toggles |

## 8. For the owner

**To go on with the bake-off:**
1. **Approve B and C's quotes** (or some of them), one per job:
   `python -m v2.ledger.ledger approve q0001 --by owner --note "..."` (q0001 to q0008, listed in
   `PHASE2_QUOTE.md`).
2. **RunPod or Modal?** The quote uses RunPod, the cheaper list price. Modal's Starter plan includes $30 of compute a
   month. If your account still has that credit, Modal would cost you nothing in cash.

**Open questions:**
1. **Tree shape in A.** Crowns now fill the measured height at the survey's width, so many trees look tall and narrow,
   like poplars. Keep this, or use rounder crowns that may hide a little more of what is under them? (Width is fixed by
   L7.1.)
2. **New check methods to approve:**
   - L4.6: a gap, or a step that stays (medians of 1 m either side) beyond what the profile and the terrain allow;
     the ways meeting at a node compared with each other.
   - L5.2: the nearest drawn line, at least 12/255 of luminance, within 1 px of the model's line.
3. **The one L4.6 exception:** the Stierchen footbridge's first edge, whose abutment steps are mapped as the bridge.
4. **Tile size.** Layers 5–7 are now coded lossless, about twice the bytes. For the whole commune that means about
   +2–3 GB on R2, around $0.05 a month.
5. **Cutaways.** All four first landmarks (the cathedral, the palace, the abbey, the casemates) are inside the test
   area, so no extension is needed. The cathedral's and the palace's footprints lie wholly inside the area, 21 m and 177 m from its edge.
6. **Still open from G0:** viaduct arch counts, the funicular timetable, R2, the GTFS licence version.

**How to look at it:**
```sh
.venv/bin/python -m v2.view test --bakeoff --port 5175    # http://localhost:5175/bakeoff.html (Ctrl-C stops it)
```
