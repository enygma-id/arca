# A-03 — Map data and tile service policy (proposed; human review)

## OpenStreetMap

- Browser viewer in `src/arca/server/static/viewer/app.js` requests `https://tile.openstreetmap.org/{z}/{x}/{y}.png` and advertises `© OpenStreetMap contributors`.
- Authoritative tile service policy: https://operations.osmfoundation.org/policies/tiles/ (reviewed 2026-10-29).
- Tile service access is **not the same** as database rights under ODbL. Interactive browser tile viewing is contemplated by the OSMF policy subject to attribution, valid identifying headers (browser Referer), caching directives, and no bulk prefetch/scraping/offline archiving.
- For the Community viewer: maintain visible attribution; do not hide off screen; do not fetch tiles not actively being viewed; do not force no-cache; honor caching and referer. `attributionControl:false` in MapLibre init at viewer/app.js:1742 is followed by custom AttributionControl at :1752 — test visibility with all engines and small screens, not just search for one flag.
- Any packaged/offline tile data requires a separate permitted source/provider. No rehosting or offline use rights are inferred from OSMF tile servers.

## BIG Rupabumi Indonesia

- Viewer in `src/arca/server/static/viewer/app.js` uses official `geoservices.big.go.id/rbi/rest/services/BASEMAP/Rupabumi_Indonesia/MapServer/tile/{z}/{y}/{x}` and identifies provider as `Badan Informasi Geospasial`.
- Official service metadata: https://geoservices.big.go.id/rbi/rest/services/BASEMAP/Rupabumi_Indonesia/MapServer . It reports copyright `Badan Informasi Geospasial` and 24 cached zoom levels.
- Endpoint is publicly readable, **but explicit rights for downloading, mirroring, bulk caching, resale or redistribution have NOT been established**. Do not state those activities are licensed. For browser interactive basemap use, seek owner review of any applicable user terms and preserve provider attribution. `NEEDS_VERIFICATION` for the legal basis if ARCA or Enterprise ever changes the use pattern.

## Engineering handoff

No requirement to disable either basemap, proxy it, insert new credentials, or change the viewer rendering. Handoff: test attribution in MapLibre/Deck/Cesium if present, keep user-visible provider credit, and document usage policy without pretending license grant.
