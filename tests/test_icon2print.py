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


def test_emoji_box(tmp_path):
    from icon2print.outline import EMOJI_FONT_CANDIDATES
    if not any(Path(f).exists() for f in EMOJI_FONT_CANDIDATES):
        pytest.skip("no colour emoji font installed")
    assert main(["box", "🦄", "-o", str(tmp_path), "-w", "90"]) == 0
    assert (tmp_path / "unicorn_face_box.stl").exists()


def _slide(src, **kw):
    g = normalize(load_icon(src), 90, smooth=1.0)
    return make_box(g, BoxParams(height=40, wall=2.4, lid_style="slide", **kw))


@pytest.mark.parametrize("name", ["barbell", "kettlebell"])
def test_slide_lid_printable_and_slides(name):
    import trimesh
    r = _slide(EX / f"{name}.svg", detent=0)
    assert r.body.is_volume and r.lid.is_volume
    g0 = 40 - (2 + 7 * 0.2)  # lid_height 3 -> 2 mm rail + 7 chamfer layers
    lid = r.lid.copy()
    lid.apply_translation([0, 0, g0])
    for dx in (0, 0.15, 2, 10, 40, 120):  # lid must clear the box all the way out
        moved = lid.copy()
        moved.apply_translation([dx, 0, 0])
        assert trimesh.boolean.intersection([r.body, moved], engine="manifold").volume < 1e-6
    lifted = lid.copy()
    lifted.apply_translation([0, 0, 1.0])  # dovetail: lid can't be lifted straight out
    assert trimesh.boolean.intersection([r.body, lifted], engine="manifold").volume > 1


def test_slide_wall_too_thin():
    with pytest.raises(ValueError):
        make_box(box(0, 0, 60, 60), BoxParams(wall=2.0, lid_style="slide"))


def test_cli_slide(tmp_path):
    assert main(["box", str(EX / "kettlebell.svg"), "-o", str(tmp_path), "--lid", "slide"]) == 0


def test_slide_capacity_excludes_lid_space():
    g = box(0, 0, 80, 80)
    plug = make_box(g, BoxParams(height=40, wall=2.4))
    slide = make_box(g, BoxParams(height=40, wall=2.4, lid_style="slide"))
    assert slide.capacity_ml < plug.capacity_ml
    assert slide.lid_z is not None and 30 < slide.lid_z < 38


@pytest.mark.parametrize("kw", [dict(lip=0), dict(lip=-1), dict(clearance=-0.1), dict(detent=3), dict(height=10)])
def test_slide_bad_params_raise_valueerror(kw):
    with pytest.raises(ValueError):
        make_box(box(0, 0, 80, 80), BoxParams(wall=2.4, lid_style="slide", **{"height": 40, **kw}))
