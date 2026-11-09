"""Shared by every layer: the camera frame in tiles, tile encodings, the scene loader and palette helpers.

Specs: v2/docs/specs/conventions.md (tiles, depth, normals), layer-*.md, compositor.md.

**Screen frame.** The camera (camera.md) maps a world point (E, N, z) to screen metres (sx, sy) and a view depth;
v2 map pixels are px = (sx - sx0) / mpp, py = (sy1 - sy) / mpp. The three axes (sx, sy, depth) are orthonormal, so
every layer can be drawn by casting view rays through pixel centres. A horizontal point can also be written in the
*plan frame* (u, f): u = sx (along north-east) and f = (ln - le) / sqrt(2) (along north-west, away from the camera):
    sy = f sin30 + z cos30,  depth = f cos30 - z sin30,  le = (u - f) / sqrt(2),  ln = (u + f) / sqrt(2).

**Tiles.** 512 x 512 map pixels, numbered (tx, ty) in the whole v2 frame at zoom 0, so the test area's tiles are the
commune's. Zoom z halves the resolution: tile (tx, ty) at zoom z covers 512 * 2^z map pixels. Every layer tile is
  c.webp   colour (RGB, lossy q90; the empty pixels are those whose depth is empty)
  g.bin    geometry: depth (uint16, cm above the tile's minimum, 65535 = empty) and the octahedral normal (2 x uint8)
  k.bin    a per-layer class/mask byte (ground class, water mask, ...), where the layer has one
  i.bin    object ids (uint32: 24-bit id + 8-bit class), layer 8 and the transport layer's drivable ids
Data tiles are raw little-endian arrays, each row delta-coded per byte (PNG's "sub" filter), zlib-compressed, so
the viewer decodes them exactly (no colour management, no premultiplied alpha) with DecompressionStream.
"""
from __future__ import annotations

import json
import math
import zlib
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import numpy as np
from PIL import Image

from v2.config import camera as cam_mod
from v2.config import palette as palette_cfg

TILE = 512
APRON = 2                 # extra pixels drawn round every tile, for edge tests across tile borders; cropped
EMPTY = 65535
S30, C30 = 0.5, math.sqrt(3) / 2
R2 = 1 / math.sqrt(2)

# Object classes (layer 8 id tiles: id << 8 | class).
CLASS = {"none": 0, "ground": 1, "wall": 2, "water": 3, "road": 4, "rail": 5, "tram": 6, "path": 7, "steps": 8,
         "deck": 9, "portal": 10, "building": 11, "window": 12, "door": 13, "shopfront": 14, "structure": 15,
         "pier": 16, "arch": 17, "tree": 18, "trunk": 19, "parapet": 20, "lift": 21, "vehicle": 30}

# Layer order (ties in depth go to the later layer, compositor.md design 2). 5-7 are placeholders in phase 1.
COLOUR_LAYERS = ["ground", "relief", "water", "transport", "buildings", "structures", "trees"]


def cam():
    return cam_mod.camera()


# ------------------------------------------------------------------------------------------------ projection
def project(e, n, z):
    """World (LUREF m, m) to (px, py, depth) in v2 map pixels at zoom 0 and metres of view depth."""
    c = cam()
    oe, on = c["origin_en"]
    le, ln = np.asarray(e, float) - oe, np.asarray(n, float) - on
    z = np.asarray(z, float)
    u = (le + ln) * R2
    f = (ln - le) * R2
    sy = f * S30 + z * C30
    return (u - c["frame"]["sx0"]) / c["mpp"], (c["frame"]["sy1"] - sy) / c["mpp"], f * C30 - z * S30


def project_local(le, ln, z):
    """As project, for coordinates already relative to the camera origin (the mesh's)."""
    c = cam()
    u = (le + ln) * R2
    f = (ln - le) * R2
    sy = f * S30 + z * C30
    return (u - c["frame"]["sx0"]) / c["mpp"], (c["frame"]["sy1"] - sy) / c["mpp"], f * C30 - z * S30


def unproject(px, py, depth):
    """Map pixel (zoom 0) and view depth back to world (E, N, z)."""
    c = cam()
    oe, on = c["origin_en"]
    u = c["frame"]["sx0"] + np.asarray(px, float) * c["mpp"]
    sy = c["frame"]["sy1"] - np.asarray(py, float) * c["mpp"]
    d = np.asarray(depth, float)
    f = sy * S30 + d * C30
    z = sy * C30 - d * S30
    return oe + (u - f) * R2, on + (u + f) * R2, z


