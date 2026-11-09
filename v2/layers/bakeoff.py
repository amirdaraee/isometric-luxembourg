"""Bake-off methods B and C (PLAN_V2 section 7): layers 5-7 drawn from painted inputs.

Nothing here paints or spends. The painted inputs are made by the jobs in v2/bakeoff/ (run only after the owner
approves their quote in the ledger: Ledger.authorise); this module reads them back and draws them with the scene's
own depth and outline, exactly as method A's geometry:

  B  layer 5: method A's render with the AI material library sampled in place of A's generated patterns (roofs,
     walls, windows, doors) and the test area's landmarks as AI-painted portraits cut to their 3D outline;
     layers 6, 7: as A
  C  layers 5, 6 (and 7 if the canopy is painted): the AI painting of each building from its unlit render, cut to
     the mesh's coverage (the POC cut rule: the outline grown by <= 2 px), depth from the mesh

Until the inputs exist every B/C layer stage stops with a NotPainted error naming the job to run.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from v2.config import v2_data


class NotPainted(RuntimeError):
    pass


def inputs_dir(method: str, area: str) -> Path:
    return v2_data() / area / "bakeoff" / method


def painted_layer(R, layer: str, tile):
    """Layer `layer` of method R.art for one tile, from the painted inputs (see the module doc)."""
    method = R.art
    d = inputs_dir(method, R.scene.area)
    done = d / "painted.json"
    if not done.exists():
        raise NotPainted(f"method {method.upper()} is not painted yet (no {done}): its jobs run only after the owner "
                         f"approves the quote (v2/docs/PHASE2_QUOTE.md; python -m v2.bakeoff {method} --help)")
    from v2.bakeoff import compose
    return compose.layer(R, method, layer, tile, d)


def cut_to(mask: np.ndarray, rgb: np.ndarray, grow: int = 2):
    """The POC cut rule: painted pixels kept only inside the mesh's coverage grown by `grow` px."""
    from scipy import ndimage
    keep = ndimage.binary_dilation(mask, iterations=grow) if grow else mask
    out = rgb.copy()
    out[~keep] = 0
    return out, keep
