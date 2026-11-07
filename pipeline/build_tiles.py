"""Join rendered frames into a deep-zoom pyramid for the web viewer (OpenSeadragon)."""
import json
import shutil
import pyvips
from common import ROOT, WORK, TILE

OUT = ROOT / "web" / "public" / "tiles"


def main():
    m = json.loads((WORK / "mosaic.json").read_text())
    frames = [pyvips.Image.new_from_file(str(WORK / "frames" / f"{c}_{r}.jpg"), access="sequential")
              for r in range(m["rows"]) for c in range(m["cols"])]
    mosaic = pyvips.Image.arrayjoin(frames, across=m["cols"])
    # Painted patches (tiler output) laid over the render: data/work/tiles/painted.json lists
    # {"file", "x0", "y0", "w", "h"} in mosaic pixels.
    pj = WORK / "tiles" / "painted.json"
    painted = json.loads(pj.read_text()) if pj.exists() else []
    for p in painted:
        im = pyvips.Image.new_from_file(str(WORK / "tiles" / p["file"]))[:3]
        im = im.resize(p["w"] / im.width, vscale=p["h"] / im.height, kernel="lanczos3")
        mosaic = mosaic.insert(im.cast(mosaic.format), p["x0"], p["y0"])
        print("painted patch", p["file"], p["x0"], p["y0"])
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    mosaic.dzsave(str(OUT / "map"), tile_size=TILE, overlap=0, suffix=".webp[Q=82,effort=4]", layout="dz")
    # Levels below one tile are never requested: the viewer stops at the 512 px level.
    for d in (OUT / "map_files").iterdir():
        if d.is_dir() and int(d.name) < 9:
            shutil.rmtree(d)
    (OUT / "meta.json").write_text(json.dumps({"width": mosaic.width, "height": mosaic.height, "tileSize": TILE,
                                               "mpp": m["mpp"], "art": "painted" if painted else "preview", "painted": painted}))
    print("pyramid", mosaic.width, mosaic.height)


if __name__ == "__main__":
    main()