# view direction (from the camera into the scene) and the screen axes, in world (E, N, up)
RIGHT = np.array([R2, R2, 0.0])
UP = np.array([-R2 * S30, R2 * S30, C30])
VIEW = np.array([-R2 * C30, R2 * C30, -S30])


# ------------------------------------------------------------------------------------------------ tiles
@dataclass(frozen=True)
class Tile:
    tx: int
    ty: int
    apron: int = APRON

    @property
    def size(self):
        return TILE + 2 * self.apron

    @property
    def px0(self):
        return self.tx * TILE - self.apron

    @property
    def py0(self):
        return self.ty * TILE - self.apron

    @cached_property
    def centres(self):
        """Pixel centres in zoom-0 map pixels: (px[cols], py[rows])."""
        return self.px0 + np.arange(self.size) + 0.5, self.py0 + np.arange(self.size) + 0.5

    def crop(self, a):
        a0 = self.apron
        return a[a0:a0 + TILE, a0:a0 + TILE] if a0 else a

    @property
    def name(self):
        return f"{self.tx}_{self.ty}"


def tile_range(area_poly, zmin, zmax, margin_m=10.0):
    """The zoom-0 tiles that can hold anything of the area between heights zmin and zmax."""
    g = area_poly.buffer(margin_m)
    ring = np.array(g.exterior.coords)
    E = np.r_[ring[:, 0], ring[:, 0]]
    N = np.r_[ring[:, 1], ring[:, 1]]
    Z = np.r_[np.full(len(ring), zmin), np.full(len(ring), zmax)]
    px, py, _ = project(E, N, Z)
    return (int(math.floor(px.min() / TILE)), int(math.floor(py.min() / TILE)),
            int(math.floor(px.max() / TILE)), int(math.floor(py.max() / TILE)))


def area_tiles(area_poly, zmin, zmax):
    """Tiles of the area: those meeting the area's outline swept from zmin to zmax (a column of tiles per x)."""
    from shapely.geometry import Polygon, box
    from shapely.ops import unary_union
    g = area_poly.buffer(10.0).simplify(2.0)
    ring = np.array(g.exterior.coords)
    lo = np.column_stack(project(ring[:, 0], ring[:, 1], np.full(len(ring), zmin))[:2])
    hi = np.column_stack(project(ring[:, 0], ring[:, 1], np.full(len(ring), zmax))[:2])
    swept = unary_union([Polygon(lo), Polygon(hi)] + [Polygon([lo[i], lo[i + 1], hi[i + 1], hi[i]]).buffer(0)
                                                        for i in range(len(ring) - 1)])
    x0, y0, x1, y1 = tile_range(area_poly, zmin, zmax)
    out = []
    for ty in range(y0, y1 + 1):
        for tx in range(x0, x1 + 1):
            if swept.intersects(box(tx * TILE, ty * TILE, (tx + 1) * TILE, (ty + 1) * TILE)):
                out.append(Tile(tx, ty))
    return out


# ------------------------------------------------------------------------------------------------ encodings
def oct_encode(nrm):
    """Unit normals (..., 3) to octahedral (..., 2) uint8."""
    n = np.asarray(nrm, float)
    n = n / np.maximum(np.abs(n).sum(-1, keepdims=True), 1e-12)
    x, y, z = n[..., 0], n[..., 1], n[..., 2]
    neg = z < 0
    ox = np.where(neg, (1 - np.abs(y)) * np.sign(x + 1e-30), x)
    oy = np.where(neg, (1 - np.abs(x)) * np.sign(y + 1e-30), y)
    return np.stack([np.clip(np.round((ox * 0.5 + 0.5) * 255), 0, 255),
                     np.clip(np.round((oy * 0.5 + 0.5) * 255), 0, 255)], -1).astype(np.uint8)


def oct_decode(o):
    o = np.asarray(o, float) / 255 * 2 - 1
    x, y = o[..., 0], o[..., 1]
    z = 1 - np.abs(x) - np.abs(y)
    t = np.clip(-z, 0, None)
    x = x + np.where(x >= 0, -t, t)
    y = y + np.where(y >= 0, -t, t)
    v = np.stack([x, y, z], -1)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


