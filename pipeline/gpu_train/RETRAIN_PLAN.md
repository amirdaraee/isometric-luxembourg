# Style retrain v2: plan (draft for review, 6 Nov 2026)

Nothing below has been run or paid for yet. Each step ends at a checkpoint where we stop if it isn't good.

## 1. Goal and how we will measure it

Fix what the showcase shows, without losing what already works.

| Problem now | Target | How we check (same views before/after) |
|---|---|---|
| Dense blocks are smudgy; windows distorted; facade lines not parallel (Place d'Armes) | Straight walls, regular window rows | Line score: share of the guide's straight edges that the painting follows (edge overlap, automatic), plus your eye |
| Detail lost at max zoom | Sharper at the same zoom | Painted at 450 src px per cell for dense quarters (0.22 m/px instead of 0.29) |
| Red Bridge deck painted red; red legs thin | Grey deck, massive red legs | Visual, plus red-pixel count on the deck mask |
| Must not get worse: water, empty roads, seams, colours, trees | Same or better | Water check (invented/missing), seam drift, colour stats vs v5, your eye |

Fixed test set (never trained on): Place d'Armes, Hôtel de Ville block, Gare station front, Kirchberg towers,
Grund (river), Red Bridge, Glacis car park, plus the 3 existing held-out city views. Same seeds every time.

## 2. New training views (60), chosen before any drawing

Scale: 900 src px per view (drawn at 1024, ~0.22 m/px): finer than the 40 we have (1200 src px).

| Group | Count | Where | Why |
|---|---|---|---|
| Dense old town | 14 | Ville Haute blocks around Grand-Rue, Rue du Fossé, Place Guillaume (not the test blocks) | Main weakness |
| Gare / Bonnevoie | 8 | Avenue de la Liberté, Rue de Strasbourg | Dense 19th-c. facades, long straight rows |
| Limpertsberg / Belair | 6 | residential streets | Ordinary houses, the bulk of the city |
| Kirchberg | 6 | towers, glass, wide avenues | Modern glass and straight lines |
| Grund / Clausen / Pfaffenthal | 8 | river, cliffs, terraced houses | Water, slopes, old houses on the river |
| Bridges and viaducts | 8 | Adolphe, Red Bridge (both ends), Passerelle, Pulvermühle, Clausen | Deck shapes, legs, joins |
| Car parks, tracks, squares | 6 | Glacis, station tracks, Place de l'Europe | Empty surfaces with markings |
| Parks and forest edges | 4 | Pétrusse, Municipal park | Keep trees good |

Picked automatically by type (building density from the 3D visibility pass), spread out, at least 150 m from
the test set, then reviewed as a contact sheet of the renders before anything is drawn.
Checkpoint A: approve or swap views. Cost $0.

## 3. What the drawing service gets

- Input: the cleaned render (cars removed, real water drawn, bridge model fixed), not the raw render. Railway
  tracks are drawn cleanly from OSM into the input (two rails and sleepers), like the river.
- Decided 6 Nov: OSM roads/tracks/water are NOT pasted over the finished painting (tested: looked worse than the
  painted ones). They are used in the inputs, for traffic and trains, and for night/season recolouring.
- Brief: the current ink brief, with two changes, because the current text says "do not straighten anything":
  - Buildings: "keep every outline where it is, but draw walls straight and parallel, and windows as regular,
    evenly spaced rows aligned with each wall and its floors."
  - Red Bridge views: "the road on top is grey asphalt; only the outer sides and the legs are red."
- Per-view hints (as before) where needed: names of landmarks, bridge rules, water width.
- First 6 views only (~$0.40), reviewed first. Checkpoint B: approve the look before the other 54.
- Then the rest (~$3.40). Each drawing is checked for: invented water, cars, red deck, and straightness (line
  score against the guide). Failing ones are redrawn once (budget ~10 extra, ~$0.60) or dropped.
  Checkpoint C: all 60 reviewed on one page; any can be vetoed.

OpenAI total: ~$4.40 cap.

## 4. Dataset

- 40 old + ~60 new drawings, 5 training examples each (the same red-box infill mix as now) = ~500 examples.
- Second input image for every example (new): a colour-coded layout map of the same view, generated from data:
  roads grey with lane/centre lines, rail tracks brown with rails, tram tracks as thin double lines, water blue,
  parks/forest green, car parks and squares light grey, buildings as two tones (walls/roofs) with the line guide
  (straight edges + window grid) drawn in. Qwen-Image-Edit-2511 takes several input images; the model learns
  what each colour means during the retrain (no extra cost: generated automatically).
- Alignment check per drawing: the teacher's drawing must line up with the layout map (water, roads, building
  edges); misaligned drawings are redrawn or dropped, or the model learns the map is only approximate.
- 25% of examples get the layout map blanked, so the model also works where the guide is missing or wrong
  (e.g. trees, cliffs, buildings the 3D data doesn't have).
- Kept apart: controls outside the dataset folder (the run-1 bug).

## 5. Training

- Qwen-Image-Edit-2511, same settings as the run that worked (rank 16, lr 1e-4), 3,500 steps (more data),
  samples every 500 steps on the test set, on one H100 in the US.
- About 3 h, ~$12. Stops itself when done or failing; checkpoints copied to the laptop as they appear.
- Checkpoint D: compare checkpoints 2000/2500/3000/3500 on the test set (as before), pick one. ~$1.

## 6. Painting

- Tiler passes the line guide as the second image for each window.
- Dense quarters at 450 src px per cell, the rest at 600.
- Repaint the showcase (~$4-5), then run all checks (water, seams, line score, red deck).
- Checkpoint E: compare v5 and v6 in the viewer.

## 7. Risks and fallbacks

| Risk | Fallback |
|---|---|
| Line guide makes buildings look generic or uniform (windows from a grid, not real) | Guide edges only, no window grid; or lower its weight |
| Drawing service still bends windows | Stronger wording, or redraw at 1536 px |
| New drawings change the overall look (colours) | Colour stats vs old set; drop outliers |
| Retrain worse on water/roads | Keep v1 model; mix old checkpoints per area |

## 8. Total

| Step | Cost |
|---|---|
| New drawings (incl. redraws) | ~$4.40 (OpenAI) |
| Training + checkpoint check | ~$13 (RunPod) |
| Showcase repaint | ~$5 (RunPod) |
| **Total** | **~$22** |

Night work waits until v6 is accepted (night is painted from the final day map). The 40 night drawings being
made now stay valid for training the night model later.
