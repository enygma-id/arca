# ARCA 3D Web Viewer Integration Guide

Guide for visualizing ARCA outputs (LOD 1.3 GeoJSON and full-detail glTF/GLB) using **MapLibre GL JS**, **Deck.gl**, and **CesiumJS**.

---

## 1. Output Data Specifications

ARCA exports two primary 3D data formats alongside a metadata envelope:

### 1.1 LOD 1.3 Extruded Footprints (`.geojson`)

Feature collection containing storey plateaus in WGS 84 (`EPSG:4326`):

```json
{
  "type": "Feature",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[119.415, -5.149, 0.0], ...]]
  },
  "properties": {
    "building_id": "mall-01",
    "name": "Level 1",
    "base_z": 0.0,
    "top_z": 5.4,
    "height": 5.4,
    "plan_area_m2": 3582.5,
    "crs": "EPSG:32750",
    "georef_method": "ifc_map_conversion"
  }
}
```

Key attributes for 3D extrusion:
- `base_z`: Bottom elevation of storey in meters (relative to project vertical datum).
- `top_z`: Top elevation of storey in meters.
- `height` (or `tinggi_m`): Storey thickness in meters (`top_z - base_z`).

### 1.2 Full-Detail 3D Asset (`.glb`)

- Standard binary glTF 2.0 (`.glb`).
- Coordinate system: Local topocentric metric coordinates (X = East, Y = Up, Z = South; standard glTF Y-up convention).
- Geometry origin `(0, 0, 0)` corresponds to the site anchor point defined in `metadata.json`.

### 1.3 Metadata Anchor (`metadata.json`)

```json
{
  "anchor": {
    "lon": 119.4151,
    "lat": -5.1492599
  },
  "georeference": {
    "crs_epsg": 32750,
    "origin_orthogonal_height": 0.0,
    "rotation_rad": 0.0
  }
}
```

### 1.4 Basemap Nasional: BIG Rupabumi Indonesia (RBI)

ARCA uses the official **Badan Informasi Geospasial (BIG)** Rupabumi Indonesia tile service as the default basemap:

- **Tile URL Template:**  
  `https://geoservices.big.go.id/rbi/rest/services/BASEMAP/Rupabumi_Indonesia/MapServer/tile/{z}/{y}/{x}`
- **Tile Format:** Standard Web Mercator (EPSG:3857) XYZ raster tiles (256×256 px).
- **Native Zoom:** Level 0 through 16.
- **Attribution:** `© Badan Informasi Geospasial (BIG)`

All viewer examples below are configured to use Peta BIG natively. Each example initializes with a nationwide overview of Indonesia (`[118.0, -2.5]`) and includes an interactive **"Go to Target"** button that dynamically computes the bounding box/center from the loaded GeoJSON data and flies smoothly to it.

---

## 2. MapLibre GL JS Integration

MapLibre GL JS supports native vector polygon extrusion via `fill-extrusion` layers and custom WebGL/Three.js layers for 3D models.

### 2.1 Extruding GeoJSON Footprints

Use `fill-extrusion-base` and `fill-extrusion-height` mapped to `base_z` and `top_z`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>ARCA GeoJSON - MapLibre GL JS</title>
  <script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
  <link rel="stylesheet" href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" />
  <style>
    body { margin: 0; padding: 0; }
    #map { position: absolute; top: 0; bottom: 0; width: 100%; }
    .btn-target {
      position: absolute;
      top: 16px;
      right: 16px;
      z-index: 1000;
      background: #0f172a;
      color: #f8fafc;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 10px 16px;
      font-family: sans-serif;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
      display: flex;
      align-items: center;
      gap: 8px;
      transition: all 0.2s ease;
    }
    .btn-target:hover {
      background: #1e293b;
      border-color: #38bdf8;
      transform: translateY(-1px);
    }
  </style>
