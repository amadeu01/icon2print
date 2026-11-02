"""Load a 2D icon (SVG or raster) into a shapely geometry measured in millimetres."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from shapely import affinity
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

RASTER_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}


def combine_rings(rings: list[np.ndarray]) -> BaseGeometry:
    """Combine closed rings into one geometry using nesting depth.

    A ring inside an even number of other rings is solid, inside an odd number it is
    a hole. Overlapping (non-nested) rings are unioned, so icons built from several
    overlapping shapes still work.
    """
    polys = []
    for r in rings:
        if len(r) < 3:
            continue
        p = Polygon(r)
        if not p.is_valid:
            p = p.buffer(0)
        if not p.is_empty and p.area > 1e-9:
            polys.append(p)
    if not polys:
        return Polygon()
    depth = []
    for i, p in enumerate(polys):
        pt = p.representative_point()
        depth.append(sum(1 for j, q in enumerate(polys) if j != i and q.area > p.area and q.contains(pt)))
    result: BaseGeometry = Polygon()
    for d, p in sorted(zip(depth, polys), key=lambda t: t[0]):
        result = result.union(p) if d % 2 == 0 else result.difference(p)
    return result


def load_svg(path: str | Path) -> BaseGeometry:
    from svgelements import SVG, Close, Line, Move, Path as SvgPath, Shape

    svg = SVG.parse(str(path), reify=True)
    rings = []
    for el in svg.elements():
        if not isinstance(el, Shape):
            continue
        if getattr(el, "fill", None) is not None and getattr(el.fill, "value", 1) is None:
            continue  # fill="none": stroke-only, ignored
        sp = SvgPath(el)
        for sub in sp.as_subpaths():
            pts: list = []
            for seg in SvgPath(sub):
                if isinstance(seg, Move):
                    pts.append((seg.end.x, seg.end.y))
                elif isinstance(seg, (Line, Close)):
                    if seg.end is not None:
                        pts.append((seg.end.x, seg.end.y))
                else:
                    ts = np.linspace(0, 1, 33)[1:]
                    pts.extend(tuple(seg.npoint(ts)[i]) for i in range(len(ts)))
            if len(pts) >= 3:
                rings.append(np.array(pts, dtype=float))
    geom = combine_rings(rings)
    return affinity.scale(geom, yfact=-1, origin=(0, 0))  # SVG y points down


def load_raster(path: str | Path, threshold: float = 0.5, invert: bool = False) -> BaseGeometry:
    """Trace a raster icon. Uses alpha if present, else dark pixels count as solid."""
    from PIL import Image
    from skimage import measure

    img = path if isinstance(path, Image.Image) else Image.open(path)
    img = img.convert("RGBA")
    a = np.asarray(img, dtype=float) / 255.0
    if a[..., 3].min() < 0.99:  # real transparency: opaque = solid
        mask = a[..., 3]
    else:
        mask = 1.0 - a[..., :3].mean(axis=2)  # dark = solid
    if invert:
        mask = 1.0 - mask
    mask = np.pad(mask, 1)  # close contours touching the border
    rings = [np.column_stack([c[:, 1], -c[:, 0]]) for c in measure.find_contours(mask, threshold)]
    geom = combine_rings(rings)
    return geom.simplify(0.35, preserve_topology=True)


EMOJI_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
    "/usr/share/fonts/noto/NotoColorEmoji.ttf",
    "/System/Library/Fonts/Apple Color Emoji.ttc",
    "C:/Windows/Fonts/seguiemj.ttf",
]


def is_emoji(text: str) -> bool:
    return bool(text) and not Path(text).exists() and not Path(text).suffix and any(ord(c) > 0x2000 for c in text)


def load_emoji(text: str, font: str | None = None, **kw) -> BaseGeometry:
    """Render an emoji with a colour emoji font and trace its silhouette."""
    from PIL import Image, ImageDraw, ImageFont

    candidates = [font] if font else EMOJI_FONT_CANDIDATES
    f = None
    for c in candidates:
        if c and Path(c).exists():
            try:
                f = ImageFont.truetype(c, 109)  # Noto/Apple bitmap fonts need fixed sizes
                break
            except OSError:
                continue
    if f is None:
        raise ValueError("No colour emoji font found; pass --emoji-font /path/to/font.ttf or use an SVG/PNG.")
    img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((20, 20), text, font=f, embedded_color=True)
    bbox = img.getchannel("A").getbbox()
    if not bbox:
        raise ValueError(f"Font has no glyph for {text!r}.")
    img = img.crop(bbox).convert("RGBA")
    img = img.resize((img.width * 4, img.height * 4), Image.LANCZOS)  # smoother contours
    kw.setdefault("threshold", 0.5)
    return load_raster(img, **kw).simplify(0.8, preserve_topology=True)


def load_icon(path: str | Path, **kw) -> BaseGeometry:
    if isinstance(path, str) and is_emoji(path):
        return load_emoji(path, **kw)
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".svg":
        return load_svg(p)
    if ext in RASTER_EXTS:
        return load_raster(p, **kw)
    raise ValueError(f"Unsupported icon format: {ext} (use .svg or {', '.join(sorted(RASTER_EXTS))})")


def normalize(geom: BaseGeometry, width: float, smooth: float = 0.0) -> BaseGeometry:
    """Scale to `width` mm wide (bounding box) and move the lower-left corner to (0, 0).

    `smooth` (mm) rounds off tiny spikes/notches, which helps printability.
    """
    if geom.is_empty:
        raise ValueError("The icon contains no filled shapes.")
    minx, miny, maxx, maxy = geom.bounds
    g = affinity.translate(geom, -minx, -miny)
    g = affinity.scale(g, width / (maxx - minx), width / (maxx - minx), origin=(0, 0))
    if smooth > 0:
        g = g.buffer(smooth, join_style="round").buffer(-smooth, join_style="round")
        g = g.buffer(-smooth, join_style="round").buffer(smooth, join_style="round")
    if isinstance(g, MultiPolygon) and len(g.geoms) > 1:
        g = unary_union(g)
    return g
