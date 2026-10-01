# Transformation method

ARCA converts BIM and CAD models (`.ifc` and `.skp`) into GIS-native multi-storey building massing (LOD 1.3 GeoJSON) and 3D render assets (glTF/GLB).

ARCA parses the IFC STEP geometry graph directly, resolves hierarchical placements into metric world coordinates, and georeferences coordinates using buildingSMART `IfcMapConversion` or site anchors. It groups horizontal surfaces by elevation binning, dissolves interior partitions through cascaded planar 2D union, eliminates slivers, and simplifies exterior boundaries into discrete storey plateaus. In parallel, surface geometry is baked into an exterior topocentric binary GLB mesh.

Each storey feature records its storey index, elevation interval (`base_z`, `top_z`), height, footprint area, and source element metadata. Output coordinates are EPSG:4326; metric measurements use the resolved projected CRS.

See [Architecture](architecture.md), [Spatial reference](spatial-reference.md), and [Representation profiles](representation-profiles.md).
