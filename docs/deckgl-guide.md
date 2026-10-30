# Deck.gl Integration Guide: Per-Building (Modular) & Whole-Precinct Visualization

Technical guide for visualizing ARCA 3D outputs (LOD 1.3 GeoJSON and glTF/GLB) using **Deck.gl v9** in both per-building (modular) and entire precinct (merged) modes.

---

## 1. ARCA Output Structure

When ARCA processes multi-building inputs in Split mode, the output directory follows a modular layout:

```text
outputs/<dataset>/
├── building.geojson                  # Master GeoJSON (entire precinct)
├── metadata.json                     # WGS84 anchor & master georeference metadata
├── render/
│   ├── model.glb                     # Master GLB (entire precinct)
│   └── model.geojson                 # Master georeference point & heading
└── buildings/
    ├── 101/                          # Sub-building 1 (e.g., Tower A)
    │   ├── building.geojson          # LOD 1.3 footprints for Tower A
    │   ├── metadata.json             # Tower A anchor & bounding box
    │   └── render/
    │       ├── model.glb             # 3D detail mesh for Tower A
    │       └── model.geojson         # WGS84 placement anchor for Tower A
    └── 102/                          # Sub-building 2 (e.g., Podium B)
        ├── building.geojson
        └── render/
            ├── model.glb
            └── model.geojson
```

---

## 2. Per-Building GeoJSON Visualization (`GeoJsonLayer`)

### 2.1 3D Elevation Attributes

Every ARCA GeoJSON feature includes standard elevation properties:
- `building_id`: Unique building identifier (`"101"`, `"102"`).
- `base_z`: Storey base elevation in meters (ellipsoidal / local project datum).
- `top_z`: Storey roof elevation in meters.
- `height` / `tinggi_m`: Mass extrusion thickness (`top_z - base_z`).

### 2.2 Deck.gl Layer Configuration

```javascript
import { GeoJsonLayer } from '@deck.gl/layers';

function createBuildingGeoJsonLayer({ data, selectedBuildingId = null }) {
  return new GeoJsonLayer({
    id: 'arca-buildings-geojson',
    data,
    extruded: true,
    filled: true,
    stroked: true,
    wireframe: false,
    lineWidthMinPixels: 1,

    // Compute extrusion relative to base_z
    getElevation: f => {
      const p = f.properties || {};
      const baseZ = Number(p.base_z || 0);
      const topZ = Number(p.top_z ?? p.height ?? 0);
      return Math.max(0, topZ - baseZ);
    },

    // Color: highlight selected building, fallback to neutral slate
    getFillColor: f => {
      const bId = String(f.properties?.building_id || '');
      if (selectedBuildingId && bId === String(selectedBuildingId)) {
        return [242, 174, 73, 230]; // Selected (amber)
      }
      return [174, 185, 198, 220]; // Default (slate)
    },
    getLineColor: [58, 68, 76, 200],

    // Reactive update triggers on selection change
    updateTriggers: {
      getFillColor: [selectedBuildingId]
    },

    pickable: true,
    autoHighlight: true,
    highlightColor: [94, 230, 184, 200]
  });
}
```

### 2.3 Two Approaches for Per-Building Rendering:
1. **Direct File Loading (Dedicated):**
   `data: './outputs/dataset/buildings/101/building.geojson'`
2. **Client-side Filtering from Master Precinct:**
   ```javascript
   const master = await fetch('./outputs/dataset/building.geojson').then(r => r.json());
   // Filter features by building ID:
   const towerA = {
     ...master,
     features: master.features.filter(f => f.properties.building_id === '101')
   };
   ```

---

## 3. Per-Building GLB Visualization (`ScenegraphLayer`)

### 3.1 WGS84 Anchor Coordinates

Each sub-building includes a companion `render/model.geojson`:
```json
{
  "type": "FeatureCollection",
  "features": [{
    "type": "Point",
    "coordinates": [106.8275, -6.1755, 12.0],
    "properties": {
      "heading": 45.0,
      "scale": 1.0,
      "model_url": "./model.glb"
    }
  }]
}
```

### 3.2 Deck.gl Layer Configuration

Place per-building `.glb` assets using metric offsets relative to the WGS84 anchor:

```javascript
import { ScenegraphLayer } from '@deck.gl/mesh-layers';
import { COORDINATE_SYSTEM } from '@deck.gl/core';
import { registerLoaders } from '@loaders.gl/core';
import { GLTFLoader } from '@loaders.gl/gltf';

registerLoaders([GLTFLoader]);

function createBuildingGlbLayer({ id, glbUrl, anchorCoords, heading = 0, scale = 1 }) {
  const [lon, lat, alt] = anchorCoords;

  return new ScenegraphLayer({
    id: `building-glb-${id}`,
    data: [{ position: [0, 0, 0] }],
    scenegraph: glbUrl,
    
    // Metric coordinate system anchored to WGS84 point
    coordinateSystem: COORDINATE_SYSTEM.METER_OFFSETS,
    coordinateOrigin: [lon, lat, alt || 0],
    
    getPosition: d => d.position,
    
    // Orientation: [pitch, yaw, roll]
    getOrientation: () => [0, -heading, 90],
    sizeScale: scale,
    _lighting: 'pbr',
    pickable: true
  });
}
```

