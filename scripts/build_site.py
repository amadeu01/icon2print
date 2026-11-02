#!/usr/bin/env python3
"""Generate the STL models + manifest shown on the GitHub Pages viewer (docs/).

Usage: python scripts/build_site.py [--width 90] [--height 40]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

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
    out = ROOT / "docs" / "models"
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    failed: list[str] = []
    for slug, label, src in MODELS:
        path = ROOT / src
        try:
            geom = load_icon(str(path) if path.exists() else src)
            geom = normalize(geom, a.width, smooth=1.0)
            r = make_box(geom, BoxParams(height=a.height))
        except (ValueError, OSError) as e:
            print(f"FAILED {slug}: {e}", file=sys.stderr)
            failed.append(slug)
            continue
        for w in r.warnings:
            print(f"  {slug}: {w}", file=sys.stderr)
        r.body.export(out / f"{slug}_box.stl")
        r.lid.export(out / f"{slug}_lid.stl")
        manifest.append({"slug": slug, "label": label, "capacity_ml": round(r.capacity_ml),
                         "inner_mm": round(r.inner_diameter, 1)})
        print(f"{slug}: {r.capacity_ml:.0f} ml")
    if failed:  # don't publish a manifest that silently drops models
        print(f"error: {len(failed)} model(s) failed ({', '.join(failed)}); manifest not written", file=sys.stderr)
        return 1
    data = {"params": {"width": a.width, "height": a.height, "wall": BoxParams().wall}, "models": manifest}
    (out / "manifest.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