SQ3 = math.sqrt(3)


def depth_ref(name: str, z: int = 0, size=TILE):
    """The depth reference of each row of tile `name` at zoom z: sqrt(3) * sy of the row's pixel centre (m).

    For ground at a fixed height, depth = sqrt(3) sy - 2 z, so storing depth minus this plane leaves only the
    height's share (a few hundred metres for the whole city): 16 bits of centimetres hold it at every zoom."""
    c = cam()
    ty = int(name.split("_")[1])
    py = (ty * size + np.arange(size) + 0.5) * 2 ** z
    return SQ3 * (c["frame"]["sy1"] - py * c["mpp"])


def depth_encode(d, ref=None):
    """Depth (m, inf = empty) to (uint16 cm above the minimum, the minimum in cm), relative to ref (per row)."""
    ok = np.isfinite(d)
    r = np.zeros(d.shape[0]) if ref is None else np.asarray(ref, float)
    rel = d - r[:, None]
    if not ok.any():
        return np.full(d.shape, EMPTY, np.uint16), 0
    dmin = int(math.floor(float(rel[ok].min()) * 100))
    code = np.full(d.shape, EMPTY, np.uint16)
    v = np.round(rel[ok] * 100 - dmin)
    if v.max() > EMPTY - 1:
        raise ValueError(f"depth range {v.max() / 100:.1f} m over a tile is more than 16 bits of cm")
    code[ok] = v.astype(np.uint16)
    return code, dmin


def depth_decode(code, dmin, ref=None):
    r = np.zeros(code.shape[0]) if ref is None else np.asarray(ref, float)
    return np.where(code == EMPTY, np.inf, (code.astype(np.float64) + dmin) / 100.0 + r[:, None])


def pack_bin(a: np.ndarray) -> bytes:
    """A (H, W[, C]) array as rows of bytes, each row delta-coded per byte, zlib-compressed."""
    a = np.ascontiguousarray(a)
    H = a.shape[0]
    raw = a.view(np.uint8).reshape(H, -1)
    bpp = a.dtype.itemsize * (a.shape[2] if a.ndim == 3 else 1)
    d = raw.copy()
    d[:, bpp:] = (raw[:, bpp:].astype(np.int16) - raw[:, :-bpp].astype(np.int16)).astype(np.uint8)
    return zlib.compress(d.tobytes(), 6)


def unpack_bin(b: bytes, shape, dtype) -> np.ndarray:
    dtype = np.dtype(dtype)
    H = shape[0]
    raw = np.frombuffer(zlib.decompress(b), np.uint8).reshape(H, -1).copy()
    bpp = dtype.itemsize * (shape[2] if len(shape) == 3 else 1)
    W = raw.shape[1] // bpp
    r = raw.reshape(H, W, bpp)
    np.cumsum(r, axis=1, dtype=np.uint8, out=r)
    return r.reshape(H, -1).view(dtype).reshape(shape)


def write_tile(folder: Path, name: str, rgb=None, depth=None, normal=None, k=None, ids=None, q=90, z=0):
    """Write one tile's files (tile `name` = "tx_ty" at zoom z); returns its depth minimum (cm, against
    depth_ref)."""
    folder.mkdir(parents=True, exist_ok=True)
    dmin = 0
    if rgb is not None:
        im = Image.fromarray(np.ascontiguousarray(rgb, np.uint8))
        if q > 100:
            im.save(folder / f"{name}.c.webp", "WEBP", lossless=True, quality=100, method=4)
        else:
            im.save(folder / f"{name}.c.webp", "WEBP", quality=q, method=4)
    if depth is not None:
        code, dmin = depth_encode(depth, depth_ref(name, z, depth.shape[0]))
        g = np.zeros(depth.shape + (4,), np.uint8)
        g[..., 0] = code & 255
        g[..., 1] = code >> 8
        if normal is not None:
            g[..., 2:] = oct_encode(normal)
        (folder / f"{name}.g.bin").write_bytes(pack_bin(g))
    if k is not None:
        (folder / f"{name}.k.bin").write_bytes(pack_bin(np.ascontiguousarray(k, np.uint8)))
    if ids is not None:
        (folder / f"{name}.i.bin").write_bytes(pack_bin(np.ascontiguousarray(ids, np.uint32)))
    return dmin


