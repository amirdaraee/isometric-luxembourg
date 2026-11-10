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

# The caption v1's style LoRA was trained with (pipeline/style/prompt.txt): every painting prompt keeps its wording
# and its trigger, so the LoRA answers as trained, and adds the even-light sentence.
V1_CAPTION = ("Fill in the outlined section with the missing pixels corresponding to the <isometric luxembourg ink> "
              "style, removing the border and exactly following the shape/style/structure of the surrounding image "
              "(if present).")
EVEN = " Evenly lit with flat light: no shadows, no shading from one side, nothing that moves."
NEW_TRIGGER = "<isometric luxembourg ink unshadowed>"

# C1 (and B2 without C's LoRA): v1's style LoRA as the teacher, asked for even light
C_TARGET_PROMPT = V1_CAPTION + EVEN
# the caption of every training example of the unshadowed LoRA (C2), and the prompt it paints with (C3, B2)
C_PAINT_PROMPT = V1_CAPTION.replace("<isometric luxembourg ink>", NEW_TRIGGER) + EVEN
LANDMARK_BRIEF = C_TARGET_PROMPT
# C4: one facade seen front-on
C_FACADE_PROMPT = C_PAINT_PROMPT + (" The image is one building facade seen exactly front-on: straight horizontal and "
                                    "vertical lines, each window where the layout shows it.")
