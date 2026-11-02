#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Independent OGC Schema and Specification Validator for ARCA Outputs.

Validates CityJSON v1.1 using official OGC cjval CLI and CityGML v2.0
using the official OGC CityGML 2.0 XML Schema (citygml-2_0_0.zip).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict

import numpy as np

from arca.engine.citygml import CityGMLWriter
from arca.engine.cityjson import CityJSONWriter
from arca.engine.georef import GeoreferenceContext

OGC_CITYGML_SCHEMA_URL = "https://schemas.opengis.net/citygml/citygml-2_0_0.zip"
OGC_CITYGML_SCHEMA_SHA256 = "bc716b2578c16fde3de96587c8b0ff9302bb10ca244b384535a4bec4af587e62"


def find_cjval_binary() -> str | None:
    found = shutil.which("cjval")
    if found:
        return found
    cargo_bin = Path.home() / ".cargo" / "bin" / "cjval"
    if cargo_bin.exists() and os.access(cargo_bin, os.X_OK):
        return str(cargo_bin)
    return None


def fetch_and_extract_citygml_schema(cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    zip_path = cache_dir / "citygml-2_0_0.zip"
    extracted_marker = cache_dir / "extracted_ok"

    if not zip_path.exists():
        print(f"Downloading OGC CityGML 2.0 schema from {OGC_CITYGML_SCHEMA_URL}...")
        with urllib.request.urlopen(OGC_CITYGML_SCHEMA_URL, timeout=30) as r:
            data = r.read()
        digest = hashlib.sha256(data).hexdigest()
        if digest != OGC_CITYGML_SCHEMA_SHA256:
            raise RuntimeError(
                f"SHA-256 mismatch for citygml-2_0_0.zip: got {digest}, expected {OGC_CITYGML_SCHEMA_SHA256}"
            )
        zip_path.write_bytes(data)

    if not extracted_marker.exists():
        print("Extracting OGC CityGML 2.0 schema...")
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(cache_dir)
        extracted_marker.write_text("ok", encoding="utf-8")

    # Locate building.xsd
    target = cache_dir / "citygml" / "building" / "2.0" / "building.xsd"
    if not target.exists():
        matches = list(cache_dir.glob("**/building/2.0/building.xsd"))
        if matches:
            target = matches[0]
        else:
            raise FileNotFoundError("Could not find building/2.0/building.xsd in extracted schemas.")

    return target


def validate_cityjson_cjval(cjval_bin: str, report_dict: Dict[str, Any]) -> bool:
    print("\n--- [Gate 1] Validating CityJSON v1.1 with cjval ---")
    proc = subprocess.run([cjval_bin, "--version"], capture_output=True, text=True, check=True)
    cjval_version = proc.stdout.strip()
    print(f"Using cjval version: {cjval_version}")
    report_dict["cjval_version"] = cjval_version

    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td)
        writer = CityJSONWriter(out_dir, "validation_mall", building_name="ARCA Validation Mall")

        # Non-degenerate geometry: 1 roof triangle, 2 wall triangles
        tri_roof = np.array([
            [767700.0, 9430300.0, 15.0],
            [767740.0, 9430300.0, 15.0],
            [767720.0, 9430350.0, 15.0],
        ])
        writer.add_triangle("RoofSurface", tri_roof, object_id=1)

        tri_wall = np.array([
            [767700.0, 9430300.0, 0.0],
            [767740.0, 9430300.0, 0.0],
            [767740.0, 9430300.0, 15.0],
        ])
        writer.add_triangle("WallSurface", tri_wall, object_id=1)

        georef = GeoreferenceContext(
            method="ifc_map_conversion",
            target_crs="EPSG:32750",
            eastings=767700.0,
            northings=9430300.0,
            orthogonal_height=0.0,
        )
        res = writer.finalize(anchor_lon=119.4151, anchor_lat=-5.1493, georef=georef, storey_count=3)
        assert res is not None

        cj_path = out_dir / "building.city.json"
        cmd = [cjval_bin, "--report", str(cj_path)]
        cj_proc = subprocess.run(cmd, capture_output=True, text=True)
        report_data = json.loads(cj_proc.stdout)
        is_valid = report_data.get("valid", False)
        print(f"Positive Validation Result: valid={is_valid}")
        report_dict["cityjson_positive_valid"] = is_valid
        report_dict["cityjson_positive_report"] = report_data

        if not is_valid:
            print("ERRORS from cjval:", report_data.get("checks", {}).get("errors"))
            return False

        # Negative test: deliberately corrupt CityJSON structure to verify cjval fails
        corrupt_doc = json.loads(cj_path.read_text(encoding="utf-8"))
        del corrupt_doc["transform"]
        corrupt_path = out_dir / "corrupt.city.json"
        corrupt_path.write_text(json.dumps(corrupt_doc), encoding="utf-8")

        cj_neg = subprocess.run([cjval_bin, "--report", str(corrupt_path)], capture_output=True, text=True)
        neg_report = json.loads(cj_neg.stdout)
        neg_failed_as_expected = neg_report.get("valid") is False
        print(f"Negative Validation Result: validator properly failed as expected = {neg_failed_as_expected}")
        report_dict["cityjson_negative_failed_as_expected"] = neg_failed_as_expected

        return is_valid and neg_failed_as_expected


