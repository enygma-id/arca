# SPDX-License-Identifier: AGPL-3.0-only
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from arca.engine.citygml import CityGMLWriter
from arca.engine.georef import GeoreferenceContext
from arca.engine.pipeline import preprocess


def test_citygml_writer_structure():
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td)
        writer = CityGMLWriter(out_dir, "test_bldg", building_name="Test Building")

        tri_roof = np.array([
            [0.0, 0.0, 10.0],
            [10.0, 0.0, 10.0],
            [5.0, 10.0, 10.0],
        ])
        writer.add_triangle("RoofSurface", tri_roof, object_id=1)

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

        res = writer.finalize(anchor_lon=106.8, anchor_lat=-6.2, georef=georef, storey_count=2)
        assert res is not None
        assert res["triangles_count"] == 2
        assert res["surfaces_count"] == 2

        gml_path = out_dir / "building.gml"
        assert gml_path.exists()

        content = gml_path.read_text(encoding="utf-8")
        assert "core:CityModel" in content
        assert "bldg:Building" in content
        assert "bldg:RoofSurface" in content
        assert "bldg:WallSurface" in content
        assert "gml:LinearRing" in content

        # Check valid XML parse
        tree = ET.fromstring(content)
        assert tree.tag.endswith("CityModel")

        # Check SRS
        assert "EPSG::32748" in content


def test_citygml_preprocess_integration():
    sample_ifc = Path("samples/arca-sample-area-01/data/arca_synthetic_mall_10f.ifc")
    if not sample_ifc.exists():
        return

    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "mall_gml"
        meta = preprocess(
            ifc_path=sample_ifc,
            out_dir=out_dir,
            generate_mode="citygml",
            anchor_lon=106.827,
            anchor_lat=-6.175,
        )

        gml_file = out_dir / "building.gml"
        assert gml_file.exists(), "building.gml was not generated"

        # Verify valid XML
        tree = ET.parse(gml_file)
        root = tree.getroot()
        assert root.tag.endswith("CityModel")

        assert meta["geometry"]["citygml"] == "building.gml"
        assert meta["storage"]["citygml_bytes"] > 0


def test_citygml_special_characters_escaping():
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td)
        special_name = "Building A & B <North-Tower> 'Phase 1'"
        writer = CityGMLWriter(out_dir, "test_special", building_name=special_name)

        tri = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ])
        writer.add_triangle("WallSurface", tri, object_id=1)
        writer.finalize(anchor_lon=106.8, anchor_lat=-6.2)

        gml_path = out_dir / "building.gml"
        content = gml_path.read_text(encoding="utf-8")

        # Must be well-formed XML and not raise ParseError
        tree = ET.fromstring(content)
        assert tree.tag.endswith("CityModel")

        # Verify parsed name matches original text exactly
        namespaces = {
            "core": "http://www.opengis.net/citygml/2.0",
            "bldg": "http://www.opengis.net/citygml/building/2.0",
            "gml": "http://www.opengis.net/gml",
        }
        bldg = tree.find(".//bldg:Building", namespaces)
        assert bldg is not None
        name_elem = bldg.find("gml:name", namespaces)
        assert name_elem is not None
        assert name_elem.text == special_name