---

## 4. Complete Standalone Example: Interactive Building Toggle

Complete standalone HTML/JS template supporting basemaps and interactive building switching:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>ARCA 3D - Deck.gl Per-Building</title>
  <script src="https://unpkg.com/deck.gl@9.0.38/dist.min.js"></script>
  <script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
  <script src="https://unpkg.com/@loaders.gl/gltf@4.3.3/dist/dist.min.js"></script>
  <link rel="stylesheet" href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" />
  <style>
    body { margin: 0; padding: 0; font-family: sans-serif; }
    #container { position: absolute; top: 0; bottom: 0; width: 100%; }
    .ui-panel {
      position: absolute;
      top: 16px;
      left: 16px;
      z-index: 1000;
      background: rgba(15, 23, 42, 0.9);
      color: #f8fafc;
      padding: 12px 16px;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }
    select, button {
      background: #1e293b;
      color: #f8fafc;
      border: 1px solid #334155;
      padding: 6px 10px;
      border-radius: 4px;
      font-size: 13px;
      cursor: pointer;
    }
  </style>
</head>
<body>
<div id="container"></div>

<div class="ui-panel">
  <label for="buildingSelect"><b>Building Scope:</b></label>
  <select id="buildingSelect">
    <option value="ALL">Entire Precinct</option>
    <option value="101">Tower A (101)</option>
    <option value="102">Podium B (102)</option>
  </select>
  
  <label style="margin-left: 12px;" for="formatSelect"><b>Format:</b></label>
  <select id="formatSelect">
    <option value="geojson">LOD 1.3 (GeoJSON)</option>
    <option value="glb">3D Detail (GLB)</option>
  </select>
</div>

<script>
  const BASE_PATH = './outputs/dataset';
  
  let currentBuilding = 'ALL';
  let currentFormat = 'geojson';
  let geojsonData = null;

  // Initialize Deck.gl
  const deckgl = new deck.DeckGL({
    container: 'container',
    mapLib: maplibregl,
    mapStyle: {
      version: 8,
      sources: {
        'osm': {
          type: 'raster',
          tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
          tileSize: 256,
          attribution: '© OpenStreetMap contributors'
        }
      },
      layers: [{ id: 'osm-layer', type: 'raster', source: 'osm' }]
    },
    initialViewState: {
      longitude: 106.8275,
      latitude: -6.1755,
      zoom: 17,
      pitch: 50,
      bearing: 15
    },
    controller: true
  });

  async function updateScene() {
    if (!geojsonData) {
      const res = await fetch(`${BASE_PATH}/building.geojson`);
      geojsonData = await res.json();
    }

    const layers = [];

    if (currentFormat === 'geojson') {
      // Filter per-building or whole precinct
      const filteredFeatures = currentBuilding === 'ALL'
        ? geojsonData.features
        : geojsonData.features.filter(f => String(f.properties.building_id) === String(currentBuilding));

      layers.push(new deck.GeoJsonLayer({
        id: 'buildings-geojson',
        data: { type: 'FeatureCollection', features: filteredFeatures },
        extruded: true,
        filled: true,
        wireframe: false,
        getElevation: f => Math.max(0, (f.properties.top_z ?? f.properties.height ?? 0) - (f.properties.base_z || 0)),
        getFillColor: [174, 185, 198, 220],
        getLineColor: [58, 68, 76, 200],
        pickable: true,
        autoHighlight: true,
        highlightColor: [94, 230, 184, 220]
      }));
    } else {
      // GLB Format: load per sub-building model or master precinct GLB
      const glbPath = currentBuilding === 'ALL'
        ? `${BASE_PATH}/render/model.glb`
        : `${BASE_PATH}/buildings/${currentBuilding}/render/model.glb`;

      // Read anchor from metadata
      const metaRes = await fetch(`${BASE_PATH}/metadata.json`).then(r => r.json());
      const lon = metaRes.anchor?.lon || 106.8275;
      const lat = metaRes.anchor?.lat || -6.1755;

      layers.push(new deck.ScenegraphLayer({
        id: `building-glb-${currentBuilding}`,
        data: [{ position: [0, 0, 0] }],
        scenegraph: glbPath,
        coordinateSystem: deck.COORDINATE_SYSTEM.METER_OFFSETS,
        coordinateOrigin: [lon, lat, 0],
        getPosition: d => d.position,
        getOrientation: () => [0, 0, 90],
        sizeScale: 1,
        _lighting: 'pbr',
        loaders: [loaders.GLTFLoader]
      }));
    }

    deckgl.setProps({ layers });
  }

  document.getElementById('buildingSelect').addEventListener('change', e => {
    currentBuilding = e.target.value;
    updateScene();
  });

  document.getElementById('formatSelect').addEventListener('change', e => {
    currentFormat = e.target.value;
    updateScene();
  });

  updateScene();
</script>
</body>
</html>
```