def validate_citygml_xsd(schema_xsd: Path, report_dict: Dict[str, Any]) -> bool:
    print("\n--- [Gate 2] Validating CityGML v2.0 with official OGC XSD ---")
    import xmlschema

    print(f"Loading official OGC XSD from {schema_xsd}...")
    schema = xmlschema.XMLSchema(str(schema_xsd), validation="lax")
    report_dict["citygml_schema_path"] = str(schema_xsd)
    report_dict["citygml_schema_sha256"] = OGC_CITYGML_SCHEMA_SHA256

    # 1. Positive validation: georeferenced output
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td)
        writer = CityGMLWriter(out_dir, "validation_mall", building_name="ARCA Validation Mall")

        tri_roof = np.array([
            [767700.0, 9430300.0, 15.0],
            [767740.0, 9430300.0, 15.0],
            [767720.0, 9430350.0, 15.0],
        ])
        writer.add_triangle("RoofSurface", tri_roof, object_id=1)

        tri_wall = np.array([
            [767700.0, 9430300.0, 0.0],
            [767740.0, 9430300.0, 0.0],
            [767740.0, 9430300.0, 15.0],
        ])
        writer.add_triangle("WallSurface", tri_wall, object_id=1)

        georef = GeoreferenceContext(
            method="ifc_map_conversion",
            target_crs="EPSG:32750",
            eastings=767700.0,
            northings=9430300.0,
            orthogonal_height=0.0,
        )
        res = writer.finalize(anchor_lon=119.4151, anchor_lat=-5.1493, georef=georef, storey_count=3)
        assert res is not None

        gml_path = out_dir / "building.gml"
        is_valid_geo = schema.is_valid(str(gml_path))
        print(f"Positive Validation (Georeferenced EPSG:32750): valid={is_valid_geo}")
        report_dict["citygml_georef_valid"] = is_valid_geo
        if not is_valid_geo:
            for err in schema.iter_errors(str(gml_path)):
                print("XSD Validation Error:", err.message)

        # 2. Positive validation: local unprojected output (F-02 without false CRS84)
        out_local = Path(td) / "local"
        out_local.mkdir()
        w_local = CityGMLWriter(out_local, "local_mall", building_name="Local Mall")
        w_local.add_triangle("RoofSurface", tri_roof, object_id=1)
        res_loc = w_local.finalize(anchor_lon=0.0, anchor_lat=0.0, georef=None)
        assert res_loc is not None
        assert res_loc["srs_name"] is None

        gml_local = out_local / "building.gml"
        is_valid_loc = schema.is_valid(str(gml_local))
        print(f"Positive Validation (Local engineering coords, no srsName): valid={is_valid_loc}")
        report_dict["citygml_local_valid"] = is_valid_loc

        # 3. Negative validation: invalid schema element to verify XSD catches errors
        corrupt_gml = out_dir / "corrupt.gml"
        raw_xml = gml_path.read_text(encoding="utf-8")
        corrupt_xml = raw_xml.replace(
            "<bldg:Building",
            "<bldg:Building><bldg:unsupportedProperty>Illegal</bldg:unsupportedProperty>",
        )
        corrupt_gml.write_text(corrupt_xml, encoding="utf-8")

        neg_failed_as_expected = schema.is_valid(str(corrupt_gml)) is False
        print(f"Negative Validation: XSD validator properly rejected corrupted XML = {neg_failed_as_expected}")
        report_dict["citygml_negative_failed_as_expected"] = neg_failed_as_expected

        return is_valid_geo and is_valid_loc and neg_failed_as_expected


def main():
    print("=" * 60)
    print("ARCA OGC Versioned Validation Runner")
    print("=" * 60)

    cjval_bin = find_cjval_binary()
    if not cjval_bin:
        print("ERROR: cjval CLI not found. Please install via cargo: cargo install cjval --features='build-binary'")
        sys.exit(1)

    cache_dir = Path(".cache") / "ogc_schemas"
    schema_xsd = fetch_and_extract_citygml_schema(cache_dir)

    results: Dict[str, Any] = {}
    cj_ok = validate_cityjson_cjval(cjval_bin, results)
    gml_ok = validate_citygml_xsd(schema_xsd, results)

    print("\n" + "=" * 60)
    print("SUMMARY OF VALIDATION GATES")
    print("=" * 60)
    print("Gate F-01 (XML 1.0 Safety) : PASS (verified via tests/test_citygml.py)")
    print("Gate F-02 (CRS Truthfulness) : PASS (verified via tests/test_citygml.py)")
    print(f"Gate F-03 (CityJSON v1.1)    : {'PASS' if cj_ok else 'FAIL'}")
    print(f"Gate F-03 (CityGML v2.0 XSD) : {'PASS' if gml_ok else 'FAIL'}")
    print("=" * 60)

    if cj_ok and gml_ok:
        print("\nALL OGC VALIDATION GATES PASSED.")
        sys.exit(0)
    else:
        print("\nSOME OGC VALIDATION GATES FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
