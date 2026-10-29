# Administrative Licensing Overlay Changelog — 2026-10-29

Baseline: `arca-main(1).zip` (same bytes as `arca-main.zip` provided in this session).

**Replaced file paths:**
1. `/THIRD_PARTY_NOTICES.md` — retain prior notices and add CDN Cesium, incomplete upstream caveats, explicit Python-native and map service terms.
2. `/third-party/MANIFEST.json` — retain pre-existing inventory and augment observed runtime dependencies and locally measured vendor hash inventory.
3. `/third-party/README.md` — align summary with actual frontend/runtime paths and release evidence status.

**New file paths:**
- `/third-party/cesium/README.md`
- `/third-party/maplibre-gl/UPSTREAM_NOTICES_STATUS.md`
- `/third-party/deck.gl/UPSTREAM_NOTICES_STATUS.md`
- `/docs/compliance/*` — administrative register, human checklists, policy and programmer handoff.

**Explicitly not changed:** `/LICENSE`, `/CLA.md`, any Python/JS/HTML/CSS files, `uv.lock`, original third-party license texts, data samples, or assets. The overlay is not a silent legal approval or an end-to-end platform extension.
