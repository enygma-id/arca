# Transformation method

ARCA converts BIM and CAD models (`.ifc` and `.skp`) into GIS-native multi-storey building massing (LOD 1.3 GeoJSON), 3D render assets (glTF/GLB), OGC CityJSON v1.1 (LOD 2.0), and OGC CityGML v2.0 (LOD 2.0).

## Core Ingestion & Georeferencing

ARCA parses the IFC STEP geometry graph directly, resolves hierarchical placements into metric world coordinates, and georeferences coordinates using buildingSMART `IfcMapConversion` or site anchors. It groups horizontal surfaces by elevation binning, dissolves interior partitions through cascaded planar 2D union, eliminates slivers, and simplifies exterior boundaries into discrete storey plateaus. In parallel, surface geometry is baked into an exterior topocentric binary GLB mesh.

Each storey feature records its storey index, elevation interval (`base_z`, `top_z`), height, footprint area, and source element metadata. Output coordinates are EPSG:4326; metric measurements use the resolved projected CRS.

## OGC CityJSON (v1.1, LOD 2.0)

CityJSON generation constructs a compact, web-ready topological model:
- **Integer Quantization**: Global metric coordinates $(X, Y, Z)$ are quantized to millimeter integer precision using affine parameters (`scale: [0.001, 0.001, 0.001]` and `translate`).
- **$O(1)$ Spatial Hash Vertex Deduplication**: Coincident vertices between adjacent surfaces are indexed into a spatial hash table, eliminating vertex redundancy.
- **Semantic Surface Classification**: Facets are classified into standard OGC surfaces (`RoofSurface`, `WallSurface`, `GroundSurface`, `OuterFloorSurface`) based on BIM product classes and outward surface normal vectors ($\vec{n}_z < -0.7$ at base elevation designates ground contact).

## OGC CityGML (v2.0 XML, LOD 2.0)

CityGML serialization outputs conformant OGC 3D city models for GIS and cadastre pipelines:
- **Linear Ring Closure**: Every polygon boundary explicitly closes its vertex sequence ($P_0 \to P_1 \to P_2 \to P_0$) in `<gml:posList>`.
- **Hierarchical Boundary Surfaces**: Geometries are grouped under `bldg:Building` within `bldg:boundedBy` elements containing `bldg:lod2MultiSurface`.
- **$O(1)$ Memory Streaming Writer**: Rather than constructing an in-memory XML DOM tree, XML structures are streamed directly to disk, ensuring zero memory bloat during massive building conversions.

See [Architecture](architecture.md), [Spatial reference](spatial-reference.md), [Representation profiles](representation-profiles.md), and [CityGML & CityJSON Guide](citygml-cityjson.md).
