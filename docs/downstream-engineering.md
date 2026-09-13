# Downstream Engineering

ARCA distinguishes canonical transformation from delivery engineering.

## ARCA Core Concern

```text
authoritative asset
        ↓
meaningful GIS-native representation
```

## Downstream Concerns

Potential downstream systems may perform:

- GeoPackage packaging;
- PostGIS loading;
- vector tiling;
- PMTiles packaging;
- 3D Tiles derivation;
- viewport streaming;
- browser caching;
- WebGL/WebGPU rendering;
- public API publication.

Those are important, but they should not dictate the only canonical ARCA
representation.

## BIM Server / CDE Integration

A future integration pattern may be:

```text
BIM Server / CDE
       │
       ├── authoritative IFC/model
       │
       ▼
      ARCA
       │
       ├── compact public profile
       ├── research profile
       ├── planning profile
       └── selected higher-detail profile
       │
       ▼
GIS publication infrastructure
```

This would allow on-demand publication without treating the BIM Server itself
as the public web renderer.

## Why This Is Future Work

The founding project first needs to prove that:

- the representations are useful;
- geometry preservation can be measured;
- semantics remain traceable;
- spatial reference is handled correctly;
- outputs are reproducible.

Service orchestration should follow a stable core methodology rather than hide
an unstable one behind an API.
