# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

import numpy as np

from arca.engine.geom import (
    area3,
    infer_product_semantic,
    item_faces,
    localplacement,
    product_info,
    rep_shape_items,
    triangulate_polygon_3d,
)
from arca.engine.georef import (
    GeoreferenceContext,
    extract_length_unit,
    find_metadata_json,
    parse_metadata_json,
    resolve_georeferencing,
    unit_factor_to_m,
)
from arca.engine.glb import GLBWriter
from arca.engine.lod import (
    PlanarUnionAccumulator,
    _cluster_face_polygon,
    _shape_to_geojson_xyz,
    write_envelope,
    write_lod13_from_plateaus,
)
from arca.engine.skp import (
    convert_skp_to_georef_ifc,
    detect_input_format,
    extract_skp_georeference,
)
from arca.engine.step import TARGETS, load_ifc
from arca.engine.utils import (
    clean_previous_outputs,
    safe_slug,
    sha256_file,
    write_json,
)


def _log(
    progress_cb,
    msg: str,
    step: int | None = None,
    total: int = 5,
    pct: int | None = None,
) -> None:
    if progress_cb is not None:
        event: dict = {"type": "progress", "message": msg}
        if step is not None:
            event["step"] = step
            event["total"] = total
            if pct is None:
                pct = int((step / total) * 100)
        if pct is not None:
            event["pct"] = pct
        progress_cb(event)
    else:
        print(msg)


