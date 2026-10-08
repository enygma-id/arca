# Changelog

All notable project changes should be documented here.

## [Unreleased]

### Added

- 3D planar triangulation using Newell normal and Shapely constrained Delaunay triangulation to avoid vertex stretching/distortion on concave and multi-vertex faces in GLB export.
- Granular progress reporting with dynamic sub-step percentages (`pct`), live elapsed timer (`mm:ss`), and animated shimmer progress bar in Web Studio to eliminate perceived freeze during heavy SketchUp/IFC geometry processing.
- Companion Metadata JSON auto-discovery and priority resolution (`CLI > Metadata JSON > Internal Model > Fallback`) for IFC and SKP, with CLI flag `--metadata` and Web Studio UI toggle.
- Metadata JSON defaults `unit` to `auto` when omitted, preventing unwanted unit forcing during model conversion.
- Building-name-based export filenames for GeoJSON and GLB downloads.
- MapLibre GL JS 3D GLB rendering support via custom Three.js WebGL layer alongside Deck.gl and CesiumJS.
- Sample datasets organized under `samples/arca-sample-area-01/` (IFC) and `samples/arca-sample-area-02/` (SKP) with dataset documentation, CC BY 4.0 data licensing, and SHA-256 integrity manifests.
- Comprehensive 3D Web Viewer Integration Guide (`docs/viewer-guide.md`) detailing standalone implementations for MapLibre GL JS, Deck.gl, and CesiumJS.
- GitHub Actions continuous integration workflow (`.github/workflows/ci.yml`) testing across Ubuntu, Windows, and macOS on Python 3.10 and 3.12 with uv and pip.
- GitHub issue templates (`.github/ISSUE_TEMPLATE/`) for bug reports, research proposals, and blank issue configuration.
- Repository `.gitattributes` for line-ending normalization (LF) and explicit binary asset tracking.

### Fixed

- SKP model unit inspection returns `auto` so intermediate millimeter-scaled IFC export is properly converted to meters without 1000x scale blowup.

## [0.2.0] - 2026-09-18

### Added

- Core BIM-to-GIS transformation engine supporting IFC (STEP ISO-10303-21) and SketchUp (.skp) inputs.
- buildingSMART IFC4 Georeferencing parser (`IfcProjectedCRS`, `IfcMapConversion`, `IfcSite`).
- Karney (2011) high-precision transverse Mercator geodesic projection with sub-millimeter precision (< 0.02 mm).
- OGC CityGML LOD 1.3 multi-storey plateau extraction and Pure GeoJSON generation.
- Topocentric East-North-Up (ENU) matrix transformations for 3D glTF/GLB generation.
- Interactive Web Studio with unified Converter and 3D Viewer tabs (`arca serve`).
- CLI subcommands: `arca serve`, `arca run`, `arca inspect`.
- Test suite with geodesic projection, CLI verification, and format detection.

## [0.1.0] - 2026-03-28

### Added

- founding project identity;
- governance and licensing model;
- Community / Enterprise structure;
- human-centered AI usage policy;
- GIS-native design principles;
- representation-profile terminology;
- known-limitations policy;
- third-party license provenance;
- research and benchmark methodology foundation.

The first public code commit will consolidate the existing prototype workflow
into the initial ARCA software package.
