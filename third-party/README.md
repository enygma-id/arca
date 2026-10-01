# Third-Party License Provenance

This directory preserves license texts and standards references identified from
the founding ARCA implementation.

ARCA-owned source is governed by the root [`LICENSE`](../LICENSE) under
`AGPL-3.0-only`.

Third-party materials remain under their original terms.

## Founding Snapshot

| Component | Snapshot / reference | Relationship |
|---|---:|---|
| OpenSKP | 1.2.0 | Direct SKP adapter dependency and compatibility target in founding prototype |
| NumPy | 2.3.5 | Direct dependency; license captured from reference runtime |
| Shapely | 2.1.2 | Direct dependency; license captured from reference runtime |
| pyproj | 3.7.2 | Direct dependency; geodetic projections (MIT / PROJ license) |
| GEOS | bundled notice from Shapely 2.1.2 reference binary | Native transitive dependency |
| Trimesh | 4.11.1 license snapshot; OpenSKP requires Trimesh >=3.0 | Transitive OpenSKP dependency |
| Deck.gl | 9.3.7 | Vendored offline frontend visualization library (Apache-2.0 / MIT) |
| MapLibre GL JS | 6.9.0 | Vendored offline frontend 2D/3D map engine (BSD-3-Clause) |
| Three.js | 0.185.0 | Vendored offline frontend 3D GLTF renderer (MIT) |

Captured versions identify license provenance only. They are not dependency
pins.

## Directory

```text
third-party/
├── MANIFEST.json
├── README.md
├── deck.gl/
│   └── LICENSE
├── maplibre-gl/
│   └── LICENSE
├── numpy/
│   └── LICENSE.txt
├── openskp/
│   └── LICENSE
├── pyproj/
│   ├── LICENSE
│   └── LICENSE_proj
├── shapely/
│   ├── LICENSE.txt
│   └── LICENSE_GEOS
├── standards/
│   ├── GEOJSON.md
│   └── IFC.md
├── three/
│   └── LICENSE
└── trimesh/
    └── LICENSE
```

Refresh this directory when dependency versions, packaging methods, or release
artifacts materially change.