def preprocess(
    ifc_path: Path,
    out_dir: Path,
    pure_geojson: bool = True,
    legacy_manifests: bool = False,
    source_format: str = "IFC",
    anchor_lon: float | None = None,
    anchor_lat: float | None = None,
    source_unit: str = "auto",
    min_area_m2: float = 1e-4,
    generate_mode: str = "all",
    generate_envelope: bool = True,
    xy_decimals: int = 8,
    z_decimals: int = 3,
    clean_legacy: bool = True,
    lod13_z_tolerance: float = 0.25,
    lod13_simplify_m: float = 0.10,
    lod13_min_component_area_m2: float = 0.25,
    crs: str | None = None,
    rotate: float = 0.0,
    ignore_georef: bool = False,
    metadata_info: Optional[dict] = None,
    progress_cb=None,
):
    if generate_mode not in {"all", "lod1.3", "glb"}:
        raise ValueError("generate_mode must be one of: all, lod1.3, glb")
    generate_lod13 = generate_mode in {"all", "lod1.3"}
    generate_glb = generate_mode in {"all", "glb"}

    dataset = ifc_path.stem
    source_bytes = ifc_path.stat().st_size
    out_dir.mkdir(parents=True, exist_ok=True)

    if clean_legacy:
        for removed in clean_previous_outputs(out_dir):
            _log(progress_cb, f"      removed old output: {removed}")

    _log(progress_cb, "[1/5] Loading IFC model ...", step=1, pct=22)
    E, entity_counts = load_ifc(ifc_path)
    _log(
        progress_cb,
        "[2/5] Extracting IFC geometry for "
        f"{generate_mode.upper()} (envelope={'yes' if generate_envelope else 'no'}) ...",
        step=2,
        pct=45,
    )

    if ignore_georef:
        eff_lon = anchor_lon if anchor_lon is not None else 112.6304
        eff_lat = anchor_lat if anchor_lat is not None else -7.98098
        det_name, det_factor = extract_length_unit(E)
        if source_unit != "auto":
            unit_str = source_unit
            to_m = unit_factor_to_m(unit_str)
        else:
            unit_str = det_name
            to_m = det_factor
        georef = GeoreferenceContext(
            method="cli_anchor_fallback",
            crs_name="WGS 84 (User CLI Anchor)",
            target_crs="EPSG:4326",
            anchor_lon=eff_lon,
            anchor_lat=eff_lat,
            anchor_elevation=0.0,
            unit_name=unit_str,
            unit_scale_to_m=to_m,
            transformer=None,
        )
    else:
        georef = resolve_georeferencing(
            E,
            fallback_lon=anchor_lon,
            fallback_lat=anchor_lat,
            cli_unit=source_unit,
            cli_crs=crs,
            cli_rotate=rotate,
            metadata_info=metadata_info,
        )

    to_m = georef.length_scale_to_m
    resolved_lon = georef.origin_lon
    resolved_lat = georef.origin_lat

    _log(progress_cb, f"      Georeference method: {georef.method}")
    if georef.is_georeferenced:
        if georef.crs_epsg:
            _log(progress_cb, f"      CRS: {georef.crs_epsg} ({georef.crs_name or 'unnamed'})")
            _log(progress_cb, f"      Map origin: E={georef.origin_easting:.3f}, N={georef.origin_northing:.3f}")
        _log(progress_cb, f"      Resolved WGS84 origin: Lon={resolved_lon:.8f}, Lat={resolved_lat:.8f}")
    else:
        _log(progress_cb, f"      Anchor WGS84 origin: Lon={resolved_lon:.8f}, Lat={resolved_lat:.8f}")
    _log(progress_cb, f"      Length unit: {georef.length_unit_name} (scale to meter: {to_m})")

    product_ids = [pid for pid, (typ, _) in E.items() if typ in TARGETS]
    _log(progress_cb, f"      Candidate products: {len(product_ids):,}")

    glb_writer = GLBWriter(out_dir, dataset) if generate_glb else None

    placement_memo = {}
    stats = {}
    global_min = np.array([np.inf, np.inf, np.inf], dtype=float)
    global_max = np.array([-np.inf, -np.inf, -np.inf], dtype=float)
    products_with_geometry = 0
    kept_faces = 0
    triangle_count = 0
    footprint_union = PlanarUnionAccumulator(flush_size=256)
    lod13_bins = {}

    for pos, pid in enumerate(product_ids, 1):
        typ, _ = E[pid]
        p = product_info(E, pid)
        T = localplacement(E, p["placement"], placement_memo)

        faces = []
        for ir in rep_shape_items(E, p["representation"]):
            faces.extend(item_faces(E, ir, T))

        faces_m = []
        for f in faces:
            q = np.asarray(f, dtype=float) * to_m
            if len(q) < 3 or area3(q) < min_area_m2:
                continue
            faces_m.append(q)
            kept_faces += 1
            global_min = np.minimum(global_min, q.min(axis=0))
            global_max = np.maximum(global_max, q.max(axis=0))

        if not faces_m:
            continue

        semantic, semantic_method, semantic_confidence = infer_product_semantic(
            typ, p, faces_m
        )
        products_with_geometry += 1
        object_id = products_with_geometry

        for q in faces_m:
            footprint_union.add_xy(q[:, :2])
            if generate_lod13:
                _cluster_face_polygon(lod13_bins, q, lod13_z_tolerance)

        product_triangles = 0
        for q in faces_m:
            for tri in triangulate_polygon_3d(q):
                product_triangles += 1
                triangle_count += 1
                if glb_writer is not None:
                    glb_writer.add_triangle(
                        semantic=semantic,
                        tri_m=tri,
                        object_id=object_id,
                    )

        stats.setdefault(typ, {"products": 0, "faces": 0, "triangles": 0})
        stats[typ]["products"] += 1
        stats[typ]["faces"] += len(faces_m)
        stats[typ]["triangles"] += product_triangles

        if pos % 250 == 0 or pos == len(product_ids):
            _log(
                progress_cb,
                f"      {pos:,}/{len(product_ids):,} products | "
                f"{products_with_geometry:,} with geometry | "
                f"{kept_faces:,} faces | {triangle_count:,} triangles",
            )

    if not np.isfinite(global_min).all():
        raise RuntimeError("IFC parsed but no supported geometry was extracted.")

    _log(progress_cb, "[3/5] Finalizing GLB ..." if generate_glb else "[3/5] GLB skipped ...", step=3, pct=68)
    glb_manifest = (
        glb_writer.finalize(resolved_lon, resolved_lat, georef=georef)
        if glb_writer is not None
        else None
    )

    minx, miny, minz = global_min
    maxx, maxy, maxz = global_max

    _log(progress_cb, "[4/5] Writing selected GIS outputs ...", step=4, pct=85)
    lod13 = (
        write_lod13_from_plateaus(
            out_dir=out_dir,
            dataset=dataset,
            footprint_union=footprint_union,
            plateau_bins=lod13_bins,
            minz=minz,
            maxz=maxz,
            anchor_lon=resolved_lon,
            anchor_lat=resolved_lat,
            xy_decimals=xy_decimals,
            z_decimals=z_decimals,
            simplify_m=lod13_simplify_m,
            min_component_area_m2=lod13_min_component_area_m2,
            georef=georef,
            pure_geojson=pure_geojson,
            legacy_manifests=legacy_manifests,
            source_format=source_format,
        )
        if generate_lod13
        else None
    )
    envelope = (
        write_envelope(
            out_dir=out_dir,
            dataset=dataset,
            footprint_union=footprint_union,
            minz=minz,
            maxz=maxz,
            anchor_lon=resolved_lon,
            anchor_lat=resolved_lat,
            xy_decimals=xy_decimals,
            z_decimals=z_decimals,
            georef=georef,
            pure_geojson=pure_geojson,
            legacy_manifests=legacy_manifests,
            source_format=source_format,
        )
        if generate_envelope
        else None
    )

    footprint_geom = footprint_union.geometry()
    building_geometry = (
        _shape_to_geojson_xyz(
            footprint_geom, minz, resolved_lon, resolved_lat, xy_decimals, z_decimals, georef=georef
        )
        if footprint_geom is not None and not footprint_geom.is_empty
        else None
    )
    building = {
        "type": "FeatureCollection",
        "name": f"{dataset} building",
        "features": [{
            "type": "Feature",
            "properties": {
                "building_id": dataset,
                "representation": "envelope",
                "primary_geometry": "envelope/manifest.json" if envelope else None,
                "z_min": round(float(minz), z_decimals),
                "z_max": round(float(maxz), z_decimals),
                "height": round(float(maxz - minz), z_decimals),
                "area_m2": round(float(footprint_geom.area), 3)
                    if footprint_geom is not None and not footprint_geom.is_empty else None,
            },
            "geometry": building_geometry,
        }],
    }
    if generate_envelope:
        write_json(out_dir / "overview.geojson", building)
        if not lod13:
            write_json(out_dir / "building.geojson", building)

    glb_bytes = glb_manifest["bytes"] if glb_manifest else 0

    storey_count = lod13.get("storey_count", 0) if lod13 else 0
    footprint_m2 = lod13.get("footprint_area_m2", 0.0) if lod13 else (round(float(footprint_geom.area), 2) if footprint_geom and not footprint_geom.is_empty else 0.0)
    total_floor_m2 = lod13.get("total_floor_area_m2", 0.0) if lod13 else footprint_m2
    max_height_m = round(float(maxz - minz), 2)

    metadata = {
        "dataset": dataset,
        "name": (metadata_info.get("name") if metadata_info else None) or dataset,
        "input": ifc_path.name,
        "input_sha256": sha256_file(ifc_path),
        "schema": "IFC4",
        "source_format": source_format,
        "plateau_count": storey_count,
        "summary": {
            "storey_count": storey_count,
            "max_height_m": max_height_m,
            "footprint_area_m2": footprint_m2,
            "total_floor_area_m2": total_floor_m2,
        },
        "source_unit": georef.length_unit_name,
        "generate_mode": generate_mode,
        "envelope_enabled": generate_envelope,
        "gis_native": True,
        "preprocess_version": "0.2.0-georeferenced",
        "geometry": {
            "lod1_3": "lod1_3/manifest.json" if lod13 else None,
            "envelope": "envelope/manifest.json" if envelope else None,
            "building_overview": "building.geojson" if generate_envelope else None,
            "render_glb": "render/model.glb" if glb_manifest else None,
        },
        "anchor": {
            "lon": resolved_lon,
            "lat": resolved_lat,
            "mode": "georeferenced" if georef.is_georeferenced else "local model anchored to WGS84",
        },
        "georeference": {
            "is_georeferenced": georef.is_georeferenced,
            "method": georef.method,
            "crs_epsg": georef.crs_epsg,
            "crs_name": georef.crs_name,
            "origin_easting": georef.origin_easting,
            "origin_northing": georef.origin_northing,
            "origin_orthogonal_height": georef.origin_orthogonal_height,
            "scale": georef.scale,
            "rotation_rad": georef.rotation_rad,
            "length_unit": georef.length_unit_name,
            "length_unit_scale_to_m": georef.length_scale_to_m,
        },
        "bounds_local_m": {
            "min": [round(float(v), 6) for v in global_min],
            "max": [round(float(v), 6) for v in global_max],
        },
        "entity_stats": stats,
        "storage": {
            "source_ifc_bytes": source_bytes,
            "lod1_3_bytes": lod13["bytes"] if lod13 else 0,
            "envelope_bytes": envelope["bytes"] if envelope else 0,
            "glb_bytes": glb_bytes,
        },
        "notes": [
            "LOD 1.3 and GLB can be generated together or independently.",
            "The optional envelope is a simple extruded source-footprint overview.",
            "GLB is a Y-up browser model generated from supported IFC product geometry.",
        ],
    }
    write_json(out_dir / "metadata.json", metadata)

    _log(progress_cb, "[5/5] SUCCESS", step=5, pct=100)
    _log(progress_cb, f"  Dataset        : {dataset}")
    _log(progress_cb, f"  Generate mode  : {generate_mode}")
    _log(progress_cb, f"  LOD1.3         : {lod13['feature_count'] if lod13 else 0:,} features")
    _log(progress_cb, f"  Envelope       : {'enabled' if envelope else 'disabled'}")
    _log(progress_cb, f"  Triangles      : {triangle_count:,}")
    _log(progress_cb, f"  GLB            : {glb_bytes / (1024 * 1024):.2f} MB" if glb_manifest else "  GLB            : disabled")
    _log(progress_cb, f"  Output         : {out_dir.resolve()}")
    return metadata


