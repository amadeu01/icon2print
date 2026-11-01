from pathlib import Path

import pytest
from shapely.geometry import Polygon, box

from icon2print.cli import main
from icon2print.models import BoxParams, extrude, make_box
from icon2print.outline import combine_rings, load_icon, normalize

EX = Path(__file__).parent.parent / "examples"


def test_nested_rings_become_hole():
    import numpy as np
    outer = np.array([(0, 0), (10, 0), (10, 10), (0, 10)], float)
    inner = np.array([(3, 3), (7, 3), (7, 7), (3, 7)], float)
    g = combine_rings([outer, inner])
    assert g.area == pytest.approx(100 - 16)


def test_overlapping_rings_union():
    import numpy as np
    a = np.array([(0, 0), (6, 0), (6, 6), (0, 6)], float)
    b = np.array([(4, 0), (10, 0), (10, 6), (4, 6)], float)
    assert combine_rings([a, b]).area == pytest.approx(60)


@pytest.mark.parametrize("name", ["barbell", "kettlebell"])
def test_svg_loads_and_scales(name):
    g = normalize(load_icon(EX / f"{name}.svg"), 100)
    minx, miny, maxx, maxy = g.bounds
    assert (minx, miny) == (pytest.approx(0), pytest.approx(0))
    assert maxx == pytest.approx(100)


def test_extrude_watertight():
    m = extrude(box(0, 0, 20, 10), 3)
    assert m.is_volume and m.volume == pytest.approx(600)


@pytest.mark.parametrize("name", ["barbell", "kettlebell"])
def test_box_and_lid_printable(name):
    g = normalize(load_icon(EX / f"{name}.svg"), 110)
    r = make_box(g, BoxParams())
    assert r.body.is_volume and r.lid.is_volume
    assert r.capacity_ml > 10
    # lid plug must fit inside the cavity: plug area < cavity area < outline area
    assert r.lid.bounds[1][2] == pytest.approx(3 + 5 - 0.01, abs=0.02)


def test_holes_sealed_by_default():
    g = Polygon([(0, 0), (60, 0), (60, 60), (0, 60)], [[(20, 20), (40, 20), (40, 40), (20, 40)]])
    r = make_box(g)
    assert r.body.is_volume
    # sealed: capacity equals a full cavity (56x56 area)
    assert r.capacity_ml == pytest.approx(56 * 56 * 38 / 1000, rel=0.02)


def test_wall_too_thick_errors():
    with pytest.raises(ValueError):
        make_box(box(0, 0, 10, 10), BoxParams(wall=6))


def test_cli_box(tmp_path):
    assert main(["box", str(EX / "kettlebell.svg"), "-o", str(tmp_path), "-w", "100"]) == 0
    assert (tmp_path / "kettlebell_box.stl").exists() and (tmp_path / "kettlebell_lid.stl").exists()


def test_raster_roundtrip(tmp_path):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (100, 100), "white")
    ImageDraw.Draw(im).ellipse((10, 10, 90, 90), fill="black")
    f = tmp_path / "dot.png"
    im.save(f)
    g = normalize(load_icon(f), 50)
    assert g.area == pytest.approx(3.14159 * 25**2, rel=0.05)
