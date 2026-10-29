# Exact post-approval edit sequence for Programmer — ARCA Community

**STATUS: ADMINISTRATIVE HANDOFF — DO NOT APPLY UNTIL LICENSE TEXTS VERIFIED AND HUMAN APPROVAL RECORDED.**

The following is an actionable file-by-file change order, not an instruction to modify conversion behavior, API, viewer UX, or release license. Match paths against the ZIP baseline. Use isolated commits/PRs to keep legal changes reviewable. Any missing external text is `NEEDS_VERIFICATION`; do not improvise.

## Gate 0 — frozen baseline

1. Obtain approved copies of `THIRD_PARTY_NOTICES.proposed.md`, `third-party/MANIFEST.proposed.json`, and complete exact-version license files from Administrative/Legal. If any mandatory legal file is missing, open a blocking issue instead of making up a placeholder as final.
2. Check `git diff -- LICENSE NOTICE.md COPYRIGHT.md ENTERPRISE.md`; none of these may be silently rewritten. `LICENSE` must remain ARCA-owned `AGPL-3.0-only`.
3. Record GitHub commit and `sha256sum` of every vendored release JS/CSS asset; the ZIP review was `SNAPSHOT_ONLY`.

## Step 1 — CesiumJS 1.145 remote runtime (LIC-01)

**Do not touch JS/CSS runtime imports unless a separate, authorized engineering issue requires it.**

1. In `src/arca/server/static/index.html` inspect lines **21, 24, 28** and in `src/arca/server/static/viewer/viewer.html` inspect **20, 25, 29**. The runtime is CesiumJS 1.145 via the official remote CDN; preserve this delivery classification.
2. In root `THIRD_PARTY_NOTICES.md`, add one explicit row identifying `CesiumJS`, `1.145`, `Apache-2.0`, `remote runtime/CDN JS/CSS/workers`, source tag link `https://github.com/CesiumGS/cesium/releases/tag/1.145`, and release-exact official license notice location. Do not state it is bundled locally.
3. In `third-party/MANIFEST.json`, add one `frontend_vendor_dependencies.cesiumjs` entry with version, deployment mode, upstream URI, original release license file path, review date, and evidence. `sha256` must be `null` or explicitly absent for CDN bytes not captured as release artefact; never fabricate checksum.
4. Only after receipt of complete official Cesium 1.145 LICENSE/ThirdParty texts and permission to redistribute those legal notices, preserve them unaltered under a reviewed `third-party/cesiumjs/` directory (or in final notices, per counsel). Existing root manifest `files` should list newly archived files if present.
5. Validate with `grep -R -n 'CesiumJS\|1.145' THIRD_PARTY_NOTICES.md third-party/MANIFEST.json`; manually check the license content and attribution chain.

## Step 2 — MapLibre GL JS v6.9.0 full legal notice (LIC-02)

1. Compare `third-party/maplibre-gl/LICENSE` (1,529-byte abbreviated local text) against the `v6.9.0` release's **complete** tagged `LICENSE.txt`.
2. Obtain and preserve the exact full notice including any inherited Mapbox GL JS v1.x, glfx.js, d3-color, or other components **if present in v6.9.0**. Do not use current `main` verbatim without version comparison.
3. Replace or supplement the existing abbreviated file only with the approved tagged full legal text; link it from root `THIRD_PARTY_NOTICES.md` and `third-party/MANIFEST.json`.
4. Recompute checksum(s) for legal files and record release asset identity. Do not change `maplibre-gl-6.9.0.mjs`, shared module, CSS, or worker as part of notice remediation.
5. Confirm the upstream legacy notices and disclaimer are preserved using exact official text, not a synthetic summary.

## Step 3 — Deck.gl 9.3.7 source/bundle classification (LIC-03)

1. Cross-check `src/arca/server/static/vendor/deck.gl-9.3.7.min.js` against the official **version 9.3.7** tarball/distribution; record bundle bytes, original source URL and legal contents.
2. Inspect `third-party/deck.gl/LICENSE` (currently a combined “Apache License, Version 2.0 / MIT License” document) against the actual bundle. Classify core MIT and any Apache submodule at the exact file/bundled-component level. Do not claim both apply to the entire bundle without proof.
3. Archive full valid legal text(s); revise public notice to state **which** component/license applies and link file-specific upstream evidence.
4. Document conditional unpkg fallback in both HTML pages (`index.html:27`, `viewer/viewer.html:28`) as **remote runtime**, not local vendor distribution.
5. No feature or CDN fallback changes in this licensing PR; if removal of CDN is desirable for independent reliability reasons, separate engineering issue.