</head>
<body>
<div id="map"></div>
<button id="btn-target" class="btn-target">Go to Target</button>
<script>
  let buildingBounds = null;

  const BIG_STYLE = {
    version: 8,
    sources: {
      'big-rbi': {
        type: 'raster',
        tiles: [
          'https://geoservices.big.go.id/rbi/rest/services/BASEMAP/Rupabumi_Indonesia/MapServer/tile/{z}/{y}/{x}'
        ],
        tileSize: 256,
        maxzoom: 16,
        attribution: '© Badan Informasi Geospasial (BIG)'
      }
    },
    layers: [
      {
        id: 'big-rbi-layer',
        type: 'raster',
        source: 'big-rbi',
        paint: { 'raster-fade-duration': 0 }
      }
    ]
  };

  // Initial camera view: Overview of Indonesia
  const map = new maplibregl.Map({
    container: 'map',
    style: BIG_STYLE,
    center: [118.0, -2.5], // Center of Indonesia
    zoom: 4.8,
    maxZoom: 20,
    pitch: 0,
    bearing: 0,
    antialias: true
  });

  map.on('load', async () => {
    // 1. Fetch GeoJSON dan hitung bounding box dinamis
    const res = await fetch('./lod1_3_reference.geojson');
    const geojsonData = await res.json();

    const bounds = new maplibregl.LngLatBounds();
    geojsonData.features.forEach(f => {
      const ring = f.geometry.type === 'Polygon' ? f.geometry.coordinates[0] : f.geometry.coordinates.flat(1);
      ring.forEach(([lon, lat]) => bounds.extend([lon, lat]));
    });
    buildingBounds = bounds;

    // 2. Tambahkan sumber data dan layer fill-extrusion
    map.addSource('arca-building', {
      type: 'geojson',
      data: geojsonData
    });

    map.addLayer({
      id: 'arca-storeys',
      type: 'fill-extrusion',
      source: 'arca-building',
      paint: {
        'fill-extrusion-color': [
          'interpolate', ['linear'], ['get', 'top_z'],
          0, '#38bdf8',
          20, '#6366f1',
          40, '#a855f7'
        ],
        'fill-extrusion-base': ['get', 'base_z'],
        'fill-extrusion-height': ['get', 'top_z'],
        'fill-extrusion-opacity': 0.85
      }
    });
  });

  // Go to target: otomatis terbang & fit sesuai bounding box koordinat GeoJSON
  document.getElementById('btn-target').addEventListener('click', () => {
    if (buildingBounds && !buildingBounds.isEmpty()) {
      map.fitBounds(buildingBounds, {
        pitch: 60,
        bearing: -20,
        maxZoom: 18,
        duration: 2500,
        padding: 60
      });
    }
  });
</script>
</body>
</html>
```

### 2.2 Rendering 3D GLB with Three.js Custom Layer

MapLibre uses a Mercator projection internally. Convert model local coordinates to Mercator space using `maplibregl.MercatorCoordinate`:

```javascript
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';

