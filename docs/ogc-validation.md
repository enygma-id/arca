# ARCA OGC Standards Validation Report

**Date:** 2026-10-30  
**Source Commit SHA:** `cbf5406ea9f9f643179787f5bf4182f67347470e`  
**Environment:** macOS (Darwin arm64), Python 3.12.13  
**Recommendation:** `READY_FOR_HUMAN_RELEASE_REVIEW`  

---

## 1. Summary of Audit Gates

| Gate ID | Area | Status | Evidence Summary |
| :--- | :--- | :--- | :--- |
| **F-01** | XML 1.0 Safety (`citygml.py`) | **PASS** | Invalid XML 1.0 codepoints (U+0000, U+0001, isolated surrogates U+D800) rejected before file opening; valid non-ASCII UTF-8 preserved; round-trip test verified in `tests/test_citygml.py`. |
| **F-02** | CRS Truthfulness (`citygml.py`, `cityjson.py`) | **PASS** | Local Cartesian metric coordinates are no longer falsely tagged with `CRS84`. Unprojected/local coordinates emit clean GML without `srsName`, conforming to GML 3.1.1 optional SRS schema rules. |
| **F-03** | OGC Versioned Validation | **PASS** | Official `cjval 0.10.0` validates `building.city.json` with 0 errors and 0 warnings. Official OGC CityGML 2.0 XSD (`citygml-2_0_0.zip`, SHA-256 `bc716b2...`) validates `building.gml` for both projected and local variants. Negative tests confirmed. |
| **F-04** | Full Checks & Regressions | **PASS** | `ruff check .` (0 errors), `pytest` (43 passed), sample inspections for IFC & SKP passed, third-party manifest verified, `git diff --check` clean. |

---

## 2. Detailed Gate Findings & Implementation

### F-01 — XML 1.0 Safety
- **Defect:** `xml_escape` alone does not reject XML 1.0 illegal characters (e.g. NUL byte `\x00`, control characters `\x01`–`\x08`, `\x0B`–`\x0C`, `\x0E`–`\x1F`, and isolated surrogates `\uD800`–`\uDFFF`).
- **Policy Implemented:** Rejection before file creation via `validate_xml_10_string()` in `src/arca/engine/citygml.py`. If invalid characters are detected in `dataset` or `building_name`, a descriptive `ValueError` is raised immediately before `out_path` is opened.
- **Evidence:**
  - `tests/test_citygml.py::test_citygml_xml_10_safety_invalid_codepoints_rejected` PASSED.
  - `tests/test_citygml.py::test_citygml_xml_10_safety_valid_non_ascii_roundtrip` PASSED.

### F-02 — CRS Truthfulness
- **Defect:** Models with zero anchor and no georeference (`anchor_lat=0, anchor_lon=0, georef=None`) defaulted to `srsName="urn:ogc:def:crs:OGC:1.3:CRS84"`, falsely asserting geographic degrees for local Cartesian meters.
- **Policy Implemented:** When georeferencing is not available, `srs_name` remains `None`, and `srsName` attribute is omitted from `<gml:Envelope>` and `<gml:MultiSurface>`. GML 3.1.1 XSD permits optional `srsName`.
- **CityJSON Alignment:** Replaced non-standard `datasetTitle` with standard `title` in CityJSON 1.1 `metadata` object.
- **Evidence:**
  - `tests/test_citygml.py::test_citygml_crs_truthfulness_local_coordinates_no_false_crs84` PASSED.
  - `tests/test_citygml.py::test_citygml_crs_truthfulness_known_epsg_retained` PASSED.

### F-03 — Independent OGC Tool Validation
- **CityJSON 1.1 Validator:**
  - Binary: `cjval 0.10.0` (compiled with `--features="build-binary"`).
  - Command: `cjval --report building.city.json`
  - Result: `valid: true`, 0 errors across `json_syntax`, `schema`, `extensions`, `parents_children_consistency`, `wrong_vertex_index`, `semantics_arrays`, `textures`, and `materials`.
  - Negative validation: deliberate corruption of required `transform` property confirmed `valid: false`.
- **CityGML 2.0 XML Schema:**
  - Source: `https://schemas.opengis.net/citygml/citygml-2_0_0.zip`
  - SHA-256: `bc716b2578c16fde3de96587c8b0ff9302bb10ca244b384535a4bec4af587e62`
  - Schema File: `citygml/building/2.0/building.xsd`
  - Validator: `xmlschema 4.3.2` (W3C XSD 1.0 validator)
  - Result: Both projected (`EPSG:32750`) and local engineering variants validated `True`.
  - Negative validation: invalid schema element properly rejected as `False`.

---

## 3. Full Command Log (F-04)

```bash
# 1. Lint and code standards
$ uv run ruff check .
All checks passed!

# 2. Test suite
$ uv run pytest -q
...........................................                              [100%]
43 passed in 5.27s

# 3. Model inspections
$ uv run python -m arca inspect samples/arca-sample-area-01/data/arca_synthetic_mall_10f.ifc
{
  "format": "IFC",
  "name": null,
  "has_georef": true,
  "method": "ifc_map_conversion",
  "crs": "EPSG:32750",
  "longitude": 119.4151,
  "latitude": -5.1492599,
  ...
}

$ uv run python -m arca inspect samples/arca-sample-area-02/data/arca_synthetic_mall_10f.skp
{
  "building_count": 1,
  "crs": "EPSG:32750",
  "format": "SKP",
  "has_georef": true,
  ...
}

# 4. Third-party manifest verification
$ python3 -m json.tool third-party/MANIFEST.json >/dev/null
(exit 0)

# 5. Git whitespace and conflict marker check
$ git diff --check
(clean, no output)

# 6. Independent OGC validation runner
$ uv run python tools/validation/validate_ogc_outputs.py
ALL OGC VALIDATION GATES PASSED.
```

---

## 4. Residual Risks & Scope Limitations

1. **Geometry Solid Semantics:** Neither XSD nor `cjval` guarantees 2-manifold water-tightness of 3D solids. ARCA exports semantic surface boundaries (`MultiSurface` LOD 2.0); client-side GIS platforms must triangulate or extrude per local rendering capabilities.
2. **Offline Schema Caching:** Full OGC schema validation requires downloading the pinned `citygml-2_0_0.zip` (466 KB) or using cached schemas in `.cache/ogc_schemas/`.
3. **No Speculative Certification:** Outputs comply with OGC CityJSON 1.1 and CityGML 2.0 schemas; this validation does not imply OGC CITE/ETS badge or formal consortium certification.

---

## 5. Final Recommendation

`READY_FOR_HUMAN_RELEASE_REVIEW`
