# Spatial Reference and Placement

Spatial placement is part of the data contract.

A visually correct model placed with ad-hoc viewer offsets is not equivalent to
a georeferenced spatial dataset.

## Current Prototype Behavior

The founding prototype currently converts local model X/Y coordinates to
longitude/latitude using a user-provided WGS84 anchor.

Conceptually:

```text
local BIM coordinates
        +
user supplied anchor_lon / anchor_lat
        ↓
WGS84-positioned GeoJSON derivative
```

This is useful for exercising GIS placement, but it is not the same as fully
reading authoritative IFC georeferencing.

## IFC Georeferencing Support

ARCA resolves standard buildingSMART IFC4 georeferencing entities directly:

- `IfcMapConversion` (Eastings, Northings, OrthogonalHeight, XAxisAbscissa, XAxisOrdinate, Scale);
- `IfcProjectedCRS` (EPSG code, projected coordinate system name);
- `IfcSite` (compound angle latitude/longitude and site elevation);
- `IfcUnitAssignment` / `IfcSIUnit` (length unit resolution and metric scale factor).

Projections use high-precision Karney (2011) series without requiring external C dependencies.

When authoritative georeferencing is present:

```text
IFC geometry (normalized to meters)
+
IFC CRS / map conversion / site reference
        ↓
Karney geodesic transform
        ↓
GIS-native output
+
CRS & transform provenance
```

## Fallback Placement

When an input model lacks embedded georeferencing:

- ARCA falls back to user-supplied anchor coordinates (`--anchor-lon`, `--anchor-lat`, `--crs`);
- user-provided placement is explicitly tagged as `cli_anchor_fallback` in output metadata;
- geographic authority is not falsely claimed.

## SKP Behavior

SKP files may contain geometry without a reliable spatial reference for the
ARCA workflow.

The SKP path therefore separates:

```text
shape preservation
```

from:

```text
authoritative world placement
```

When the source cannot establish authoritative placement, the user or calling
system remains responsible for positioning.

## No Silent Georeferencing

ARCA should prefer an explicit unresolved state over a silently invented
location.
