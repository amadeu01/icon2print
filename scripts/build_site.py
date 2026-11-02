#!/usr/bin/env python3
"""Generate the STL models + manifest shown on the GitHub Pages viewer (docs/).

Usage: python scripts/build_site.py [--width 90] [--height 40]
"""
from __future__ import annotations

import argparse
import json
import sys
import shutil
import tempfile
from pathlib import Path
from dataclasses import replace

from icon2print import BoxParams, load_icon, make_box, normalize

ROOT = Path(__file__).resolve().parent.parent
MODELS = [  # (slug, label, source)
    ("unicorn", "Unicorn 🦄", "🦄"),
    ("steak", "Steak 🥩", "🥩"),
    ("biceps", "Flexed biceps 💪", "💪"),
    ("fire", "Fire 🔥", "🔥"),
    ("gorilla", "Gorilla 🦍", "🦍"),
    ("bear", "Bear 🐻", "🐻"),
    ("t-rex", "T-Rex 🦖", "🦖"),
    ("shark", "Shark 🦈", "🦈"),
    ("octopus", "Octopus 🐙", "🐙"),
    ("pizza", "Pizza 🍕", "🍕"),
    ("burger", "Burger 🍔", "🍔"),
    ("rocket", "Rocket 🚀", "🚀"),
    ("star", "Star ⭐", "⭐"),
    ("heart", "Heart ❤️", "❤️"),
    ("mech-arm", "Mechanical arm 🦾", "🦾"),
    ("drumstick", "Drumstick 🍗", "🍗"),
    ("ox", "Ox 🐂", "🐂"),
    ("lion", "Lion 🦁", "🦁"),
    ("kettlebell", "Kettlebell (SVG)", "examples/kettlebell.svg"),
    ("barbell", "Barbell (SVG)", "examples/barbell.svg"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=float, default=90)
    ap.add_argument("--height", type=float, default=40)
    a = ap.parse_args()
    final = ROOT / "docs" / "models"
    out = Path(tempfile.mkdtemp(prefix="models-", dir=final.parent))  # built here, swapped in only on success
    manifest = []
    failed: list[str] = []
    params = BoxParams(height=a.height, wall=2.4)  # one wall that works for both lid styles
    for slug, label, src in MODELS:
        path = ROOT / src
        entry = {"slug": slug, "label": label}
        try:
            geom = load_icon(str(path) if path.exists() else src)
            geom = normalize(geom, a.width, smooth=1.0)
            for style in ("plug", "slide"):
                r = make_box(geom, replace(params, lid_style=style))
                for w in r.warnings:
                    print(f"  {slug}/{style}: {w}", file=sys.stderr)
                r.body.export(out / f"{slug}_{style}_box.stl")
                r.lid.export(out / f"{slug}_{style}_lid.stl")
                entry[style] = {"capacity_ml": round(r.capacity_ml), "inner_mm": round(r.inner_diameter, 1)}
                if r.lid_z is not None:
                    entry[style]["lid_z"] = round(r.lid_z, 3)
        except (ValueError, OSError) as e:
            print(f"FAILED {slug}: {e}", file=sys.stderr)
            failed.append(slug)
            continue
        manifest.append(entry)
        print(f"{slug}: plug {entry['plug']['capacity_ml']} ml, slide {entry['slide']['capacity_ml']} ml")
    if failed:  # keep the previous models/manifest untouched rather than publish a partial set
        print(f"error: {len(failed)} model(s) failed ({', '.join(failed)}); docs/models left unchanged", file=sys.stderr)
        shutil.rmtree(out)
        return 1
    data = {"params": {"width": a.width, "height": a.height, "wall": params.wall, "lid_height": params.lid_height}, "models": manifest}
    (out / "manifest.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
    if final.exists():
        shutil.rmtree(final)
    out.rename(final)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
