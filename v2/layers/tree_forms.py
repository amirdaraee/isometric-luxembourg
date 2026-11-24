"""Tree species as drawn (spec: v2/docs/specs/layer-07-trees.md, "Species"): each species' crown outline, texture,
colours and trunk, from v2/config/tree_species.json and the palette. Nothing here knows where a tree stands: which species
a tree is comes from the scene (v2/data/scene/tree_species.py)."""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from v2.config import params, tree_species
from v2.layers.common import pal


@lru_cache(maxsize=None)
def table() -> dict:
    """The species of tree_species.json, as arrays in the list's order."""
    S = tree_species()
    names = list(S["list"])
    rows = [{**S["defaults"], **S["list"][n]} for n in names]
    form = [S["forms"][r["form"]] for r in rows]
    col = lambda k, src=rows: np.array([r[k] for r in src], float)
    return {
        "names": names, "form": [r["form"] for r in rows],
        "widest": col("widest", form), "top": col("top", form), "bottom": col("bottom", form),
        "foot": col("foot"), "open": col("open"), "lobes": col("lobes"), "squash": col("squash"), "hang": col("hang"),
        "clump": np.array([r["clump"][0] for r in rows], float), "clump_max": np.array([r["clump"][1] for r in rows], float),
        "width": np.array([r["width"] for r in rows], float), "h": np.array([r["h"] for r in rows], float),
        "share": col("share"), "trunk": [r["trunk"] for r in rows], "trunk_w": col("trunk_w_m"),
        "light": np.array([pal("trees", f"sp_{n}_light") for n in names]),
        "dark": np.array([pal("trees", f"sp_{n}_dark") for n in names]),
    }


def by_type(typ, type_names=None) -> np.ndarray:
    """The species drawn for a tree of which only the survey's type is known (tree_species.json by_type)."""
    B = tree_species()["by_type"]
    names = table()["names"]
    types = [str(t) for t in (type_names if type_names is not None else params()["trees"]["types"])]
    lut = np.array([names.index(B.get(t, B["other"])) for t in types])
    return lut[np.asarray(typ, int)]


def species_index(T) -> np.ndarray:
    """Each tree's row in table(): the scene's species where it has them, else its type's."""
    if "species" in T and "species_names" in T:
        names = table()["names"]
        lut = np.array([names.index(str(s)) for s in T["species_names"]])
        return lut[np.asarray(T["species"], int)]
    return by_type(T["type"], T.get("type_names"))


def form_of(sp) -> dict:
    """The per-tree form arrays of trees of species rows `sp`."""
    t = table()
    sp = np.asarray(sp, int)
    return {k: t[k][sp] for k in ("widest", "top", "bottom", "foot", "open", "lobes", "squash", "hang", "clump", "clump_max")}


def profile(zz, widest, top, bottom):
    """A crown's radius (share of its widest) at height zz (-1 its foot, 1 its top): widest at `widest` (0 to 1 up
    the crown); a superellipse of power `top` above and `bottom` below (2 is a round arc, 1 a straight taper)."""
    t = (np.asarray(zz, float) + 1) / 2
    up = t >= widest
    u = np.clip(np.where(up, (t - widest) / np.maximum(1 - widest, 1e-6), (widest - t) / np.maximum(widest, 1e-6)), 0, 1)
    p = np.where(up, top, bottom)
    return np.clip(1 - u ** p, 0, 1) ** (1 / p)


GRID = 512


@lru_cache(maxsize=None)
def _surface(widest, top, bottom):
    """For one outline: heights spread evenly over its surface (GRID + 1 values from top to foot), and the surface's
    size against a round crown's. On a round crown the heights are evenly spaced, as a sphere's surface is."""
    zz = np.linspace(-1, 1, 1025)
    f = profile(zz, widest, top, bottom)
    w = np.sqrt(f ** 2 + np.gradient(f ** 2 / 2, zz) ** 2)        # surface per unit height (1 all the way on a sphere)
    cdf = np.concatenate([[0], np.cumsum((w[1:] + w[:-1]) / 2 * np.diff(zz))])
    inv = np.interp(np.linspace(0, 1, GRID + 1), cdf / cdf[-1], zz)
    return inv[::-1].copy(), float(cdf[-1] / 2)


def spread(q, widest, top, bottom):
    """Heights zz for places q (0 the top, 1 the foot) spread evenly over each tree's crown surface, and each
    crown's surface against a round one's (per tree)."""
    q = np.clip(np.asarray(q, float), 0, 1)
    zz = np.empty(len(q))
    key = np.column_stack([widest, top, bottom]).round(4)
    for u in np.unique(key, axis=0):
        m = (key == u).all(1)
        inv, _ = _surface(*map(float, u))
        zz[m] = np.interp(q[m] * GRID, np.arange(GRID + 1), inv)
    return zz


def surface_share(widest, top, bottom):
    key = np.column_stack([widest, top, bottom]).round(4)
    out = np.ones(len(key))
    for u in np.unique(key, axis=0):
        out[(key == u).all(1)] = _surface(*map(float, u))[1]
    return out
