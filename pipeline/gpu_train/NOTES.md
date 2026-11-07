# Training run 1 (5 Nov 2026): stopped at step 500

## What happened
- Data: 40 inked drawings (OpenAI gpt-image-2.6, `ink` brief) turned into 200 masked examples with isometric-nyc's
  `create_omni_dataset.py`; config adapted from isometric-nyc's and ai-toolkit's Qwen-Image-Edit examples.
- GPU: community A100 80 GB on RunPod, $1.39/h.
- Speed: about 7.8 to 9.4 s per step at 1024 px, batch 1. 3000 steps would be about 6.5 to 7.5 h.
- Result at step 500: the model copies its input. Held-out views, three city views and even two of its own training
  inputs came back photo-like, with none of the inked style. Stage 2 was therefore not started.
- Cost: about $2.53 of GPU time.

## Likely causes, to check before paying for another run
1. Too little learning signal: 80% of examples are infills where most of the control already equals the target, so
   "copy the input" is nearly optimal. Try a higher share of full-view examples, or full-view only for a first run.
2. Learning rate and steps: 1e-4 for 500 steps may simply be early. NYC trained 3000 steps; check its training
   samples on Oxen at steps 200 to 1000 to see when style appeared for them.
3. Control handling: confirm ai-toolkit actually feeds `control_path` images for `qwen_image_edit` in this version
   (commit beb9482), e.g. by checking its dataset logs or a tiny overfit test on 2 images for about 100 steps.

## Files
- On the pod volume: /workspace/output/luxembourg-ink-v1 (checkpoints at 250 and 500, samples), train.log, guard.log.
- Locally: data/work/style/train_samples (samples, city500.jpg, probe/probe.jpg).

## Root cause found (2026-11-06)
ai-toolkit scans `folder_path` recursively (os.walk). With `control_path` inside the dataset folder
(`data/control`), the 200 input photos were also loaded as training targets, each paired with itself as
control ("Found 400 images" for 200 pairs). Half of every batch taught "copy the input"; training loss
was ~0.002. Fix: keep control images outside the dataset folder (`/workspace/data_control`).
2-image overfit check on Qwen-Image-Edit-2511 then learned the style within 150 steps (loss ~0.1–0.3),
including on a held-out view. Full run: `full/full.yaml` (2500 steps, lr 1e-4) on an H100.

## Full run result (2026-11-06)
H100, 2500 steps at 2.94 s/step (~2 h, ~$9). From step 1000 all 3 held-out city views are fully restyled.
Checkpoints: data/work/style/lora_full/ (every 250 steps + final). Known issue: training view 14_a
invents a pond on the square (steps 1000-2500). Pick the checkpoint by a wider held-out check.

## Checkpoint check (2026-11-06)
10 pilot views x steps 1500/2000/2500 (data/work/style/train_samples/pilot_check/sheet.jpg). All restyle cleanly, no invented water.
Only step 2500 keeps the Red Bridge red (1500/2000 turn it grey) -> use the final LoRA (lora_full/luxembourg-ink-2511.safetensors).
Minor: a few tiny cars drawn on station roads.
