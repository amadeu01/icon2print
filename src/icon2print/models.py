"""Build printable meshes (STL) from a 2D shapely geometry. All units are millimetres."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import trimesh
from shapely.geometry import MultiPolygon, Polygon
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


@dataclass
class BoxResult:
    body: trimesh.Trimesh
    lid: trimesh.Trimesh
    capacity_ml: float
    inner_diameter: float       # widest circle that fits in the cavity (mm)
    warnings: list[str] = field(default_factory=list)


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
    if p.fill_holes and outer.interiors:
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
    return BoxResult(body, lid, capacity, inner_d, warns)


def _inscribed(poly: Polygon) -> float:
    from shapely import maximum_inscribed_circle

    line = maximum_inscribed_circle(poly)
    return float(2 * line.length)
