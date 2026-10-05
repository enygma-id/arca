# SPDX-License-Identifier: AGPL-3.0-only
import json
from arca.engine import (
    compound_angle_to_degrees,
    degrees_to_compound_dms,
    find_metadata_json,
    latlon_to_utm_wgs84,
    parse_metadata_json,
    resolve_georeferencing,
    utm_to_latlon_wgs84,
)


def test_dms_roundtrip():
    lat = -5.1492598707
    dms = degrees_to_compound_dms(lat)
    assert dms[0] == -5
    assert dms[1] == 8
    assert dms[2] == 57
    restored = compound_angle_to_degrees(dms)
    assert abs(restored - lat) < 1e-6


def test_utm_karney_projection_precision():
    lat = -5.1492598707
    lon = 119.4150999836
    epsg_int, zone_str, easting, northing = latlon_to_utm_wgs84(lat, lon)

    assert epsg_int == 32750
    assert zone_str == "50S"
    assert abs(easting - 767741.36) < 0.05
    assert abs(northing - 9430330.03) < 0.05

    restored_lon, restored_lat = utm_to_latlon_wgs84(easting, northing, zone=50, south=True)
    assert abs(restored_lat - lat) < 1e-7
    assert abs(restored_lon - lon) < 1e-7


def test_find_metadata_json(tmp_path):
    model = tmp_path / "building.ifc"
    model.write_text("dummy", encoding="utf-8")

    # No metadata file yet
    assert find_metadata_json(model) is None

    # Companion building.json
    meta = tmp_path / "building.json"
    meta.write_text('{"crs": "EPSG:32750"}', encoding="utf-8")
    assert find_metadata_json(model) == meta

    # Remove building.json and test metadata.json
    meta.unlink()
    fallback_meta = tmp_path / "metadata.json"
    fallback_meta.write_text('{"crs": "EPSG:32750"}', encoding="utf-8")
    assert find_metadata_json(model) == fallback_meta


def test_parse_metadata_json_and_geojson(tmp_path):
    # Standard JSON format
    json_file = tmp_path / "meta.json"
    json_file.write_text(json.dumps({
        "name": "Tower A",
        "longitude": 119.4151,
        "latitude": -5.14926,
        "crs": "EPSG:32750",
        "rotate": 45.0
    }), encoding="utf-8")

    info = parse_metadata_json(json_file)
    assert info["has_georef"] is True
    assert info["name"] == "Tower A"
    assert abs(info["longitude"] - 119.4151) < 1e-5
    assert abs(info["latitude"] - (-5.14926)) < 1e-5
    assert info["crs"] == "EPSG:32750"
    assert info["rotate"] == 45.0

    # GeoJSON FeatureCollection format
    geojson_file = tmp_path / "anchor.geojson"
    geojson_file.write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [112.63, -7.98]
                },
                "properties": {
                    "name": "Tower B",
                    "crs": "EPSG:32749"
                }
            }
        ]
    }), encoding="utf-8")

    geo_info = parse_metadata_json(geojson_file)
    assert geo_info["has_georef"] is True
    assert geo_info["name"] == "Tower B"
    assert abs(geo_info["longitude"] - 112.63) < 1e-5
    assert abs(geo_info["latitude"] - (-7.98)) < 1e-5
    assert geo_info["crs"] == "EPSG:32749"


def test_resolve_georef_metadata_priority():
    # Empty entities (no IFC internal georeference)
    ents = {}
    metadata_info = {
        "has_georef": True,
        "name": "Metadata Tower",
        "longitude": 119.4151,
        "latitude": -5.14926,
        "crs": "EPSG:32750",
        "rotate": 15.0,
        "file_name": "building.json"
    }

    ctx = resolve_georeferencing(
        ents,
        metadata_info=metadata_info
    )

    assert ctx is not None
    assert ctx.is_georeferenced is True
    assert ctx.method == "metadata_json"
    assert abs(ctx.origin_lon - 119.4151) < 1e-4
    assert abs(ctx.origin_lat - (-5.14926)) < 1e-4
    assert ctx.crs_epsg == "EPSG:32750"


def test_metadata_json_unit_default_to_auto(tmp_path):
    # 1. Without unit key -> default "auto"
    f1 = tmp_path / "meta_no_unit.json"
    f1.write_text(json.dumps({
        "name": "Tower No Unit",
        "longitude": 119.4151,
        "latitude": -5.14926,
        "crs": "EPSG:32750"
    }), encoding="utf-8")
    info1 = parse_metadata_json(f1)
    assert info1["unit"] == "auto"

    ctx1 = resolve_georeferencing({}, metadata_info=info1)
    assert ctx1.unit_name == "m"
    assert ctx1.unit_scale_to_m == 1.0

    # 2. With explicit unit key -> honors unit
    f2 = tmp_path / "meta_mm.json"
    f2.write_text(json.dumps({
        "name": "Tower MM",
        "longitude": 119.4151,
        "latitude": -5.14926,
        "crs": "EPSG:32750",
        "unit": "mm"
    }), encoding="utf-8")
    info2 = parse_metadata_json(f2)
    assert info2["unit"] == "mm"

    ctx2 = resolve_georeferencing({}, metadata_info=info2)
    assert ctx2.unit_name == "mm"
    assert ctx2.unit_scale_to_m == 0.001