def read_tile(folder: Path, name: str, dmin: int, size=TILE, z=0):
    """Decoded tile: dict with rgb, depth, normal, k, ids (those that exist)."""
    out = {}
    p = folder / f"{name}.c.webp"
    if p.exists():
        out["rgb"] = np.asarray(Image.open(p).convert("RGB"))
    p = folder / f"{name}.g.bin"
    if p.exists():
        g = unpack_bin(p.read_bytes(), (size, size, 4), np.uint8)
        code = g[..., 0].astype(np.uint16) | (g[..., 1].astype(np.uint16) << 8)
        out["depth"] = depth_decode(code, dmin, depth_ref(name, z, size))
        out["oct"] = g[..., 2:]
        out["normal"] = oct_decode(g[..., 2:])
    p = folder / f"{name}.k.bin"
    if p.exists():
        out["k"] = unpack_bin(p.read_bytes(), (size, size), np.uint8)
    p = folder / f"{name}.i.bin"
    if p.exists():
        out["ids"] = unpack_bin(p.read_bytes(), (size, size), np.uint32)
    return out


# ------------------------------------------------------------------------------------------------ palette
def pal(group: str, name: str) -> np.ndarray:
    return np.array(palette_cfg()[group][name]["rgb"], float)


def palette_colours() -> np.ndarray:
    out = []
    for g, d in palette_cfg().items():
        if isinstance(d, dict):
            for k, v in d.items():
                if isinstance(v, dict) and "rgb" in v:
                    out.append(v["rgb"])
    return np.array(out, float)


def grain(px, py, amount=0.03, seed=0):
    """Paper grain: a fixed pseudo-random luminance factor per zoom-0 map pixel (1 +- amount), seamless across tiles."""
    x = np.asarray(px, np.int64)[None, :] if np.ndim(px) == 1 else np.asarray(px, np.int64)
    y = np.asarray(py, np.int64)[:, None] if np.ndim(py) == 1 else np.asarray(py, np.int64)
    h = (x * 374761393 + y * 668265263 + seed * 2246822519) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    h = h ^ (h >> 16)
    return 1.0 + amount * ((h & 0xFFFF) / 65535.0 * 2 - 1)


def lum(rgb):
    rgb = np.asarray(rgb, float)
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


# ------------------------------------------------------------------------------------------------ scene
class Scene:
    """Lazy access to the parts of one built scene (scene/<key>/scene.json)."""

    def __init__(self, scene_folder: Path):
        self.folder = Path(scene_folder)
        self.index = json.loads((self.folder / "scene.json").read_text())
        self.area = self.index["area"]

    def part(self, name) -> Path:
        return Path(self.index["parts"][name]["folder"])

    @cached_property
    def terrain(self):
        return dict(np.load(self.part("terrain") / "terrain.npz"))

    @cached_property
    def graph(self):
        return json.loads((self.part("transport") / "graph.json").read_text())

    @cached_property
    def mesh(self):
        return dict(np.load(self.part("buildings") / "mesh.npz"))

    @cached_property
    def buildings(self):
        return json.loads((self.part("buildings") / "buildings.json").read_text())["buildings"]

    @cached_property
    def facades(self):
        return json.loads((self.part("facades") / "facades.json").read_text())

    @cached_property
    def trees(self):
        return dict(np.load(self.part("trees") / "trees.npz"))

    @cached_property
    def water(self):
        return json.loads((self.part("water") / "water.json").read_text())

    @cached_property
    def walls(self):
        return json.loads((self.part("terrain") / "walls.json").read_text())["walls"]

    @cached_property
    def structures(self):
        return json.loads((self.part("structures") / "structures.json").read_text())

    @cached_property
    def places(self):
        return json.loads((self.part("places") / "places.json").read_text())["places"]

    @cached_property
    def transit(self):
        return json.loads((self.part("transit") / "transit.json").read_text())

    @cached_property
    def polygon(self):
        from v2.data.geo import area_polygon
        return area_polygon(self.area)

    @cached_property
    def z_range(self):
        t = self.terrain["mnt"]
        return float(np.nanmin(t)), float(np.nanmax(t))

    @cached_property
    def tiles(self):
        zmin, zmax = self.z_range
        return area_tiles(self.polygon, zmin - 2, zmax + 80)
