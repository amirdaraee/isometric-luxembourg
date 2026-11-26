"""Roof coverings from the orthophoto (v2/data/scene/roofs.py): the classing on made-up roofs."""
import numpy as np

from v2.config import params
from v2.data.scene import roofs as RF
from v2.layers.common import pal

P = params()["roofs"]
SLATE, DARK_SLATE, BLUE_SLATE, GREY_SLATE = (126, 130, 138), (96, 101, 108), (118, 128, 146), (134, 134, 136)
TILE, BROWN_TILE, GRAVEL, MEMBRANE, SEDUM, SHADE = (214, 128, 78), (150, 118, 100), (150, 138, 118), (150, 152, 156), (104, 132, 84), (20, 24, 26)


def roof(colour, n=400, other=None, share=0.0):
    a = np.tile(np.array(colour, float), (n, 1))
    if other is not None:
        a[: int(n * share)] = other
    return a


def test_slate_in_its_shades_and_tile():
    assert RF.classify(roof(SLATE), False, P)[0] == "roof_slate"
    assert RF.classify(roof(DARK_SLATE), False, P)[0] == "roof_slate_dark"
    assert RF.classify(roof(BLUE_SLATE), False, P)[0] == "roof_slate_blue"
    assert RF.classify(roof(GREY_SLATE), False, P)[0] == "roof_slate_warm"
    assert RF.classify(roof(TILE), False, P)[0] == "roof_tile"
    assert RF.classify(roof(BROWN_TILE), False, P)[0] == "roof_tile_brown"


def test_a_slate_roof_with_a_tiled_dormer_or_a_shadow_stays_slate():
    assert RF.classify(roof(SLATE, other=TILE, share=0.3), False, P)[0] == "roof_slate"
    name, fig = RF.classify(roof(SLATE, other=SHADE, share=0.45), False, P)
    assert name == "roof_slate" and fig["px"] == 220                     # the shadow is not read


def test_flat_roofs_and_a_roof_too_small_to_read():
    assert RF.classify(roof(MEMBRANE), True, P)[0] == "roof_flat"
    assert RF.classify(roof(GRAVEL), True, P)[0] == "roof_flat_gravel"
    assert RF.classify(roof(SEDUM), True, P)[0] == "roof_flat_green"
    assert RF.classify(roof(TILE), True, P)[0] in RF.FLATS                # a flat roof never gets tile or slate
    assert RF.classify(roof(SLATE), False, P)[0] in RF.SLATES
    assert RF.classify(roof(SLATE, n=P["min_px"] - 1), False, P)[0] is None
    assert RF.classify(roof(SHADE), False, P)[0] is None


def test_every_covering_is_a_palette_colour_and_slate_is_blue_over_red():
    for n in RF.SLATES + RF.TILES + RF.FLATS:
        assert len(pal("buildings", n)) == 3
    for n in RF.SLATES:
        r, g, b = pal("buildings", n)
        assert b > g > r                                                 # v1's slate: blue-grey
    for n in RF.TILES:
        r, g, b = pal("buildings", n)
        assert r > g > b
