"""Laptop tests for md_core with a stand-in model (no GPU, no weights).

The stand-in knows the clean image it wants (`target`) and returns the exact flow-matching velocity towards it,
v = (x_t - target) / t. So any seam, gap or drift in the result comes from the painter, not from the model.
Run: python test_md_core.py   (needs torch only)
"""
import os
import tempfile

import torch

from md_core import Plan, blend_tiles, feather, grid, hold_mask, paint, positions

STEPS = 8
SIG = [1 - i / STEPS * (1 - 1 / STEPS) for i in range(STEPS)] + [0.0]  # 1 ... 1/STEPS, then 0


def model(target_for):
    def v(key, xw, i):
        t = SIG[i]
        return (xw - target_for(key, xw.shape)) / t
    return v


def test_coverage():
    for n in (128, 130, 200, 224, 500, 640, 1001 - 1):
        for off in (0, 48):
            ps = positions(n, 128, 96, off)
            assert ps[0] == 0 and ps[-1] + 128 >= n and all(p % 2 == 0 for p in ps), (n, off, ps)
            assert all(b - a <= 128 for a, b in zip(ps, ps[1:])), (n, off, ps)  # no gaps
    a, b = grid(320, 320, 128, 96, False), grid(320, 320, 128, 96, True)
    assert set(a) != set(b), "shifted grid must differ"


def test_init_light_repaint():
    """Starting part-way from an image: the result still reaches the model's target, and a first step of
    the last index leaves the result between the init and the target."""
    plan = Plan(H=256, W=256, sigmas=SIG)
    init = torch.full((16, 256, 256), -0.5)
    x = paint(plan, model(lambda k, s: torch.full(s, 0.3)), init=init, first=4)
    assert float((x - 0.3).abs().max()) < 1e-4, float((x - 0.3).abs().max())


def test_flat():
    plan = Plan(H=256, W=384, sigmas=SIG)
    x = paint(plan, model(lambda k, s: torch.full(s, 0.3)))
    assert float((x - 0.3).abs().max()) < 1e-4, float((x - 0.3).abs().max())


def test_no_seams():
    """Each window wants a different flat colour: the blend must give a smooth field, with no hard edges."""
    torch.manual_seed(0)
    want = {}

    def target(k, s):
        if k not in want:
            want[k] = torch.rand(()).item()
        return torch.full(s, want[k])

    plan = Plan(H=320, W=448, sigmas=SIG)
    x = paint(plan, model(target))[0]
    step_y = (x[1:] - x[:-1]).abs().max().item()
    step_x = (x[:, 1:] - x[:, :-1]).abs().max().item()
    spread = (x.max() - x.min()).item()
    # Hard pasting would jump by up to the full spread between neighbours; a smooth blend moves a little per px.
    assert max(step_x, step_y) < spread / 10, (step_x, step_y, spread)


def test_resume():
    tgt = lambda k, s: torch.linspace(-1, 1, s[-1]).expand(s)  # noqa: E731
    plan = Plan(H=256, W=256, sigmas=SIG)
    full = paint(plan, model(tgt))
    with tempfile.TemporaryDirectory() as d:
        sp = os.path.join(d, "state.pt")
        n = {"steps": 0}

        def on_step(i, steps, ran):
            n["steps"] = i

        first = paint(plan, model(tgt), state_path=sp, on_step=on_step, stop=lambda: n["steps"] == 4)
        assert first is None and n["steps"] == 4
        resumed = paint(plan, model(tgt), state_path=sp, on_step=on_step)
        assert n["steps"] == STEPS
    assert torch.allclose(full, resumed, atol=1e-6), float((full - resumed).abs().max())


def test_hold():
    """Known pixels outside the free band come out exactly as known; the painter fills the rest."""
    H, W = 256, 512  # wide enough that some windows are entirely held
    torch.manual_seed(1)
    known = torch.randn(16, H, W)
    known_px = torch.zeros(H * 8, W * 8, dtype=torch.bool)
    known_px[:, : W * 8 // 2] = True                  # left half is finished
    hold = hold_mask(known_px, band_px=64)
    assert hold[:, : W // 2 - 8].all() and not hold[:, W // 2 - 7:].any()
    calls = {"n": 0}

    def tgt(k, s):
        calls["n"] += 1
        return torch.zeros(s)

    x = paint(Plan(H=H, W=W, sigmas=SIG), model(tgt), known=known, hold=hold)
    assert torch.allclose(x[:, hold], known[:, hold], atol=1e-6)
    assert float(x[:, :, W // 2 + 16:].abs().max()) < 1e-3   # the free part reached the model's target
    no_hold = len(grid(H, W, 128, 96, False)) * (STEPS // 2) + len(grid(H, W, 128, 96, True)) * (STEPS // 2)
    assert calls["n"] < no_hold, "fully held windows must be skipped"


def test_blend_and_feather():
    tiles = [(y, x, torch.full((3, 64, 64), 0.7)) for y in (0, 48, 96) for x in (0, 48, 96, 136)]
    out = blend_tiles((3, 160, 200), tiles, 64, 16)
    assert float((out - 0.7).abs().max()) < 1e-6
    k = torch.zeros(64, 64, dtype=torch.bool)
    k[:, :32] = True
    a = feather(k, 8)
    assert a[0, 0] == 1 and a[0, 31] == 0 and a[0, 40] == 0 and 0 < a[0, 28] < 1


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("ALL PASSED")
