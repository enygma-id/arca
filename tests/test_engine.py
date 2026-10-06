# SPDX-License-Identifier: AGPL-3.0-only
import tempfile
from pathlib import Path

from arca.engine import detect_input_format


def test_detect_input_format():
    with tempfile.TemporaryDirectory() as td:
        ifc_path = Path(td) / "test.ifc"
        ifc_path.write_text("ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n")
        assert detect_input_format(ifc_path) == "IFC"

        skp_path = Path(td) / "test.skp"
        skp_path.write_bytes(b"SketchUp Model\x00")
        assert detect_input_format(skp_path) == "SKP"


def test_openskp_importable():
    import openskp
    assert openskp is not None


def test_inject_georeference_into_data_section():
    from arca.engine.skp import inject_georeference_into_step

    with tempfile.TemporaryDirectory() as td:
        ifc_path = Path(td) / "sample.ifc"
        ifc_path.write_text(
            "ISO-10303-21;\n"
            "HEADER;\n"
            "FILE_DESCRIPTION(('Test'),'2;1');\n"
            "ENDSEC;\n"
            "DATA;\n"
            "#1=IFCPROJECT('guid',$,'Project',$,$,$,$,(#2),#3);\n"
            "ENDSEC;\n"
            "END-ISO-10303-21;\n"
        )
        out_path = Path(td) / "sample_georef.ifc"
        inject_georeference_into_step(
            ifc_path=ifc_path,
            out_path=out_path,
            lat=-6.2,
            lon=106.8,
            elev=10.0,
            epsg_code="EPSG:32748",
            zone_str="48S",
            easting=700000.0,
            northing=9300000.0,
            north_angle=270.0,
        )

        content = out_path.read_text()
        data_pos = content.find("DATA;")
        map_pos = content.find("IFCMAPCONVERSION")
        crs_pos = content.find("IFCPROJECTEDCRS")
        last_endsec = content.rfind("ENDSEC;")

        # Must be strictly after DATA; and before final ENDSEC;
        assert data_pos != -1
        assert map_pos > data_pos
        assert crs_pos > data_pos
        assert map_pos < last_endsec
        assert crs_pos < last_endsec


def test_bilingual_classifier():
    from arca.engine.skp import bilingual_classifier

    assert bilingual_classifier("Group_1", "Atap") == ("IFCROOF", "IfcRoof")
    assert bilingual_classifier("Dinding_Luar", "") == ("IFCWALL", "IfcWall")
    assert bilingual_classifier("Lantai_1", "") == ("IFCSLAB", "IfcSlab")
    assert bilingual_classifier("Kolom_K1", "") == ("IFCCOLUMN", "IfcColumn")
    assert bilingual_classifier("Balok_B1", "") == ("IFCBEAM", "IfcBeam")
    assert bilingual_classifier("Jendela_Kaca", "") == ("IFCWINDOW", "IfcWindow")
    assert bilingual_classifier("Pintu_Utama", "") == ("IFCDOOR", "IfcDoor")
    assert bilingual_classifier("Custom_Mesh", "Unknown_Tag") == (
        "IFCBUILDINGELEMENTPROXY",
        "IfcBuildingElementProxy",
    )


def test_convert_skp_to_georef_ifc_progress_callback(tmp_path, monkeypatch):
    from unittest.mock import MagicMock

    from arca.engine.skp import convert_skp_to_georef_ifc

    events = []
    def callback(evt):
        events.append(evt)

    mock_skp = MagicMock()
    mock_scene = MagicMock()
    mock_scene.glb_primitives = [1, 2, 3]
    mock_skp.build_scene.return_value = mock_scene

    monkeypatch.setattr("arca.engine.skp.SkpFile.open", lambda p: mock_skp)
    monkeypatch.setattr("arca.engine.skp.restore_skp_orientation_for_ifc", lambda sc: 100)
    monkeypatch.setattr("arca.engine.skp.openskp_ifc.export", lambda sc, p, scale, schema, classifier: None)
    monkeypatch.setattr("arca.engine.skp.inject_georeference_into_step", lambda **kwargs: None)

    georef = {
        "latitude": -7.98,
        "longitude": 112.63,
        "elevation": 0.0,
        "crs": "EPSG:32749",
        "utm_zone": "49S",
        "easting": 679700.0,
        "northing": 9117400.0,
        "north_angle": 0.0,
    }

    dummy_skp = tmp_path / "model.skp"
    dummy_skp.write_text("dummy")
    out_ifc = tmp_path / "model.ifc"

    res = convert_skp_to_georef_ifc(dummy_skp, out_ifc, georef, progress_cb=callback)
    assert res == out_ifc
    assert len(events) >= 5
    assert all("pct" in e for e in events)
    assert events[0]["pct"] < events[-1]["pct"]
    messages = [e["message"] for e in events]
    assert any("Reading SketchUp file" in m for m in messages)
    assert any("Coordinate orientation corrected" in m for m in messages)
    assert any("Injecting buildingSMART georeferencing" in m for m in messages)


def test_triangulate_polygon_3d():
    import numpy as np
    from shapely.geometry import Point, Polygon

    from arca.engine.geom import triangulate_polygon_3d

    # Degenerate
    assert triangulate_polygon_3d(np.empty((2, 3))) == []

    # Triangle
    tri = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=float)
    res_tri = triangulate_polygon_3d(tri)
    assert len(res_tri) == 1
    assert np.allclose(res_tri[0], tri)

    # Quad
    quad = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], dtype=float)
    res_quad = triangulate_polygon_3d(quad)
    assert len(res_quad) == 2

    # Concave L-shape: must not leak into empty corner (1.9, 1.9)
    l_shape = np.array(
        [
            [3.0, 1.0, 5.0],
            [1.0, 1.0, 5.0],
            [1.0, 3.0, 5.0],
            [0.0, 3.0, 5.0],
            [0.0, 0.0, 5.0],
            [3.0, 0.0, 5.0],
        ],
        dtype=float,
    )
    res_l = triangulate_polygon_3d(l_shape)
    assert len(res_l) >= 4
    for t in res_l:
        poly_2d = Polygon(t[:, :2])
        assert not poly_2d.contains(Point(1.9, 1.9))
        assert np.allclose(t[:, 2], 5.0)




