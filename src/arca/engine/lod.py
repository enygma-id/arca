# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import math
import shutil
from pathlib import Path
from typing import Optional

import numpy as np

try:
    from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
    from shapely.ops import unary_union
except ImportError as exc:
    raise RuntimeError(
        "Shapely is required for topology-preserving LOD1.3/envelope derivation. "
        "Install with: uv add shapely"
    ) from exc

from .geom import normal
from .georef import _ring_geo_xy, local_to_lonlat
from .utils import write_json_compact


class PlanarUnionAccumulator:
    """Batch-union source-face XY projections without bbox/convex-hull loss."""

    def __init__(self, flush_size: int = 256, min_projected_area: float = 1e-6):
        self.flush_size = max(8, int(flush_size))
        self.min_projected_area = float(min_projected_area)
        self.pending = []
        self.merged = None
        self.source_polygons = 0

    def add_xy(self, xy):
        arr = np.asarray(xy, dtype=float)
        if arr.ndim != 2 or len(arr) < 3 or arr.shape[1] < 2:
            return
        ring = [(float(x), float(y)) for x, y in arr[:, :2]]
        if len(ring) >= 2 and np.allclose(ring[0], ring[-1], atol=1e-9):
            ring = ring[:-1]
        if len(ring) < 3:
            return
        try:
            poly = Polygon(ring)
            if not poly.is_valid:
                poly = poly.buffer(0)
        except Exception:
            return
        if poly.is_empty or float(poly.area) <= self.min_projected_area:
            return
        self.pending.append(poly)
        self.source_polygons += 1
        if len(self.pending) >= self.flush_size:
            self.flush()

    def flush(self):
        if not self.pending:
            return
        batch = unary_union(self.pending)
        self.pending = []
        self.merged = batch if self.merged is None else unary_union([self.merged, batch])

    def geometry(self):
        self.flush()
        return self.merged


def _polygonal_only(geom):
    if geom is None or geom.is_empty:
        return None
    if isinstance(geom, (Polygon, MultiPolygon)):
        return geom
    if isinstance(geom, GeometryCollection):
        polys = [g for g in geom.geoms if isinstance(g, (Polygon, MultiPolygon))]
        return unary_union(polys) if polys else None
    return None


def _drop_small_components(geom, min_area_m2: float):
    geom = _polygonal_only(geom)
    if geom is None:
        return None
    threshold = max(0.0, float(min_area_m2))
    if isinstance(geom, Polygon):
        return geom if float(geom.area) >= threshold else None
    polys = [p for p in geom.geoms if float(p.area) >= threshold]
    if not polys:
        return None
    return polys[0] if len(polys) == 1 else MultiPolygon(polys)


def _simplify_planar(geom, tolerance_m: float, min_area_m2: float):
    """Topology-preserving simplification; curved tessellation remains curved/polyline."""
    geom = _polygonal_only(geom)
    if geom is None:
        return None
    tol = max(0.0, float(tolerance_m))
    if tol:
        geom = geom.simplify(tol, preserve_topology=True)
    if not geom.is_valid:
        geom = geom.buffer(0)
    return _drop_small_components(geom, min_area_m2)


def _shape_to_geojson_xyz(geom, z, anchor_lon, anchor_lat, xy_decimals, z_decimals, georef=None):
    geom = _polygonal_only(geom)
    if geom is None:
        return None

    def polygon_coords(poly):
        rings = [_ring_geo_xy(
            list(poly.exterior.coords), z, anchor_lon, anchor_lat,
            xy_decimals, z_decimals, georef=georef
        )]
        for hole in poly.interiors:
            rings.append(_ring_geo_xy(
                list(hole.coords), z, anchor_lon, anchor_lat,
                xy_decimals, z_decimals, georef=georef
            ))
        return rings

    if isinstance(geom, Polygon):
        return {"type": "Polygon", "coordinates": polygon_coords(geom)}
    return {
        "type": "MultiPolygon",
        "coordinates": [polygon_coords(p) for p in geom.geoms],
    }


