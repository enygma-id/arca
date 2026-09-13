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
| GEOS | bundled notice from Shapely 2.1.2 reference binary | Native transitive dependency |
| Trimesh | 4.11.1 license snapshot; OpenSKP requires Trimesh >=3.0 | Transitive OpenSKP dependency |

Captured versions identify license provenance only. They are not dependency
pins.

## Directory

```text
third-party/
├── MANIFEST.json
├── README.md
├── licenses/
│   ├── numpy-LICENSE.txt
│   ├── openskp-LICENSE.txt
│   ├── shapely-GEOS-LICENSE.txt
│   ├── shapely-LICENSE.txt
│   └── trimesh-LICENSE.txt
└── standards/
    ├── GEOJSON.md
    └── IFC.md
```

Refresh this directory when dependency versions, packaging methods, or release
artifacts materially change.
