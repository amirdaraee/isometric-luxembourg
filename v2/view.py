"""Open the v2 viewer locally: python -m v2.view [area] [--port N] [--build]

Serves the area's built release (python -m v2.build <area> release; --build builds it first) with the viewer's dev
server at http://localhost:<port>/ until Ctrl-C. Installs the viewer's Node packages on first use (npm ci).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from v2.config import V2, v2_data


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m v2.view", description=__doc__)
    ap.add_argument("area", nargs="?", default="test")
    ap.add_argument("--port", type=int, default=5174)
    ap.add_argument("--build", action="store_true", help="build the release first")
    a = ap.parse_args(argv)
    if a.build:
        r = subprocess.run([sys.executable, "-m", "v2.build", a.area, "release"])
        if r.returncode:
            return r.returncode
    cur = v2_data() / a.area / "release" / "current.json"
    if not cur.exists():
        print(f"no release for {a.area}: run  python -m v2.build {a.area} release  (or add --build)")
        return 1
    rel = cur.parent / json.loads(cur.read_text())["folder"]
    web = V2 / "web"
    if not (web / "node_modules" / "vite").exists():
        subprocess.run(["npm", "ci", "--ignore-scripts"], cwd=web, check=True)
    print(f"v2 viewer for {a.area}: http://localhost:{a.port}/   (release {rel.name}; Ctrl-C to stop)")
    env = dict(os.environ, V2_AREA=a.area, ISOLUX_DATA=str(v2_data().parent))   # the current release, also after a rebuild
    try:
        return subprocess.run(["node", str(web / "node_modules" / "vite" / "bin" / "vite.js"), "--port", str(a.port)],
                              cwd=web, env=env).returncode
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
