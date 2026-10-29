# Third-Party Software Notices

**ARCA Community — license inventory update, 29 October 2026.**

ARCA-owned Community source remains licensed under `AGPL-3.0-only` (see [LICENSE](./LICENSE)).
Third-party code, native libraries, sample data and external services retain their independent terms. No Enygma Community or future Enterprise grant relicenses software or data owned by third parties.

> **Release evidence status:** This document is an accurate inventory of observed baseline integrations and known notices, **not a certification that every exact-version notice obligation is already satisfied**. Entries explicitly marked `NEEDS_VERIFICATION` must be reconciled with exact package/release artifacts before claiming a completed licensing review. See [`docs/compliance/RELEASE_LICENSE_GATES.md`](./docs/compliance/RELEASE_LICENSE_GATES.md).

## Frontend and runtime dependencies

| Component | Observed version | Delivery in baseline | Upstream license family | Local material / action |
|---|---|---|---|---|
| **CesiumJS** | **1.145** | CDN script, CSS and Cesium assets invoked by Studio and viewer | Apache-2.0; release-specific third-party notices | Fetched upstream [`LICENSE.md`](./third-party/cesium/LICENSE.md) and [`ThirdParty.json`](./third-party/cesium/ThirdParty.json); exact CDN build and notice completeness still `NEEDS_VERIFICATION`. |
| **Deck.gl** | **9.3.7** | Local minified bundle plus remote unpkg fallback | MIT root; bundled transitive components to verify | Fetched [`v9.3.7 LICENSE`](./third-party/deck.gl/LICENSE.upstream-v9.3.7); attribution and license composition of the shipped bundle still `NEEDS_VERIFICATION`. |
| **MapLibre GL JS** | **6.9.0** | Local MJS, worker, shared module and CSS | BSD-3-Clause with inherited component notices | Fetched full [`v6.9.0 LICENSE.txt`](./third-party/maplibre-gl/LICENSE.upstream-v6.9.0.txt), including upstream-origin attribution; vendored build provenance remains `NEEDS_VERIFICATION`. |
| **Three.js** | **0.185.0 (r185)** | Local Three core, module and addons | MIT | Fetched tagged [`r185 LICENSE`](./third-party/three/LICENSE.upstream-r185); exact vendored-file origin still requires comparison. |

**Cesium entrypoints (not vendored):**
`src/arca/server/static/index.html` and `src/arca/server/static/viewer/viewer.html` reference
`https://cesium.com/downloads/cesiumjs/releases/1.145/Build/Cesium/`.
Both entrypoints also contain a Deck.gl 9.3.7 CDN fallback. CDN delivery does not establish completeness of application redistribution notices.

**Local vendored files:** `src/arca/server/static/vendor/`. SHA-256 fingerprints of all 10 observed files are recorded in [`third-party/MANIFEST.json`](./third-party/MANIFEST.json); they establish baseline integrity only, **not** equivalence to an official upstream published bundle.

## Python runtime, transitive dependencies and native code

| Component | Role | Licensing basis | Existing license path / release limitation |
|---|---|---|---|
| OpenSKP | SKP ingestion/IFC export | MIT | [`third-party/openskp/LICENSE`](./third-party/openskp/LICENSE); founding snapshot targets 1.2.x |
| NumPy | Numerical operations | BSD-3-Clause plus possible binary notices | [`third-party/numpy/LICENSE.txt`](./third-party/numpy/LICENSE.txt); reference snapshot 2.3.5 **does not cover every wheel in `uv.lock`** |
| Shapely | Polygon processing | BSD-3-Clause | [`third-party/shapely/LICENSE.txt`](./third-party/shapely/LICENSE.txt); native GEOS may be included |
| GEOS | Native geometry engine associated with Shapely builds | LGPL-2.1 basis recorded in reference bundle | [`third-party/shapely/LICENSE_GEOS`](./third-party/shapely/LICENSE_GEOS); verify distributed binary and LGPL obligations per platform |
| pyproj / PROJ | Coordinate reference transforms | MIT / PROJ terms | [`third-party/pyproj/LICENSE`](./third-party/pyproj/LICENSE) and [`LICENSE_proj`](./third-party/pyproj/LICENSE_proj); data/binary dependencies vary by wheel |
| Trimesh | Transitive OpenSKP dependency | MIT | [`third-party/trimesh/LICENSE`](./third-party/trimesh/LICENSE); reference snapshot is not a lock pin |

The actual `uv.lock` contains conditionally resolved versions for different Python environments. Do not interpret one founding license snapshot as evidence for every Windows, Linux and macOS wheel. Bundled native elements such as OpenBLAS, libgfortran and libquadmath are **artifact-dependent**, and their applicable terms must be preserved where distributed. The locked/build-time/dev dependency graph is tracked in the administrative register, not all automatically shipped with ARCA.

## Samples, assets, map services and standards

- **Sample Area 01 / 02:** separate `samples/*/LICENSE-DATA.md` declares CC BY 4.0 for the synthetic datasets; data license does not relicense the ARCA engine or trademarks. Sample hashes are covered by `samples/*/MANIFEST.sha256`.
- **Enygma/ARCA branding:** source ownership is declared by Enygma, with optional internal provenance evidence; the source license does not automatically authorize third-party brand impersonation or trademark use.
- **OpenStreetMap:** underlying OSM data is distinct from the `tile.openstreetmap.org` server terms. Respect provider attribution, cache directives, service restrictions and any applicable data license. Official guidance: https://operations.osmfoundation.org/policies/tiles/ .
- **BIG Rupabumi Indonesia:** official raster service at `geoservices.big.go.id` is third-party map imagery. Preserve provider credit. Public access **does not by itself grant mirroring, bulk download or republication rights**. Service reference: https://geoservices.big.go.id/rbi/rest/services/BASEMAP/Rupabumi_Indonesia/MapServer .
- **IFC4 / GeoJSON:** format standards, not dependency license grants; see `third-party/standards/`.

For the detailed separation of *viewer tile access* from *redistribution rights*, see [`docs/compliance/MAP_DATA_POLICY.md`](./docs/compliance/MAP_DATA_POLICY.md).

## Sources and outstanding legal evidence

- Cesium 1.145: https://github.com/CesiumGS/cesium/releases/tag/1.145 and https://github.com/CesiumGS/cesium/tree/1.145
- Deck.gl 9.3.7: https://github.com/visgl/deck.gl/releases/tag/v9.3.7
- MapLibre GL JS 6.9.0: https://github.com/maplibre/maplibre-gl-js/releases/tag/v6.9.0
- Three.js r185: https://github.com/mrdoob/three.js/releases/tag/r185

**Tagged upstream legal texts and Cesium ThirdParty.json are now archived in `third-party/`**, with SHA-256 in `third-party/MANIFEST.json` and retrieval evidence in `docs/compliance/UPSTREAM_FETCH_EVIDENCE.json`. This is documentary evidence, not completion of bundled-module attribution, Python-native wheel licensing, service terms, or legal review. See [`docs/compliance/RECONCILIATION_REPORT.md`](./docs/compliance/RECONCILIATION_REPORT.md).

## Enterprise licensing boundary

Commercial rights in ARCA-owned code may be granted by PT Enygma Solusi Negeri only to the extent it holds sufficient rights; upstream third-party terms remain in force for any components included in either edition. `CLA.md` remains expressly **draft for legal review**; no contribution agreement is deemed executed by this notice. For internal counsel review see `docs/compliance/CLA_LEGAL_REVIEW_CHECKLIST.md`.
