"""HTTP helpers for the fetch stages: retries with back-off, byte ranges, and a seekable remote file.

Downloads are polite and modest: one request at a time, a User-Agent naming the project, back-off on busy servers.
"""
from __future__ import annotations

import io
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "isometric-luxembourg-v2-build/0.1 (+https://github.com/amirdaraee/isometric-luxembourg)"


def get(url: str, data: bytes | None = None, headers: dict | None = None, timeout: float = 180, tries: int = 8,
        wait: float = 15) -> bytes:
    h = {"User-Agent": UA, **(headers or {})}
    last = None
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=timeout) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as ex:  # busy server: wait and retry
            last = ex
            code = getattr(ex, "code", None)
            if code in (400, 403, 404):
                raise
            print(f"  http retry {attempt + 1}/{tries}: {ex}", flush=True)
            time.sleep(min(wait * (attempt + 1), 240))
    raise RuntimeError(f"giving up on {url}: {last}")


def head_size(url: str) -> int:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(r.headers["Content-Length"])


def get_range(url: str, a: int, b: int) -> bytes:
    """Bytes a..b inclusive."""
    return get(url, headers={"Range": f"bytes={a}-{b}"}, timeout=120)


def post_form(url: str, form: dict, timeout: float = 300) -> bytes:
    return get(url, data=urllib.parse.urlencode(form).encode(), timeout=timeout,
               headers={"Accept": "application/json"})


class RangeFile(io.RawIOBase):
    """A read-only, seekable view of a remote file, fetched in 64 KiB blocks on demand (for COG headers)."""

    BLOCK = 1 << 16

    def __init__(self, url: str):
        super().__init__()
        self.url, self.pos = url, 0
        self.size = head_size(url)
        self.cache: dict[int, bytes] = {}
        self.fetched = 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else (self.pos + off if whence == 1 else self.size + off)
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        if n <= 0:
            return b""
        B = self.BLOCK
        a, b = self.pos // B, (self.pos + n - 1) // B
        missing = [k for k in range(a, b + 1) if k not in self.cache]
        if missing:
            lo, hi = missing[0] * B, min((missing[-1] + 1) * B, self.size) - 1
            data = get_range(self.url, lo, hi)
            self.fetched += len(data)
            for i, k in enumerate(range(missing[0], missing[-1] + 1)):
                self.cache[k] = data[i * B:(i + 1) * B]
        buf = b"".join(self.cache[k] for k in range(a, b + 1))
        s = self.pos - a * B
        out = buf[s:s + n]
        self.pos += len(out)
        return out

    def readinto(self, b):
        d = self.read(len(b))
        b[:len(d)] = d
        return len(d)