function createThreeLayer(modelUrl, anchorLngLat, altitude = 0) {
  const modelAsMercatorCoordinate = maplibregl.MercatorCoordinate.fromLngLat(
    anchorLngLat,
    altitude
  );

  const modelTransform = {
    translateX: modelAsMercatorCoordinate.x,
    translateY: modelAsMercatorCoordinate.y,
    translateZ: modelAsMercatorCoordinate.z,
    rotateX: Math.PI / 2, // glTF Y-up to MapLibre Z-up
    rotateY: 0,
    rotateZ: 0,
    scale: modelAsMercatorCoordinate.meterInMercatorCoordinateUnits()
  };

  return {
    id: 'arca-3d-model',
    type: 'custom',
    renderingMode: '3d',
    onAdd: function (map, gl) {
      this.camera = new THREE.Camera();
      this.scene = new THREE.Scene();

      const light1 = new THREE.DirectionalLight(0xffffff, 1.2);
      light1.position.set(50, 100, 50);
      this.scene.add(light1);
      this.scene.add(new THREE.AmbientLight(0xffffff, 0.6));

      const loader = new GLTFLoader();
      loader.load(modelUrl, (gltf) => {
        this.scene.add(gltf.scene);
        map.triggerRepaint();
      });
      this.map = map;
      this.renderer = new THREE.WebGLRenderer({
        canvas: map.getCanvas(),
        context: gl,
        antialias: true
      });
      this.renderer.autoClear = false;
    },
    render: function (gl, matrix) {
      const rotationX = new THREE.Matrix4().makeRotationAxis(new THREE.Vector3(1, 0, 0), modelTransform.rotateX);
      const m = new THREE.Matrix4().fromArray(matrix);
      const l = new THREE.Matrix4()
        .makeTranslation(modelTransform.translateX, modelTransform.translateY, modelTransform.translateZ)
        .scale(new THREE.Vector3(modelTransform.scale, -modelTransform.scale, modelTransform.scale))
        .multiply(rotationX);

      this.camera.projectionMatrix = m.multiply(l);
      this.renderer.resetState();
      this.renderer.render(this.scene, this.camera);
      this.map.triggerRepaint();
    }
  };
}
```

---

## 3. Deck.gl Integration

Deck.gl handles large polygon datasets with high-performance WebGL/WebGPU instancing and offers direct glTF support via loaders.gl.

### 3.1 Complete Deck.gl HTML/JS Example

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>ARCA 3D - Deck.gl</title>
  <script src="https://unpkg.com/deck.gl@9.0.38/dist.min.js"></script>
  <script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
  <script src="https://unpkg.com/@loaders.gl/gltf@4.3.3/dist/dist.min.js"></script>
  <link rel="stylesheet" href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" />
  <style>
    body { margin: 0; padding: 0; }
    #container { position: absolute; top: 0; bottom: 0; width: 100%; }
    .btn-target {
      position: absolute;
      top: 16px;
      right: 16px;
      z-index: 1000;
      background: #0f172a;
      color: #f8fafc;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 10px 16px;
      font-family: sans-serif;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
      display: flex;
      align-items: center;
      gap: 8px;
      transition: all 0.2s ease;
    }
    .btn-target:hover {
      background: #1e293b;
      border-color: #38bdf8;
      transform: translateY(-1px);
    }
  </style>
</head>
<body>
<div id="container"></div>
<button id="btn-target" class="btn-target">Go to Target</button>
<script>
  let targetCenter = [119.4151, -5.14926]; // default fallback

  // Peta BIG Rupabumi Indonesia Style
  const BIG_STYLE = {
    version: 8,
    sources: {
      'big-rbi': {
        type: 'raster',
        tiles: [
          'https://geoservices.big.go.id/rbi/rest/services/BASEMAP/Rupabumi_Indonesia/MapServer/tile/{z}/{y}/{x}'
        ],
        tileSize: 256,
        maxzoom: 16,
        attribution: '© Badan Informasi Geospasial (BIG)'
      }
    },
    layers: [
      {
        id: 'big-rbi-layer',
        type: 'raster',
        source: 'big-rbi'
      }
    ]
  };

  // Initial camera view: Overview of Indonesia
  const deckgl = new deck.DeckGL({
    container: 'container',
    mapLib: maplibregl,
    mapStyle: BIG_STYLE,
    initialViewState: {
      longitude: 118.0, // Center of Indonesia
      latitude: -2.5,
      zoom: 4.8,
      maxZoom: 20,
      pitch: 0,
      bearing: 0
    },
    controller: true
  });

  // Load GeoJSON & hitung titik pusat dinamis
  async function loadData() {
    const res = await fetch('./lod1_3_reference.geojson');
    const geojsonData = await res.json();

    let minLon = Infinity, maxLon = -Infinity, minLat = Infinity, maxLat = -Infinity;
    geojsonData.features.forEach(f => {
      const ring = f.geometry.type === 'Polygon' ? f.geometry.coordinates[0] : f.geometry.coordinates.flat(1);
      ring.forEach(([lon, lat]) => {
        if (lon < minLon) minLon = lon;
        if (lon > maxLon) maxLon = lon;
        if (lat < minLat) minLat = lat;
        if (lat > maxLat) maxLat = lat;
      });
    });
    if (minLon !== Infinity) {
      targetCenter = [(minLon + maxLon) / 2, (minLat + maxLat) / 2];
    }

    // Layer 1: LOD 1.3 GeoJSON Extrusion
    const geojsonLayer = new deck.GeoJsonLayer({
      id: 'arca-geojson',
      data: geojsonData,
      extruded: true,
      wireframe: true,
      getElevation: f => (f.properties.top_z || 0) - (f.properties.base_z || 0),
      getFillColor: [56, 189, 248, 200],
      getLineColor: [255, 255, 255, 120],
      pickable: true
    });

    // Layer 2: Full-Detail GLB Model
    const glbLayer = new deck.ScenegraphLayer({
      id: 'arca-glb',
      scenegraph: './render/model.glb',
      data: [{ position: [targetCenter[0], targetCenter[1], 0] }],
      getPosition: d => d.position,
      getOrientation: [0, 0, 90],
      sizeScale: 1,
      pickable: true,
      loaders: [loaders.GLTFLoader]
    });

    deckgl.setProps({ layers: [geojsonLayer, glbLayer] });
  }

  loadData();

  // Go to target: otomatis terbang ke koordinat pusat GeoJSON
  document.getElementById('btn-target').addEventListener('click', () => {
    deckgl.setProps({
      initialViewState: {
        longitude: targetCenter[0],
        latitude: targetCenter[1],
        zoom: 17.5,
        pitch: 55,
        bearing: 30,
        transitionDuration: 2500,
        transitionInterpolator: new deck.FlyToInterpolator()
      }
    });
  });
  document.getElementById('container').addEventListener('contextmenu', e => e.preventDefault());
</script>
</body>
</html>
```

