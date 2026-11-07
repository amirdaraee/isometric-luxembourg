"""Whole-canvas painting with overlapping windows (MultiDiffusion with a shifted grid), model-agnostic.

The whole area is one latent. At every step each overlapping window predicts a velocity for its part; the
predictions are blended with weights that are flat in the middle and fall towards the window's inner edges, and
one Euler step (flow matching) moves the whole latent. Every other step the window grid is shifted by half a
stride, so no window edge stays in one place and no seam can form.

Known pixels (finished neighbours, or everything outside a patch being repaired) are held: after every step they
are reset to the known latent re-noised to the current noise level (RePaint, adapted to flow matching:
x_t = (1 - t) * x0 + t * noise). Windows that are entirely held are skipped.

State is saved after every step, so a stopped job resumes where it was.

Shapes: latents are (C, H, W) in latent pixels (1/8 of image pixels). This module has no model in it: the
caller passes `velocity(key, x_window, step_index) -> v_window`.
Method from Pixel Singapore: https://www.yadongxie.com/blog/how-pixel-singapore-was-made
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, asdict
from typing import Callable

import torch


def positions(n: int, size: int, stride: int, offset: int = 0) -> list[int]:
    """Window starts along one axis covering [0, n): a regular grid starting at `offset`, plus both ends."""
    if n <= size:
        return [0]
    ps = {0, n - size}
    p = offset % stride
    while p + size < n:
        ps.add(p)
        p += stride
    return sorted(q - (q % 2) for q in ps)  # even, so latents pack into 2x2 patches


def ramp(size: int, fade: int, at_start: bool, at_end: bool) -> torch.Tensor:
    """1D weight: 1 in the middle, falling linearly over `fade` towards each edge that is not a canvas border."""
    i = torch.arange(size, dtype=torch.float32) + 0.5
    w = torch.ones(size)
    if not at_start:
        w = torch.minimum(w, i / fade)
    if not at_end:
        w = torch.minimum(w, (size - i) / fade)
    return w


def window_weight(y: int, x: int, size: int, fade: int, H: int, W: int) -> torch.Tensor:
    wy = ramp(min(size, H), fade, y == 0, y + size >= H)
    wx = ramp(min(size, W), fade, x == 0, x + size >= W)
    return wy[:, None] * wx[None, :]


def grid(H: int, W: int, size: int, stride: int, shifted: bool) -> list[tuple[int, int]]:
    off = stride // 2 if shifted else 0
    return [(y, x) for y in positions(H, size, stride, off) for x in positions(W, size, stride, off)]


@dataclass
class Plan:
    H: int                 # latent height
    W: int                 # latent width
    sigmas: list[float]    # noise levels, len = steps + 1, ending at 0
    size: int = 128        # window, latent px (1024 image px)
    stride: int = 96       # 768 image px
    fade: int = 32         # = size - stride: weights fall over the whole overlap
    seed: int = 1867

    def key(self) -> str:
        return hashlib.sha1(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()[:12]


def save_state(path: str, state: dict) -> None:
    tmp = path + ".tmp"
    torch.save(state, tmp)
    os.replace(tmp, path)


def paint(
    plan: Plan,
    velocity: Callable[[tuple[int, int], torch.Tensor, int], torch.Tensor],
    channels: int = 16,
    known: torch.Tensor | None = None,      # (C, H, W) known latent
    hold: torch.Tensor | None = None,       # (H, W) bool, True = hold to `known`
    state_path: str | None = None,
    on_step: Callable[[int, int, int], None] | None = None,   # (step, steps, windows run)
    stop: Callable[[], bool] | None = None,  # return True to save and stop early (deadline)
) -> torch.Tensor | None:
    """Run the plan; returns the final latent, or None if `stop` asked to stop (state saved)."""
    H, W, steps = plan.H, plan.W, len(plan.sigmas) - 1
    assert H % 2 == 0 and W % 2 == 0, "latent size must be even"
    if hold is not None:
        assert known is not None and hold.shape == (H, W)
        hold = hold.float()

    start = 0
    st = torch.load(state_path, weights_only=True) if state_path and os.path.exists(state_path) else None
    if st is not None and st["plan"] == plan.key():
        x, noise, start = st["x"], st["noise"], st["step"]
    else:
        g = torch.Generator().manual_seed(plan.seed)
        noise = torch.randn((channels, H, W), generator=g)
        x = noise.clone()
        if hold is not None:  # sigma_0 is ~1, but keep the held area exactly on the schedule
            s0 = plan.sigmas[0]
            x = hold * ((1 - s0) * known + s0 * noise) + (1 - hold) * x

    weights: dict[tuple[int, int], torch.Tensor] = {}
    for i in range(start, steps):
        s, s_next = plan.sigmas[i], plan.sigmas[i + 1]
        acc = torch.zeros_like(x)
        wsum = torch.zeros((H, W))
        ran = 0
        for (y, xx) in grid(H, W, plan.size, plan.stride, shifted=i % 2 == 1):
            h, w = min(plan.size, H), min(plan.size, W)
            if hold is not None and bool(hold[y:y + h, xx:xx + w].all()):
                continue  # nothing to paint in this window
            k = (y, xx)
            if k not in weights:
                weights[k] = window_weight(y, xx, plan.size, plan.fade, H, W)
            wt = weights[k]
            v = velocity(k, x[:, y:y + h, xx:xx + w], i)
            acc[:, y:y + h, xx:xx + w] += v.float() * wt
            wsum[y:y + h, xx:xx + w] += wt
            ran += 1
        free = wsum > 0
        if hold is not None:
            assert bool((free | (hold > 0)).all()), "a free pixel is in no window"
        else:
            assert bool(free.all()), "a pixel is in no window"
        v = acc / wsum.clamp_min(1e-8)
        x = torch.where(free, x + (s_next - s) * v, x)  # Euler step (flow matching)
        if hold is not None:
            x = hold * ((1 - s_next) * known + s_next * noise) + (1 - hold) * x
        if state_path:
            save_state(state_path, {"plan": plan.key(), "step": i + 1, "x": x, "noise": noise})
        if on_step:
            on_step(i + 1, steps, ran)
        if stop and i + 1 < steps and stop():
            return None
    return x


def blend_tiles(
    shape: tuple[int, int, int],
    tiles: list[tuple[int, int, torch.Tensor]],
    size: int,
    fade: int,
) -> torch.Tensor:
    """Blend overlapping (C, h, w) tiles placed at (y, x) into one (C, H, W) image with the window weights.
    Used to decode the latent in pieces and blend the pieces in pixel space."""
    C, H, W = shape
    acc = torch.zeros(shape)
    wsum = torch.zeros((H, W))
    for y, x, t in tiles:
        h, w = t.shape[1:]
        wt = window_weight(y, x, size, fade, H, W)[:h, :w]
        acc[:, y:y + h, x:x + w] += t.float() * wt
        wsum[y:y + h, x:x + w] += wt
    assert bool((wsum > 0).all()), "tiles leave a gap"
    return acc / wsum


def hold_mask(known_px: torch.Tensor, band_px: int, scale: int = 8) -> torch.Tensor:
    """Latent-resolution hold mask from an image-resolution known mask (True = known): a latent pixel is held
    only if its whole 8x8 block is known and it is more than `band_px` from any unknown pixel. The free band
    lets the new paint blend into what is already there."""
    k = known_px.float()[None, None]
    blk = -torch.nn.functional.max_pool2d(-k, scale)          # min-pool: block fully known
    r = max(1, round(band_px / scale))
    grown = torch.nn.functional.max_pool2d(1 - blk, 2 * r + 1, stride=1, padding=r)  # unknown, grown by the band
    return (grown[0, 0] == 0)


def feather(known_px: torch.Tensor, band_px: int) -> torch.Tensor:
    """Image-resolution alpha for putting the known pixels back at the end: 1 deep inside the known area, falling
    to 0 at the unknown edge across the band."""
    k = known_px.float()[None, None]
    a = k.clone()
    for _ in range(band_px):  # distance in px to the unknown area, capped at band_px
        a = a + (-torch.nn.functional.max_pool2d(-k, 3, stride=1, padding=1))
        k = -torch.nn.functional.max_pool2d(-k, 3, stride=1, padding=1)
    return ((a[0, 0] - 1).clamp(0, band_px) / band_px)
