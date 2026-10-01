# Architecture

## Founding Architecture

The initial ARCA workflow contains two source paths.

### SKP Path

```text
SketchUp (.skp)
      ↓
OpenSKP
      ↓
IFC4
      ↓
ARCA IFC processing
      ↓
GIS-native representations
```

### Direct IFC Path

```text
IFC4
  ↓
ARCA IFC processing
  ↓
GIS-native representations
```

## Current Prototype Characteristics

The audited founding prototype:

- parses the relevant IFC STEP entities directly for the supported geometry
  graph rather than wrapping IfcOpenShell;
- supports IFC tessellation including `IfcTriangulatedFaceSet`;
- includes basic `IfcPolygonalFaceSet` support;
- supports selected BRep and extruded-solid paths;
- resolves local placements and mapped items for supported cases;
- uses NumPy for numerical geometry work;
- uses Shapely for topology-preserving planar union and simplification;
- writes GeoJSON-first derivatives;
- can produce optional render-oriented derivative caches without treating those
  caches as canonical.

## Architectural Boundary

ARCA core is responsible for:

```text
source interpretation
→ geometry normalization
→ semantics/provenance
→ representation generalization
→ spatial output
```

ARCA core is not responsible for forcing one specific:

- tile server;
- browser renderer;
- database;
- BIM Server;
- cloud platform.

Those are downstream integrations.

## Consolidated Package Structure

The engine is consolidated into the `arca` package:

- `arca.engine`: STEP ISO-10303-21 parser, geodesic georeferencing, BRep/tessellation geometry graph, and LOD 1.3 plateaus;
- `arca.server`: web Studio API and lightweight browser spatial viewer;
- `arca.cli`: unified CLI command entry point (`arca run`, `arca inspect`, `arca serve`).