## Step 4 — Three.js r185 (LIC-04)

1. Verify upstream tag `r185` official `LICENSE` and validate the locally recorded `third-party/three/LICENSE` against that text.
2. For each of the physical Three assets (`three.core.js`, `three-0.185.0.module.js`, `utils/SkeletonUtils.js`, `utils/BufferGeometryUtils.js`, `three-addons/GLTFLoader.js`) document its origin/tag, whether locally patched, and expected exact source hash if obtainable.
3. Preserve upstream MIT notice; do not remove bundled copyright/header lines or assume all addons have exactly the same source provenance without checking.
4. Update manifest artifact entries without changing Three imports, GLB transforms, or full-detail viewer logic.

## Step 5 — Python/native release distribution (LIC-05)

1. For each **supported** OS/Python combination, generate a clean resolved dependency inventory from `uv.lock`. Its variants include NumPy 2.2.6/2.4.6/2.5.3, pyproj 3.7.1/3.7.2/3.8.0, and Trimesh 5.1.0. Do not mark all version variants as simultaneously installed.
2. Locate each **actually shipped** wheel/sdist, inspect `*.dist-info/METADATA`, `RECORD`, `LICENSE*`, `NOTICE*`, binaries (`.so`, `.dylib`, `.dll`) and runtime data. Store checksums and component license text in release evidence/SBOM.
3. Identify Shapely GEOS LGPL-2.1 and whether binary is bundled. For wheels with NumPy native dependencies, check actual OpenBLAS/libgfortran/libquadmath presence, not assumptions based on founding snapshots. Similarly inspect pyproj/PROJ data licenses.
4. Have Administrative/Legal approve release-specific native obligations, especially corresponding source/relink options where LGPL applies, before distributing a bundled binary package.
5. Add release-specific generated license bundle/report into release process, not into the conversion core; do not pin/unpin dependencies without separate approved engineering change.

## Step 6 — Map attribution QA (LIC-07)

1. In `src/arca/server/static/viewer/app.js`, verify provider strings at approximately 1066–1084 and attribution control at 1742–1752; code line numbers may drift.
2. Run viewer manually with each offered engine at mobile and desktop sizes. Confirm OSM credit visible with OSM; BIG credit visible with BIG. The `attributionControl:false` MapLibre configuration is followed by custom `AttributionControl`; do not 'fix' solely based on first keyword.
3. Capture evidence screenshots for both basemaps, and ensure no hidden attribution due to overlays/popups. If a real visibility bug is observed, log a narrowly scoped UI bug fix for approval.
4. Do not enable tile prefetch, tile archiving, proxy, or rehosting. BIG redistribution rights remain a legal review issue, not a technical permission inferred from HTTP success.

## Step 7 — Samples and images (LIC-06)

1. Keep `samples/*/LICENSE-DATA.md` alongside sample files and manifests; rerun SHA-256 check after packaging.
2. Retain icon/logo files; archive original Enygma design/source files internally when supplied. For any third-party asset revealed, obtain its actual license and add notice, subject to human legal approval.
3. No inference that all copyright/brand rights are transferable solely from existing Git visibility.

## Step 8 — CLA and legal sign-off (LIC-08/09)

1. Leave `CLA.md` marked `Draft for legal review` until counsel supplies final legally adopted text. Do not create a fake signature record or invent contributor assent.
2. Only after legal approval, merge reviewed `THIRD_PARTY_NOTICES.md`, `third-party/MANIFEST.json`, selected full license files, and accompanying documentation; keep AGPL root unchanged.
3. Rerun checks: `python -m json.tool third-party/MANIFEST.json`, `sha256sum` on vendored files, sample manifest validation, `git diff --check`, repository CI and packaging checks.
4. In the PR description attach the final license register, evidence links, exact changes, outstanding `NEEDS_VERIFICATION` items and signed human decision. **No agent may declare legal certification.**

## Scope acceptance

- No code in `src/arca/engine/` changed.
- No Community license change.
- No viewer core refactor, Drop Anything change, authentication, project management, or Enterprise API work.
- Changed third-party legal text remains exactly as sourced, with provenance and version.
- Any planned additional runtime code change requires a separate approved engineering issue.
