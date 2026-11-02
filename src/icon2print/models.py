"""Build printable meshes (STL) from a 2D shapely geometry. All units are millimetres."""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import numpy as np
import trimesh
from shapely import affinity
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union


def _polygons(geom: BaseGeometry) -> list[Polygon]:
    if geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    return [p for g in getattr(geom, "geoms", []) for p in _polygons(g)]


def extrude(geom: BaseGeometry, height: float, z0: float = 0.0) -> trimesh.Trimesh:
    """Extrude a 2D geometry straight up from z0 to z0 + height."""
    meshes = []
    for p in _polygons(geom):
        p = p.simplify(0.005, preserve_topology=True)  # drop duplicate points that break triangulation
        m = trimesh.creation.extrude_polygon(p, height)
        m.apply_translation([0, 0, z0])
        meshes.append(m)
    if not meshes:
        raise ValueError("Nothing to extrude (empty geometry).")
    return meshes[0] if len(meshes) == 1 else trimesh.util.concatenate(meshes)


def _union(a: trimesh.Trimesh, b: trimesh.Trimesh) -> trimesh.Trimesh:
    return trimesh.boolean.union([a, b], engine="manifold")


@dataclass
class BoxParams:
    height: float = 40.0        # total body height
    wall: float = 2.0           # wall thickness (use >= 2 x nozzle width)
    floor: float = 2.0          # bottom thickness
    lid_height: float = 3.0     # lid plate thickness
    plug_height: float = 5.0    # how far the lid plug goes into the box
    clearance: float = 0.25     # gap between plug and cavity (friction fit); tune per printer
    min_cavity_area: float = 20.0  # drop cavity islands smaller than this (mm^2)
    fill_holes: bool = True     # icon holes would leak chalk; seal them by default
    lid_style: str = "plug"     # "plug" (friction-fit) or "slide" (dovetail rail, slides out towards +X)
    lip: float = 1.0            # slide: how far the lid's rail reaches into the wall
    detent: float = 0.3         # slide: height of the click bump (0 disables); >0.4 makes it an interference fit
    layer: float = 0.2          # slide: slice height used to build the 45 degree dovetail


@dataclass
class BoxResult:
    body: trimesh.Trimesh
    lid: trimesh.Trimesh
    capacity_ml: float
    inner_diameter: float       # widest circle that fits in the cavity (mm)
    warnings: list[str] = field(default_factory=list)
    lid_z: float | None = None  # slide: z of the lid's underside when closed (for assembly previews)


def make_box(outline: BaseGeometry, p: BoxParams = BoxParams()) -> BoxResult:
    """Make an icon-shaped container and a matching lid.

    The lid is oriented for printing: plate on the bed, plug pointing up.
    """
    warns: list[str] = []
    parts = _polygons(outline)
    if not parts:
        raise ValueError("Empty outline.")
    if len(parts) > 1:
        parts.sort(key=lambda q: q.area, reverse=True)
        warns.append(f"Icon has {len(parts)} separate parts; the box uses the largest only.")
    outer = parts[0]
    if p.lid_style not in ("plug", "slide"):
        raise ValueError("lid_style must be 'plug' or 'slide'.")
    if p.lid_style == "slide" and not p.fill_holes:
        warns.append("--keep-holes is ignored for sliding lids (holes would leak chalk).")
    if (p.fill_holes or p.lid_style == "slide") and outer.interiors:
        outer = Polygon(outer.exterior)
    cavity_depth = p.height - p.floor
    if cavity_depth <= 0:
        raise ValueError("height must be larger than floor.")
    if p.plug_height >= cavity_depth:
        raise ValueError("plug_height must be smaller than the cavity depth.")
    if p.lid_height <= 0 or p.wall <= 0 or p.floor <= 0:
        raise ValueError("wall, floor and lid_height must be positive.")

    cavity = outer.buffer(-p.wall, join_style="round")
    cav_parts = [c for c in _polygons(cavity) if c.area >= p.min_cavity_area]
    if not cav_parts:
        raise ValueError("Walls consume the whole icon; increase --width or reduce --wall.")
    if len(cav_parts) < len(_polygons(cavity)) or len(cav_parts) > 1:
        warns.append("Thin sections of the icon are too narrow for a cavity and are printed solid.")
    cavity = unary_union(cav_parts)

    if p.lid_style == "slide":
        body, lid, lid_z = _slide_parts(outer, cavity, p, warns)
        cavity_depth = lid_z - p.floor  # the lid and its roof occupy the top of the box
    else:
        plug = cavity.buffer(-p.clearance, join_style="round")
        if plug.is_empty:
            raise ValueError("Clearance too large for this cavity.")
        walls = outer.difference(cavity)
        body = _union(extrude(outer, p.floor), extrude(walls, cavity_depth, z0=p.floor))
        lid = _union(extrude(outer, p.lid_height), extrude(plug, p.plug_height, z0=p.lid_height - 0.01))

    inner_d = max(_inscribed(c) for c in _polygons(cavity))
    capacity = cavity.area * cavity_depth / 1000.0
    if not (body.is_watertight and lid.is_watertight):
        warns.append("A mesh is not watertight; check it in your slicer before printing.")
    return BoxResult(body, lid, capacity, inner_d, warns, lid_z if p.lid_style == "slide" else None)


def _inscribed(poly: Polygon) -> float:
    from shapely import maximum_inscribed_circle

    line = maximum_inscribed_circle(poly)
    return float(2 * line.length)


