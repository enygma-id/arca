# ARCA — Upstream license documents (version-specific)

## Scope

This additional overlay **does not replace the previous licensing overlay**. It adds a one-step retrieval utility; original ZIP, core code, UI, root AGPL `LICENSE`, `uv.lock`, and vendor binaries are untouched.

Direct upstream license downloads could not be completed in the artifact-generation environment (network resolution/download restrictions). This bundle therefore **does not pretend that upstream legal files are already present**. It downloads original byte-for-byte upstream files directly to their intended repository folders on a network-connected Mac. No synthetic/reconstructed license text is provided.

## Instructions (macOS)

1. Extract the overlay ZIP.
2. Copy **its contents**, retaining relative folders, into the root of your local ARCA clone. Do not drag the entire outer ZIP folder into the repository.
3. From Finder, use right-click → Open on `FETCH_UPSTREAM_LICENSES_MAC.command`. If Gatekeeper blocks an unsigned local script, open Terminal at the repo root and use `bash FETCH_UPSTREAM_LICENSES_MAC.command`. No admin/sudo required.
4. Review `docs/compliance/UPSTREAM_FETCH_REPORT.md` and `docs/compliance/UPSTREAM_FETCH_EVIDENCE.json` for success status, original source URLs, SHA-256, and any missing evidence.
5. Check GitHub Desktop changes. Only commit verified license copies; note that this is not final legal approval.

## Files downloaded to ARCA root relative paths

| Exact upstream component | File path (after download) | Source |
|---|---|---|
| CesiumJS 1.145 | `third-party/cesium/LICENSE.md` | `CesiumGS/cesium` Git tag `1.145` |
| MapLibre GL JS v6.9.0 | `third-party/maplibre-gl/LICENSE.upstream-v6.9.0.txt` | `maplibre/maplibre-gl-js` Git tag `v6.9.0` |
| Deck.gl v9.3.7 | `third-party/deck.gl/LICENSE.upstream-v9.3.7` | `visgl/deck.gl` Git tag `v9.3.7` |
| Three.js r185 | `third-party/three/LICENSE.upstream-r185` | `mrdoob/three.js` Git tag `r185` |
| CesiumJS 1.145 optional bundle-specific notices | `third-party/cesium/ThirdParty.json` | Exact npm release distribution when available; optional, may return 404 |

**Do not delete the older `third-party/maplibre-gl/LICENSE`, `third-party/deck.gl/LICENSE`, or `third-party/three/LICENSE` blindly.** They remain historical snapshots. The new upstream-tagged files can be reviewed and reconciled before any curated license replacement. If tagged URLs unexpectedly change or fail, the utility records `NEEDS_VERIFICATION` and preserves existing files.

## Verification and release limits

- The utility checks known legal text signatures, minimal length, JSON syntax where appropriate, and captures SHA-256 with tagged URLs. **This proves retrieval only**, not exact JS bundle provenance or a complete native binary compliance assessment.
- The Cesium file embeds substantial third-party notice content; the optional distribution `ThirdParty.json` requires separate inspection if present. The runtime is still loaded from CDN, not shipped in this overlay.
- The Deck.gl root MIT license should not be simplistically read as covering every transitive library in the prebuilt `dist.min.js`.
- The previous overlay's `third-party/MANIFEST.json` and `THIRD_PARTY_NOTICES.md` **are not automatically marked compliant**; a reviewer should update document links and status based on the evidence report.
- Preserve Enygma's AGPL-3.0-only Community licensing and dual-license business strategy. The archive adds no product features.
