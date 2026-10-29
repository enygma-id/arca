# CityGML & CityJSON Specification & Integration Guide

This document describes the Open Geospatial Consortium (OGC) 3D GIS standards **CityGML** and **CityJSON**, architectural comparisons, and their pure mathematical implementation in ARCA.

---

## 1. Format Comparison

| Metric / Feature | CityGML 2.0 | CityJSON 1.1 |
| :--- | :--- | :--- |
| **Standard Baseline** | OGC Encoding Standard (GML 3.1.1 / XML) | OGC Community Standard (JSON-based) |
| **File Architecture** | Deeply nested XML element trees | Flat JSON Object with global dictionary indices |
| **Coordinate Storage** | Repeated coordinate tuples in every polygon (`gml:posList`) | Shared global `vertices` array; polygons reference integer indices |
| **Quantization** | Text-based floating-point decimals | Integer millimeter quantization via affine `transform` (`scale` & `translate`) |
| **File Footprint** | Large (repetitive XML opening and closing tags) | Compact (6x to 10x smaller than CityGML) |
| **Target Consumers** | QGIS, ArcGIS Pro, FME, 3DCityDB, government cadastre pipelines | Modern Web 3D GIS (Three.js, Cesium), Python, Node.js, REST APIs |

---

## 2. CityJSON (v1.1, LOD 2.0)

### Concept & Objectives
CityJSON was designed by the 3D Geoinformation Group at TU Delft to resolve the syntactic verbosity and parsing overhead of XML-based CityGML. It preserves the exact semantic model of CityGML while adopting lightweight, web-native JSON structures.

### Data Structure in ARCA (`building.city.json`)
```json
{
  "type": "CityJSON",
  "version": "1.1",
  "CityObjects": {
    "bldg_dataset_id": {
      "type": "Building",
      "attributes": {
        "measuredHeight": 32.5,
        "storeysAboveGround": 10
      },
      "geometry": [
        {
          "type": "MultiSurface",
          "lod": "2.0",
          "boundaries": [
            [[0, 1, 2]],
            [[2, 3, 0]]
          ],
          "semantics": {
            "surfaces": [
              { "type": "RoofSurface" },
              { "type": "WallSurface" },
              { "type": "GroundSurface" },
              { "type": "OuterFloorSurface" }
            ],
            "values": [0, 1]
          }
        }
      ]
    }
  },
  "vertices": [
    [0, 0, 10000],
    [10000, 0, 10000],
    [10000, 10000, 10000],
    [0, 10000, 10000]
  ],
  "transform": {
    "scale": [0.001, 0.001, 0.001],
    "translate": [700000.0, 9300000.0, 15.0]
  },
  "metadata": {
    "referenceSystem": "urn:ogc:def:crs:EPSG::32748"
  }
}
```

### Quantization & Vertex Deduplication
- **$O(1)$ Spatial Hash Table**: Global 3D coordinates are quantized to millimeter integer precision:
  $$ix = \lfloor (x - translate_x) / scale_x \rceil$$
  Duplicate vertices are detected via integer hash keys `(ix, iy, iz)` and eliminated in $O(1)$ time.
- **Payload Compression**: Shared vertices between walls, roofs, and slabs are referenced solely by index numbers, eliminating geometry redundancy.

---

## 3. CityGML (v2.0, LOD 2.0)

### Concept & Objectives
CityGML v2.0 is an international de jure OGC standard for the storage and exchange of 3D virtual city models. It is widely mandated for municipal 3D cadastre, legal land administration, and national spatial data infrastructures (SDIs).

