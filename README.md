# ARCA

**ARCA: Asset Representation Conversion Architecture**

ARCA is an open-source, GIS-native research and engineering initiative for
transforming authoritative digital-asset representations into lighter,
interoperable spatial representations without treating the original BIM model
as disposable.

**Founded and stewarded by Enygma.**  
Legal entity: **PT Enygma Solusi Negeri**

## Why ARCA Exists

BIM and GIS are both mature disciplines, but they optimize for different
questions.

BIM is excellent at preserving engineering intent, construction detail,
component relationships, and asset lifecycle information.

GIS is excellent at answering spatial questions across buildings, parcels,
roads, terrain, infrastructure, hazards, administrative boundaries, imagery,
and other city-scale layers.

The difficulty begins when a high-detail BIM asset is treated as though the
same representation must also become the public web representation.

A complete BIM model may be the correct authoritative source and still be the
wrong delivery object for:

- a public map;
- a city-scale asset inventory;
- a browser running on a mobile connection;
- spatial joins and filters;
- research that needs footprints, height, massing, or selected semantics;
- downstream vector tiling;
- open WebGL/WebGPU visualization.

ARCA begins from a fit-for-purpose question:

> What is the least complex GIS-native representation that preserves the
> information required by the intended downstream use, while keeping the
> authoritative BIM source intact?

## The Missing Representation Layer

ARCA is not a BIM replacement and not a GIS replacement.

It is intended to occupy the layer between them.

```text
Authoritative Asset Source
        │
        ├── IFC
        ├── SKP through an adapter
        └── future source adapters
        │
        ▼
       ARCA
semantic extraction
geometry normalization
representation generalization
spatial placement
        │
        ▼
GIS-native representations
        │
        ├── GeoJSON
        ├── future GeoPackage/PostGIS workflows
        └── future tile/publication derivatives
        │
        ▼
Open geospatial ecosystem
```

The initial implementation path is deliberately pragmatic:

```text
SKP
 ↓
OpenSKP adapter
 ↓
IFC4
 ↓
ARCA generalization
 ↓
GIS-native output
```

or, when IFC is already available:

```text
IFC4
 ↓
ARCA generalization
 ↓
GIS-native output
```

## Quickstart

End users can install the engine and server with pip:

```sh
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install ".[server]"
arca serve
```

Contributors can use the same commands on Windows, Linux, and macOS without activating a shell:

```sh
uv sync --extra dev
uv run arca serve

# Convert a BIM model (IFC or SKP) directly via CLI
uv run arca run input_model.ifc --out outputs/

# Inspect embedded georeferencing without full conversion
uv run arca inspect input_model.ifc
```

`uv` creates and uses `.venv`. Shell activation is optional.

## Sample Datasets

ARCA includes ready-to-use sample datasets for reproducible research, testing, and demonstration:

- **Sample Area 01 (`IFC`):** synthetic commercial building model in IFC4 format ([`samples/arca-sample-area-01/`](samples/arca-sample-area-01/))
- **Sample Area 02 (`SKP`):** synthetic commercial building model in Trimble SketchUp format with companion georeferencing ([`samples/arca-sample-area-02/`](samples/arca-sample-area-02/))

Each sample directory includes its own documentation, model overview, SHA-256 integrity manifest, and data license.

The sample data are licensed separately from the ARCA software under **Creative Commons Attribution 4.0 International (CC BY 4.0)**.

## Current Representation Direction

The founding prototype explores three practical representation layers:

1. **Canonical full-detail GIS-native derivative**  
   IFC product geometry remains queryable as GIS features. This is not a
   formal CityGML LoD3 conformance claim.

2. **Enhanced LOD1.3**  
   A richer generalized representation that preserves more dominant
   height/mass variation than conventional LOD1.3 while deliberately avoiding
   a formal LOD2.2 claim until roof morphology and conformance are validated.

3. **LOD1.3**  
   A compact building-mass representation intended for efficient city-scale
   spatial use.

ARCA deliberately uses conservative terminology. A more detailed output is not
called LOD2.2 merely because it contains more polygons or height plateaus.

See [`docs/representation-profiles.md`](./docs/representation-profiles.md).

## GIS-Native by Design

ARCA treats GIS-native output as a first-class architectural decision rather
than a temporary export format.

The current direction favors ordinary spatial features carrying geometry,
identity, semantics, height, and provenance so they can remain useful outside
one renderer.

ARCA aims for representations that can participate in:

- spatial indexing;
- filtering;
- spatial joins;
- asset lookup;
- database storage;
- web mapping;
- browser 3D visualization;
- downstream vector/3D tiling;
- reproducible research.

Rendering is downstream engineering. The canonical spatial representation
should not depend on one renderer.

See [`docs/gis-native-principles.md`](./docs/gis-native-principles.md).

## Spatial Reference