---

## 4. CesiumJS Integration

CesiumJS renders 3D geospatial entities directly on an accurate WGS 84 ellipsoid with full terrain integration.

### 4.1 Extruding Footprints (`Cesium.Entity`)

Cesium uses absolute ellipsoidal heights:

```javascript
fetch('./lod1_3_reference.geojson')
  .then(res => res.json())
  .then(geojson => {
    geojson.features.forEach(feature => {
      const coords = feature.geometry.coordinates[0];
      const flatPositions = [];
      coords.forEach(([lon, lat]) => {
        flatPositions.push(lon, lat);
      });

      const baseZ = feature.properties.base_z || 0.0;
      const topZ = feature.properties.top_z || 5.0;

      viewer.entities.add({
        name: feature.properties.name || 'Storey',
        polygon: {
          hierarchy: Cesium.Cartesian3.fromDegreesArray(flatPositions),
          height: baseZ,
          extrudedHeight: topZ,
          material: Cesium.Color.fromCssColorString('#38bdf8').withAlpha(0.7),
          outline: true,
          outlineColor: Cesium.Color.WHITE
        },
        properties: feature.properties
      });
    });
  });
```

### 4.2 Placing 3D GLB via East-North-Up (ENU) Transform

Because glTF geometry generated by ARCA is in local meters relative to the anchor point, position the model using `Cesium.Transforms.eastNorthUpToFixedFrame`:

```javascript
async function loadArcaGlb(viewer, glbUrl, lon, lat, height = 0) {
  const origin = Cesium.Cartesian3.fromDegrees(lon, lat, height);
  const modelMatrix = Cesium.Transforms.eastNorthUpToFixedFrame(origin);

  try {
    const model = await Cesium.Model.fromGltfAsync({
      url: glbUrl,
      modelMatrix: modelMatrix,
      scale: 1.0,
      minimumPixelSize: 64,
      maximumScale: 20000
    });

    viewer.scene.primitives.add(model);
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(lon, lat - 0.002, height + 150),
      orientation: {
        heading: Cesium.Math.toRadians(0),
        pitch: Cesium.Math.toRadians(-35),
        roll: 0.0
      }
    });
  } catch (err) {
    console.error('Failed to load GLB model:', err);
  }
}
```

### 4.3 Complete Standalone CesiumJS Example

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>ARCA 3D - CesiumJS</title>
  <script src="https://cesium.com/downloads/cesiumjs/releases/1.120/Build/Cesium/Cesium.js"></script>
  <link href="https://cesium.com/downloads/cesiumjs/releases/1.120/Build/Cesium/Widgets/widgets.css" rel="stylesheet" />
  <style>
    body { margin: 0; padding: 0; }
    #cesiumContainer { position: absolute; top: 0; bottom: 0; width: 100%; }
    .btn-target {
      position: absolute;
      top: 16px;
      right: 16px;
      z-index: 1000;
      background: #0f172a;
      color: #f8fafc;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 10px 16px;
      font-family: sans-serif;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
      display: flex;
      align-items: center;
      gap: 8px;
      transition: all 0.2s ease;
    }
    .btn-target:hover {
      background: #1e293b;
      border-color: #38bdf8;
      transform: translateY(-1px);
    }
  </style>
