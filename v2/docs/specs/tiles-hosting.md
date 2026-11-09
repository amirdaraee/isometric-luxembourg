# Tiles and hosting (Cloudflare R2)

**Why R2.** The commune at 0.125 m/px is 121 856 × 66 048 px per layer (8 Gpx); with several layers, buffers and
seasons that is far over GitHub Pages' 1 GB. v1's viewer already reads tiles from a configurable URL.

**Tile sets.** One per layer and channel group (`config/layers.json` "tiles"): 512 × 512 px, zoom 0 = full
resolution (0.125 m), each level halves, down to one tile for the commune. Paths:

    <bucket>/<release>/<layer>[/<variant>]/<z>/<x>_<y>.webp
    <bucket>/<release>/index.json        layers, variants, zoom range, frame (camera.json), per-tile depth offsets

`variant` is a season or an hour band where a layer has them (trees per season). Formats: conventions.md.

**Far zoom.** Below a set zoom (decided at G1 by measurement), layers 1–7 are merged into one colour tile set with
gentle generalisation (small clutter dropped, main streets slightly emphasised: DECISIONS 9 Nov), and the buffers
by nearest surface. The near zooms stay exact.

**Releases are immutable.** A release folder is never rewritten; a fix is a new release that copies the unchanged
tiles server-side and ships the changed ones (OTHERS 7.4: London's patch-as-layer). The viewer's `index.json` URL
picks the release; v1 stays at `/v1`.

**Cost.** R2 storage ≈ $0.015/GB-month, no egress fees; Class A writes ≈ $4.50 per million. Estimated at G1 from the
test area's real tile sizes, quoted in the ledger (`phase5_launch`), capped.

**Checks.**
- T1 (gate) Every tile of the release's index exists and decodes; no tile outside the area's frame + 1 tile.
- T2 (gate) The share of the commune polygon covered by the release's tiles at zoom 0 = 100% for a "whole city"
  release (V1_RETRO P8).
- T3 (gate) Seams across tile borders (conventions) at every zoom.
- T4 (gate) First view under 0.5 s on a mid phone from R2 (PLAN_V2 section 8, Speed).
