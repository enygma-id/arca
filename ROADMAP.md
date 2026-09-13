# Roadmap

This roadmap describes direction, not a commitment to dates or guaranteed
features.

## Repository Foundation

- public repository;
- licensing and governance;
- third-party provenance;
- contribution process;
- reference documentation;
- tagged releases.

## First Public Software Workflow

- consolidate the current prototype scripts into one coherent package;
- SKP adapter using OpenSKP;
- direct IFC input;
- canonical GIS-native derivative;
- LOD1.3;
- Enhanced LOD1.3;
- explicit spatial-placement metadata;
- deterministic output layout;
- CLI and Python API.

## Georeferencing

- inspect IFC georeferencing sources;
- support `IfcMapConversion` where present;
- support `IfcProjectedCRS` where present;
- inspect `IfcSite` geographic reference where appropriate;
- preserve CRS and transform provenance;
- fail loudly when authoritative placement cannot be resolved.

## Scientific Validation

- multiple building typologies;
- curved-roof failure cases;
- footprint IoU;
- boundary/Hausdorff metrics;
- height deviation;
- volume deviation;
- semantic retention;
- runtime and memory benchmarks;
- reproducible test corpus.

## Packaging and GIS Integration

Potential directions:

- GeoPackage;
- PostGIS;
- vector-tile/PMTiles derivation;
- open viewer examples;
- service-friendly API boundaries.

## On-Demand Publication

Longer-term direction:

```text
BIM Server / CDE / Asset Repository
             ↓
            ARCA
             ↓
Purpose-specific GIS representation
             ↓
Web / Research / Planning / Public applications
```

This phase should follow, not precede, a stable and validated transformation
methodology.
