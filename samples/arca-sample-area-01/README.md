# ARCA Sample Area 01

A synthetic commercial building model created by **Enygma** for ARCA research, reproducibility, and BIM-to-GIS transformation experiments.

## Data provenance

According to Enygma, the input in this package was produced as follows:

| File | Creator | Production method |
| --- | --- | --- |
| `data/arca_synthetic_mall_10f.ifc` | Enygma | Synthetic IFC4 building design fixture created for ARCA testing and benchmarking. |

No proprietary client BIM data was used. The model represents a realistic multi-storey commercial building with ground-level entrance, stepped upper-level setbacks, exterior envelope, slabs, walls, and window surfaces.

## Model overview

| Property | Value |
| --- | --- |
| Format | IFC4 (STEP ISO-10303-21) |
| Storeys | 10 floors |
| Total building height | 39.6 m (Ground: 5.4 m, Levels 2–10: 3.8 m each) |
| Authoritative footprint area | ~3,582.5 m² |
| Upper floor taper / setbacks | Levels 1–7: 0.0 m, Level 8: 1.2 m, Level 9: 2.4 m, Level 10: 3.6 m |
| Projected CRS | EPSG:32750 (WGS 84 / UTM Zone 50S) |
| Map conversion origin | Easting: 767741.36 m, Northing: 9430330.03 m |
| Site centroid (WGS 84) | 119.4151° E, -5.1493° S |

## ARCA workflow

```text
arca_synthetic_mall_10f.ifc
        │
        ├── STEP ISO-10303-21 parser & geometry graph resolution
        ├── Karney (2011) geodesic projection & WGS 84 placement
        ├── Topocentric East-North-Up (ENU) matrix & 3D glTF/GLB export
        └── Multi-storey plateau slicing & GIS-native LOD 1.3 GeoJSON
```

## Package layout

```text
arca-sample-area-01/
├── README.md
├── LICENSE-DATA.md
├── MANIFEST.sha256
└── data/
    └── arca_synthetic_mall_10f.ifc
```

## Quick usage

Execute the ARCA transformation pipeline directly on the sample model:

```bash
# Convert to full-detail GLB and LOD 1.3 GeoJSON
arca run samples/arca-sample-area-01/data/arca_synthetic_mall_10f.ifc --out outputs/

# Inspect embedded IFC georeferencing without full conversion
arca inspect samples/arca-sample-area-01/data/arca_synthetic_mall_10f.ifc
```

Or launch the interactive web studio:

```bash
arca serve
```

## Licensing and attribution

Enygma releases the sample IFC model under **Creative Commons Attribution 4.0 International (CC BY 4.0)**. Attribution is required for copies and adaptations; modified versions must indicate changes. See `LICENSE-DATA.md` and the [official license](https://creativecommons.org/licenses/by/4.0/).

Suggested attribution:

> ARCA Sample Area 01, created by Enygma, licensed under CC BY 4.0. https://creativecommons.org/licenses/by/4.0/

This data license is distinct from ARCA's software license and does not license third-party software, basemaps, logos, or trademarks.

## Integrity verification

```bash
# macOS (run from this directory)
shasum -a 256 -c MANIFEST.sha256

# Linux
sha256sum -c MANIFEST.sha256
```
