# v2 data: sources, licences, dates

All data is open. Nothing here is in git except the small config files named below; downloads and outputs live in
`<data>/raw` (v1's, reused, read only) and `<data>/v2` (v2's). Every fetch is a stage of the build graph, so its
query, URL and snapshot label are in its manifest. Credits for the published map: ACT (Administration du cadastre
et de la topographie), data.public.lu, Administration des transports publics, © OpenStreetMap contributors.

## Reused from v1 (`data/raw`, `data/work`, `web/public/data`)

| Data | Where | Source, licence | Date | Size | Used for |
|---|---|---|---|---|---|
| 3D buildings, LoD2.2, the commune (CityGML + textures) | `raw/bati3d/act2023v2-bati3d-luxembourg.zip` | ACT "Bâtiments 3D" (bati3d) 2023 v2, data.public.lu, **CC0** | file 17 Mar 2026; buildings created 29 Apr 2024 | 6.4 GB zip (1.1 GB GML) | `scene_buildings` (23,373 buildings) |
| National GTFS timetable | `raw/gtfs/20261104/` | Administration des transports publics / data.public.lu, **CC BY** (as v1 credits it) | feed of 4 Nov 2026 | 85 MB | `scene_transit` |
| Landmark cards (129) and places (1,035) | `web/public/data/landmarks.json`, `places.json` (in git) | v1's research (`research/`, licences per file) and OSM | v1 | 0.3 MB | `scene_places` |
| v1 terrain (LiDAR 2019 2 m, fitted) | `work/terrain.npz` | ACT LiDAR 2019 MNT, CC0 (via v1) | 2019 | 22 MB | only to turn v1 pixels back into metres exactly |
| Orthophoto 2023 tiles (pilot box) | `raw/ortho2023` | ACT / geoportail, CC0 | 2023 | 73 MB | not used in Phase 0 (classes only, phase 1) |

Not reused: v1's OSM extracts (`raw/osm/*.json`: pilot box only and without node ids, which junctions need), v1's
2 m LiDAR terrain (replaced by LiDAR 2024 at 0.5/1 m), v1's tree cut for block b00 (replaced by the commune cut),
v1's painted art and warp outputs (reference only; PLAN_V2 section 11).

## Fetched in Phase 0 (`data/v2`)

| Data | Stage | Source, licence | Date | Download | Stored |
|---|---|---|---|---|---|
| Commune boundary (relation 407489) and its 24 quarters (admin_level 9) | `python -m v2.data.fetch.boundary` → `v2/config/areas/*.geojson` (in git) | OpenStreetMap, **ODbL** | OSM of 9 Nov 2026 07:26 UTC | < 1 MB | 0.4 MB in git |
| OSM transport: highways, railways, aerialways, bridges and bridge outlines, tunnels, with node ids | `fetch_osm_transport` (shared) | Overpass API, **ODbL** | OSM of 9 Nov 2026 07:34 UTC | 12.7 MB | 12.7 MB |
| OSM ground: land use, leisure, natural, water, walls, cliffs, squares, pedestrian areas, street lamps | `fetch_osm_ground` (shared) | Overpass API, **ODbL** | same | 13.8 MB | 13.8 MB |
| LiDAR 2024 terrain (MNT) and surface (MNS) | `fetch_lidar` (per area) | ACT "Lidar 2024 – Relevé 3D", COGs `MNT_Lidar2024.tif`, `MNS_Lidar2024.tif`, data.public.lu, **CC0** | survey 2024, published 23 Dec 2024 | test: 96 MB (0.5 m, full resolution); commune: 2.3 GB (the 0.5 m tiles, reduced to 1 m as they arrive: terrain by mean, surface by max) | test 46 MB, commune 541 MB (compressed float32) |
| OSM entrances, shops, crafts and amenities (for doors and shop fronts) | `fetch_osm_pois` (shared) | Overpass API, **ODbL** | OSM of 9 Nov 2026 | ~ 3 MB | ~ 3 MB |
| OSM places of worship with their outlines: ways and relations tagged `building=church`, `cathedral` or `chapel`, or `amenity=place_of_worship` (for church facades) | `fetch_osm_worship` (shared) | Overpass API, **ODbL** | OSM of 13 Nov 2026 | 0.07 MB | 0.07 MB |
| LiDAR 2024 tree survey (crown centroids, height, crown widths, type) | `fetch_trees` (shared) | ACT "LiDAR 2024 – Arbres", GeoPackage points, data.public.lu, **CC0** | resource of 1 Oct 2026 | 3.9 GB streamed (not stored): the SQLite pages are decoded on the fly and only the commune's 1,119,104 trees kept | 61 MB |

Downloads ran one at a time (the whole set in about 7 minutes at ~40 MB/s); the LiDAR COGs are read by HTTP ranges
(only the tiles of the window, one request per tile row). Total stored: ~0.9 GB of fetches, ~2 GB with the
commune's scene outputs.

## Notes and limits

- **Heights.** ACT 3D buildings and LiDAR use the same national heights; buildings sit on the LiDAR ground with a
  median difference of ~1 m (check TR4).
- **CityGML axis order.** The bati3d file stores northing, easting, height (the envelope confirms it).
- **Tree survey.** Automated detection: positions are crown centroids, not trunks; a few spikes (cranes, masts)
  are dropped by the 50 m cap. Only `crown_*`, `tree_height`, `tree_type`, `terrain`, `luref_x/y`, `tree_uuid` are
  kept.
- **Commune terrain at 1 m** (kept at 1 m, owner G0). It is built from the 0.5 m tiles, not from ACT's 1 m
  overviews: those of the terrain and the surface model are not made the same way (at 1 m the surface lay below the
  terrain on 0.6% of the commune, never at 0.5 m; check TR3). Terrain = mean of each 2 × 2 block, surface = max.
- **Bridges.** ACT removes bridges from the terrain model (MNT) and keeps them in the surface model (MNS): decks come
  from the MNS (transport-graph.md).
