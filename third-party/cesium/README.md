# CesiumJS — Third-party runtime used by ARCA

- Observed exact runtime version: **1.145**.
- Delivery: **remote Cesium CDN**, not bundled in the ARCA ZIP.
- Usage: both `src/arca/server/static/index.html` and `src/arca/server/static/viewer/viewer.html` load the remote JS/CSS and configure its assets/workers base URL.
- Official release: https://github.com/CesiumGS/cesium/releases/tag/1.145
- Tag reference: https://github.com/CesiumGS/cesium/tree/1.145
- Main project license basis: Apache License 2.0.
- **Status:** `NEEDS_VERIFICATION` for complete **version 1.145** upstream `LICENSE.md`, possible bundled `ThirdParty` notices, asset/workers/worker dependencies and exact remote distribution obligations.

This file documents the newly discovered dependency. **It is not the Cesium license text, and it does not certify that notice requirements have been fulfilled.** Obtain the official release documents before changing this status. Do not vendor Cesium or change the existing CDN URLs as part of this administrative overlay.

See `docs/compliance/UPSTREAM_LICENSE_FETCH.md` for the pending source-fetch steps.
