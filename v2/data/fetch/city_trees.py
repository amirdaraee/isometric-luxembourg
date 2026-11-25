"""Fetch: the city's tree register (Ville de Luxembourg, Service Parcs), for each tree's species.

The layer behind maps.vdl.lu/maps/cadastre_trees. It is published for consultation and states no licence; it is used
by the owner's decision (25 Nov 2026; research/v2/DECISIONS.md)."""
from __future__ import annotations

import json

import numpy as np

from v2.config import params


def city_trees_params(area: str) -> dict:
    return dict(params()["fetch"]["city_trees"])


def fetch_city_trees(ctx):
    """The city's tree register (Ville de Luxembourg, Service Parcs): every tree's species, cultivar, height and
    crown, read from the public map service a page at a time. city_trees.json: one row per tree, in LUREF metres."""
    import urllib.parse

    from v2.data.fetch.http import get
    from v2.data.geo import lonlat_to_en
    p = ctx.params
    rows, offset = [], 0
    while True:
        q = urllib.parse.urlencode({"where": "1=1", "outFields": ",".join(p["fields"]), "returnGeometry": "true",
                                    "outSR": 4326, "orderByFields": "OBJECTID", "resultOffset": offset,
                                    "resultRecordCount": p["page"], "f": "json"})
        d = json.loads(get(f"{p['url']}?{q}", headers={"User-Agent": "Mozilla/5.0 (compatible; map-build)"}))
        if "error" in d:
            raise RuntimeError(f"city tree register: {d['error']}")
        got = d.get("features", [])
        for f in got:
            g, a = f.get("geometry"), f["attributes"]
            if not g or g.get("x") is None:
                continue
            rows.append((g["x"], g["y"], (a.get("BAUMART") or "").strip(), (a.get("SORTE") or "").strip(),
                         (a.get("BAUMART_GROUP") or "").strip(), (a.get("GA_NAME") or "").strip(),
                         a.get("BAUMHOEHE"), a.get("KRONENDURCHMESSER")))
        ctx.log(f"register: {len(rows)} trees")
        offset += len(got)
        if not got or not d.get("exceededTransferLimit"):
            break
    e, n = lonlat_to_en(np.array([r[0] for r in rows]), np.array([r[1] for r in rows]))
    out = [{"e": round(float(a), 2), "n": round(float(b), 2), "latin": r[2], "cultivar": r[3], "genus": r[4], "place": r[5],
            "height": r[6], "crown": r[7]} for a, b, r in zip(e, n, rows)]
    (ctx.out / "city_trees.json").write_text(json.dumps({"source": p["url"], "trees": out}, ensure_ascii=False))
    return {"trees": len(out), "with_species": sum(1 for r in out if r["latin"])}
