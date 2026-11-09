import numpy as np

from v2.data.scene.profile import resample, solve


def test_grade_cap_and_pins():
    h = np.r_[np.zeros(10), np.full(10, 10.0)]            # a 10 m step in the data
    z = solve(h, 2.0, 0.3, z0=0.0, z1=10.0, smooth_n=1)
    assert z is not None
    assert abs(z[0]) < 1e-9 and abs(z[-1] - 10) < 1e-9
    assert np.all(np.abs(np.diff(z)) <= 0.3 * 2.0 + 1e-6)  # never steeper than the cap


def test_outlier_is_ignored():
    h = np.full(30, 100.0)
    h[15] = 108.0                                          # a lorry on the deck in the surface model
    z = solve(h, 2.0, 0.05)
    assert np.max(np.abs(z - 100.0)) < 0.06


def test_infeasible_pins_return_none():
    assert solve(np.zeros(5), 1.0, 0.01, z0=0.0, z1=5.0) is None


def test_soft_upper_bound_pulls_down():
    n = 40
    h = np.full(n, np.nan)
    hi = np.full(n, 90.0); hi[[0, -1]] = 100.0
    z = solve(h, 2.0, 0.5, z0=100.0, z1=100.0, prior=np.full(n, 100.0), prior_w=0.01, hi_soft=hi, smooth_n=1)
    assert z[n // 2] <= 90.0 + 1e-6


def test_resample_keeps_ends():
    en = np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 5.0]])
    pts, s = resample(en, 2.0)
    assert np.allclose(pts[0], en[0]) and np.allclose(pts[-1], en[-1])
    assert np.all(np.diff(s) <= 2.0 + 1e-9) and abs(s[-1] - 15.0) < 1e-9