Spatial placement is treated as data, not as a viewer-only adjustment.

The founding prototype currently supports a user-supplied WGS84 anchor for
local BIM geometry. It does **not yet automatically resolve the complete IFC
georeferencing stack** such as `IfcMapConversion`, `IfcProjectedCRS`, or
`IfcSite` geographic reference fields.

That distinction is important:

- a local SKP-derived model may require explicit positioning;
- an IFC containing authoritative georeferencing should eventually preserve and
  propagate that information automatically;
- ARCA must not silently invent geographic truth.

See [`docs/spatial-reference.md`](./docs/spatial-reference.md).

## What ARCA Is Not

ARCA is not intended to compete by re-implementing established
IFC-to-CityGML or IFC-to-CityJSON research as though that work did not exist.

Those approaches address important standardized city-model transformation
problems.

ARCA focuses on a complementary question:

> How can a high-detail authoritative BIM asset be reduced into practical,
> open, GIS-native representations for spatial analysis, web delivery, public
> access, and downstream tiling without forcing every consumer to load the full
> BIM representation?

ARCA is also not currently:

- a BIM authoring application;
- a Common Data Environment;
- a BIM Server;
- a real-time BIM synchronization service;
- a formal CityGML implementation;
- a formal CityJSON implementation;
- a guarantee that every source model can be generalized without loss.

See [`KNOWN_LIMITATIONS.md`](./KNOWN_LIMITATIONS.md).

## Long-Term System Position

The founding release is intentionally a converter/generalization toolset first.

The longer-term architectural opportunity is broader:

```text
BIM / Asset Repository
        │
        ▼
ARCA on-demand representation layer
        │
        ├── public lightweight representation
        ├── research representation
        ├── planning representation
        └── higher-detail internal representation
        │
        ▼
GIS / Web / Analytics / Digital Twin consumers
```

That future direction does not require the founding implementation to become a
server before the transformation methodology itself is stable.

See [`docs/downstream-engineering.md`](./docs/downstream-engineering.md).

## Founding Observation

ARCA emerged from a practical experiment in which a large SketchUp building
model could be reduced into dramatically smaller GIS-native representations
while preserving useful building form.

That observation is a motivation, not yet a universal performance claim.

ARCA therefore treats benchmark quality as multidimensional:

```text
size reduction
+
geometry preservation
+
semantic preservation
+
spatial accuracy
+
web readiness
```

See [`research/benchmark-methodology.md`](./research/benchmark-methodology.md).

## Project Identity

| Item | Value |
|---|---|
| Project | ARCA |
| Expanded name | Asset Representation Conversion Architecture |
| Founding Organization | Enygma |
| Project Steward | Enygma |
| Legal entity | PT Enygma Solusi Negeri |
| Founding phase | 2026 |
| Enygma GitHub organization | https://github.com/enygma-id |
| Community license | AGPL-3.0-only |

Founding attribution is recorded in
[`FOUNDING_TEAM.md`](./FOUNDING_TEAM.md).

The chronological origin of the project is documented in
[`docs/project-history.md`](./docs/project-history.md).

## Editions

### Community Edition

ARCA Community Edition is the canonical public open-source edition.

Covered ARCA-owned source code is licensed under:

**GNU Affero General Public License, Version 3 only (`AGPL-3.0-only`)**

The complete license text is in [`LICENSE`](./LICENSE).

### Enterprise Edition

ARCA Enterprise Edition is a separate commercial offering from Enygma for
organizations requiring proprietary integration rights, private extensions,
OEM arrangements, enterprise support, SLA, or separately negotiated licensing
terms.

See [`ENTERPRISE.md`](./ENTERPRISE.md).

## AI-Assisted Development

ARCA acknowledges LLM use directly rather than hiding it.

The project follows this principle:

> **Human-originated, AI-assisted, human-validated.**

The problem, architecture, acceptance criteria, validation, licensing,
scientific claims, and final software decisions remain human responsibilities.

See [`AI_USAGE.md`](./AI_USAGE.md).

## Third-Party Software

The founding implementation directly relies on or materially consumes:

- OpenSKP;
- NumPy;
- Shapely;
- IFC4 as an open BIM exchange standard.

The audited OpenSKP 1.2.0 package also declares Trimesh as a runtime
dependency. Shapely binary distributions may bundle GEOS.

ARCA does not list future compatibility targets as though they were current
runtime dependencies.

See:

- [`THIRD_PARTY_NOTICES.md`](./THIRD_PARTY_NOTICES.md)
- [`third-party/`](./third-party/)

## Research Status

ARCA is early-stage research and engineering software.

Before a stable 1.0 release, APIs, representation profiles, file layout,
generalization parameters, georeferencing behavior, and benchmark methodology
may change.

Claims about fidelity, LoD conformance, performance, or semantic preservation
should be supported by reproducible evidence rather than screenshots alone.
