# Rationale

## Why ARCA Exists

ARCA did not begin from a desire to create another file converter.

It emerged from a practical tension between two valid representations of the
same physical asset.

A detailed BIM model may be the best engineering source of truth.

The same model may be unnecessarily expensive, specialized, or cumbersome when
the downstream question is:

- Where is this building?
- What shape does it occupy?
- What is its useful height?
- What dominant masses matter?
- Which asset is this?
- Can it be queried with normal GIS tools?
- Can it be published through ordinary spatial infrastructure?
- Can a browser render the required representation without downloading the full
  engineering model?

The representation problem is therefore not:

> How do we make BIM less detailed?

It is:

> Which information must remain, and which representation is appropriate for
> the consumer?

## Fit-for-Purpose

ARCA follows a fit-for-purpose principle:

> Use the least complex spatial representation that preserves the information
> required by the intended analysis or publication task.

This principle does not reject BIM, CityGML, CityJSON, meshes, 3D Tiles, or
other models.

It rejects the assumption that the highest-detail source representation must
always be the delivery representation.

## Source Authority vs Publication Representation

ARCA distinguishes two responsibilities.

```text
Authoritative source
    IFC / BIM / SKP-derived IFC

Publication/analysis representation
    GIS-native derivative
```

The derivative must preserve provenance back to the authoritative source.

## Government and Public Infrastructure Context

A city may reasonably require property or infrastructure projects to submit
open BIM such as IFC.

That does not mean every citizen, researcher, GIS analyst, or public web map
should consume the full BIM model.

ARCA explores an open mechanism for generating purpose-specific spatial
representations without forcing public distribution to depend on one vendor's
BIM renderer.

## Openness

ARCA Community Edition is licensed under `AGPL-3.0-only`.

Openness is also a data-architecture principle.

The canonical derivative should remain inspectable, portable, and usable by
multiple GIS tools and renderers.

## Founding Observation

An early ARCA experiment used a large real-world SketchUp building model and
generated much smaller GIS-native derivatives while retaining useful building
form.

The size difference was striking enough to motivate the project, but ARCA does
not treat one case as scientific proof.

The benchmark program therefore evaluates not only payload reduction but also
what was preserved.
