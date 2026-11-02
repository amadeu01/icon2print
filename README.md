# icon2print

Turn a flat 2D icon (SVG or PNG/JPG) into 3D-printable STL files. The headline feature:
**icon-shaped chalk boxes** (magnesium carbonate) with a matching friction-fit lid, so a
powerlifter can carry chalk in a kettlebell, barbell, plate… or any logo-shaped container.

**Live 3D viewer:** https://amadeu01.github.io/icon2print/ (rotate and download the STLs in your browser).
Rebuild the models with `python scripts/build_site.py`; the page itself is static (`docs/`, three.js vendored).

## Install

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

Chalk box + lid (two STLs, each already oriented for printing):

```bash
icon2print box examples/kettlebell.svg -o out --width 110 --height 45
# -> out/kettlebell_box.stl, out/kettlebell_lid.stl
```

Solid plaque / keychain / coaster:

```bash
icon2print extrude examples/barbell.svg -o out/barbell_plaque.stl --width 80 --height 3
```

The tool prints the box capacity (ml) and the widest circle that fits inside the cavity, so you
can check that your chalk block fits (measure your block, and keep the inner diameter larger).

### Emoji boxes

Pass an emoji instead of a file; its silhouette becomes the box shape (needs a colour emoji font,
e.g. `fonts-noto-color-emoji`; use `--emoji-font` for another font):

```bash
icon2print box 🦄 -o out --width 90 --height 40 --smooth 1   # -> unicorn_face_box.stl / _lid.stl
scripts/emoji_boxes.sh out/emoji                              # batch: unicorn, steak, biceps, gorilla, shark...
```

**Apple style:** on a Mac, point at Apple's font (Apple's glyphs are proprietary, so the repo doesn't ship them):

```bash
icon2print box 🦄 -o out --emoji-font "/System/Library/Fonts/Apple Color Emoji.ttc"
```

Chunky silhouettes (🥩 🍗 ❤️ 🦄 🍔) hold the most chalk; thin-legged animals have less room.

### Sliding lid (dovetail)

`--lid slide` swaps the friction-fit plug for a rail lid that slides out towards +X. The top of the
walls gets a 45° dovetail groove (prints without supports); the lid has the matching profile and a
small click bump + dimple (`--detent`, 0 disables). It's parametric, so it works for any icon shape.

```bash
icon2print box 🦄 -o out --lid slide --width 90 --height 40   # wall defaults to 2.4 mm
```

`--clearance 0.2` is a good start for a calibrated printer; `--lip` is the rail depth. Needs
`wall >= lip + clearance + 0.8`. Print the box upright and the lid flat. The bump height is a
guess and needs tuning on your printer.

### Box options

| Option | Default | Meaning |
|---|---|---|
| `--width` | 80 | Icon width in mm (sets overall size) |
| `--height` | 40 | Box height in mm |
| `--wall` / `--floor` | 2 / 2 | Wall and bottom thickness (≥ 2× nozzle width) |
| `--lid-height` | 3 | Lid plate thickness |
| `--plug-height` | 5 | How far the lid plug enters the box |
| `--clearance` | 0.25 | Lid fit gap; raise if too tight, lower if loose |
| `--smooth` | 0 | Round off details smaller than N mm (helps printing) |
| `--keep-holes` | off | Keep icon holes (they would leak chalk, so they're sealed by default) |

Raster icons: `--threshold 0.5` controls tracing, `--invert` treats light pixels as solid.
Transparent PNGs use the alpha channel.

## Icon tips

- Emojis and PNGs are traced from their silhouette (alpha), so colours don't matter.
- Use a **single-colour, filled** silhouette. Stroke-only paths are ignored; convert strokes to outlines first.
- Overlapping shapes are merged; shapes nested inside others become holes (even-odd rule).
- Chunky shapes make good boxes. Thin bars (like the barbell's bar) leave little inner space; thin
  sections narrower than ~2× wall are printed solid.
- If an icon has several disconnected parts, the box uses the largest part.

## Printing

PLA/PETG, 0.2 mm layers, 3+ perimeters. Print the box upright and the lid as exported (plate on the bed).
Do a quick clearance test print before a big one; fit varies by printer.

## Development

```bash
pytest
```

Layout: `src/icon2print/outline.py` (load/scale icons), `models.py` (extrude, box, lid), `cli.py`.

## Ideas

Belt/carabiner loop, embossed lettering, magnet-closing lid, sifter/shaker lid for loose chalk.
