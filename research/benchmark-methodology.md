# Benchmark Methodology

## Purpose

ARCA benchmark results should answer:

> What complexity was removed, what spatial meaning was preserved, and what was
> the practical benefit?

A file-size table alone cannot answer that.

## Required Metric Groups

### 1. Representation Cost

Measure:

- source file size;
- output file size;
- feature count;
- coordinate/vertex count;
- triangle count where meaningful;
- object count;
- processing time;
- peak memory where available.

### 2. Footprint Preservation

Recommended metrics:

- footprint Intersection over Union (IoU);
- area difference;
- perimeter difference;
- Hausdorff distance or other boundary-deviation metric.

### 3. Vertical Preservation

Measure:

- source height vs generalized height;
- absolute and percentage height error;
- dominant mass-height preservation.

### 4. Volume / Mass Preservation

Where the source and output support meaningful comparison:

- approximate volume difference;
- mass segmentation retention.

### 5. Semantic Preservation

Measure whether intended semantics survive, such as:

- source object identity;
- source IFC class;
- building identity;
- useful height attributes;
- selected asset metadata.

### 6. Spatial Placement

Where georeferencing is authoritative:

- CRS preservation;
- centroid/anchor displacement;
- rotation error;
- placement provenance.

User-supplied placement should not be scored as automatic IFC
georeferencing.

### 7. Web Readiness

Measure:

- bytes transferred;
- parse time;
- first useful render;
- memory use;
- mobile/browser behavior where appropriate.

## Example Benchmark Structure

```text
Source
  original SKP / IFC
        ↓
ARCA
        ├── canonical full-detail derivative
        ├── Enhanced LOD1.3
        └── LOD1.3
        ↓
same metrics + fidelity comparison
```

## Early 167 MB Case

The founding experiment involving a roughly 167 MB SKP source may be used as a
reference case once the source can be legally published or otherwise
reproducibly described.

The previously observed small output sizes are useful motivation but should be
reported together with geometry and semantic preservation metrics.

## Reproducibility

Published benchmark cases should record:

- ARCA version/commit;
- source provenance and license;
- source format/version;
- parameters;
- runtime environment;
- dependency versions;
- commands;
- output checksums.
