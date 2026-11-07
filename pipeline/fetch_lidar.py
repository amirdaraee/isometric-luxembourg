"""Stream the national LiDAR terrain TIFF out of its zip, without storing the zip (about 27 GB temporary)."""
import struct
import time
import urllib.request
import zlib
from common import RAW

U = "https://s3.eu-central-1.amazonaws.com/download.data.public.lu/resources/lidar-2019-modele-numerique-du-terrain/20200121-082330/ACT2019_MNT_EPSG2169.zip"
EXPECT = 27076985843
LOCAL_HEADER = 427
OUT = RAW / "lidar" / "mnt.tif"


def rng(a, b):
    return urllib.request.urlopen(urllib.request.Request(U, headers={"Range": f"bytes={a}-{b}"})).read()


h = rng(LOCAL_HEADER, LOCAL_HEADER + 300)
assert h[:4] == b"PK\x03\x04"
nl, xl = struct.unpack("<HH", h[26:30])
start = LOCAL_HEADER + 30 + nl + xl
assert h[30:30 + nl].endswith(b".tif"), h[30:30 + nl]
r = urllib.request.urlopen(urllib.request.Request(U, headers={"Range": f"bytes={start}-"}), timeout=120)
d = zlib.decompressobj(-15)
n = 0
t0 = time.time()
tmp = OUT.with_suffix(".part")
with open(tmp, "wb") as f:
    while not d.eof:
        b = r.read(1 << 22)
        if not b:
            break
        o = d.decompress(b)
        f.write(o)
        n += len(o)
        if n % (1 << 32) < len(o):
            print(f"{n / 1e9:.1f} GB {time.time() - t0:.0f}s", flush=True)
print("bytes", n, "complete" if n == EXPECT else "INCOMPLETE")
if n == EXPECT:
    tmp.rename(OUT)
