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

## Current Known Limitation

The founding prototype does not yet automatically parse the full IFC
georeferencing stack, including fields/entities such as:

- `IfcMapConversion`;
- `IfcProjectedCRS`;
- `IfcSite` reference latitude/longitude;
- authoritative projected-coordinate metadata.

Therefore:

- ARCA must not claim automatic preservation of IFC georeferencing yet;
- user-provided placement should be identified as user-provided;
- geographic authority must not be inferred from a convenient default anchor.

## Intended IFC Behavior

When authoritative IFC georeferencing is present, the long-term ARCA behavior
should be:

```text
IFC geometry
+
IFC CRS / map conversion / site reference
        ↓
resolved spatial transform
        ↓
GIS-native output
+
CRS provenance
+
transform provenance
```

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
