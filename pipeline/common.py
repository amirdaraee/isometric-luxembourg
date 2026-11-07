"""Shared paths, projections and camera for the Luxembourg City map."""
from pathlib import Path
import math
import re
import numpy as np
from pyproj import Transformer

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
WORK = ROOT / "data" / "work"
WEB = ROOT / "web"
BATI_ZIP = RAW / "bati3d" / "act2023v2-bati3d-luxembourg.zip"

# LUREF (EPSG:2169). Local origin keeps float32 vertices precise.
ORIGIN_E, ORIGIN_N = 70000.0, 65000.0
_to_luref = Transformer.from_crs(4326, 2169, always_xy=True)
_to_wgs = Transformer.from_crs(2169, 4326, always_xy=True)


def lonlat_to_en(lon, lat):
    return _to_luref.transform(lon, lat)


def en_to_lonlat(e, n):
    return _to_wgs.transform(e, n)


# Pilot: Gare, Ville Haute, Grund, Clausen, Kirchberg.
PILOT_LONLAT = (6.115, 49.597, 6.175, 49.637)
METRES_PER_PIXEL = 0.25  # at the deepest zoom
TILE = 512

# Camera sits south-east, looking north-west, in 2:1 dimetric projection.
ELEV = math.radians(30.0)
R = 1 / math.sqrt(2)
RIGHT = np.array([R, R, 0.0])     # (E, N, z): screen right is north-east
FWD = np.array([-R, R, 0.0])      # into the screen is north-west


def to_screen(e, n, z):
    """World metres (local E, N, z) to screen metres, y up."""
    sx = (e - ORIGIN_E) * RIGHT[0] + (n - ORIGIN_N) * RIGHT[1]
    f = (e - ORIGIN_E) * FWD[0] + (n - ORIGIN_N) * FWD[1]
    sy = f * math.sin(ELEV) + z * math.cos(ELEV)
    return sx, sy


def depth(e, n, z):
    """Distance along the view ray: smaller is nearer the camera."""
    f = (e - ORIGIN_E) * FWD[0] + (n - ORIGIN_N) * FWD[1]
    return f * math.cos(ELEV) - z * math.sin(ELEV)


def landmark_slug(s):
    """URL-safe slug of a landmark title, as used for web/public/landmarks/<slug>/."""
    s = s.lower().replace("ë", "e").replace("é", "e").replace("è", "e").replace("ô", "o").replace("ü", "u").replace("â", "a")
    s = s.replace("ä", "a").replace("ö", "o").replace("ç", "c").replace("ê", "e").replace("î", "i").replace("û", "u").replace("œ", "oe")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def readme_sections(text):
    """The '### Title' sections of a research README, each with its '| key | value |' rows."""
    out = []
    for blk in re.split(r"\n(?=### )", text):
        if blk.startswith("### "):
            title = blk.splitlines()[0][4:].strip()
            rows = dict(re.findall(r"^\| ([^|]+?) \| (.+?) \|\s*$", blk, re.M))
            out.append((title, rows, blk))
    return out
