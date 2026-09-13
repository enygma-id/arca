# Related Work and Project Position

ARCA should be evaluated in relation to existing BIM, 3D-city, and GIS work
rather than presented as though the problem space were empty.

## IFC and openBIM

IFC provides an open exchange representation for BIM.

ARCA treats IFC as an important authoritative/intermediate source rather than
attempting to replace it.

## IFC to CityGML / CityJSON

Existing research and software have explored transformation from IFC into
standardized semantic city models such as CityGML and CityJSON.

ARCA does not claim novelty merely because it can produce spatial geometry from
IFC.

Its focus is different:

```text
high-detail asset source
        ↓
fit-for-purpose GIS-native derivative
        ↓
ordinary geospatial analysis and publication
```

## BIM Viewers and BIM Servers

BIM viewers and BIM Servers solve important coordination, collaboration,
inspection, and lifecycle problems.

ARCA does not attempt to reproduce those systems.

A future ARCA deployment may instead sit downstream of a BIM repository and
generate purpose-specific GIS representations on demand.

## Mesh / 3D Delivery Formats

Mesh, glTF, and 3D Tiles are effective rendering/delivery technologies.

ARCA treats rendering optimization as downstream engineering rather than
requiring every canonical derivative to become a mesh-first object.

## Research Claim Discipline

ARCA should make claims only where reproducible evaluation supports them.

The project should distinguish:

- engineering usefulness;
- research novelty;
- standards conformance;
- performance;
- fidelity.

Those are related but not interchangeable.
