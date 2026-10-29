# Upstream legal texts — exact-version retrieval checklist

**Human/administrative evidence step.** This overlay does not include upstream legal texts it could not download and independently verify. The commands below are examples to run on a network-connected trusted workstation **after checking version/tag URLs**. Never claim retrieval occurred because this document exists. Do not alter `LICENSE` or existing vendor binaries in this step.

From the **repository root**, prepare a temporary evidence directory outside the tracked source tree:

```bash
mkdir -p /tmp/arca-license-evidence
curl -fL --retry 2 'https://raw.githubusercontent.com/maplibre/maplibre-gl-js/v6.9.0/LICENSE.txt' -o /tmp/arca-license-evidence/maplibre-v6.9.0-LICENSE.txt
curl -fL --retry 2 'https://raw.githubusercontent.com/CesiumGS/cesium/1.145/LICENSE.md' -o /tmp/arca-license-evidence/cesium-1.145-LICENSE.md
curl -fL --retry 2 'https://raw.githubusercontent.com/mrdoob/three.js/r185/LICENSE' -o /tmp/arca-license-evidence/three-r185-LICENSE
curl -fL --retry 2 'https://raw.githubusercontent.com/visgl/deck.gl/v9.3.7/LICENSE' -o /tmp/arca-license-evidence/deck-gl-v9.3.7-LICENSE
shasum -a 256 /tmp/arca-license-evidence/*
```

**Important:** these are intended paths inferred from official release tags, **not successful-download attestations**. If a path returns 404, inspect the tagged repository/package distribution to locate the authoritative file—do not substitute a license from `main` silently. Cesium may have third-party notices nested inside `LICENSE.md` and package directories. Deck.gl may distribute component licenses in individual packages; inspect the released tarball and shipped `dist.min.js`, not only repository root LICENSE.

For the exact artifact actually released, preserve relevant complete license/NOTICE texts, source URLs, date, SHA-256, and upstream tag. Copy or replace license files in the repository only after a reviewer verifies completeness and gives approval.

For Python platforms, inspect and save licenses inside **resolved wheels actually shipped**, especially Shapely/GEOS, pyproj/PROJ, NumPy/BLAS/libgfortran/libquadmath, and the dependencies implied by extras. A founding snapshot alone is insufficient.
