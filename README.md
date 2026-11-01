# icon2print

Turn a flat 2D icon (SVG or PNG/JPG) into 3D-printable STL files. The headline feature:
**icon-shaped chalk boxes** (magnesium carbonate) with a matching friction-fit lid, so a
powerlifter can carry chalk in a kettlebell, barbell, plate… or any logo-shaped container.

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
