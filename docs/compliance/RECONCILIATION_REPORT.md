# ARCA — Upstream License Reconciliation Report

Generated (UTC): 2026-10-29T09:30:26+00:00

## Verified inputs
- All five upstream files exist and were checked against `UPSTREAM_FETCH_EVIDENCE.json`.
- Four tagged license text SHA-256 values match the originally captured reference digests.
- CesiumJS `ThirdParty.json` is parseable JSON and matches the local fetch evidence hash.
- 10 vendored frontend hashes match `third-party/MANIFEST.json`.

## Scope of changes
- Only notices, manifest, third-party reference README/status files, license register and this report/evidence are updated.
- No ARCA-owned `LICENSE`, Python/JS runtime, conversion engine, `uv.lock`, or upload/server endpoints modified.
- 12 existing register rows updated with tagged evidence; statuses remain `NEEDS_VERIFICATION`.

## Outstanding (not closed by this reconciliation)
- Confirm exact bundled JS/CSS/worker provenance and transitive notices for MapLibre, Deck.gl, Three.js.
- Verify Cesium notices correspond to the actual Cesium CDN distribution including assets/workers.
- Check exact native Python wheels on supported OS/platforms, and terms for map services and branding.
- Conduct human/legal final review; do not declare full compliance from document retrieval.

## Evidence inventory

| ID | File | SHA-256 |
|---|---|---|
| CESIUM-1.145 | `third-party/cesium/LICENSE.md` | `721844bc0cdaa9b1a9a145dbca1f981e2de15a7e200a5d1fd9f5f1eed8e5d030` |
| MAPLIBRE-v6.9.0 | `third-party/maplibre-gl/LICENSE.upstream-v6.9.0.txt` | `ee5fc05a0677eaf69601d2c7db0d9ecd6cc27c3abc1d0733bc9ed34707cf8ef2` |
| DECK-v9.3.7 | `third-party/deck.gl/LICENSE.upstream-v9.3.7` | `e499a2c2ba3b9faabe91fdfddf43e329439263264b7148e5548d0ec605cce9f2` |
| THREE-r185 | `third-party/three/LICENSE.upstream-r185` | `8b378ebe60e2fe500158cb0ac71cb5e8b7d92953c2abcc63a0eb90499653b5bc` |
| CESIUM-1.145-THIRDPARTY | `third-party/cesium/ThirdParty.json` | `cef3b6d1cfa17d53ba6d1dcd0005ca2b84d3ed8885e3ebfa346e836830acda39` |
