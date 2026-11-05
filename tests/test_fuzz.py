# SPDX-License-Identifier: AGPL-3.0-only
"""Property-based fuzz testing and input sanitization fuzzers for ARCA."""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from arca.engine.atap import is_atap_geojson
from arca.engine.citygml import validate_xml_10_string
from arca.engine.georef import latlon_to_utm_wgs84
from arca.engine.utils import safe_slug
from arca.server.app import safe_resolve_child

try:
    import atheris
except ImportError:
    atheris = None


@settings(max_examples=200, deadline=None)
@given(path_str=st.text())
def test_fuzz_safe_resolve_child(path_str: str) -> None:
    base_dir = Path("/tmp/arca_fuzz_sandbox")
    resolved = safe_resolve_child(base_dir, path_str)
    if resolved is not None:
        assert resolved.is_absolute()
        assert str(resolved).startswith(str(base_dir.resolve()))
        assert ".." not in resolved.parts


@settings(max_examples=200, deadline=None)
@given(text=st.text())
def test_fuzz_validate_xml_10_string(text: str) -> None:
    try:
        validate_xml_10_string(text)
    except ValueError as exc:
        assert "Invalid XML 1.0 character" in str(exc)


@settings(max_examples=200, deadline=None)
@given(name=st.text())
def test_fuzz_safe_slug(name: str) -> None:
    slug = safe_slug(name)
    assert isinstance(slug, str)
    assert slug != ""
    assert all(c.isalnum() or c == "_" for c in slug)


@settings(max_examples=200, deadline=None)
@given(
    lat=st.floats(min_value=-80.0, max_value=84.0, allow_nan=False, allow_infinity=False),
    lon=st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False),
)
def test_fuzz_latlon_to_utm_wgs84(lat: float, lon: float) -> None:
    epsg, zone, easting, northing = latlon_to_utm_wgs84(lat, lon)
    assert isinstance(epsg, int)
    assert epsg > 0
    assert isinstance(zone, str)
    assert math.isfinite(easting)
    assert math.isfinite(northing)


@settings(max_examples=50, deadline=None)
@given(data=st.dictionaries(keys=st.text(max_size=20), values=st.text(max_size=20), max_size=10))
def test_fuzz_is_atap_geojson(data: dict[str, str]) -> None:
    with tempfile.TemporaryDirectory() as td:
        test_file = Path(td) / "test.json"
        test_file.write_text(json.dumps(data), encoding="utf-8")
        result = is_atap_geojson(test_file)
        assert isinstance(result, bool)


def fuzz_target_one_input(data: bytes) -> None:
    """Entry point for Atheris fuzzing engine."""
    if not data:
        return
    text = data.decode("utf-8", errors="ignore")
    try:
        validate_xml_10_string(text)
    except ValueError:
        pass
    safe_slug(text)
