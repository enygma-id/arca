# SPDX-License-Identifier: AGPL-3.0-only
import json
import tempfile
from pathlib import Path

from arca.engine.atap import inspect_atap_file, is_atap_geojson, preprocess_atap
from arca.engine.pipeline import detect_input_format, inspect_model_file

SAMPLE_ATAP_GEOJSON = {
    "type": "FeatureCollection",
    "name": "sample_atap_building",
    "atap": {
        "engine_version": "0.2.0",
        "profile_version": "0.6",
    },
    "features": [
        {
            "type": "Feature",
            "properties": {
                "object_id": "101",
                "part_id": "101-P00",
                "name": "Block A",
                "base_elevation_m": 10.0,
                "top_elevation_m": 25.0,
                "part_height_m": 15.0,
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [106.8270, -6.1750],
                        [106.8280, -6.1750],
                        [106.8280, -6.1760],
                        [106.8270, -6.1760],
                        [106.8270, -6.1750],
                    ]
                ],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "object_id": "102",
                "part_id": "102-P01",
                "name": "Block B Tower",
                "base_elevation_m": 25.0,
                "top_elevation_m": 45.0,
                "part_height_m": 20.0,
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [106.8272, -6.1752],
                        [106.8278, -6.1752],
                        [106.8278, -6.1758],
                        [106.8272, -6.1758],
                        [106.8272, -6.1752],
                    ]
                ],
            },
        },
    ],
}


