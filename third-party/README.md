# Third-Party License Provenance — ARCA Community

ARCA-owned code: [`AGPL-3.0-only`](../LICENSE). Third-party licenses are independent.
The manifest [`MANIFEST.json`](./MANIFEST.json) enumerates **observed** library versions and vendor-file hashes; it is not proof of completed binary or upstream release attribution.

## Inventory

| Component | Use / delivery | Local evidence | Review status |
|---|---|---|---|
| CesiumJS 1.145 | Remote browser CDN, two entrypoints | [`cesium/README.md`](./cesium/README.md) | Exact release notices outstanding |
| Deck.gl 9.3.7 | Local bundle + remote fallback | [`deck.gl/LICENSE`](./deck.gl/LICENSE), [`deck.gl/UPSTREAM_NOTICES_STATUS.md`](./deck.gl/UPSTREAM_NOTICES_STATUS.md) | Bundle notice map outstanding |
| MapLibre 6.9.0 | Local modules / worker / CSS | [`maplibre-gl/LICENSE`](./maplibre-gl/LICENSE), [`maplibre-gl/UPSTREAM_NOTICES_STATUS.md`](./maplibre-gl/UPSTREAM_NOTICES_STATUS.md) | Full tagged license outstanding |
| Three.js r185 | Local module/core/addons | [`three/LICENSE`](./three/LICENSE) | License basis captured; file provenance needs mapping |
| OpenSKP | Python runtime | [`openskp/LICENSE`](./openskp/LICENSE) | Reference 1.2.x; verify installed version |
| NumPy | Python runtime + optional native binary | [`numpy/LICENSE.txt`](./numpy/LICENSE.txt) | Reference snapshot not all wheel versions |
| Shapely / GEOS | Python / native | [`shapely/LICENSE.txt`](./shapely/LICENSE.txt), [`LICENSE_GEOS`](./shapely/LICENSE_GEOS) | Binary-dependent LGPL requirements |
| pyproj / PROJ | Python / native | [`pyproj/LICENSE`](./pyproj/LICENSE), [`LICENSE_proj`](./pyproj/LICENSE_proj) | Exact wheel/data terms by platform |
| Trimesh | Transitive | [`trimesh/LICENSE`](./trimesh/LICENSE) | Reference version only |

## Founding reference versions versus releases

The previously recorded versions (OpenSKP 1.2.x, NumPy 2.3.5, Shapely 2.1.2, pyproj 3.7.2, Trimesh 4.11.1) are not enforced pins. The authoritative runtime dependency set is resolved from `uv.lock`/packaged artifacts on the actual platform. Keep upstream license files and native dependency notices that apply to **that artifact**.

## What to do before tagging a release

1. Review `docs/compliance/RELEASE_LICENSE_GATES.md` and `docs/compliance/UPSTREAM_LICENSE_FETCH.md`.
2. Obtain authoritative version-exact source license texts and `NOTICE`/third-party attribution files; archive SHA-256 and tagged upstream source URLs.
3. For Linux/macOS/Windows builds, reconcile vendored frontend hashes plus Python wheel content.
4. Resolve legal unknowns with designated human approver. Do **not** change `LICENSE`, engine code, or enterprise features as a substitute for license evidence.

See the updated root [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md) for the public-facing inventory and the limitations of this review.
