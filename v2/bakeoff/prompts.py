"""Prompts and lists for bake-off methods B and C. Every prompt forbids light, shadows and anything that moves (brief
5 and 9); every output is checked for both before it is used (dataset.py, compose.py)."""
from __future__ import annotations

COMMON_NEGATIVE = ("shadows, cast shadows, shading, sunlight, highlights, gradient lighting, ambient occlusion, "
                   "perspective, vanishing point, cars, vehicles, people, animals, text, watermark, signature")

MATERIAL_BRIEF = ("A seamless tileable texture swatch, seen exactly front-on (orthographic), evenly lit with flat "
                  "light and no shadows at all, in a hand-drawn inked illustration style: clean dark ink lines, flat "
                  "colour fills, a little paper grain. Straight horizontal and vertical lines. {what}. "
                  "Colour close to RGB {rgb}. No perspective, no light direction, nothing that moves.")

# name -> (what, palette key whose colour it follows, real size in metres the swatch covers (w, h))
MATERIALS = {
    "roof_slate": ("Blue-grey slate roof: rows of small rectangular slates, staggered joints", "buildings.roof_slate", (2.0, 2.0)),
    "roof_slate_dark": ("Dark slate roof: rows of slates, staggered joints", "buildings.roof_slate_dark", (2.0, 2.0)),
    "roof_tile": ("Red clay tile roof: rows of curved tiles", "buildings.roof_tile", (2.0, 2.0)),
    "roof_tile_old": ("Weathered terracotta tile roof: rows of tiles, slight tone changes", "buildings.roof_tile_old", (2.0, 2.0)),
    "roof_flat": ("Flat roof covered with fine gravel", "buildings.roof_flat", (2.0, 2.0)),
    **{f"wall_{c}": (f"Smooth lime-rendered wall, {c} colour, faint render texture", f"buildings.facade_{c}", (2.0, 2.0))
       for c in ("cream", "ochre", "pink", "yellow", "blue", "sage", "white", "apricot")},
    "wall_stone": ("Yellow sandstone ashlar wall: regular courses of dressed blocks", "buildings.wall_stone", (2.0, 2.0)),
    "plinth": ("Sandstone base course: large dressed blocks", "buildings.plinth", (2.0, 1.0)),
    "window_casement": ("One tall casement window, white frame, glazing bars, dark glass, stone sill", "buildings.window", (1.1, 1.45)),
    "window_shuttered": ("One tall window with two painted wooden louvred shutters open beside it", "buildings.shutter_green", (2.2, 1.45)),
    "window_shop": ("A shop window front with a striped awning on top, glazing bars", "buildings.awning_red", (3.0, 3.0)),
    "door_panel": ("A painted wooden front door with panels and a fanlight, stone frame", "buildings.door_green", (1.2, 2.3)),
    "door_double": ("A double wooden door with panels and a fanlight", "buildings.door_red", (1.6, 2.3)),
    "door_garage": ("A garage door with horizontal panels", "buildings.door_wood", (2.6, 2.3)),
    "cornice": ("A plain moulded stone cornice band", "buildings.trim", (2.0, 0.4)),
    "quoins": ("Stone corner quoins, alternating long and short blocks", "buildings.trim", (0.6, 2.0)),
    "stone_viaduct": ("Grey-yellow masonry of a railway viaduct: large ashlar courses", "structures.stone", (2.0, 2.0)),
    "railing": ("A simple painted steel railing with vertical bars", "structures.railing", (2.0, 1.1)),
}

LANDMARK_BRIEF = ("<isometric luxembourg ink> Paint the outlined building in the inked style: clean dark ink outlines, "
                  "flat colour, detailed stonework, straight windows exactly where they are drawn. Evenly lit: no "
                  "sun, no cast shadows, no shading from one side. Keep its exact outline and every line of the "
                  "drawing. Nothing that moves: no cars, people or birds.")

C_PAINT_PROMPT = ("<isometric luxembourg ink unshadowed> Fill in the outlined buildings in the inked style: clean dark "
                  "ink lines, flat colours, detailed roofs and facades, every window exactly where the layout shows "
                  "it. Evenly lit: no shadows. Nothing that moves.")

C_TARGET_PROMPT = ("<isometric luxembourg ink> Convert the outlined section to the inked style with even, flat light: "
                   "no sun shadows, no shading, no cars, no people. Keep every line and window of the input.")

C_FACADE_PROMPT = ("<isometric luxembourg ink unshadowed> Paint this building facade seen exactly front-on, in the inked "
                   "style: straight horizontal and vertical lines, each window where the layout shows it, flat even "
                   "light, no shadows, nothing that moves.")