### Data Structure in ARCA (`building.gml`)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<core:CityModel xmlns:core="http://www.opengis.net/citygml/2.0"
                xmlns:bldg="http://www.opengis.net/citygml/building/2.0"
                xmlns:gml="http://www.opengis.net/gml"
                xmlns:xlink="http://www.w3.org/1999/xlink"
                xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                xsi:schemaLocation="http://www.opengis.net/citygml/building/2.0 http://schemas.opengis.net/citygml/building/2.0/building.xsd">
  <gml:boundedBy>
    <gml:Envelope srsName="urn:ogc:def:crs:EPSG::32748">
      <gml:lowerCorner>699980.000 9299950.000 15.000</gml:lowerCorner>
      <gml:upperCorner>700050.000 9300050.000 47.500</gml:upperCorner>
    </gml:Envelope>
  </gml:boundedBy>
  <core:cityObjectMember>
    <bldg:Building gml:id="bldg_model_1">
      <gml:name>Building A</gml:name>
      <bldg:measuredHeight uom="urn:ogc:def:uom:OGC:1.0:metre">32.50</bldg:measuredHeight>
      <bldg:storeysAboveGround>10</bldg:storeysAboveGround>
      <bldg:boundedBy>
        <bldg:RoofSurface gml:id="RoofSurface_bldg_model_1">
          <bldg:lod2MultiSurface>
            <gml:MultiSurface srsName="urn:ogc:def:crs:EPSG::32748">
              <gml:surfaceMember>
                <gml:Polygon gml:id="poly_bldg_model_1_1">
                  <gml:exterior>
                    <gml:LinearRing>
                      <gml:posList>
                        699980.000 9299950.000 47.500 700020.000 9299950.000 47.500 700000.000 9300000.000 47.500 699980.000 9299950.000 47.500
                      </gml:posList>
                    </gml:LinearRing>
                  </gml:exterior>
                </gml:Polygon>
              </gml:surfaceMember>
            </gml:MultiSurface>
          </bldg:lod2MultiSurface>
        </bldg:RoofSurface>
      </bldg:boundedBy>
    </bldg:Building>
  </core:cityObjectMember>
</core:CityModel>
```

### Implementation Details
- **Linear Ring Closure**: Conforming to GML 3.1.1 geometry rules, the first and last point coordinates in `<gml:posList>` are identical ($P_0 \to P_1 \to P_2 \to P_0$).
- **$O(1)$ Memory Streaming Writer**: XML output is streamed directly to disk chunk-by-chunk without constructing an in-memory XML DOM tree. This avoids heap exhaustion when converting complex, high-polygon building models.

---

## 4. Semantic Surface Mapping (LOD 2.0)

ARCA maps source BIM entities (IFC classes and SketchUp tags) to standard OGC LOD 2.0 boundary surfaces:

| Source Entity (IFC / SKP Tag) | OGC Semantic Surface | Classification Logic |
| :--- | :--- | :--- |
| `IfcRoof` | `RoofSurface` | Pitched and flat roof boundaries |
| `IfcWall`, `IfcWallStandardCase` | `WallSurface` | Exterior vertical envelope walls |
| `IfcSlab` (Ground contact, Normal $\vec{n}_z < -0.7$) | `GroundSurface` | Downward-facing bottom slab at lowest elevation |
| `IfcSlab` (Upper floors) | `OuterFloorSurface` | Exposed floor slabs, balconies, and overhangs |
| `IfcWindow`, `IfcDoor` | `WallSurface` / Sub-surface | Integrated into wall surface boundaries at LOD 2.0 |
| `IfcColumn`, `IfcBeam`, `IfcStair` | `WallSurface` | Exterior structural components |

Surface normal vectors are computed via cross product of polygon edge vectors ($e_1 \times e_2$).

---

## 5. Usage in ARCA

### Via Command-Line Interface (`arca run`)
Select the generation target using the `--generate` flag:

```bash
# Export CityJSON only
uv run arca run model.ifc --generate cityjson --out outputs/

# Export CityGML (XML) only
uv run arca run model.ifc --generate citygml --out outputs/

# Export all outputs (GeoJSON LOD 1.3, GLB, CityJSON, CityGML)
uv run arca run model.ifc --generate all --out outputs/
```

### Via Web Studio & REST API
1. Launch Web Studio with `arca serve`.
2. In the **Output Generation Target** dropdown, select CityJSON or CityGML.
3. Download generated files directly via action buttons or endpoints:
   - `GET /api/download?dataset={id}&file=building.city.json`
   - `GET /api/download?dataset={id}&file=building.gml`

---

## 6. Downstream Verification

- **CityJSON**:
  - Web Viewer & Validator: Open [CityJSON Ninja](https://ninja.cityjson.org/) and drag-and-drop the `.city.json` file.
  - CLI Validation: `cjio building.city.json validate`
- **CityGML**:
  - Desktop GIS: Open directly in **QGIS** (using the CityGML plugin or native OGR provider) and **ArcGIS Pro**.
  - ETL Pipelines: Fully compatible with **FME** workflows and **3DCityDB** imports.
