# Third-Party Software Notices

ARCA Community Edition is licensed under `AGPL-3.0-only` for covered ARCA-owned
source.

Third-party software remains subject to its respective upstream copyright,
license, attribution, patent, and NOTICE terms. Use of a dependency by ARCA
does not relicense that dependency under the ARCA AGPL.

The current founding implementation was audited from the working Python
prototype. The directly imported/materially used external components are:

- OpenSKP;
- NumPy;
- Shapely.

OpenSKP 1.2.0 declares NumPy, Trimesh, and Shapely as runtime dependencies.
Shapely binary distributions may bundle GEOS.

The files in [`third-party/licenses/`](./third-party/licenses/) preserve a
founding provenance snapshot of the relevant license texts/notices.

Captured versions identify the source of those license files; they are **not**
dependency pins unless a future dependency manifest explicitly pins them.

## License and Role Summary

| Component | License / Basis | ARCA Relationship | Founding Role |
|---|---|---|---|
| OpenSKP | MIT | Direct | Reads/builds SKP scene data and provides IFC4 export in the SKP adapter path. |
| NumPy | BSD-3-Clause plus bundled notices | Direct; also OpenSKP dependency | Numerical arrays, transforms, vector/matrix geometry processing. |
| Shapely | BSD-3-Clause | Direct; also OpenSKP dependency | Polygon topology, projected unions, topology-preserving simplification/generalization. |
| GEOS | LGPL-2.1 | Native library commonly bundled with Shapely binary distributions | Geometry engine used underneath Shapely. |
| Trimesh | MIT | Transitive OpenSKP runtime dependency | Part of the OpenSKP Python runtime dependency graph; ARCA code does not currently import Trimesh directly. |
| IFC4 | Open standard / buildingSMART ecosystem | Input/intermediate standard, not a Python dependency | BIM exchange representation consumed by the ARCA workflow. |
| GeoJSON | IETF RFC 7946 family / open interchange format | Output representation | Current GIS-native output family. |

## OpenSKP

**Source:** https://github.com/iamahsanmehmood/openskp  
**PyPI:** https://pypi.org/project/openskp/  
**License:** MIT  
**License file:** [`third-party/licenses/openskp-LICENSE.txt`](./third-party/licenses/openskp-LICENSE.txt)

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
**License file:** [`third-party/licenses/numpy-LICENSE.txt`](./third-party/licenses/numpy-LICENSE.txt)

ARCA uses NumPy for numerical geometry processing, coordinate transforms,
matrix operations, and mesh/face calculations.

The preserved NumPy license file includes notices applicable to the reference
binary distribution from which it was captured.

## Shapely

**Source:** https://github.com/shapely/shapely  
**License:** BSD-3-Clause  
**License file:** [`third-party/licenses/shapely-LICENSE.txt`](./third-party/licenses/shapely-LICENSE.txt)

ARCA uses Shapely for topology-preserving planar geometry work, including
polygon unions and simplification used by generalized building
representations.

## GEOS

**Source:** https://libgeos.org/  
**License basis in captured Shapely binary:** LGPL-2.1  
**License file:** [`third-party/licenses/shapely-GEOS-LICENSE.txt`](./third-party/licenses/shapely-GEOS-LICENSE.txt)

GEOS is not imported directly by ARCA Python code, but may be present as the
native geometry engine distributed with Shapely binaries.

Binary redistributors must preserve the applicable GEOS terms.

## Trimesh

**Source:** https://github.com/mikedh/trimesh  
**License:** MIT  
**License file:** [`third-party/licenses/trimesh-LICENSE.txt`](./third-party/licenses/trimesh-LICENSE.txt)

The audited ARCA Python files do not currently import Trimesh directly.
It is recorded because OpenSKP 1.2.0 declares Trimesh as a Python runtime
dependency.

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
