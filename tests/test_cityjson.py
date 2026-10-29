# SPDX-License-Identifier: AGPL-3.0-only
import json
import tempfile
from pathlib import Path

import numpy as np

from arca.engine.cityjson import CityJSONWriter
from arca.engine.georef import GeoreferenceContext
from arca.engine.pipeline import preprocess


def test_cityjson_writer_structure():
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td)
        writer = CityJSONWriter(out_dir, "test_bldg", building_name="Test Building")

        # Add roof triangle
        tri_roof = np.array([
            [0.0, 0.0, 10.0],
            [10.0, 0.0, 10.0],
            [5.0, 10.0, 10.0],
        ])
        writer.add_triangle("RoofSurface", tri_roof, object_id=1)

        # Add wall triangle
        tri_wall = np.array([
            [0.0, 0.0, 0.0],
            [10.0, 0.0, 0.0],
            [10.0, 0.0, 10.0],
        ])
        writer.add_triangle("WallSurface", tri_wall, object_id=1)

        georef = GeoreferenceContext(
            method="ifc_map_conversion",
            target_crs="EPSG:32748",
            eastings=700000.0,
            northings=9300000.0,
            orthogonal_height=15.0,
        )

        res = writer.finalize(anchor_lon=106.8, anchor_lat=-6.2, georef=georef, storey_count=3)
        assert res is not None
        assert res["triangles_count"] == 2
        assert res["surfaces_count"] == 2
        assert res["lod"] == "2.0"

        cj_path = out_dir / "building.city.json"
        assert cj_path.exists()

        data = json.loads(cj_path.read_text(encoding="utf-8"))
        assert data["type"] == "CityJSON"
        assert data["version"] == "1.1"
        assert "transform" in data
        assert "scale" in data["transform"]
        assert "translate" in data["transform"]

        bldg = data["CityObjects"]["Building_test_bldg"]
        assert bldg["type"] == "Building"
        assert bldg["attributes"]["name"] == "Test Building"
        assert bldg["attributes"]["storeysAboveGround"] == 3

        geom = bldg["geometry"][0]
        assert geom["type"] == "MultiSurface"
        assert geom["lod"] == "2.0"
        assert len(geom["boundaries"]) == 2
        assert len(geom["semantics"]["values"]) == 2
        assert any(s["type"] == "RoofSurface" for s in geom["semantics"]["surfaces"])
        assert any(s["type"] == "WallSurface" for s in geom["semantics"]["surfaces"])

        # Check metadata
        assert data["metadata"]["referenceSystem"] == "https://www.opengis.net/def/crs/EPSG/0/32748"
        assert len(data["metadata"]["geographicalExtent"]) == 6


def test_cityjson_preprocess_integration():
    sample_ifc = Path("samples/arca-sample-area-01/data/arca_synthetic_mall_10f.ifc")
    if not sample_ifc.exists():
        return

    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "mall_output"
        meta = preprocess(
            ifc_path=sample_ifc,
            out_dir=out_dir,
            generate_mode="all",
            anchor_lon=106.827,
            anchor_lat=-6.175,
        )

        cj_file = out_dir / "building.city.json"
        assert cj_file.exists(), "building.city.json was not generated"

        doc = json.loads(cj_file.read_text(encoding="utf-8"))
        assert doc["type"] == "CityJSON"
        assert doc["version"] == "1.1"

        bldg_keys = list(doc["CityObjects"].keys())
        assert len(bldg_keys) == 1
        bldg = doc["CityObjects"][bldg_keys[0]]
        assert bldg["type"] == "Building"
        assert len(bldg["geometry"]) >= 1

        geom = bldg["geometry"][0]
        assert geom["type"] == "MultiSurface"
        assert len(geom["boundaries"]) > 0

        # Storage metadata checks
        assert meta["geometry"]["cityjson"] == "building.city.json"
        assert meta["storage"]["cityjson_bytes"] > 0
