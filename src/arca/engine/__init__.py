# SPDX-License-Identifier: AGPL-3.0-only
"""ARCA BIM2GIS Engine - Geodesic & topological transformation pipeline."""

from arca.engine.georef import (
    GeoreferenceContext,
    compound_angle_to_degrees,
    degrees_to_compound_dms,
    extract_crs_epsg,
    extract_length_unit,
    find_metadata_json,
    latlon_to_utm_wgs84,
    local_to_lonlat,
    parse_metadata_json,
    resolve_georeferencing,
    ring_geo,
    unit_factor_to_m,
    utm_to_latlon_wgs84,
)
from arca.engine.glb import GLBWriter
from arca.engine.lod import (
    PlanarUnionAccumulator,
    write_envelope,
    write_lod13_from_plateaus,
)
from arca.engine.pipeline import (
    build_parser,
    discover_bim_files,
    inspect_model_file,
    main,
    preprocess,
    process_one,
    sync_latest_viewer,
)
from arca.engine.skp import (
    convert_skp_to_georef_ifc,
    detect_input_format,
    extract_skp_georeference,
    inject_georeference_into_step,
    restore_skp_orientation_for_ifc,
)
from arca.engine.step import load_ifc
from arca.engine.utils import (
    clean_previous_outputs,
    safe_slug,
    sha256_file,
    write_json,
    write_json_compact,
)

__all__ = [
    "GeoreferenceContext",
    "compound_angle_to_degrees",
    "degrees_to_compound_dms",
    "extract_crs_epsg",
    "extract_length_unit",
    "find_metadata_json",
    "latlon_to_utm_wgs84",
    "local_to_lonlat",
    "parse_metadata_json",
    "resolve_georeferencing",
    "ring_geo",
    "unit_factor_to_m",
    "utm_to_latlon_wgs84",
    "GLBWriter",
    "PlanarUnionAccumulator",
    "write_envelope",
    "write_lod13_from_plateaus",
    "build_parser",
    "discover_bim_files",
    "inspect_model_file",
    "main",
    "preprocess",
    "process_one",
    "sync_latest_viewer",
    "convert_skp_to_georef_ifc",
    "detect_input_format",
    "extract_skp_georeference",
    "inject_georeference_into_step",
    "restore_skp_orientation_for_ifc",
    "load_ifc",
    "clean_previous_outputs",
    "safe_slug",
    "sha256_file",
    "write_json",
    "write_json_compact",
]
