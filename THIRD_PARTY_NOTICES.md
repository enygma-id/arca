# Third-Party Software Notices

ARCA Community Edition is licensed under `AGPL-3.0-only` for covered ARCA-owned
source.

Third-party software remains subject to its respective upstream copyright,
license, attribution, patent, and NOTICE terms. Use of a dependency by ARCA
does not relicense that dependency under the ARCA AGPL.

The current implementation incorporates both Python engine dependencies and
vendored offline frontend geospatial/3D libraries:

- OpenSKP;
- NumPy;
- Shapely;
- pyproj;
- Deck.gl (Apache-2.0 / MIT);
- MapLibre GL JS (BSD-3-Clause);
- Three.js (MIT).

OpenSKP 1.2.0 declares NumPy, Trimesh, and Shapely as runtime dependencies.
Shapely binary distributions may bundle GEOS.

The files in [`third-party/`](./third-party/) preserve a
founding provenance snapshot of the relevant license texts/notices.

Captured versions identify the source of those license files; they are **not**
dependency pins unless a future dependency manifest explicitly pins them.

## License and Role Summary

| Component | License / Basis | ARCA Relationship | Founding Role |
|---|---|---|---|
| OpenSKP | MIT | Direct | Reads/builds SKP scene data and provides IFC4 export in the SKP adapter path. |
| NumPy | BSD-3-Clause plus bundled notices | Direct; also OpenSKP dependency | Numerical arrays, transforms, vector/matrix geometry processing. |
| Shapely | BSD-3-Clause | Direct; also OpenSKP dependency | Polygon topology, projected unions, topology-preserving simplification/generalization. |
| pyproj | MIT / PROJ license | Direct | Geodetic coordinate transformations and UTM projections. |
| GEOS | LGPL-2.1 | Native library commonly bundled with Shapely binary distributions | Geometry engine used underneath Shapely. |
| Trimesh | MIT | Transitive OpenSKP runtime dependency | Part of the OpenSKP Python runtime dependency graph; ARCA code does not currently import Trimesh directly. |
| Deck.gl | Apache-2.0 / MIT | Vendored frontend | Large-scale WebGL data overlay rendering in Web Studio viewer. |
| MapLibre GL JS | BSD-3-Clause | Vendored frontend | Client-side map rendering, camera projection, vector/raster basemap handling. |
| Three.js | MIT | Vendored frontend | Custom MapLibre layer for rendering 3D GLTF/GLB models with lighting & materials. |
| IFC4 | Open standard / buildingSMART ecosystem | Input/intermediate standard, not a Python dependency | BIM exchange representation consumed by the ARCA workflow. |
| GeoJSON | IETF RFC 7946 family / open interchange format | Output representation | Current GIS-native output family. |

## OpenSKP

**Source:** https://github.com/iamahsanmehmood/openskp  
**PyPI:** https://pypi.org/project/openskp/  
**License:** MIT  
**License file:** [`third-party/openskp/LICENSE`](./third-party/openskp/LICENSE)

ARCA uses OpenSKP in the SKP source path:

```text
SKP
 ↓
OpenSKP
 ↓
IFC4
 ↓
ARCA
```

OpenSKP is an independent project. SketchUp is a trademark of Trimble Inc.;
ARCA does not imply affiliation or endorsement.

## NumPy

**Source:** https://github.com/numpy/numpy  
**License:** BSD-3-Clause with bundled third-party notices in binary distributions  
**License file:** [`third-party/numpy/LICENSE.txt`](./third-party/numpy/LICENSE.txt)

ARCA uses NumPy for numerical geometry processing, coordinate transforms,
matrix operations, and mesh/face calculations.

The preserved NumPy license file includes notices applicable to the reference
binary distribution from which it was captured.

## Shapely

**Source:** https://github.com/shapely/shapely  
**License:** BSD-3-Clause  
**License file:** [`third-party/shapely/LICENSE.txt`](./third-party/shapely/LICENSE.txt)

ARCA uses Shapely for topology-preserving planar geometry work, including
polygon unions and simplification used by generalized building
representations.

## pyproj

**Source:** https://github.com/pyproj4/pyproj  
**License:** MIT (pyproj) and MIT-style (PROJ)  
**License files:** [`third-party/pyproj/LICENSE`](./third-party/pyproj/LICENSE), [`third-party/pyproj/LICENSE_proj`](./third-party/pyproj/LICENSE_proj)

ARCA uses pyproj for cartographic transformations, geodesic computations, and
UTM projection resolution in `engine/georef.py`.

## GEOS

**Source:** https://libgeos.org/  
**License basis in captured Shapely binary:** LGPL-2.1  
**License file:** [`third-party/shapely/LICENSE_GEOS`](./third-party/shapely/LICENSE_GEOS)

GEOS is not imported directly by ARCA Python code, but may be present as the
native geometry engine distributed with Shapely binaries.

Binary redistributors must preserve the applicable GEOS terms.

## Trimesh

**Source:** https://github.com/mikedh/trimesh  
**License:** MIT  
**License file:** [`third-party/trimesh/LICENSE`](./third-party/trimesh/LICENSE)

The audited ARCA Python files do not currently import Trimesh directly.
It is recorded because OpenSKP 1.2.0 declares Trimesh as a Python runtime
dependency.

## Deck.gl

**Source:** https://github.com/visgl/deck.gl  
**Version:** 9.3.7 (vendored offline)  
**License:** Apache-2.0 / MIT  
**License file:** [`third-party/deck.gl/LICENSE`](./third-party/deck.gl/LICENSE)  
**Path:** `src/arca/server/static/vendor/deck.gl-9.3.7.min.js`

ARCA uses Deck.gl for WebGL-accelerated data visualization layers in the interactive Web Studio.

## MapLibre GL JS

**Source:** https://github.com/maplibre/maplibre-gl-js  
**Version:** 6.9.0 (vendored offline)  
**License:** BSD-3-Clause  
**License file:** [`third-party/maplibre-gl/LICENSE`](./third-party/maplibre-gl/LICENSE)  
**Path:** `src/arca/server/static/vendor/maplibre-gl-6.9.0.mjs`

ARCA uses MapLibre GL JS as the foundational 2D/3D geospatial map rendering engine for coordinate projections, basemaps (BIG & OSM), and camera controls.

## Three.js

**Source:** https://github.com/mrdoob/three.js  
**Version:** 0.185.0 (vendored offline)  
**License:** MIT  
**License file:** [`third-party/three/LICENSE`](./third-party/three/LICENSE)  
**Path:** `src/arca/server/static/vendor/three-0.185.0.module.js`

ARCA integrates Three.js via a custom MapLibre GL layer (`viewer/app.js`) to parse and render 3D `.glb` assets with PBR shading, orientation, and shadow mapping.

## Standards

### IFC4

ARCA consumes IFC4-style data in the founding pipeline.

See [`third-party/standards/IFC.md`](./third-party/standards/IFC.md).

### GeoJSON

ARCA currently produces GIS-native GeoJSON derivatives.

See [`third-party/standards/GEOJSON.md`](./third-party/standards/GEOJSON.md).

## Enterprise Licensing Boundary

Alternative or commercial licensing offered by Enygma applies only to material
for which Enygma has sufficient licensing authority.

Third-party components remain governed by their original licenses in Community
and Enterprise distributions.

## License Compatibility vs Security

This file records attribution and license provenance.

It does not certify that a particular dependency version is free from security
vulnerabilities, nor does it substitute for legal review of a specific
distribution artifact.
