# Project History

## Origin

ARCA originated within **Enygma** from practical BIM, 3D, and geospatial work.

The initial concern was not that BIM contained too much information.

The concern was that the same high-detail engineering representation was being
asked to serve purposes for which ordinary GIS geometry might be more
appropriate.

The founding question became:

> Can an authoritative BIM asset produce a much lighter GIS-native
> representation without losing the spatial meaning needed by the downstream
> use case?

## First Implementation

**Erick Karya**, CEO of Enygma during the founding phase, wrote the first
implementation and established the initial working pipeline.

That experiment combined:

```text
SKP
↓
OpenSKP
↓
IFC4
↓
GIS-native extraction and generalization
```

with a direct IFC path for assets that were already available as IFC.

The implementation deliberately avoided making a BIM viewer the center of the
architecture.

## Implementation Continuation

**Hanafi**, Frontend Engineer at Enygma during the founding phase, continued
the technical work after the initial implementation.

The work expanded from a one-off conversion experiment toward a workflow that
could be inspected through web geospatial renderers and refined as a reusable
tool.

## Representation Refinement

Early experiments produced a compact LOD1.3 representation and a richer
representation initially described internally as `LOD2.2-style`.

Review of curved-roof and morphology cases led the founding team to adopt a
more conservative public terminology:

- **LOD1.3**;
- **Enhanced LOD1.3**.

The choice reflects a project principle: terminology should follow evidence,
not marketing.

## Founding Observation

One early real-world SketchUp building case was approximately 167 MB at the
source.

The working prototype produced dramatically smaller generalized spatial
representations, including an enhanced representation in the hundreds of
kilobytes and a compact LOD1.3 representation in the tens of kilobytes.

Those observations helped justify the project direction.

They are not presented as universal ratios. Formal benchmark publication
requires repeatable tests across multiple assets and fidelity metrics.

## GIS-Native Direction

The founding work converged on this principle:

```text
authoritative BIM
        ↓
ARCA transformation
        ↓
GIS-native canonical derivative
        ↓
optional renderer / tile / service derivatives
```

The renderer is a consumer, not the owner of the data model.

## AI-Assisted Development

LLM systems assisted parts of coding, debugging, technical comparison,
documentation, and iterative architecture discussion.

Human contributors remained responsible for the project problem, the first
implementation, representation choices, validation, licensing, and final
acceptance.

See [`../AI_USAGE.md`](../AI_USAGE.md).
