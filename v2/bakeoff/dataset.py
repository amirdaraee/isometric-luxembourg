"""The training dataset of method C's unshadowed style LoRA (job C2), and the checks every painting must pass.

Plan (all $0 except C1, which paints the targets):
1. Crops: 80 windows of 1024 px over the test area's buildings (inputs.windows), picked to spread over the area and
   its kinds (old town, slopes, viaducts, the plateau's blocks). Each has its unlit render (control 1) and layout
   (control 2), as v1's style v2 LoRA was trained (pipeline/gpu_train/v2/v2.yaml: two control images).
2. Targets: v1's style LoRA (luxembourg-ink-v2, HF amirdaraee/isometric-ink-style) is the teacher: it paints each
   unlit crop with the even-light prompt (prompts.C_TARGET_PROMPT), two seeds (job C1; 8 crops first, C1p).
3. Filter (here, locally): a target is kept only if
     - flat_light(): no baked shadow: on every building, the same material on faces turned different ways has the
       same median luminance within 5% (L5.1's rule, by orientation, as the photo sun is not in a painting);
     - the vehicle detector (OWLv2, v1's, as brief 9) finds nothing >= 0.1 (no cars, people or boats);
     - line_score(): its building edges and window rows are within 1 px of the model's over >= 95% (brief 6).
   At least 60 kept pairs are needed; fewer and C2 does not start (re-quote with another teacher prompt).
4. Train (C2): ai-toolkit, Qwen-Image-Edit-2511, rank 16, 2,000 steps (pod/c2_train.yaml), captions with the new
   trigger "<isometric luxembourg ink unshadowed>"; 25% of examples with a blank layout (v1's recipe).
"""
from __future__ import annotations

import numpy as np

from v2.layers.common import lum


def flat_light(rgb, ids, normal, min_px=150, tol=0.05):
    """Faces of one building's material turned different ways (N, E, S, W quadrants of the wall normal; roofs by
    their slope's quadrant) must have the same median luminance within tol. Returns (worst relative difference,
    [(building id, class, worst)]) over buildings with >= min_px pixels on at least two sides."""
    from scipy import ndimage
    L = lum(np.asarray(rgb, float))
    cls = ids & 255
    obj = ids >> 8
    h = np.hypot(normal[..., 0], normal[..., 1])
    az = np.degrees(np.arctan2(normal[..., 0], normal[..., 1])) % 360
    quad = (((az + 45) % 360) // 90).astype(int)
    # as L5.1: pixels within 2 px of a change of object, class or facing are left out (the ink lines at edges are
    # the drawing, not light)
    key = ids.astype(np.int64) * 4 + quad
    edge = np.zeros(key.shape, bool)
    edge[:, 1:] |= key[:, 1:] != key[:, :-1]
    edge[:, :-1] |= key[:, 1:] != key[:, :-1]
    edge[1:, :] |= key[1:, :] != key[:-1, :]
    edge[:-1, :] |= key[1:, :] != key[:-1, :]
    inner = ~ndimage.binary_dilation(edge, iterations=2)
    # faces seen at a grazing angle are all ink (their depth steps past the outline rule every pixel): left out
    from v2.layers.common import VIEW
    inner &= -(normal @ VIEW) > 0.3
    worst, bad = 0.0, []
    for c in (11, 23):                                   # walls (building), roofs
        m = (cls == c) & (h > (0.7 if c == 11 else 0.1)) & inner
        if not m.any():
            continue
        for o in np.unique(obj[m]):
            mo = m & (obj == o)
            meds = [np.median(L[mo & (quad == q)]) for q in range(4) if (mo & (quad == q)).sum() >= min_px]
            if len(meds) < 2:
                continue
            d = (max(meds) - min(meds)) / max(max(meds), 1e-6)
            worst = max(worst, d)
            if d > tol:
                bad.append((int(o), int(c), round(float(d), 3)))
    return round(worst, 4), bad


def pick_crops(wins, n=80, seed=7):
    """n windows spread over the area: every k-th of the windows sorted along a space-filling order."""
    if len(wins) <= n:
        return list(wins)
    order = sorted(wins, key=lambda p: (p[1] // 3072, p[0] if (p[1] // 3072) % 2 == 0 else -p[0]))
    idx = np.linspace(0, len(order) - 1, n).round().astype(int)
    return [order[i] for i in idx]