def _viewer_item(
    dataset: str,
    item_id,
    name: str,
    longitude: float,
    latitude: float,
    scale: float,
    rotate: float,
    metadata: dict,
):
    height = None
    area = None
    storey_count = None
    bounds = metadata.get("bounds_local_m") or {}
    lower = bounds.get("min") or []
    upper = bounds.get("max") or []
    if len(lower) >= 3 and len(upper) >= 3:
        height = round(float(upper[2]) - float(lower[2]), 3)

    try:
        b = json.loads((Path(metadata["_out_dir"]) / "building.geojson").read_text(encoding="utf-8"))
        top_props = b.get("properties") or {}
        area = top_props.get("total_floor_area_m2") or top_props.get("footprint_area_m2")
        storey_count = top_props.get("storey_count")
        if top_props.get("total_height_m"):
            height = top_props.get("total_height_m")
    except Exception:
        pass
    return {
        "id": item_id,
        "name": name,
        "type": 4,
        "latitude": latitude,
        "longitude": longitude,
        "center_point_latitude": latitude,
        "center_point_longitude": longitude,
        "scale": scale,
        "rotate": rotate,
        "geojson": ({
            "lod1_3": f"./multilod/{dataset}/lod1_3/building.geojson",
        } if metadata.get("geometry", {}).get("lod1_3") else {}),
        "detail": {
            "glb": f"./multilod/{dataset}/render/model.glb",
            "metadata": f"./multilod/{dataset}/metadata.json",
            "bytes": (metadata.get("storage") or {}).get("glb_bytes"),
        } if metadata.get("geometry", {}).get("render_glb") else None,
        "attributes": {
            "infrastructure_name": name,
            "fungsi": None,
            "alamat": None,
            "tahun": None,
            "luas": area,
            "tinggi": height,
            "jumlah_lantai": storey_count,
            "status_kepemilikan": None,
        },
        "color": None,
    }