def _projected_area_xy(q) -> float:
    if len(q) < 3:
        return 0.0
    try:
        p = Polygon([(float(x), float(y)) for x, y in q[:, :2]])
        if not p.is_valid:
            p = p.buffer(0)
        return float(p.area) if not p.is_empty else 0.0
    except Exception:
        return 0.0


def _cluster_face_polygon(bins: dict, q: np.ndarray, tolerance: float):
    """Collect actual projected roof/floor polygons, grouped by mean Z."""
    if len(q) < 3:
        return
    n = normal(q)
    if abs(float(n[2])) < 0.60:
        return
    area_xy = _projected_area_xy(q)
    if area_xy <= 1e-6:
        return

    z = float(np.mean(q[:, 2]))
    key = int(round(z / tolerance))
    st = bins.setdefault(key, {
        "union": PlanarUnionAccumulator(flush_size=256),
        "z_weighted": 0.0,
        "area_weight": 0.0,
        "faces": 0,
    })
    st["union"].add_xy(q[:, :2])
    st["z_weighted"] += z * area_xy
    st["area_weight"] += area_xy
    st["faces"] += 1


def _face_to_geojson_xyz(q, anchor_lon, anchor_lat, xy_decimals, z_decimals, georef=None):
    q = np.asarray(q, dtype=float)
    if len(q) < 3:
        return None
    ring = []
    for x, y, z in q:
        lon, lat = local_to_lonlat(float(x), float(y), anchor_lon, anchor_lat, georef=georef)
        ring.append([
            round(lon, xy_decimals),
            round(lat, xy_decimals),
            round(float(z), z_decimals),
        ])
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def write_lod13_from_plateaus(
    out_dir: Path,
    dataset: str,
    footprint_union: PlanarUnionAccumulator,
    plateau_bins: dict,
    minz: float,
    maxz: float,
    anchor_lon: float,
    anchor_lat: float,
    xy_decimals: int,
    z_decimals: int,
    simplify_m: float,
    min_component_area_m2: float,
    georef=None,
    pure_geojson: bool = True,
    legacy_manifests: bool = False,
    source_format: str = "IFC",
) -> Optional[dict]:
    """Write LOD1.3 from fine height plateaus with Pure GeoJSON properties."""
    source = footprint_union.geometry()
    if source is None or source.is_empty:
        return None
    fp = _simplify_planar(source, simplify_m, min_component_area_m2)
    if fp is None or fp.is_empty:
        return None

    dec = int(xy_decimals)
    features = []
    fid = 1
    for _, st in sorted(plateau_bins.items()):
        if st["faces"] <= 0 or st["area_weight"] <= 0:
            continue
        geom = _simplify_planar(
            st["union"].geometry(), simplify_m, min_component_area_m2
        )
        if geom is None or geom.is_empty:
            continue
        z = st["z_weighted"] / st["area_weight"]
        gj = _shape_to_geojson_xyz(
            geom, minz, anchor_lon, anchor_lat, dec, z_decimals, georef=georef
        )
        if gj is None:
            continue
        h = max(0.0, z - minz)
        features.append({
            "type": "Feature",
            "id": fid,
            "properties": {
                "building_id": dataset,
                "name": f"Level {fid}",
                "storey_id": fid,
                "lod": "1.3-style",
                "semantic_type": "BuildingMass",
                "render_role": "surface",
                "mass_role": "height_plateau",
                "base_z": round(float(minz), z_decimals),
                "top_z": round(float(z), z_decimals),
                "height": round(float(h), z_decimals),
                "tinggi_m": round(float(h), z_decimals),
                "plan_area_m2": round(float(geom.area), 3),
                "luas_m2": round(float(geom.area), 3),
                "crs": georef.crs_epsg if georef and georef.crs_epsg else "EPSG:4326",
                "georef_method": georef.method if georef else "fallback",
                "origin_easting": round(georef.origin_easting, 4) if georef and georef.origin_easting else None,
                "origin_northing": round(georef.origin_northing, 4) if georef and georef.origin_northing else None,
                "origin_orthogonal_height": round(georef.origin_orthogonal_height, 3) if georef else 0.0,
                "origin_lon": round(anchor_lon, dec),
                "origin_lat": round(anchor_lat, dec),
                "source_format": source_format,
            },
            "geometry": gj,
        })
        fid += 1

    if not features:
        gj = _shape_to_geojson_xyz(
            fp, minz, anchor_lon, anchor_lat, dec, z_decimals, georef=georef
        )
        h = maxz - minz
        features.append({
            "type": "Feature",
            "id": 1,
            "properties": {
                "building_id": dataset,
                "name": "Building Mass",
                "storey_id": 1,
                "lod": "1.3-style",
                "semantic_type": "BuildingMass",
                "render_role": "surface",
                "mass_role": "fallback",
                "base_z": round(float(minz), z_decimals),
                "top_z": round(float(maxz), z_decimals),
                "height": round(float(h), z_decimals),
                "tinggi_m": round(float(h), z_decimals),
                "plan_area_m2": round(float(fp.area), 3),
                "luas_m2": round(float(fp.area), 3),
                "crs": georef.crs_epsg if georef and georef.crs_epsg else "EPSG:4326",
                "georef_method": georef.method if georef else "fallback",
                "origin_easting": round(georef.origin_easting, 4) if georef and georef.origin_easting else None,
                "origin_northing": round(georef.origin_northing, 4) if georef and georef.origin_northing else None,
                "origin_orthogonal_height": round(georef.origin_orthogonal_height, 3) if georef else 0.0,
                "origin_lon": round(anchor_lon, dec),
                "origin_lat": round(anchor_lat, dec),
                "source_format": source_format,
            },
            "geometry": gj,
        })

    total_floor_area = sum(f["properties"]["luas_m2"] for f in features)
    for f in features:
        f["properties"]["jumlah_lantai"] = len(features)
        f["properties"]["total_luas_m2"] = round(float(total_floor_area), 3)

    fc = {
        "type": "FeatureCollection",
        "name": f"{dataset} LOD1.3",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
        },
        "properties": {
            "dataset": dataset,
            "source_format": source_format,
            "georef_method": georef.method if georef else "fallback",
            "projected_crs": georef.crs_epsg if georef and georef.crs_epsg else "EPSG:4326",
            "origin_easting": round(georef.origin_easting, 4) if georef and georef.origin_easting else None,
            "origin_northing": round(georef.origin_northing, 4) if georef and georef.origin_northing else None,
            "origin_orthogonal_height": round(georef.origin_orthogonal_height, 3) if georef else 0.0,
            "anchor_wgs84": {"lon": round(anchor_lon, dec), "lat": round(anchor_lat, dec)},
            "rotation_deg": round(math.degrees(georef.rotation_rad), 4) if georef else 0.0,
            "footprint_area_m2": round(float(fp.area), 3),
            "total_floor_area_m2": round(float(total_floor_area), 3),
            "storey_count": len(features),
            "base_z": round(float(minz), z_decimals),
            "top_z": round(float(maxz), z_decimals),
            "total_height_m": round(float(maxz - minz), z_decimals),
        },
        "features": features,
    }

    building_geojson = out_dir / "building.geojson"
    write_json_compact(building_geojson, fc)

    info = {
        "version": 3,
        "dataset": dataset,
        "lod": "1.3-style",
        "primary_format": "GeoJSON",
        "feature_count": len(features),
        "bytes": building_geojson.stat().st_size,
        "footprint_area_m2": round(float(fp.area), 3),
        "total_floor_area_m2": round(float(total_floor_area), 3),
        "storey_count": len(features),
        "geojson_file": building_geojson.name,
    }

    if legacy_manifests:
        primary_geojson = out_dir / f"{dataset}.geojson"
        write_json_compact(primary_geojson, fc)
        lod13_dir = out_dir / "lod1_3"
        lod13_dir.mkdir(parents=True, exist_ok=True)
        write_json_compact(lod13_dir / "building.geojson", fc)
        write_json_compact(lod13_dir / "manifest.json", info)

    return info


