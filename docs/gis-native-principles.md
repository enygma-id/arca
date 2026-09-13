# GIS-Native Design Principles

## Spatial Geometry Is a First-Class Output

ARCA aims to preserve useful asset meaning in ordinary spatial geometry and
attributes wherever practical.

The goal is not to hide the useful representation inside an opaque viewer-only
object.

## Identity and Provenance Remain Data

A generalized object should retain enough provenance to answer:

- which source asset did this come from?
- which source IFC object or class contributed?
- what method produced this representation?
- what assumptions were applied?

## 3D Meaning Does Not Require One Canonical Renderer

A GIS feature may carry useful 3D meaning through:

```text
geometry
+
base elevation / height
+
top elevation / height
+
semantic type
+
source identity
```

A downstream renderer can extrude, triangulate, tile, or stream that
representation without becoming the owner of the canonical data model.

## Spatial Analysis Matters as Much as Visualization

ARCA outputs should remain suitable, where practical, for:

- indexing;
- filtering;
- containment;
- intersection;
- joins;
- asset lookup;
- area and height analysis;
- database queries.

## Renderer Independence

ARCA does not mandate one web renderer.

Compatibility with open geospatial renderers is a downstream design goal, not
a reason to make one renderer-specific format the only canonical source.

## Detail Is Purpose-Driven

More geometric detail is useful when the use case requires it.

More detail is not automatically more correct.

ARCA therefore separates representation profiles from source fidelity and
avoids using LoD labels as marketing terminology.

## GIS-Native Is a Research Direction

ARCA does not claim that current GIS-native representations solve every BIM or
3D-city problem.

The project asserts a research direction:

> High-detail digital assets should be able to produce open, purpose-specific,
> spatial representations without surrendering source authority or
> interoperability.
