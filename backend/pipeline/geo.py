"""Geometry helpers: planar projection (metres), ward polygons, road segments, STRtree."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass

from shapely.geometry import LineString, Point, shape
from shapely.strtree import STRtree

import config

# Mumbai sits near 19N: a single local equirectangular projection is accurate to well under 1%.
_LAT0 = 19.0
_KX = 111_320.0 * math.cos(math.radians(_LAT0))
_KY = 110_574.0


def to_xy(lat: float, lon: float) -> tuple[float, float]:
    return lon * _KX, lat * _KY


def to_latlon(x: float, y: float) -> tuple[float, float]:
    return y / _KY, x / _KX


def dist_m(lat1, lon1, lat2, lon2) -> float:
    x1, y1 = to_xy(lat1, lon1)
    x2, y2 = to_xy(lat2, lon2)
    return math.hypot(x1 - x2, y1 - y2)


def _project_coords(coords):
    return [to_xy(lat, lon) for lon, lat in coords]


@dataclass
class Geo:
    ward_polys: dict          # ward_code -> shapely Polygon (projected)
    ward_geojson: dict        # raw (lon/lat) for the frontend
    road_lines: dict          # road_id -> shapely LineString (projected)
    road_ward: dict           # road_id -> ward_code
    road_ids: list
    _road_tree: STRtree

    def ward_at(self, lat: float, lon: float) -> str | None:
        p = Point(*to_xy(lat, lon))
        for code, poly in self.ward_polys.items():
            if poly.contains(p):
                return code
        return None

    def nearest_road(self, lat: float, lon: float, max_m: float, ward: str | None = None):
        """Nearest road segment within max_m; optionally restricted to a ward. -> (road_id, metres) | (None, None)"""
        p = Point(*to_xy(lat, lon))
        idxs = self._road_tree.query(p.buffer(max_m))
        best = (None, None)
        for i in idxs:
            rid = self.road_ids[int(i)]
            if ward and self.road_ward.get(rid) != ward:
                continue
            d = self.road_lines[rid].distance(p)
            if d <= max_m and (best[1] is None or d < best[1]):
                best = (rid, d)
        return best

    def roads_within(self, lat: float, lon: float, radius_m: float):
        p = Point(*to_xy(lat, lon))
        out = []
        for i in self._road_tree.query(p.buffer(radius_m)):
            rid = self.road_ids[int(i)]
            d = self.road_lines[rid].distance(p)
            if d <= radius_m:
                out.append((rid, d))
        return sorted(out, key=lambda t: t[1])


_GEO: Geo | None = None


def load_geo(force: bool = False) -> Geo:
    global _GEO
    if _GEO is not None and not force:
        return _GEO
    wards = json.loads((config.DATA_DIR / "wards.geojson").read_text(encoding="utf-8"))
    roads = json.loads((config.DATA_DIR / "roads.geojson").read_text(encoding="utf-8"))
    from shapely.geometry import Polygon

    polys = {}
    for f in wards["features"]:
        g = shape(f["geometry"])
        polys[f["properties"]["ward_code"]] = Polygon(_project_coords(g.exterior.coords))
    lines, road_ward = {}, {}
    for f in roads["features"]:
        rid = f["properties"]["road_id"]
        lines[rid] = LineString(_project_coords(f["geometry"]["coordinates"]))
        road_ward[rid] = f["properties"]["ward_code"]
    ids = list(lines)
    tree = STRtree([lines[i] for i in ids])
    _GEO = Geo(polys, wards, lines, road_ward, ids, tree)
    return _GEO
