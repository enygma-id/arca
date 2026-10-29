# Representation Profiles

ARCA uses conservative representation terminology.

## Why Conservative Naming Matters

A representation should not be called LOD2.2 merely because it contains more
surface features than LOD1.3.

Formal LoD terminology carries geometric and semantic expectations.

The founding prototype initially used an internal `2.2-style` label for a
finer plateau representation. ARCA's public terminology intentionally steps
back from that label until roof morphology and conformance can be validated.

## LOD1.3

ARCA's LOD1.3 direction represents the building as a compact mass model.

The current method is based on:

- a true projected footprint derived from source geometry;
- topology-preserving simplification;
- a representative base mass;
- only a limited number of dominant secondary masses;
- meaningful height differences.

The intent is to preserve recognizable building mass without reproducing
architectural detail.

## Enhanced LOD1.3

Enhanced LOD1.3 preserves more source-derived height variation than the compact
LOD1.3 profile.

It may include finer height plateaus or additional mass differentiation.

It is **not currently presented as formal LOD2.2** because the founding method
does not yet guarantee preservation of all significant roof morphology, curved
roof surfaces, ridges, eaves, or other LoD2.x expectations.

This label is deliberately descriptive:

```text
more informative than compact LOD1.3
without claiming full LOD2.2 conformance
```

## OGC LOD 2.0 (CityJSON v1.1 & CityGML v2.0)

ARCA provides standards-conformant OGC LOD 2.0 representations:

- **CityJSON (v1.1)**: Stored as `building.city.json`, featuring topological vertex de-duplication, integer millimeter coordinate quantization via an affine transform (`scale` and `translate`), and semantic surface classification (`RoofSurface`, `WallSurface`, `GroundSurface`, `OuterFloorSurface`).
- **CityGML (v2.0)**: Stored as `building.gml`, formatted in compliant GML 3.1.1 XML featuring topological linear ring loop closures and semantic `<bldg:boundedBy>` boundary surface elements.

Unlike generalized LOD1.3 mass plateaus, LOD 2.0 retains individual exterior boundary facets, distinct sloped/flat roof geometry, and exterior structural envelopes while excluding internal partitions and sub-element fittings.

See [`docs/citygml-cityjson.md`](./citygml-cityjson.md) for full mapping specifications and algorithms.

## Canonical Full-Detail GIS-Native Derivative

The prototype can also preserve source IFC product geometry as GIS features.

This is useful for provenance, inspection, and deriving lower-detail
representations.

ARCA does not call this a standards-conformant CityGML LoD3 model merely
because source faces or product geometry are retained.

## Future Promotion of Claims

A stronger representation label may be adopted only after:

- explicit criteria are defined;
- multiple building typologies are validated;
- curved and complex roofs are tested;
- failure cases are published;
- comparison against recognized LoD expectations is documented.
