# SPDX-License-Identifier: AGPL-3.0-only
"""ATAP GeoJSON Ingestion & Extrusion Adapter for ARCA.

Converts hierarchical 2.5D building-mass polygons from ATAP into
canonical ARCA LOD 1.3 GeoJSON, 3D GLB mesh, CityJSON v1.1, and CityGML v2.0.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import Polygon

from .citygml import CityGMLWriter
from .cityjson import CityJSONWriter
from .georef import GeoreferenceContext, latlon_to_utm_wgs84
from .glb import GLBWriter
from .utils import clean_previous_outputs, safe_slug, write_json


def is_atap_geojson(path: Path) -> bool:
    """Check if file is a valid ATAP GeoJSON FeatureCollection."""
    ext = path.suffix.lower()
    if ext not in {".geojson", ".json"}:
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            chunk = f.read(2048)
            if '"atap"' in chunk or '"base_elevation_m"' in chunk or '"part_id"' in chunk:
                return True
            # Check parsed content if header wasn't in first chunk
            f.seek(0)
            data = json.load(f)
            if isinstance(data, dict):
                if "atap" in data:
                    return True
                feats = data.get("features", [])
                if feats and isinstance(feats[0], dict):
                    props = feats[0].get("properties", {})
                    if "base_elevation_m" in props or "top_elevation_m" in props or "part_id" in props:
                        return True
    except Exception:
        pass
    return False


def inspect_atap_file(file_path: Path) -> dict:
    """Inspect metadata from an ATAP GeoJSON file."""
    file_path = Path(file_path)
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features", [])
    if not features:
        return {
            "format": "ATAP",
            "name": file_path.stem,
            "has_georef": False,
            "message": "File GeoJSON ATAP tidak memuat fitur bangunan (empty features).",
        }

    lons = []
    lats = []
    min_elev = np.inf
    max_elev = -np.inf

    for feat in features:
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates") or []
        gtype = geom.get("type")
        props = feat.get("properties") or {}

        base_z = float(props.get("base_elevation_m") or props.get("base_height_agl_m") or 0.0)
        top_z = float(props.get("top_elevation_m") or props.get("top_height_agl_m") or (base_z + float(props.get("part_height_m", 3.0))))
        min_elev = min(min_elev, base_z)
        max_elev = max(max_elev, top_z)

        rings = []
        if gtype == "Polygon":
            rings = coords
        elif gtype == "MultiPolygon":
            for poly in coords:
                rings.extend(poly)

        for ring in rings:
            for pt in ring:
                if len(pt) >= 2:
                    lons.append(pt[0])
                    lats.append(pt[1])

    if not lons or not lats:
        return {
            "format": "ATAP",
            "name": file_path.stem,
            "has_georef": False,
            "message": "Geometri poligon tidak ditemukan dalam file GeoJSON ATAP.",
        }

    center_lon = float((min(lons) + max(lons)) / 2.0)
    center_lat = float((min(lats) + max(lats)) / 2.0)
    utm_epsg, utm_zone, easting, northing = latlon_to_utm_wgs84(center_lat, center_lon)

    bldg_ids = set()
    for feat in features:
        props = feat.get("properties") or {}
        bid = props.get("parent_id") or props.get("object_id") or props.get("id") or props.get("OBJECTID") or props.get("FGSBGN")
        if bid is not None:
            bldg_ids.add(str(bid))
    bldg_count = len(bldg_ids) if bldg_ids else len(features)

    atap_info = data.get("atap", {})
    atap_ver = atap_info.get("engine_version", "unknown")

    return {
        "format": "ATAP",
        "name": data.get("name") or file_path.stem,
        "has_georef": True,
        "method": "atap_wgs84",
        "crs": f"EPSG:{utm_epsg}",
        "longitude": round(center_lon, 7),
        "latitude": round(center_lat, 7),
        "easting": round(easting, 3),
        "northing": round(northing, 3),
        "rotate": 0.0,
        "unit": "m",
        "unit_scale": 1.0,
        "building_count": bldg_count,
        "part_count": len(features),
        "message": f"ATAP GeoJSON v{atap_ver}: {len(features)} bagian bangunan ({bldg_count} gedung) terdeteksi (Tinggi {min_elev:.1f}m - {max_elev:.1f}m).",
    }


def _extract_building_key(props: dict, default_id: int) -> str:
    for k in ("parent_id", "object_id", "id", "OBJECTID", "FGSBGN"):
        val = props.get(k)
        if val is not None and str(val).strip():
            return str(val).strip()
    return f"{default_id:03d}"


def _extract_building_name(features: list[dict], fallback_key: str) -> str:
    for feat in features:
        props = feat.get("properties") or {}
        for k in ("building_name", "nama_bangunan", "name"):
            val = props.get(k)
            if val and str(val).strip() and not str(val).startswith("Int. Polygon") and not str(val).startswith("Part"):
                return str(val).strip()
    for feat in features:
        props = feat.get("properties") or {}
        val = props.get("name")
        if val and str(val).strip():
            return str(val).strip()
    return f"Building {fallback_key}"


def _triangulate_poly_2d(poly: Polygon) -> list[Polygon]:
    """Triangulate a 2D Shapely polygon, returning only internal triangles."""
    if not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_empty:
        return []
    collection = shapely.constrained_delaunay_triangles(poly)
    parts = collection.geoms if hasattr(collection, "geoms") else [collection]
    res = []
    for g in parts:
        if isinstance(g, Polygon) and not g.is_empty and poly.covers(g.representative_point()):
            res.append(g)
    return res


def _process_atap_group(
    features: list[dict],
    out_dir: Path,
    dataset: str,
    building_name: str,
    utm_epsg: int,
    utm_zone: str,
    generate_mode: str = "all",
    source_bytes: int = 0,
    is_sub_building: bool = False,
    split_building_ids: bool = False,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    all_lons = []
    all_lats = []
    all_elevs = []

    for feat in features:
        geom = feat.get("geometry") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates") or []
        props = feat.get("properties") or {}

        base_z = float(props.get("base_elevation_m") or props.get("base_height_agl_m") or 0.0)
        top_z = float(props.get("top_elevation_m") or props.get("top_height_agl_m") or (base_z + float(props.get("part_height_m", 3.0))))
        if top_z <= base_z:
            top_z = base_z + max(float(props.get("part_height_m", 3.0)), 1.0)
        all_elevs.extend([base_z, top_z])

        rings = coords if gtype == "Polygon" else [ring for poly in coords for ring in poly]
        for ring in rings:
            for pt in ring:
                if len(pt) >= 2:
                    all_lons.append(pt[0])
                    all_lats.append(pt[1])

    if not all_lons or not all_lats:
        return {}

    min_lon, max_lon = float(np.min(all_lons)), float(np.max(all_lons))
    min_lat, max_lat = float(np.min(all_lats)), float(np.max(all_lats))
    anchor_lon = round((min_lon + max_lon) / 2.0, 8)
    anchor_lat = round((min_lat + max_lat) / 2.0, 8)
    min_elev = float(min(all_elevs))
    max_elev = float(max(all_elevs))
    _, _, anchor_utm_e, anchor_utm_n = latlon_to_utm_wgs84(anchor_lat, anchor_lon)

    georef = GeoreferenceContext(
        method="atap_wgs84",
        crs_name=f"WGS 84 / UTM zone {utm_zone}",
        target_crs=f"EPSG:{utm_epsg}",
        anchor_lon=anchor_lon,
        anchor_lat=anchor_lat,
        anchor_elevation=min_elev,
        eastings=anchor_utm_e,
        northings=anchor_utm_n,
        orthogonal_height=0.0,
        x_axis_abscissa=1.0,
        x_axis_ordinate=0.0,
        scale=1.0,
        unit_name="METRE",
        unit_scale_to_m=1.0,
        utm_zone=int(utm_zone.rstrip("NS")),
        utm_south=utm_zone.endswith("S"),
    )

    generate_glb = generate_mode in {"all", "glb"}
    generate_cityjson = generate_mode in {"all", "cityjson"}
    generate_citygml = generate_mode in {"all", "citygml"}

    glb_writer = GLBWriter(out_dir, dataset=dataset) if generate_glb else None
    cityjson_writer = CityJSONWriter(out_dir, dataset=dataset, building_name=building_name) if generate_cityjson else None
    citygml_writer = CityGMLWriter(out_dir, dataset=dataset, building_name=building_name) if generate_citygml else None

    total_triangles = 0
    total_footprint_m2 = 0.0
    arca_features = []
    global_min = np.array([np.inf, np.inf, np.inf], dtype=float)
    global_max = np.array([-np.inf, -np.inf, -np.inf], dtype=float)

    for idx, feat in enumerate(features, start=1):
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates") or []

        base_z = float(props.get("base_elevation_m") or props.get("base_height_agl_m") or min_elev)
        top_z = float(props.get("top_elevation_m") or props.get("top_height_agl_m") or (base_z + float(props.get("part_height_m", 3.0))))
        if top_z <= base_z:
            top_z = base_z + max(float(props.get("part_height_m", 3.0)), 1.0)

        height = round(top_z - base_z, 3)
        part_name = str(props.get("name") or props.get("part_id") or f"Part {idx}")
        obj_id = int(props.get("OBJECTID") or props.get("id") or idx)

        polys_coords = [coords] if gtype == "Polygon" else coords if gtype == "MultiPolygon" else []
        for poly_c in polys_coords:
            if not poly_c:
                continue
            ext_ring = poly_c[0]
            int_rings = poly_c[1:]

            def to_local_ring(ring_pts):
                local_pts = []
                for pt in ring_pts:
                    _, _, ue, un = latlon_to_utm_wgs84(pt[1], pt[0])
                    local_pts.append((ue - anchor_utm_e, un - anchor_utm_n))
                return local_pts

            local_ext = to_local_ring(ext_ring)
            local_ints = [to_local_ring(h) for h in int_rings]

            try:
                poly_2d = Polygon(shell=local_ext, holes=local_ints)
                if not poly_2d.is_valid:
                    poly_2d = poly_2d.buffer(0)
                if poly_2d.is_empty:
                    continue
            except Exception:
                continue

            area_m2 = round(float(poly_2d.area), 3)
            total_footprint_m2 += area_m2

            # Triangulate Roof and Ground
            sub_tris = _triangulate_poly_2d(poly_2d)
            for st in sub_tris:
                tri_pts = list(st.exterior.coords)[:3]
                p0 = np.array([tri_pts[0][0], tri_pts[0][1], top_z])
                p1 = np.array([tri_pts[1][0], tri_pts[1][1], top_z])
                p2 = np.array([tri_pts[2][0], tri_pts[2][1], top_z])
                tri_roof = np.array([p0, p1, p2])

                n = np.cross(p1 - p0, p2 - p0)
                if n[2] < 0:
                    tri_roof = tri_roof[[0, 2, 1]]

                tri_ground = tri_roof.copy()
                tri_ground[:, 2] = base_z
                tri_ground = tri_ground[[0, 2, 1]]

                for writer in (glb_writer, cityjson_writer, citygml_writer):
                    if writer:
                        writer.add_triangle("RoofSurface", tri_roof, obj_id)
                        writer.add_triangle("GroundSurface", tri_ground, obj_id)
                total_triangles += 2
                global_min = np.minimum(global_min, tri_ground.min(axis=0))
                global_max = np.maximum(global_max, tri_roof.max(axis=0))

            # Extrude Walls
            all_rings = [poly_2d.exterior] + list(poly_2d.interiors)
            for ring in all_rings:
                r_coords = list(ring.coords)
                for i in range(len(r_coords) - 1):
                    pa = r_coords[i]
                    pb = r_coords[i + 1]
                    if math.hypot(pb[0] - pa[0], pb[1] - pa[1]) < 1e-6:
                        continue

                    v0 = np.array([pa[0], pa[1], base_z])
                    v1 = np.array([pb[0], pb[1], base_z])
                    v2 = np.array([pb[0], pb[1], top_z])
                    v3 = np.array([pa[0], pa[1], top_z])

                    tri_w1 = np.array([v0, v1, v2])
                    tri_w2 = np.array([v0, v2, v3])

                    for writer in (glb_writer, cityjson_writer, citygml_writer):
                        if writer:
                            writer.add_triangle("WallSurface", tri_w1, obj_id)
                            writer.add_triangle("WallSurface", tri_w2, obj_id)
                    total_triangles += 2
                    global_min = np.minimum(global_min, tri_w1.min(axis=0))
                    global_max = np.maximum(global_max, tri_w2.max(axis=0))

        def _elevate_coords(c_list, z_val):
            if not isinstance(c_list, (list, tuple)):
                return c_list
            if len(c_list) >= 2 and isinstance(c_list[0], (int, float)) and isinstance(c_list[1], (int, float)):
                return [round(float(c_list[0]), 8), round(float(c_list[1]), 8), round(float(z_val), 3)]
            return [_elevate_coords(sub, z_val) for sub in c_list]

        geom_3d = {
            "type": gtype,
            "coordinates": _elevate_coords(coords, base_z) if coords else coords,
        }

        b_key = _extract_building_key(props, idx)
        feat_bldg_id = dataset if is_sub_building else (f"{dataset}_{b_key}" if split_building_ids else dataset)
        feat_bldg_name = building_name if is_sub_building else (_extract_building_name([feat], b_key) if split_building_ids else building_name)

        arca_features.append({
            "type": "Feature",
            "id": idx,
            "properties": {
                "building_id": feat_bldg_id,
                "__asset_id": feat_bldg_id,
                "__asset_name": feat_bldg_name,
                "is_single_precinct": not split_building_ids,
                "granularity": "split" if split_building_ids else "single_precinct",
                "name": part_name,
                "part_id": props.get("part_id", f"{feat_bldg_id}-P{idx:02d}"),
                "storey_id": idx,
                "lod": "1.3-style",
                "semantic_type": "BuildingMass",
                "render_role": "surface",
                "mass_role": "height_plateau",
                "base_z": round(base_z, 3),
                "top_z": round(top_z, 3),
                "height": height,
                "tinggi_m": height,
                "plan_area_m2": area_m2,
                "luas_m2": area_m2,
                "crs": f"EPSG:{utm_epsg}",
                "georef_method": "atap_wgs84",
                "origin_lon": round(anchor_lon, 8),
                "origin_lat": round(anchor_lat, 8),
                "source_format": "ATAP",
                **{k: v for k, v in props.items() if k not in {"base_elevation_m", "top_elevation_m", "part_height_m"}},
            },
            "geometry": geom_3d,
        })

    # Write building.geojson
    arca_geojson = {
        "type": "FeatureCollection",
        "name": dataset,
        "properties": {
            "building_id": dataset,
            "name": building_name,
            "total_height_m": round(float(max_elev - min_elev), 3),
            "footprint_area_m2": round(total_footprint_m2, 2),
            "total_floor_area_m2": round(total_footprint_m2, 2),
            "storey_count": len(arca_features),
            "source_format": "ATAP",
        },
        "features": arca_features,
    }
    write_json(out_dir / "building.geojson", arca_geojson)

    cityjson_manifest = None
    if cityjson_writer:
        cityjson_manifest = cityjson_writer.finalize(
            anchor_lon=anchor_lon,
            anchor_lat=anchor_lat,
            georef=georef,
            storey_count=len(arca_features),
        )

    citygml_manifest = None
    if citygml_writer:
        citygml_manifest = citygml_writer.finalize(
            anchor_lon=anchor_lon,
            anchor_lat=anchor_lat,
            georef=georef,
            storey_count=len(arca_features),
        )

    glb_bytes = 0
    glb_manifest = None
    if glb_writer:
        glb_manifest = glb_writer.finalize(
            anchor_lon=anchor_lon,
            anchor_lat=anchor_lat,
            georef=georef,
        )
        if glb_manifest:
            glb_file = out_dir / "render" / glb_manifest["file"]
            glb_bytes = glb_file.stat().st_size if glb_file.exists() else 0
            render_dir = out_dir / "render"
            render_dir.mkdir(parents=True, exist_ok=True)
            anchor_geojson = {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [anchor_lon, anchor_lat, round(min_elev, 3)],
                    },
                    "properties": {
                        "id": dataset,
                        "name": building_name,
                        "model_url": "./model.glb",
                        "scale": 1.0,
                        "heading": 0.0,
                        "pitch": 0.0,
                        "roll": 0.0,
                        "height_m": round(float(max_elev - min_elev), 3),
                        "storeys": len(arca_features),
                        "crs": f"EPSG:{utm_epsg}",
                    },
                }],
            }
            write_json(render_dir / "model.geojson", anchor_geojson)

    metadata = {
        "dataset": dataset,
        "name": building_name,
        "source_format": "ATAP",
        "created_at_epoch": int(time.time()),
        "plateau_count": len(arca_features),
        "summary": {
            "max_height_m": round(float(max_elev - min_elev), 3),
            "footprint_area_m2": round(total_footprint_m2, 2),
            "total_floor_area_m2": round(total_footprint_m2, 2),
        },
        "geometry": {
            "lod1_3": "building.geojson",
            "render_glb": "render/model.glb" if glb_manifest else None,
            "model_anchor": "render/model.geojson" if glb_manifest else None,
            "cityjson": cityjson_manifest["file"] if cityjson_manifest else None,
            "citygml": citygml_manifest["file"] if citygml_manifest else None,
        },
        "anchor": {
            "lon": anchor_lon,
            "lat": anchor_lat,
            "mode": "georeferenced",
        },
        "georeference": {
            "is_georeferenced": True,
            "method": "atap_wgs84",
            "crs_epsg": utm_epsg,
            "crs_name": f"WGS 84 / UTM zone {utm_zone}",
            "origin_easting": anchor_utm_e,
            "origin_northing": anchor_utm_n,
            "origin_orthogonal_height": min_elev,
            "scale": 1.0,
            "rotation_rad": 0.0,
            "length_unit": "METRE",
            "length_unit_scale_to_m": 1.0,
        },
        "bounds_local_m": {
            "min": [round(float(v), 6) for v in global_min],
            "max": [round(float(v), 6) for v in global_max],
        },
        "storage": {
            "source_ifc_bytes": source_bytes,
            "lod1_3_bytes": (out_dir / "building.geojson").stat().st_size,
            "glb_bytes": glb_bytes,
            "cityjson_bytes": (out_dir / "building.city.json").stat().st_size if cityjson_manifest else 0,
            "citygml_bytes": (out_dir / "building.gml").stat().st_size if citygml_manifest else 0,
        },
    }
    write_json(out_dir / "metadata.json", metadata)

    return {
        "dataset": dataset,
        "name": building_name,
        "lon": anchor_lon,
        "lat": anchor_lat,
        "min_elev": min_elev,
        "max_elev": max_elev,
        "height_m": round(float(max_elev - min_elev), 3),
        "footprint_m2": round(total_footprint_m2, 2),
        "storeys": len(arca_features),
        "triangles": total_triangles,
        "glb_bytes": glb_bytes,
        "metadata": metadata,
        "features": arca_features,
    }


def preprocess_atap(
    geojson_path: Path,
    out_dir: Path,
    dataset: str | None = None,
    building_name: str | None = None,
    generate_mode: str = "all",
    clean_legacy: bool = True,
    merge: bool = False,
    progress_cb=None,
) -> dict:
    """Preprocess ATAP GeoJSON into GLB, CityJSON, CityGML, and ARCA building.geojson."""
    t0 = time.time()
    dataset = dataset or safe_slug(geojson_path.stem)
    source_bytes = geojson_path.stat().st_size
    out_dir.mkdir(parents=True, exist_ok=True)

    if clean_legacy:
        for removed in clean_previous_outputs(out_dir):
            if progress_cb:
                progress_cb({"type": "progress", "message": f"      removed old output: {removed}"})

    def _log(msg: str, step: int | None = None, pct: int | None = None):
        if progress_cb:
            event = {"type": "progress", "message": msg}
            if step is not None:
                event["step"] = step
                event["total"] = 5
            if pct is not None:
                event["pct"] = pct
            progress_cb(event)
        else:
            print(msg)

    _log(f"[1/5] Ingesting ATAP GeoJSON: {geojson_path.name} ...", step=1, pct=20)
    with open(geojson_path, "r", encoding="utf-8") as f:
        src_data = json.load(f)

    features = src_data.get("features", [])
    if not features:
        raise ValueError(f"No features found in ATAP GeoJSON: {geojson_path}")

    # Dataset-wide CRS
    all_lons = []
    all_lats = []
    for feat in features:
        geom = feat.get("geometry") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates") or []
        rings = coords if gtype == "Polygon" else [ring for poly in coords for ring in poly]
        for ring in rings:
            for pt in ring:
                if len(pt) >= 2:
                    all_lons.append(pt[0])
                    all_lats.append(pt[1])

    if not all_lons or not all_lats:
        raise ValueError("No valid coordinates found in ATAP GeoJSON.")

    center_lon = float(np.mean(all_lons))
    center_lat = float(np.mean(all_lats))
    utm_epsg, utm_zone, _, _ = latlon_to_utm_wgs84(center_lat, center_lon)
    _log(f"      Resolved UTM Zone: {utm_zone} (EPSG:{utm_epsg})", pct=35)

    # Group by building
    bldg_groups: dict[str, list[dict]] = {}
    for idx, feat in enumerate(features, start=1):
        props = feat.get("properties") or {}
        bkey = _extract_building_key(props, idx)
        bldg_groups.setdefault(bkey, []).append(feat)

    should_split = (not merge) and (len(bldg_groups) > 1)
    b_name = building_name or src_data.get("name") or dataset

    sub_buildings_meta = []
    if should_split:
        _log(f"[2/5] Extruding {len(bldg_groups)} buildings ({len(features)} parts) ...", step=2, pct=40)
        buildings_dir = out_dir / "buildings"
        buildings_dir.mkdir(parents=True, exist_ok=True)

        for bkey, b_feats in bldg_groups.items():
            b_bldg_name = _extract_building_name(b_feats, bkey)
            b_out_dir = buildings_dir / bkey
            b_dataset_id = f"{dataset}_{bkey}"
            res = _process_atap_group(
                features=b_feats,
                out_dir=b_out_dir,
                dataset=b_dataset_id,
                building_name=b_bldg_name,
                utm_epsg=utm_epsg,
                utm_zone=utm_zone,
                generate_mode=generate_mode,
                source_bytes=source_bytes,
                is_sub_building=True,
                split_building_ids=False,
            )
            if res:
                sub_buildings_meta.append({
                    "id": bkey,
                    "name": b_bldg_name,
                    "lon": res["lon"],
                    "lat": res["lat"],
                    "height_m": res["height_m"],
                    "footprint_m2": res["footprint_m2"],
                    "storeys": res["storeys"],
                    "glb_bytes": res["glb_bytes"],
                    "dir": f"buildings/{bkey}",
                })

    _log(f"[{'3' if should_split else '2'}/5] Generating master precinct outputs ...", step=3 if should_split else 2, pct=70)
    master_res = _process_atap_group(
        features=features,
        out_dir=out_dir,
        dataset=dataset,
        building_name=b_name,
        utm_epsg=utm_epsg,
        utm_zone=utm_zone,
        generate_mode=generate_mode,
        source_bytes=source_bytes,
        is_sub_building=False,
        split_building_ids=should_split,
    )

    metadata = master_res["metadata"]
    if should_split:
        metadata["is_split"] = True
        metadata["granularity"] = "split"
        metadata["building_count"] = len(bldg_groups)
        metadata["buildings"] = sub_buildings_meta
        write_json(out_dir / "metadata.json", metadata)
    else:
        metadata["is_split"] = False
        metadata["granularity"] = "single_precinct"
        metadata["building_count"] = 1
        write_json(out_dir / "metadata.json", metadata)

    elapsed = round(time.time() - t0, 2)
    _log(f"[5/5] SUCCESS: Finished processing in {elapsed}s", step=5, pct=100)
    _log(f"  Dataset        : {dataset}")
    if should_split:
        _log(f"  Granularity    : Split ({len(bldg_groups)} buildings across {len(features)} parts)")
    else:
        _log(f"  Granularity    : Merged ({len(features)} parts)")
    _log(f"  LOD 1.3        : {len(features)} features ({metadata['storage']['lod1_3_bytes'] / 1024:.1f} KB)")
    _log(f"  Output         : {out_dir.resolve()}")

    return metadata