def sync_latest_viewer(
    viewer_root: Path,
    source_out: Path,
    dataset: str,
    metadata: dict,
    item_id,
    name: str,
    longitude: float,
    latitude: float,
    scale: float,
    rotate: float,
    placement_mode: str,
):
    viewer_root = viewer_root.expanduser().resolve()
    if not viewer_root.exists():
        raise FileNotFoundError(f"viewer root not found: {viewer_root}")
    target = viewer_root / "multilod" / dataset
    if source_out.resolve() != target.resolve():
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_out, target)

    lod13_file = target / "lod1_3" / "building.geojson"
    if not lod13_file.exists() and (target / "building.geojson").exists():
        lod13_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target / "building.geojson", lod13_file)

    data_path = viewer_root / "data.json"
    if data_path.exists():
        data = json.loads(data_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {"items": []}
    else:
        data = {"items": []}

    settings = data.setdefault("settings", {})
    settings.setdefault("default_engine", "maplibre")
    settings.setdefault("default_basemap", "osm")
    settings["display_lod"] = "LOD 1.3"
    settings["source_lod_key"] = "lod1_3"
    settings["placement_mode"] = placement_mode
    settings.setdefault(
        "big_tile_url",
        "https://geoservices.big.go.id/rbi/rest/services/BASEMAP/Rupabumi_Indonesia/MapServer/tile/{z}/{y}/{x}",
    )
    settings.setdefault("big_max_zoom", 15)
    settings.setdefault("osm_tile_url", "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
    settings.setdefault("osm_max_zoom", 19)
    settings.setdefault("big_osm_gap_fill", False)

    metadata = dict(metadata)
    metadata["_out_dir"] = str(target)
    new_item = _viewer_item(
        dataset, item_id, name, longitude, latitude, scale, rotate, metadata
    )
    items = data.setdefault("items", [])
    match = None
    for i, item in enumerate(items):
        if str(item.get("id")) == str(item_id) or item.get("name") == name:
            match = i
            break
    if match is None:
        items.append(new_item)
    else:
        old = items[match]
        attrs = dict(old.get("attributes") or {})
        attrs.update({k: v for k, v in new_item["attributes"].items() if v is not None})
        merged = dict(old)
        merged.update({k: v for k, v in new_item.items() if k != "attributes"})
        merged["attributes"] = attrs
        items[match] = merged

    # Ponytail: sanitize items to prune any phantom entries without actual files in viewer_root
    valid_items = []
    for item in items:
        geo_rel = (item.get("geojson") or {}).get("lod1_3")
        glb_rel = (item.get("detail") or {}).get("glb")
        has_geo = geo_rel and (viewer_root / geo_rel.lstrip("./")).exists()
        has_glb = glb_rel and (viewer_root / glb_rel.lstrip("./")).exists()
        if has_geo or has_glb:
            valid_items.append(item)
    items = valid_items
    data["items"] = items

    labels = settings.setdefault("display_labels", {})
    labels["lod1_3"] = "LOD 1.3"
    labels["glb"] = "GLB"
    settings["enabled_representations"] = [
        key for key, available in (
            ("lod1_3", any((item.get("geojson") or {}).get("lod1_3") for item in items)),
            ("glb", any((item.get("detail") or {}).get("glb") for item in items)),
        ) if available
    ]

    write_json(data_path, data)
    print(f"  Viewer data.json : {data_path}")
    print(f"  Viewer dataset   : {target}")


def build_parser():
    p = argparse.ArgumentParser(
        description="ARCA BIM2GIS: Unified SKP/IFC to Pure GeoJSON & 3D WebGIS Pipeline"
    )
    p.add_argument(
        "input",
        type=Path,
        help="Input .skp or .ifc file, or a folder containing models",
    )
    p.add_argument(
        "--out",
        "--out-dir",
        dest="out",
        type=Path,
        default=None,
        help="Output dataset directory. Default: ./dist/<model stem>",
    )
    p.add_argument(
        "--recursive",
        action="store_true",
        help="When input is a folder, also find models in subfolders",
    )
    p.add_argument(
        "--anchor-lon",
        type=float,
        default=None,
        help="Fallback anchor longitude (WGS84) if model lacks georeferencing (default: 112.6304)",
    )
    p.add_argument(
        "--anchor-lat",
        type=float,
        default=None,
        help="Fallback anchor latitude (WGS84) if model lacks georeferencing (default: -7.98098)",
    )
    p.add_argument(
        "--source-unit",
        choices=("auto", "mm", "m", "cm", "in", "ft"),
        default="auto",
        help="Length unit of IFC geometry. 'auto' reads from IFC unit assignment (default: auto)",
    )
    p.add_argument(
        "--crs",
        type=str,
        default=None,
        help="Override or specify target CRS (e.g. EPSG:32750)",
    )
    p.add_argument(
        "--metadata",
        type=Path,
        default=None,
        help="Path to companion metadata JSON / GeoJSON file",
    )
    p.add_argument(
        "--ignore-georef",
        action="store_true",
        default=False,
        help="Ignore model georeferencing and force fallback anchor placement",
    )
    p.add_argument("--min-area-m2", type=float, default=1e-4)
    p.add_argument("--xy-decimals", type=int, default=8)
    p.add_argument("--z-decimals", type=int, default=3)

    p.add_argument(
        "--generate",
        choices=("all", "lod1.3", "glb"),
        default="lod1.3",
        help="Output selection: lod1.3 (Pure GeoJSON), glb, or all (default: lod1.3)",
    )
    p.add_argument(
        "--pure-geojson",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Generate standalone Pure GeoJSON without separate manifest files (default: True)",
    )
    p.add_argument(
        "--keep-ifc",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Keep georeferenced intermediate IFC file when converting from SKP (default: True)",
    )
    p.add_argument(
        "--legacy-manifests",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Also write legacy lod1_3/manifest.json and envelope/manifest.json (default: False)",
    )
    p.add_argument(
        "--envelope",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Generate building envelope (default: False)",
    )
    p.add_argument("--lod13-z-tolerance", type=float, default=0.25)
    p.add_argument("--lod13-simplify-m", type=float, default=0.10)
    p.add_argument("--lod13-min-component-area-m2", type=float, default=0.25)
    p.add_argument("--clean-legacy", action=argparse.BooleanOptionalAction, default=True)

    # Viewer integration options
    p.add_argument("--viewer-root", type=Path, default=None)
    p.add_argument("--item-id", default=None)
    p.add_argument("--name", default=None)
    p.add_argument("--longitude", type=float, default=None)
    p.add_argument("--latitude", type=float, default=None)
    p.add_argument("--scale", type=float, default=1.0)
    p.add_argument("--rotate", type=float, default=0.0)
    p.add_argument(
        "--placement-mode",
        choices=("item_center", "native"),
        default="item_center",
    )
    return p


def inspect_model_file(file_path: Path, metadata_path: Optional[Path] = None) -> dict:
    file_path = Path(file_path)
    fmt = detect_input_format(file_path)

    meta_file = metadata_path or find_metadata_json(file_path)
    meta_info = parse_metadata_json(meta_file) if meta_file else None

    if fmt == "IFC":
        ents, _ = load_ifc(file_path)
        georef = resolve_georeferencing(ents, metadata_info=meta_info)
        detected_unit_name, detected_unit_factor = extract_length_unit(ents)
        has_georef = georef.is_georeferenced

        rot_deg = round(math.degrees(georef.rotation_rad), 2) if has_georef else 0.0

        if meta_info and meta_info.get("has_georef"):
            meta_fname = Path(meta_info.get("file_path", "")).name
            msg = f"Georeferensi terdeteksi dari metadata JSON ({meta_fname})."
        elif has_georef:
            msg = f"Georeferensi otomatis terdeteksi: {georef.crs_epsg or 'WGS84'} (Metode: {georef.method})."
        else:
            msg = "Model IFC tidak memiliki entitas georeferensi bawaan (IfcProjectedCRS / IfcSite)."

        if meta_info:
            inspected_unit = meta_info.get("unit") or "auto"
            inspected_unit_scale = unit_factor_to_m(inspected_unit) if inspected_unit != "auto" else detected_unit_factor
        else:
            inspected_unit = detected_unit_name or "auto"
            inspected_unit_scale = detected_unit_factor

        return {
            "format": "IFC",
            "name": meta_info.get("name") if meta_info else None,
            "has_georef": has_georef,
            "method": georef.method,
            "crs": georef.crs_epsg if has_georef else None,
            "longitude": round(georef.origin_lon, 7) if has_georef else None,
            "latitude": round(georef.origin_lat, 7) if has_georef else None,
            "easting": round(georef.origin_easting, 3) if (has_georef and georef.origin_easting is not None) else None,
            "northing": round(georef.origin_northing, 3) if (has_georef and georef.origin_northing is not None) else None,
            "rotate": rot_deg,
            "unit": inspected_unit,
            "unit_scale": inspected_unit_scale,
            "message": msg,
        }
    elif fmt == "SKP":
        skp_info = extract_skp_georeference(file_path, metadata_info=meta_info)
        has_georef = bool(skp_info.get("has_georef", False))
        if meta_info and meta_info.get("has_georef"):
            meta_fname = Path(meta_info.get("file_path", "")).name
            msg = f"Georeferensi terdeteksi dari metadata JSON ({meta_fname})."
        elif has_georef:
            msg = f"Georeferensi terdeteksi dari metadata SketchUp ({skp_info.get('source')})."
        else:
            msg = "Model SKP tidak memiliki metadata geolokasi (GeoReference / ShadowInfo)."

        if meta_info and meta_info.get("unit") and meta_info.get("unit") != "auto":
            skp_unit = meta_info.get("unit")
            skp_unit_scale = unit_factor_to_m(skp_unit)
        else:
            skp_unit = "auto"
            skp_unit_scale = 1.0

        return {
            "format": "SKP",
            "name": meta_info.get("name") if meta_info else None,
            "has_georef": has_georef,
            "method": skp_info.get("source"),
            "crs": skp_info.get("crs"),
            "longitude": round(skp_info["longitude"], 7) if has_georef else None,
            "latitude": round(skp_info["latitude"], 7) if has_georef else None,
            "rotate": round(skp_info.get("north_angle", 0.0), 2) if has_georef else 0.0,
            "unit": skp_unit,
            "unit_scale": skp_unit_scale,
            "message": msg,
        }
    else:
        return {
            "format": "UNKNOWN",
            "has_georef": False,
            "message": "Format file tidak dikenal atau tidak didukung.",
        }


def process_one(
    args,
    input_path: Path,
    out_dir: Path,
    batch: bool = False,
    dataset: str | None = None,
    progress_cb=None,
):
    dataset = dataset or safe_slug(input_path.stem)
    out_dir.mkdir(parents=True, exist_ok=True)
    fmt = detect_input_format(input_path)

    meta_file = getattr(args, "metadata", None) or find_metadata_json(input_path)
    meta_info = parse_metadata_json(meta_file) if meta_file else None

    if fmt == "SKP":
        _log(progress_cb, f"[0/5] Ingesting SketchUp (.skp): {input_path.name}", step=0, pct=3)
        skp_georef = extract_skp_georeference(
            skp_path=input_path,
            fallback_lon=args.anchor_lon,
            fallback_lat=args.anchor_lat,
            fallback_crs=args.crs,
            fallback_rotate=args.rotate,
            metadata_info=meta_info,
        )
        _log(progress_cb, f"      SKP Georeference source: {skp_georef['source']}", pct=5)
        _log(progress_cb, f"      CRS: {skp_georef['crs']}, Anchor: ({skp_georef['longitude']:.8f}, {skp_georef['latitude']:.8f})")
        _log(progress_cb, f"      UTM Map Origin: E={skp_georef['easting']:.3f}, N={skp_georef['northing']:.3f}")

        intermediate_ifc = out_dir / f"{dataset}.ifc"
        convert_skp_to_georef_ifc(
            skp_path=input_path,
            out_ifc_path=intermediate_ifc,
            georef=skp_georef,
            progress_cb=progress_cb,
        )
        _log(progress_cb, f"      Generated georeferenced IFC4: {intermediate_ifc.name}", pct=20)
        actual_ifc_path = intermediate_ifc
        source_format = "SKP"
    elif fmt == "IFC":
        actual_ifc_path = input_path
        source_format = "IFC"
    else:
        raise ValueError(f"Unsupported model format for file: {input_path}")

    metadata = preprocess(
        ifc_path=actual_ifc_path,
        out_dir=out_dir,
        anchor_lon=args.anchor_lon,
        anchor_lat=args.anchor_lat,
        source_unit=args.source_unit,
        min_area_m2=args.min_area_m2,
        generate_mode=args.generate,
        generate_envelope=args.envelope,
        xy_decimals=args.xy_decimals,
        z_decimals=args.z_decimals,
        clean_legacy=args.clean_legacy,
        lod13_z_tolerance=args.lod13_z_tolerance,
        lod13_simplify_m=args.lod13_simplify_m,
        lod13_min_component_area_m2=args.lod13_min_component_area_m2,
        crs=args.crs,
        rotate=getattr(args, "rotate", 0.0),
        ignore_georef=args.ignore_georef,
        pure_geojson=args.pure_geojson,
        legacy_manifests=args.legacy_manifests,
        source_format=source_format,
        metadata_info=meta_info,
        progress_cb=progress_cb,
    )

    if fmt == "SKP" and not getattr(args, "keep_ifc", True) and intermediate_ifc.exists():
        intermediate_ifc.unlink()

    resolved_anchor = metadata.get("anchor", {})
    resolved_lon = resolved_anchor.get("lon", 112.6304)
    resolved_lat = resolved_anchor.get("lat", -7.98098)

    item_id = dataset if batch or getattr(args, "item_id", None) is None else args.item_id
    default_name = (meta_info.get("name") if meta_info else None) or input_path.stem
    name = default_name if batch or getattr(args, "name", None) is None else args.name
    longitude = getattr(args, "longitude", None) if getattr(args, "longitude", None) is not None else resolved_lon
    latitude = getattr(args, "latitude", None) if getattr(args, "latitude", None) is not None else resolved_lat

    georef_meta = metadata.get("georeference", {})
    rotate = getattr(args, "rotate", 0.0) or 0.0
    if rotate == 0.0 and georef_meta.get("rotation_rad"):
        rotate = round(math.degrees(georef_meta["rotation_rad"]), 4)

    if getattr(args, "viewer_root", None) is not None:
        sync_latest_viewer(
            viewer_root=args.viewer_root,
            source_out=out_dir,
            dataset=dataset,
            metadata=metadata,
            item_id=item_id,
            name=name,
            longitude=longitude,
            latitude=latitude,
            scale=getattr(args, "scale", 1.0),
            rotate=rotate,
            placement_mode=getattr(args, "placement_mode", "item_center"),
        )
    elif getattr(args, "legacy_manifests", False) or getattr(args, "generate", "lod1.3") in {"all", "glb"}:
        md = dict(metadata)
        md["_out_dir"] = str(out_dir)
        item = _viewer_item(
            dataset=dataset,
            item_id=item_id,
            name=name,
            longitude=longitude,
            latitude=latitude,
            scale=getattr(args, "scale", 1.0),
            rotate=rotate,
            metadata=md,
        )
        write_json(out_dir / "viewer_item.json", item)
    return metadata


def discover_bim_files(input_path: Path, recursive: bool):
    SUPPORTED = {".ifc", ".skp"}
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() in SUPPORTED else []
    iterator = input_path.rglob("*") if recursive else input_path.iterdir()
    return sorted(
        (path for path in iterator if path.is_file() and path.suffix.lower() in SUPPORTED),
        key=lambda path: str(path).lower(),
    )


def main():
    args = build_parser().parse_args()
    input_path = args.input.expanduser().resolve()
    if not input_path.exists():
        print(f"ERROR: input not found: {input_path}", file=sys.stderr)
        return 2
    if not input_path.is_file() and not input_path.is_dir():
        print(f"ERROR: input must be a .skp/.ifc file or folder: {input_path}", file=sys.stderr)
        return 2

    files = discover_bim_files(input_path, args.recursive)
    if not files:
        scope = "recursively" if args.recursive else "directly"
        print(f"ERROR: no .skp or .ifc files found {scope} in: {input_path}", file=sys.stderr)
        return 2

    batch = input_path.is_dir()
    output_arg = args.out.expanduser().resolve() if args.out is not None else None
    output_base = output_arg or (Path.cwd() / "dist").resolve()
    failures = []
    stem_counts = Counter(safe_slug(path.stem) for path in files)

    try:
        for index, file_path in enumerate(files, 1):
            stem_slug = safe_slug(file_path.stem)
            dataset = (
                safe_slug(str(file_path.relative_to(input_path).with_suffix("")))
                if batch and stem_counts[stem_slug] > 1
                else stem_slug
            )
            out_dir = output_base / dataset if batch else (
                output_arg or output_base / dataset
            )
            if batch:
                print(f"\n=== [{index}/{len(files)}] {file_path.name} ===")
            try:
                process_one(args, file_path, out_dir, batch=batch, dataset=dataset)
            except Exception as exc:
                failures.append((file_path, exc))
                print(f"\nERROR [{file_path.name}]: {exc}", file=sys.stderr)

    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130

    if failures:
        print(
            f"\nBATCH COMPLETE: {len(files) - len(failures)}/{len(files)} succeeded; "
            f"{len(failures)} failed.",
            file=sys.stderr,
        )
        for path, error in failures:
            print(f"  - {path}: {error}", file=sys.stderr)
        return 1

    if batch:
        print(f"\nBATCH SUCCESS: {len(files)}/{len(files)} models processed.")
        print(f"  Output root     : {output_base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