def test_is_atap_geojson():
    with tempfile.TemporaryDirectory() as td:
        atap_file = Path(td) / "test_atap.geojson"
        atap_file.write_text(json.dumps(SAMPLE_ATAP_GEOJSON), encoding="utf-8")
        assert is_atap_geojson(atap_file) is True
        assert detect_input_format(atap_file) == "ATAP"

        normal_file = Path(td) / "normal.geojson"
        normal_file.write_text(json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8")
        assert is_atap_geojson(normal_file) is False


def test_inspect_atap_file():
    with tempfile.TemporaryDirectory() as td:
        atap_file = Path(td) / "sample_tower.geojson"
        atap_file.write_text(json.dumps(SAMPLE_ATAP_GEOJSON), encoding="utf-8")

        res = inspect_atap_file(atap_file)
        assert res["format"] == "ATAP"
        assert res["has_georef"] is True
        assert res["building_count"] == 2
        assert "EPSG:" in res["crs"]
        assert res["longitude"] is not None
        assert res["latitude"] is not None
        assert "2 bagian bangunan" in res["message"]

        # Unified inspect_model_file routing
        routed = inspect_model_file(atap_file)
        assert routed["format"] == "ATAP"
        assert routed["has_georef"] is True
        assert routed["building_count"] == 2


def test_preprocess_atap_full_export():
    with tempfile.TemporaryDirectory() as td:
        atap_file = Path(td) / "sample_tower.geojson"
        atap_file.write_text(json.dumps(SAMPLE_ATAP_GEOJSON), encoding="utf-8")

        out_dir = Path(td) / "out_atap"
        meta = preprocess_atap(
            geojson_path=atap_file,
            out_dir=out_dir,
            generate_mode="all",
        )

        assert meta["source_format"] == "ATAP"
        assert meta["summary"]["max_height_m"] == 35.0  # 45.0 - 10.0
        assert meta["plateau_count"] == 2

        # Check all outputs
        assert (out_dir / "building.geojson").exists()
        assert (out_dir / "building.city.json").exists()
        assert (out_dir / "building.gml").exists()
        assert (out_dir / "render" / "model.glb").exists()
        assert (out_dir / "render" / "model.geojson").exists()

        # Check canonical 3D coordinates & bbox midpoint anchor
        b_geo = json.loads((out_dir / "building.geojson").read_text(encoding="utf-8"))
        p0 = b_geo["features"][0]["geometry"]["coordinates"][0][0]
        assert len(p0) == 3
        assert p0[2] == 10.0
        assert meta["anchor"]["lon"] == 106.8275
        assert meta["anchor"]["lat"] == -6.1755

        # Check CityJSON content
        cj = json.loads((out_dir / "building.city.json").read_text(encoding="utf-8"))
        assert cj["type"] == "CityJSON"
        assert len(cj["CityObjects"]) >= 1

        # Check CityGML content
        gml = (out_dir / "building.gml").read_text(encoding="utf-8")
        assert "core:CityModel" in gml
        assert "bldg:Building" in gml
        assert "bldg:RoofSurface" in gml
        assert "bldg:WallSurface" in gml
        assert "bldg:GroundSurface" in gml


def test_preprocess_atap_split_and_merge_modes():
    with tempfile.TemporaryDirectory() as td:
        atap_file = Path(td) / "sample_tower.geojson"
        atap_file.write_text(json.dumps(SAMPLE_ATAP_GEOJSON), encoding="utf-8")

        # 1. Default (Split mode)
        out_split = Path(td) / "out_split"
        meta_split = preprocess_atap(
            geojson_path=atap_file,
            out_dir=out_split,
            generate_mode="all",
            merge=False,
        )
        assert meta_split.get("is_split") is True
        assert meta_split.get("building_count") == 2
        assert len(meta_split.get("buildings", [])) == 2
        assert (out_split / "buildings" / "101" / "building.geojson").exists()
        assert (out_split / "buildings" / "101" / "render" / "model.glb").exists()
        assert (out_split / "buildings" / "102" / "building.geojson").exists()
        assert (out_split / "buildings" / "102" / "render" / "model.glb").exists()

        # 2. Merged mode
        out_merged = Path(td) / "out_merged"
        meta_merged = preprocess_atap(
            geojson_path=atap_file,
            out_dir=out_merged,
            generate_mode="all",
            merge=True,
        )
        assert meta_merged.get("is_split") is False
        assert meta_merged.get("granularity") == "single_precinct"
        assert not (out_merged / "buildings").exists()
        assert (out_merged / "building.geojson").exists()
        assert (out_merged / "render" / "model.glb").exists()

        merged_fc = json.loads((out_merged / "building.geojson").read_text(encoding="utf-8"))
        assert merged_fc["features"][0]["properties"]["is_single_precinct"] is True
        assert merged_fc["features"][0]["properties"]["granularity"] == "single_precinct"


def test_sync_latest_viewer_split_mode():
    from arca.engine.pipeline import sync_latest_viewer

    with tempfile.TemporaryDirectory() as td:
        atap_file = Path(td) / "sample_tower.geojson"
        atap_file.write_text(json.dumps(SAMPLE_ATAP_GEOJSON), encoding="utf-8")

        out_dir = Path(td) / "out_split"
        meta = preprocess_atap(
            geojson_path=atap_file,
            out_dir=out_dir,
            generate_mode="all",
            merge=False,
        )

        viewer_root = Path(td) / "viewer"
        viewer_root.mkdir()

        sync_latest_viewer(
            viewer_root=viewer_root,
            source_out=out_dir,
            dataset="sample_dataset",
            metadata=meta,
            item_id="sample_dataset",
            name="Sample Precinct",
            longitude=106.8275,
            latitude=-6.1755,
            scale=1.0,
            rotate=0.0,
            placement_mode="native",
        )

        data_json = json.loads((viewer_root / "data.json").read_text(encoding="utf-8"))
        items = data_json.get("items", [])
        assert len(items) == 2
        ids = {it["id"] for it in items}
        assert "sample_dataset_101" in ids
        assert "sample_dataset_102" in ids
        for it in items:
            glb_path = viewer_root / it["detail"]["glb"].lstrip("./")
            assert glb_path.exists()
            geo_path = viewer_root / it["geojson"]["lod1_3"].lstrip("./")
            assert geo_path.exists()
