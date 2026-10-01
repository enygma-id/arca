# ARCA Sample Area 02

A synthetic commercial building model in Trimble SketchUp (`.skp`) format created by **Enygma** for ARCA research, format conversion testing, and BIM-to-GIS transformation experiments.

## Data provenance

According to Enygma, the input in this package was produced as follows:

| File | Creator | Production method |
| --- | --- | --- |
| `data/arca_synthetic_mall_10f.skp` | Enygma | Synthetic SketchUp commercial building model fixture created for ARCA testing and benchmarking (originally `ARCA_synthetic_mall_10f_clean_authoritative.skp`). |
| `data/arca_synthetic_mall_10f.json` | Enygma | Companion georeference metadata specifying projected CRS and WGS 84 anchor. |

No proprietary client CAD/BIM data was used. The model represents a realistic multi-storey commercial building with ground-level entrance, stepped setbacks, exterior envelope, slabs, walls, and window surfaces.

## Model overview

| Property | Value |
| --- | --- |
| Format | Trimble SketchUp (`.skp`) |
| Mesh primitives | 604 products / meshes (19,650 vertices) |
| Total building height | ~39.6 m |
| Projected CRS | EPSG:32750 (WGS 84 / UTM Zone 50S) |
| Site centroid (WGS 84) | 119.4151° E, -5.1493° S |
| Georeference mechanism | Companion JSON metadata (`data/arca_synthetic_mall_10f.json`) |

## ARCA workflow

```text
arca_synthetic_mall_10f.skp (+ arca_synthetic_mall_10f.json)
        │
        ├── OpenSKP native C/C++ scene ingestion & mesh parsing
        ├── Coordinate frame conversion (glTF Y-up to IFC Z-up)
        ├── Intermediate IFC4 injection with IfcMapConversion / IfcProjectedCRS
        ├── Topocentric East-North-Up (ENU) matrix & 3D glTF/GLB export
        └── Multi-storey plateau slicing & GIS-native LOD 1.3 GeoJSON
```

## Package layout

```text
arca-sample-area-02/
├── README.md
├── LICENSE-DATA.md
├── MANIFEST.sha256
└── data/
    ├── arca_synthetic_mall_10f.json
    └── arca_synthetic_mall_10f.skp
```

## Quick usage

Execute the ARCA transformation pipeline directly on the sample SketchUp model:

```bash
# Convert SKP to full-detail GLB and LOD 1.3 GeoJSON
arca run samples/arca-sample-area-02/data/arca_synthetic_mall_10f.skp --out outputs/

# Inspect detected format and companion georeferencing
arca inspect samples/arca-sample-area-02/data/arca_synthetic_mall_10f.skp
```

Or launch the interactive web studio:

```bash
arca serve
```

## Licensing and attribution

Enygma releases the sample SketchUp model and metadata under **Creative Commons Attribution 4.0 International (CC BY 4.0)**. Attribution is required for copies and adaptations; modified versions must indicate changes. See `LICENSE-DATA.md` and the [official license](https://creativecommons.org/licenses/by/4.0/).

Suggested attribution:

> ARCA Sample Area 02, created by Enygma, licensed under CC BY 4.0. https://creativecommons.org/licenses/by/4.0/

This data license is distinct from ARCA's software license and does not license third-party software, basemaps, logos, or trademarks.

## Integrity verification

```bash
# macOS (run from this directory)
shasum -a 256 -c MANIFEST.sha256

# Linux
sha256sum -c MANIFEST.sha256
```
