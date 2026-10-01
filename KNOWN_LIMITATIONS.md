# Known Limitations

ARCA is intentionally narrow about what the founding implementation can claim.

## Representation Scope

The current direction focuses on generating meaningful GIS-native
representations from SKP-derived IFC and direct IFC inputs.

It does not guarantee equivalent behavior for every BIM authoring ecosystem or
every IFC representation item.

## Not an IFC-to-CityGML / CityJSON Replacement

ARCA does not position itself as a substitute for existing IFC-to-CityGML or
IFC-to-CityJSON research.

Those projects address standardized 3D-city-model transformation.

ARCA focuses on fit-for-purpose GIS-native representations and public/spatial
consumption.

The approaches may be complementary.

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
