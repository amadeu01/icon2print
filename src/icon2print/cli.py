from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .models import BoxParams, extrude, make_box
import unicodedata

from .outline import is_emoji, load_icon, normalize


def _stem(icon: str) -> str:
    if is_emoji(icon):
        names = [unicodedata.name(c, "").lower().replace(" ", "_") for c in icon if ord(c) > 0x2000 and unicodedata.name(c, "")]
        return "_".join(n for n in names if "variation" not in n) or "emoji"
    return Path(icon).stem


def _common(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("icon", help="SVG, raster (PNG/JPG/...) file, or an emoji character such as 🦄")
    sp.add_argument("-o", "--out", required=True, help="output file (extrude) or directory (box)")
    sp.add_argument("-w", "--width", type=float, default=80.0, help="icon width in mm (default 80)")
    sp.add_argument("--smooth", type=float, default=0.0, help="round off details smaller than this many mm")
    sp.add_argument("--threshold", type=float, default=0.5, help="raster tracing threshold 0..1")
    sp.add_argument("--emoji-font", help="path to a colour emoji font (for emoji input)")
    sp.add_argument("--invert", action="store_true", help="raster: treat light pixels as solid")


d_wall = BoxParams().wall


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="icon2print", description="2D icon -> 3D printable STL")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("extrude", help="solid plaque/keychain/coaster in the icon shape")
    _common(e)
    e.add_argument("--height", type=float, default=3.0, help="thickness in mm (default 3)")

    b = sub.add_parser("box", help="icon-shaped box with lid (e.g. for gym chalk)")
    _common(b)
    d = BoxParams()
    b.add_argument("--height", type=float, default=d.height, help="box height in mm (default 40)")
    b.add_argument("--lid", choices=["plug", "slide"], default="plug",
                   help="lid style: friction-fit plug, or dovetail sliding lid (slides out towards +X)")
    b.add_argument("--wall", type=float, default=None, help="wall thickness (default 2, or 2.4 for --lid slide)")
    b.add_argument("--lip", type=float, default=d.lip, help="slide lid: rail depth into the wall")
    b.add_argument("--detent", type=float, default=d.detent, help="slide lid: click bump height, 0 = none")
    b.add_argument("--floor", type=float, default=d.floor)
    b.add_argument("--lid-height", type=float, default=d.lid_height)
    b.add_argument("--plug-height", type=float, default=d.plug_height)
    b.add_argument("--clearance", type=float, default=d.clearance, help="lid fit gap in mm (default 0.25)")
    b.add_argument("--keep-holes", action="store_true", help="keep holes in the icon (they will leak!)")

    a = ap.parse_args(argv)
    raster_kw = {"threshold": a.threshold, "invert": a.invert}
    if a.emoji_font:
        raster_kw["font"] = a.emoji_font
    try:
        geom = load_icon(a.icon, **(raster_kw if not a.icon.lower().endswith(".svg") else {}))
        geom = normalize(geom, a.width, a.smooth)
        minx, miny, maxx, maxy = geom.bounds
        print(f"Icon size: {maxx - minx:.1f} x {maxy - miny:.1f} mm")
        if a.cmd == "extrude":
            out = Path(a.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            extrude(geom, a.height).export(out)
            print(f"Wrote {out}")
        else:
            wall = a.wall if a.wall is not None else (2.4 if a.lid == "slide" else d_wall)
            params = BoxParams(a.height, wall, a.floor, a.lid_height, a.plug_height, a.clearance,
                               fill_holes=not a.keep_holes, lid_style=a.lid, lip=a.lip, detent=a.detent)
            r = make_box(geom, params)
            out = Path(a.out)
            out.mkdir(parents=True, exist_ok=True)
            stem = _stem(a.icon)
            r.body.export(out / f"{stem}_box.stl")
            r.lid.export(out / f"{stem}_lid.stl")
            print(f"Wrote {out / (stem + '_box.stl')} and {out / (stem + '_lid.stl')}")
            print(f"Capacity: {r.capacity_ml:.0f} ml | widest inner circle: {r.inner_diameter:.1f} mm")
            for w in r.warnings:
                print(f"WARNING: {w}", file=sys.stderr)
    except (ValueError, OSError) as ex:
        print(f"error: {ex}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
