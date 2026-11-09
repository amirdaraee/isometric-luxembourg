"""Build any area from raw data, stage by stage.

    python -m v2.build <area> [stage ...]      build the stages (and what they need); default: g0
    python -m v2.build <area> --list           the stages, their status and output folders
    python -m v2.build <area> X --force X      rebuild X even if it is up to date

Areas are the files in v2/config/areas (test, commune). Outputs: <data>/v2/<area>/<stage>/<key>/ with a
manifest.json each. A failed check stage makes the command exit with status 1. Workers per stage are capped
(params.json "workers", or V2_WORKERS) so the build shares the machine.
"""
from __future__ import annotations

import argparse
import os
import sys

from v2.build.stages import graph
from v2.config import area_names, params, v2_data


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m v2.build", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("area", choices=area_names())
    ap.add_argument("stages", nargs="*", default=["g0"])
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--force", action="append", default=[], help="stage to rebuild (repeatable; 'all' for every one)")
    a = ap.parse_args(argv)
    g = graph()
    if a.list:
        for n in g.order(list(g.stages)):
            s = g.stages[n]
            print(f"{n:<28} {s.kind:<7} {g.status(n, a.area):<8} {g.folder(n, a.area).relative_to(v2_data())}"
                  f"  <- {', '.join(s.deps) or '-'}")
        return 0
    workers = int(os.environ.get("V2_WORKERS", params().get("workers", 2)))
    return g.build(a.area, a.stages, workers=workers, force=set(a.force))


if __name__ == "__main__":
    sys.exit(main())
