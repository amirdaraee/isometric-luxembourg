"""Stream rows out of a GeoPackage (SQLite) inside a remote zip, without storing the archive or the database.

The national LiDAR 2024 tree survey is one 10 GB GeoPackage in a 3.9 GB zip. The commune needs a few hundred
thousand of its rows, so the zip member is inflated as it downloads and each SQLite page is decoded on the fly:
table leaf pages hold the rows, and the rows of the feature table are recognised by their column count and their
GeoPackage geometry blob. Nothing but the kept rows touches the disk.

SQLite file format: https://www.sqlite.org/fileformat2.html
"""
from __future__ import annotations

import re
import struct
import urllib.request
import zlib

from .http import UA, get_range


def varint(b: bytes, i: int):
    v = 0
    for k in range(8):
        c = b[i + k]
        v = (v << 7) | (c & 0x7F)
        if c < 0x80:
            return v, i + k + 1
    return (v << 8) | b[i + 8], i + 9


def record(b: bytes, i: int):
    """Decode one SQLite record starting at i: list of values (bytes for blobs, str for text)."""
    hsize, j = varint(b, i)
    end = i + hsize
    types = []
    while j < end:
        t, j = varint(b, j)
        types.append(t)
    vals = []
    p = end
    for t in types:
        if t == 0:
            vals.append(None)
        elif 1 <= t <= 6:
            n = (1, 2, 3, 4, 6, 8)[t - 1]
            vals.append(int.from_bytes(b[p:p + n], "big", signed=True)); p += n
        elif t == 7:
            vals.append(struct.unpack(">d", b[p:p + 8])[0]); p += 8
        elif t in (8, 9):
            vals.append(t - 8)
        elif t >= 12 and t % 2 == 0:
            n = (t - 12) // 2; vals.append(bytes(b[p:p + n])); p += n
        elif t >= 13:
            n = (t - 13) // 2; vals.append(b[p:p + n].decode("utf-8", "replace")); p += n
        else:
            return None
    return vals


def leaf_cell(page: bytes, base: int, usable: int, c: int):
    """(rowid, values) of cell c of a table leaf page, or None (cells that spill to overflow pages are skipped)."""
    ptr = struct.unpack(">H", page[base + 8 + 2 * c:base + 10 + 2 * c])[0]
    try:
        size, i = varint(page, ptr)
        rowid, i = varint(page, i)
        if size > usable - 35 or i + size > len(page):
            return None
        vals = record(page, i)
    except (IndexError, struct.error):
        return None
    return None if vals is None else (rowid, vals)


def leaf_count(page: bytes, base: int) -> int:
    return struct.unpack(">H", page[base + 3:base + 5])[0] if page[base] == 0x0D else 0


def leaf_rows(page: bytes, base: int, usable: int, cells=None):
    """(rowid, values) of the cells of a table leaf page."""
    for c in (range(leaf_count(page, base)) if cells is None else cells):
        r = leaf_cell(page, base, usable, c)
        if r is not None:
            yield r


def zip_member_stream(url: str, name_hint: str = ".gpkg", chunk: int = 1 << 22):
    """Yields the inflated bytes of the first zip member whose name contains name_hint (deflate only)."""
    head = get_range(url, 0, 4095)
    assert head[:4] == b"PK\x03\x04", "not a zip"
    method = struct.unpack("<H", head[8:10])[0]
    nl, xl = struct.unpack("<HH", head[26:30])
    name = head[30:30 + nl].decode()
    assert name_hint in name, name
    assert method == 8, f"compression method {method}"
    start = 30 + nl + xl
    req = urllib.request.Request(url, headers={"Range": f"bytes={start}-", "User-Agent": UA})
    r = urllib.request.urlopen(req, timeout=300)
    d = zlib.decompressobj(-15)
    while not d.eof:
        b = r.read(chunk)
        if not b:
            break
        out = d.decompress(b)
        if out:
            yield out


def stream_table(url: str, table_hint: str, keep, log=print, skip_page=None):
    """Rows of the GeoPackage feature table whose name contains table_hint, as dicts, for which keep(row) is true.

    skip_page(first_row, last_row), when given, lets a whole page be skipped from its first and last rows (rows are
    stored in insertion order, which in the survey is tile by tile, so a page's rows lie close together)."""
    buf = bytearray()
    page_size = usable = None
    columns = None
    pageno = 0
    seen = set()
    total = 0
    for out in zip_member_stream(url):
        buf += out
        if page_size is None and len(buf) >= 100:
            assert buf[:16] == b"SQLite format 3\x00"
            page_size = struct.unpack(">H", buf[16:18])[0]
            page_size = 65536 if page_size == 1 else page_size
            usable = page_size - buf[20]
        if page_size is None:
            continue
        n = len(buf) // page_size
        for k in range(n):
            page = bytes(buf[k * page_size:(k + 1) * page_size])
            pageno += 1
            base = 100 if pageno == 1 else 0
            if columns is None:
                # the schema lives in sqlite_master, rooted at page 1 (small, read before any data pages)
                for _, v in leaf_rows(page, base, usable):
                    if len(v) == 5 and v[0] == "table" and table_hint in str(v[1]) and isinstance(v[4], str):
                        body = v[4][v[4].index("(") + 1: v[4].rindex(")")]
                        cols = [re.split(r"\s+", c.strip())[0].strip('"`[]') for c in re.split(r",(?![^(]*\))", body)]
                        columns = [c for c in cols if c and c.upper() not in ("PRIMARY", "UNIQUE", "CONSTRAINT")]
                        log(f"table {v[1]}: {columns}")
                continue
            nc = leaf_count(page, base)
            if not nc:
                continue
            if skip_page is not None and nc >= 2:
                a, b = leaf_cell(page, base, usable, 0), leaf_cell(page, base, usable, nc - 1)
                if (a and b and len(a[1]) == len(b[1]) == len(columns)
                        and skip_page(dict(zip(columns, a[1])), dict(zip(columns, b[1])))):
                    total += nc
                    continue
            for rowid, v in leaf_rows(page, base, usable):
                if len(v) != len(columns) or rowid in seen:
                    continue
                row = dict(zip(columns, v))
                geom = next((x for x in v if isinstance(x, bytes)), None)
                if geom is None or not geom.startswith(b"GP"):
                    continue
                total += 1
                if keep(row):
                    seen.add(rowid)
                    row["_rowid"] = rowid
                    yield row
            if pageno % 250000 == 0:
                log(f"{pageno * page_size / 1e9:.1f} GB read, {total} rows, {len(seen)} kept")
        del buf[:n * page_size]
    log(f"done: {pageno * (page_size or 0) / 1e9:.2f} GB, {total} rows, {len(seen)} kept")
