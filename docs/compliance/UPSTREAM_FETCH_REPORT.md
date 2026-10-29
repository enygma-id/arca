# ARCA upstream license document retrieval

Date (UTC): 2026-10-29T09:15:22.586314+00:00

**This is evidence of source retrieval, not proof of complete legal compliance.**

| Component | Version | Status | Destination | SHA-256 |
|---|---|---|---|---|
| CesiumJS | 1.145 | FETCHED_TAGGED_SOURCE | `third-party/cesium/LICENSE.md` | `721844bc0cdaa9b1a9a145dbca1f981e2de15a7e200a5d1fd9f5f1eed8e5d030` |
| MapLibre GL JS | v6.9.0 | FETCHED_TAGGED_SOURCE | `third-party/maplibre-gl/LICENSE.upstream-v6.9.0.txt` | `ee5fc05a0677eaf69601d2c7db0d9ecd6cc27c3abc1d0733bc9ed34707cf8ef2` |
| Deck.gl | v9.3.7 | FETCHED_TAGGED_SOURCE | `third-party/deck.gl/LICENSE.upstream-v9.3.7` | `e499a2c2ba3b9faabe91fdfddf43e329439263264b7148e5548d0ec605cce9f2` |
| Three.js | r185 = 0.185.0 | FETCHED_TAGGED_SOURCE | `third-party/three/LICENSE.upstream-r185` | `8b378ebe60e2fe500158cb0ac71cb5e8b7d92953c2abcc63a0eb90499653b5bc` |
| CesiumJS third-party bundle inventory | 1.145 | FETCHED_TAGGED_SOURCE | `third-party/cesium/ThirdParty.json` | `cef3b6d1cfa17d53ba6d1dcd0005ca2b84d3ed8885e3ebfa346e836830acda39` |

## Remaining human/administrative checks
- Verify Cesium 1.145 license and notices correspond to the remote Cesium distribution.
- Confirm MapLibre full tagged LICENSE text governs the exact vendored JS/CSS/worker files.
- Reconcile Deck.gl bundled source/modules; root MIT license is not proof for all transitive modules.
- Inspect Python-native wheels on actual target platforms separately.
- Do NOT change the root AGPL-3.0-only LICENSE or treat these texts as Enygma-owned.
- Do NOT publish a declaration of complete compliance without human approval.

## Version-specific official sources

- CESIUM-1.145: https://raw.githubusercontent.com/CesiumGS/cesium/1.145/LICENSE.md
- MAPLIBRE-v6.9.0: https://raw.githubusercontent.com/maplibre/maplibre-gl-js/v6.9.0/LICENSE.txt
- DECK-v9.3.7: https://raw.githubusercontent.com/visgl/deck.gl/v9.3.7/LICENSE
- THREE-r185: https://raw.githubusercontent.com/mrdoob/three.js/r185/LICENSE
- CESIUM-1.145-THIRDPARTY: https://raw.githubusercontent.com/CesiumGS/cesium/1.145/ThirdParty.json
