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
