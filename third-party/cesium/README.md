# CesiumJS 1.145 — license evidence (CDN runtime)

- ARCA loads CesiumJS through `https://cesium.com/downloads/cesiumjs/releases/1.145/Build/Cesium/` in two HTML entrypoints.
- [Exact tagged `LICENSE.md`](./LICENSE.md) and [exact tagged `ThirdParty.json`](./ThirdParty.json) were captured by ARCA's upstream fetch tool.
- Exact SHA-256 and original source URLs are recorded in [`third-party/MANIFEST.json`](../MANIFEST.json) and `docs/compliance/UPSTREAM_FETCH_EVIDENCE.json`.
- **Status: `NEEDS_VERIFICATION` for legal attribution coverage of the actual remote Cesium CDN build**. The tagged source-file list is not automatically proof of the compiled distributable's complete obligations.
- Cesium binary is not vendored by ARCA in this snapshot. Do not add full Cesium assets or change runtime paths as part of licensing reconciliation.
- Final human/legal review remains required. Root ARCA `AGPL-3.0-only` is unchanged.