def write_envelope(
    out_dir: Path,
    dataset: str,
    footprint_union: PlanarUnionAccumulator,
    minz: float,
    maxz: float,
    anchor_lon: float,
    anchor_lat: float,
    xy_decimals: int,
    z_decimals: int,
    georef=None,
    pure_geojson: bool = True,
    legacy_manifests: bool = False,
    source_format: str = "IFC",
) -> Optional[dict]:
    """Write extruded-footprint envelope with Pure GeoJSON properties."""
    footprint = footprint_union.geometry()
    if footprint is None or footprint.is_empty:
        return None

    dec = int(xy_decimals)
    geometry = _shape_to_geojson_xyz(
        footprint,
        minz,
        anchor_lon,
        anchor_lat,
        dec,
        z_decimals,
        georef=georef,
    )
    if geometry is None:
        return None

    h = maxz - minz
    area = round(float(footprint.area), 3)
    feature_collection = {
        "type": "FeatureCollection",
        "name": f"{dataset} envelope",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
        },
        "properties": {
            "dataset": dataset,
            "source_format": source_format,
            "georef_method": georef.method if georef else "fallback",
            "projected_crs": georef.crs_epsg if georef and georef.crs_epsg else "EPSG:4326",
            "origin_easting": round(georef.origin_easting, 4) if georef and georef.origin_easting else None,
            "origin_northing": round(georef.origin_northing, 4) if georef and georef.origin_northing else None,
            "origin_orthogonal_height": round(georef.origin_orthogonal_height, 3) if georef else 0.0,
            "anchor_wgs84": {"lon": round(anchor_lon, dec), "lat": round(anchor_lat, dec)},
            "footprint_area_m2": area,
            "total_height_m": round(float(h), z_decimals),
            "storey_count": 1,
        },
        "features": [{
            "type": "Feature",
            "id": 1,
            "properties": {
                "building_id": dataset,
                "name": "Building Envelope",
                "representation": "envelope",
                "semantic_type": "BuildingEnvelope",
                "render_role": "envelope",
                "base_z": round(float(minz), z_decimals),
                "top_z": round(float(maxz), z_decimals),
                "height": round(float(h), z_decimals),
                "tinggi_m": round(float(h), z_decimals),
                "area_m2": area,
                "luas_m2": area,
                "crs": georef.crs_epsg if georef and georef.crs_epsg else "EPSG:4326",
                "georef_method": georef.method if georef else "fallback",
                "origin_easting": round(georef.origin_easting, 4) if georef and georef.origin_easting else None,
                "origin_northing": round(georef.origin_northing, 4) if georef and georef.origin_northing else None,
                "origin_lon": round(anchor_lon, dec),
                "origin_lat": round(anchor_lat, dec),
                "source_format": source_format,
            },
            "geometry": geometry,
        }],
    }

    env_geojson = out_dir / "envelope.geojson"
    write_json_compact(env_geojson, feature_collection)

    manifest = {
        "version": 1,
        "dataset": dataset,
        "representation": "envelope",
        "file": env_geojson.name,
        "feature_count": 1,
        "bytes": env_geojson.stat().st_size,
        "footprint_area_m2": area,
        "z_min": round(float(minz), z_decimals),
        "z_max": round(float(maxz), z_decimals),
    }

    if legacy_manifests:
        directory = out_dir / "envelope"
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "building.geojson"
        write_json_compact(path, feature_collection)
        write_json_compact(directory / "manifest.json", manifest)

    return manifest
