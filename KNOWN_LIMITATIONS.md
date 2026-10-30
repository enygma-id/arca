# Known Limitations

ARCA is intentionally narrow about what the founding implementation can claim.

## Representation Scope

The current direction focuses on generating meaningful GIS-native
representations from SKP-derived IFC and direct IFC inputs.

It does not guarantee equivalent behavior for every BIM authoring ecosystem or
every IFC representation item.

## CityGML & CityJSON LOD Scope

ARCA provides direct OGC CityJSON (v1.1) and CityGML (v2.0) LOD 2.0 representations with semantic boundary surfaces.

However, ARCA does not claim full LOD3 or LOD4 reconstruction (interior spaces, detailed window frames, or architectural fixtures are generalized into external LOD 2.0 boundary surfaces). Complex non-manifold geometries from arbitrary BIM authoring tools may be simplified to preserve GIS validity.

## OGC Schema Conformance vs Syntactic Output

ARCA generates CityJSON (v1.1) and CityGML (v2.0) files structured for compatibility with tools such as QGIS, CityJSON Ninja, and 3D GIS viewers.

However:
- Syntactic generation (producing well-formed XML and JSON) does not constitute formal OGC Schema Conformance certification.
- Outputs have not been subjected to the official OGC Compliance Testing Program (CITE/ETS) or full XML Schema (XSD) validation suites.
- Available tests verify structural validity and parser ingest, but do not imply exhaustive schema compliance across all edge cases of the OGC standards.
- Users requiring strict compliance guarantees should validate output files against official OGC schemas before ingestion into formal municipal SDI workflows.

## Enhanced LOD1.3 Is Not LOD2.2

The current richer generalized profile may preserve multiple roof-height
plateaus or dominant mass changes.

It does not yet guarantee preservation of:

- curved roof morphology;
- ridges and eaves;
- all architecturally significant roof surfaces;
- formal LoD2.x semantics.

Therefore ARCA currently calls it **Enhanced LOD1.3**.

## IFC Geometry Coverage

The founding parser supports selected IFC geometry paths used by the current
prototype.

It is not a complete IFC implementation.

Unsupported geometry may be skipped or require future adapters.

## IFC Georeferencing

ARCA extracts and resolves standard buildingSMART IFC4 Georeferencing
(`IfcProjectedCRS`, `IfcMapConversion`, and `IfcSite` DMS coordinates).

When an input IFC model lacks embedded georeferencing entities, ARCA falls back
to companion JSON metadata or user-supplied anchor parameters (`--anchor-lon`,
`--anchor-lat`, `--crs`).

See [`docs/spatial-reference.md`](./docs/spatial-reference.md).

## SKP Placement

The SKP workflow preserves geometry through the adapter path but does not
guarantee authoritative geographic placement.

Users or upstream systems may need to provide positioning.

## Source Quality

ARCA cannot recover semantic or geometric truth that is missing or ambiguous in
the source.

Poor source organization, invalid geometry, inconsistent units, or weak
semantic naming can reduce output quality.

## Benchmark Status

Early size-reduction observations are motivating examples, not universal
performance guarantees.

Scientific evaluation must include fidelity and semantic metrics, not file size
alone.

## Server and Realtime Scope

The founding project is a transformation toolset.

BIM Server/CDE integration, on-demand generation, caching, and live publication
are future system layers.
