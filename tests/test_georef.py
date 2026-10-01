# SPDX-License-Identifier: AGPL-3.0-only
from arca.engine import (
    compound_angle_to_degrees,
    degrees_to_compound_dms,
    latlon_to_utm_wgs84,
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
