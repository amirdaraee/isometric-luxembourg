import sqlite3

from v2.checks.framework import Report
from v2.data.fetch.gpkg_stream import leaf_count, leaf_rows


def test_report_gates_and_notes():
    r = Report("x")
    r.at_most("A1", "bad things", 0, 0)
    r.info("A2", "a fact", 12)
    assert r.result()["passed"]
    r.at_least("A3", "share", 0.5, 0.9, examples=["e1"])
    res = r.result()
    assert not res["passed"]
    assert any(line.startswith("FAIL A3") for line in res["lines"])
    r2 = Report("y")
    r2.add("B1", "only a note", False, severity="report")
    assert r2.result()["passed"]


def test_sqlite_pages_decode(tmp_path):
    """The streaming GeoPackage reader decodes SQLite table leaf pages like SQLite itself."""
    db = tmp_path / "t.sqlite"
    con = sqlite3.connect(db)
    con.execute("PRAGMA page_size=4096")
    con.execute("CREATE TABLE trees (id INTEGER PRIMARY KEY, geom BLOB, luref_x TEXT, h REAL, kind TEXT)")
    rows = [(i, b"GP\x00\x01" + bytes(20), f"{77000 + i}.5", 10.0 + i / 10, "conifer") for i in range(1, 400)]
    con.executemany("INSERT INTO trees VALUES (?,?,?,?,?)", rows)
    con.commit(); con.close()
    data = db.read_bytes()
    size = 4096
    usable = size - data[20]
    got = {}
    for k in range(len(data) // size):
        page = data[k * size:(k + 1) * size]
        base = 100 if k == 0 else 0
        if leaf_count(page, base):
            for rowid, v in leaf_rows(page, base, usable):
                if len(v) == 5 and isinstance(v[1], bytes):
                    got[rowid] = v
    assert len(got) == 399
    assert got[7][2] == "77007.5" and abs(got[7][3] - 10.7) < 1e-9 and got[7][4] == "conifer"


def test_hue_of_what_is_lit_to_the_top():
    """V8's measure (L9.6): a cream wall lit past white and cut off channel by channel turns lemon, far from its own
    hue; scaled back and paled (the light pass's rule, light.json sun.toon.pale) it keeps it."""
    import numpy as np
    from v2.checks.g1_checks import _hue_deg, _sat
    from v2.layers.light import LIGHT
    sun, grade = LIGHT["sun"], LIGHT["grade"]
    white = sun["ambient"] + sun["direct"] * np.array(grade["day_tint"])          # a white surface, lit
    walls = np.array([[247, 225, 178], [247, 231, 183], [237, 199, 142], [232, 180, 128]]) / 255
    lit = walls * white
    assert (lit.max(-1) > 1).all()
    cut = np.clip(lit, 0, 1)
    top = lit.max(-1, keepdims=True)
    kept = lit / top + (1 - lit / top) * np.clip((top - 1) * sun["toon"]["pale"], 0, 1)
    turn = lambda c: np.abs((_hue_deg(c) - _hue_deg(walls) + 180) % 360 - 180)
    assert (turn(cut) > 6).any() and turn(cut).max() > 10
    assert turn(kept).max() < 4            # what is left is the sun's own colour on the wall
    assert (_sat(kept) >= 0.15).all() and (kept.max(-1) >= 0.99).all()
    assert abs(_hue_deg(np.array([1.0, 0.0, 0.0]))) < 1e-9 and abs(_hue_deg(np.array([0.0, 1.0, 0.0])) - 120) < 1e-9