</head>
<body>
<div id="cesiumContainer"></div>
<button id="btn-target" class="btn-target">Go to Target</button>
<script>
  // Peta BIG Rupabumi Indonesia Imagery Provider
  const bigImagery = new Cesium.UrlTemplateImageryProvider({
    url: 'https://geoservices.big.go.id/rbi/rest/services/BASEMAP/Rupabumi_Indonesia/MapServer/tile/{z}/{y}/{x}',
    minimumLevel: 0,
    maximumLevel: 16,
    credit: 'Badan Informasi Geospasial (BIG)'
  });

  const viewer = new Cesium.Viewer('cesiumContainer', {
    imageryProvider: bigImagery,
    terrainProvider: new Cesium.EllipsoidTerrainProvider(),
    animation: false,
    timeline: false,
    baseLayerPicker: false
  });

  // Initial camera view: Overview of Indonesia
  viewer.camera.setView({
    destination: Cesium.Cartesian3.fromDegrees(118.0, -2.5, 4500000), // Overview of Indonesia
    orientation: {
      heading: 0.0,
      pitch: Cesium.Math.toRadians(-90),
      roll: 0.0
    }
  });

  let targetDataSource = null;

  // Load GeoJSON dan terapkan ekstrusi 3D
  Cesium.GeoJsonDataSource.load('./lod1_3_reference.geojson', {
    clampToGround: false
  }).then(dataSource => {
    targetDataSource = dataSource;
    viewer.dataSources.add(dataSource);

    for (const entity of dataSource.entities.values) {
      if (entity.polygon) {
        const p = entity.properties;
        const baseZ = p.base_z ? p.base_z.getValue() : 0.0;
        const topZ = p.top_z ? p.top_z.getValue() : 5.0;
        entity.polygon.height = baseZ;
        entity.polygon.extrudedHeight = topZ;
        entity.polygon.material = Cesium.Color.fromCssColorString('#38bdf8').withAlpha(0.7);
        entity.polygon.outline = true;
        entity.polygon.outlineColor = Cesium.Color.WHITE;
      }
    }
  });

  const ANCHOR_LON = 119.4151;
  const ANCHOR_LAT = -5.14926;
  const ANCHOR_HEIGHT = 0.0;

  // Add 3D Model
  const origin = Cesium.Cartesian3.fromDegrees(ANCHOR_LON, ANCHOR_LAT, ANCHOR_HEIGHT);
  const modelMatrix = Cesium.Transforms.eastNorthUpToFixedFrame(origin);

  Cesium.Model.fromGltfAsync({
    url: './render/model.glb',
    modelMatrix: modelMatrix,
    scale: 1.0
  }).then(model => {
    viewer.scene.primitives.add(model);
  });

  // Go to target: otomatis terbang & fokus sesuai batas koordinat GeoJSON
  document.getElementById('btn-target').addEventListener('click', () => {
    if (targetDataSource) {
      viewer.flyTo(targetDataSource, {
        duration: 2.5,
        offset: new Cesium.HeadingPitchRange(
          Cesium.Math.toRadians(0),
          Cesium.Math.toRadians(-35),
          250
        )
      });
    }
  });
</script>
</body>
</html>
```

---

## 5. Technical Pitfalls and Troubleshooting

### 5.1 Height Interpretation (Relative vs Absolute)
- **MapLibre GL JS**: `fill-extrusion-base` is the bottom elevation; `fill-extrusion-height` is the **top elevation** (absolute from ground), **not** the relative storey thickness. Setting `height = height` instead of `top_z` makes the 10th floor render on the ground!
- **Deck.gl**: `getElevation` specifies extrusion height above `base_z`. If using standard `GeoJsonLayer`, use `getElevation: f => f.properties.top_z - f.properties.base_z`.
- **CesiumJS**: `height` is the base elevation; `extrudedHeight` is the top elevation.

### 5.2 Y-up vs Z-up Coordinate Alignment
- ARCA exports standard glTF 2.0 where $+Y$ is Up, $+X$ is East, and $-Z$ is North.
- MapLibre and Three.js expect coordinate transformations (`rotateX: Math.PI / 2`).
- Deck.gl `ScenegraphLayer` automatically handles glTF Y-up conventions.
- CesiumJS `eastNorthUpToFixedFrame` maps glTF $+X \to \text{East}$, $+Y \to \text{North}$, $+Z \to \text{Up}$. If your model appears tilted $90^\circ$, apply a local pitch rotation matrix (`Cesium.Matrix3.fromRotationX(Math.PI / 2)`).

### 5.3 CORS and Local File Access
When loading `.geojson` or `.glb` via `fetch` or WebGL loaders from `file://`, modern browsers block cross-origin requests. Use a lightweight local HTTP server:
```bash
# Python
python3 -m http.server 8000

# Node.js
npx serve .
```