def sweep_x(geom: BaseGeometry, dist: float) -> BaseGeometry:
    """Exact area swept by `geom` translated along +X by `dist` (Minkowski sum with a segment)."""
    parts = []
    for poly in _polygons(geom):
        poly = Polygon(poly.exterior)
        parts += [poly, affinity.translate(poly, dist, 0)]
        c = list(poly.exterior.coords)
        for (x0, y0), (x1, y1) in zip(c[:-1], c[1:]):
            q = Polygon([(x0, y0), (x1, y1), (x1 + dist, y1), (x0 + dist, y0)])
            if q.area > 1e-9:
                parts.append(q)
    return unary_union(parts)


def _stack(regions: list[tuple[BaseGeometry, float]], z0: float = 0.0) -> list[trimesh.Trimesh]:
    """Extrude consecutive (region, thickness) slices on top of each other."""
    meshes, z = [], z0
    for region, t in regions:
        region = region.buffer(0)
        if not region.is_empty:
            meshes.append(extrude(region, t, z0=z))
        z += t
    return meshes


def _slide_parts(outer: Polygon, cavity: BaseGeometry, p: BoxParams, warns: list[str]):
    """Dovetail sliding lid. The lid slides out towards +X; the groove is cut into the top of the walls.

    Cross-section (lid): vertical rail `lip` wide for h_s, then a 45 degree chamfer back to the
    cavity edge, so the box roof above the lid is a 45 degree overhang and prints without supports.
    """
    lip, clr, dz = p.lip, p.clearance, p.layer
    if lip <= 0 or dz <= 0 or clr < 0 or p.detent < 0:
        raise ValueError("Sliding lid needs lip > 0, layer > 0, clearance >= 0 and detent >= 0.")
    h_s = p.lid_height - lip                       # height of the vertical part of the lid rail
    if h_s < 2 * dz:
        raise ValueError("lid_height must exceed lip by at least 0.4 mm for a sliding lid.")
    if p.wall - lip - clr < 0.79:
        raise ValueError(f"wall too thin for a sliding lid: need wall >= lip + clearance + 0.8 = {lip + clr + 0.8:.1f} mm.")
    n_l = max(1, round(lip / dz))
    step = lip / n_l
    # Groove chamfer = lid chamfer shifted up one layer and out by the clearance, so the 45 degree
    # staircase keeps `clearance` of free space at every corner.
    n_g = math.ceil((lip + clr) / step + 0.5)
    top_zone = h_s + n_g * step
    g0 = p.height - top_zone                       # groove floor (lid rests here)
    if g0 < p.floor + 5:
        raise ValueError(f"Box too short for a sliding lid (only {g0 - p.floor:.1f} mm of cavity); use --height {p.floor + 5 + top_zone:.0f} or more.")
    if p.detent > h_s - 0.7:
        raise ValueError(f"detent too large for this lid; use <= {max(h_s - 0.7, 0):.1f} mm.")

    # --- lid: bottom on the bed, rail first, chamfer on top
    lid_slices = [(cavity.buffer(lip, join_style="round"), h_s)]
    lid_slices += [(cavity.buffer(lip - (k + 0.5) * lip / n_l, join_style="round"), lip / n_l) for k in range(n_l)]
    lid = _union_all(_stack(lid_slices))

    # --- box: base + ring + groove zone (outer minus swept groove profile)
    minx, _, maxx, _ = outer.bounds
    dist = (maxx - minx) + 4 * (lip + clr)
    def groove_region(o: float) -> BaseGeometry:
        return outer.difference(sweep_x(cavity.buffer(o, join_style="round"), dist))

    zone = [(groove_region(lip + clr), h_s)]
    zone += [(groove_region(min(lip + clr, max(lip + clr - (k - 0.5) * step, 0.0))), step) for k in range(n_g)]
    pieces = [extrude(outer, p.floor), extrude(outer.difference(cavity), g0 - p.floor, z0=p.floor)]
    pieces += _stack(zone, z0=g0)
    body = _union_all(pieces)

    if p.detent > 0:  # click bump on the groove floor + dimple under the lid, at the top and bottom of the cavity
        ledge = cavity.buffer(lip, join_style="round").difference(cavity)
        ext = max(_polygons(cavity), key=lambda q: q.area).exterior.coords
        r = min(0.5, lip / 2)
        spots = [(pt[0], pt[1] + sgn * lip / 2) for pt, sgn in
                 ((max(ext, key=lambda c: c[1]), 1), (min(ext, key=lambda c: c[1]), -1))]
        if all(ledge.buffer(0.05).contains(Point(x, y).buffer(r)) for x, y in spots):  # both or none, so the lid sits level
            for x, y in spots:
                bump = trimesh.creation.cylinder(radius=r, height=p.detent + 0.01, sections=16)
                bump.apply_translation([x, y, g0 - 0.01 + (p.detent + 0.01) / 2])
                body = _union_all([body, bump])
                dimple = trimesh.creation.cylinder(radius=r + clr, height=p.detent + 0.2, sections=16)
                dimple.apply_translation([x, y, (p.detent + 0.2) / 2 - 0.1])
                lid = trimesh.boolean.difference([lid, dimple], engine="manifold")
        else:
            warns.append("Could not place the click bump on this shape; the lid is friction-only.")
    return body, lid, g0


def _union_all(meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    return meshes[0] if len(meshes) == 1 else trimesh.boolean.union(meshes, engine="manifold")
