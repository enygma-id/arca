import * as maplibregl from "maplibre-gl";
import * as THREE from "three";
import {GLTFLoader} from "three/addons/loaders/GLTFLoader.js";

const deck = window.deck;
const Cesium = window.Cesium;

const viewerNode = document.getElementById("viewer");
const statusNode = document.getElementById("status");
const engineLabel = document.getElementById("engineLabel");
const basemapSelect = document.getElementById("basemapSelect");
const basemapCaption = document.getElementById("basemapCaption");
const assetCard = document.getElementById("assetCard");
const selectedSummary = document.getElementById("selectedSummary");
const representationBadge = document.getElementById("representationBadge");
const representationHint = document.getElementById("representationHint");
const glbButton = document.getElementById("glbButton");

const metricNodes = {
  buildings: document.getElementById("metricBuildings"),
  loaded: document.getElementById("metricLoaded"),
  failed: document.getElementById("metricFailed"),
  features: document.getElementById("metricFeatures"),
  vertices: document.getElementById("metricVertices"),
  bytes: document.getElementById("metricBytes"),
  loadTime: document.getElementById("metricLoadTime")
};

const drawingMode =
  new URLSearchParams(location.search).get("mode") === "drawing";

const editNodes = {
  section: document.getElementById("drawingSection"),
  lat: document.getElementById("editLatitude"),
  lon: document.getElementById("editLongitude"),
  scale: document.getElementById("editScale"),
  rotate: document.getElementById("editRotate"),
  apply: document.getElementById("applyEdit"),
  save: document.getElementById("saveData")
};

const state = {
  config: {
    items: [],
    settings: {
      default_engine: "maplibre",
      default_basemap: "big",
      enabled_representations: ["lod1_3", "glb"],
      big_osm_gap_fill: false
    }
  },
  items: [],
  itemRecords: [],
  assets: [],
  assetById: new Map(),
  engine: "maplibre",
  basemap: "big",
  representation: "lod1_3",
  gisRepresentation: "lod1_3",
  renderer: null,
  selected: null,
  failedAssets: [],
  fallbackAssets: [],
  representationBusy: false,
  loadMetrics: {
    configMs: 0,
    overviewMs: 0,
    bytes: 0,
    features: 0,
    vertices: 0,
    loaded: 0,
    failed: 0,
    fallback: 0
  }
};

const EARTH_RADIUS_M = 6378137.0;

function metadataUrlCandidates(item) {
  const candidates = [];
  const push = value => {
    if (typeof value === "string" && value && !candidates.includes(value)) {
      candidates.push(value);
    }
  };

  // Prefer the explicitly configured metadata URL, but do not assume it is
  // the root metadata.json. Older data.json files sometimes point this field
  // to render/manifest.json. detailPlacementForAsset() accepts both schemas.
  push(item?.detail?.metadata);

  const lod13 = item?.geojson?.lod1_3;
  if (typeof lod13 === "string") {
    push(lod13.replace(
      /\/lod1_3\/building\.geojson(?:[?#].*)?$/i,
      "/metadata.json"
    ));
  }

  const glb = item?.detail?.glb;
  if (typeof glb === "string") {
    push(glb.replace(
      /\/render\/[^/?#]+(?:[?#].*)?$/i,
      "/metadata.json"
    ));
    push(glb.replace(
      /\/render\/[^/?#]+(?:[?#].*)?$/i,
      "/render/manifest.json"
    ));
  }

  return candidates;
}

function placementMetadata(data) {
  const anchor =
    data?.anchor ||
    data?.coordinate_system?.anchor_wgs84 ||
    data?.placement?.anchor ||
    null;
  const bounds =
    data?.bounds_local_m ||
    data?.placement?.bounds_local_m ||
    data?.source_local_bounds_m ||
    null;
  return {anchor, bounds};
}

function lodBaseZ(asset) {
  let min = Infinity;
  for (const feature of asset?.raw?.features || []) {
    const value = Number(feature?.properties?.base_z);
    if (Number.isFinite(value)) min = Math.min(min, value);
  }
  return Number.isFinite(min) ? min : 0;
}

function lonLatToLocalMeters(lon, lat, anchorLon, anchorLat) {
  const x = (
    (Number(lon) - Number(anchorLon)) * Math.PI / 180
  ) * EARTH_RADIUS_M * Math.cos(Number(anchorLat) * Math.PI / 180);
  const y = (
    (Number(lat) - Number(anchorLat)) * Math.PI / 180
  ) * EARTH_RADIUS_M;
  return [x, y];
}

async function detailPlacementForAsset(asset) {
  if (asset.detailPlacement) return asset.detailPlacement;

  const candidates = metadataUrlCandidates(asset.item);
  if (!candidates.length) {
    throw new Error(`Cannot infer placement metadata for ${asset.item.name}`);
  }

  const timeoutMs = Number(state.config?.settings?.item_timeout_ms ?? 12000);
  const sourceCenter = geojsonCenter(asset.raw);
  const errors = [];

  for (const metadataUrl of candidates) {
    try {
      const result = await fetchJsonMeasured(metadataUrl, {timeoutMs});
      const {anchor, bounds} = placementMetadata(result.data);
      const anchorLon = Number(anchor?.lon);
      const anchorLat = Number(anchor?.lat);
      if (!Number.isFinite(anchorLon) || !Number.isFinite(anchorLat)) {
        throw new Error(`no valid WGS84 anchor`);
      }

      const boundsMin = bounds?.min || [];
      const boundsMax = bounds?.max || [];
      const sourceCenterLocalM = sourceCenter
        ? lonLatToLocalMeters(sourceCenter[0], sourceCenter[1], anchorLon, anchorLat)
        : [
            (Number(boundsMin[0]) + Number(boundsMax[0])) / 2,
            (Number(boundsMin[1]) + Number(boundsMax[1])) / 2
          ];
      if (!sourceCenterLocalM.every(Number.isFinite)) {
        throw new Error(`no usable source center/bounds`);
      }

      const boundsBaseZ = Number(boundsMin[2]);
      asset.detailPlacement = {
        metadataUrl,
        sourceCenterLonLat: sourceCenter,
        sourceCenterLocalM,
        baseZ: sourceCenter
          ? lodBaseZ(asset)
          : (Number.isFinite(boundsBaseZ) ? boundsBaseZ : 0),
        anchor: [anchorLon, anchorLat]
      };
      const glbBytes = result.data?.storage?.glb_bytes ?? result.data?.bytes ?? null;
      if (glbBytes) {
        asset.glbBytes = glbBytes;
        asset.detailPlacement.glbBytes = glbBytes;
      }
      const triangles = result.data?.triangles ?? null;
      if (triangles) {
        asset.glbTriangles = triangles;
        asset.detailPlacement.triangles = triangles;
      }
      return asset.detailPlacement;
    } catch (error) {
      errors.push(`${metadataUrl}: ${errorMessage(error)}`);
    }
  }

  throw new Error(
    `No usable GLB placement metadata for ${asset.item.name}. ${errors.join(" | ")}`
  );
}

async function resolveGlbSize(asset) {
  if (asset.glbBytes) return asset.glbBytes;
  if (asset.item?.detail?.bytes) {
    asset.glbBytes = asset.item.detail.bytes;
    return asset.glbBytes;
  }
  try {
    await detailPlacementForAsset(asset);
    if (asset.glbBytes) return asset.glbBytes;
  } catch (_) {}
  const glbUrl = asset.item?.detail?.glb;
  if (glbUrl) {
    try {
      const res = await fetch(glbUrl, {method: 'HEAD'});
      const len = res.headers.get('content-length');
      if (len) {
        asset.glbBytes = parseInt(len, 10);
        return asset.glbBytes;
      }
    } catch (_) {}
  }
  return null;
}

function assertGlb2(arrayBuffer, url) {
  if (!(arrayBuffer instanceof ArrayBuffer) || arrayBuffer.byteLength < 12) {
    throw new Error(`Invalid or empty GLB: ${url}`);
  }
  const bytes = new Uint8Array(arrayBuffer, 0, 4);
  const magic = String.fromCharCode(...bytes);
  const version = new DataView(arrayBuffer).getUint32(4, true);
  if (magic !== "glTF" || version !== 2) {
    throw new Error(`Unsupported GLB header (${magic}, v${version}) at ${url}`);
  }
}

function setStatus(message) {
  statusNode.textContent = message;
}

function errorMessage(error) {
  return error?.message || String(error || "Unknown error");
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return "–";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatTime(ms) {
  if (!Number.isFinite(ms)) return "–";
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(2)} s`;
}

function countVerticesInCoords(coords) {
  if (!Array.isArray(coords)) return 0;
  if (
    coords.length >= 2 &&
    typeof coords[0] === "number" &&
    typeof coords[1] === "number"
  ) return 1;
  return coords.reduce((n, c) => n + countVerticesInCoords(c), 0);
}

function countVertices(fc) {
  return (fc?.features || []).reduce(
    (n, f) => n + countVerticesInCoords(f.geometry?.coordinates),
    0
  );
}

async function fetchJsonMeasured(url, {timeoutMs = 12000} = {}) {
  const t0 = performance.now();
  const controller = new AbortController();
  const timer = setTimeout(
    () => controller.abort(),
    Math.max(1000, Number(timeoutMs) || 12000)
  );
  try {
    const response = await fetch(url, {
      cache: "no-store",
      signal: controller.signal
    });
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}: ${url}`);
    }
    const text = await response.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch (error) {
      throw new Error(`Invalid JSON: ${url} (${error.message})`);
    }
    return {
      data,
      bytes: new TextEncoder().encode(text).byteLength,
      ms: performance.now() - t0
    };
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error(`Timeout after ${timeoutMs} ms: ${url}`);
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

function finitePosition(position) {
  return Array.isArray(position) &&
    position.length >= 2 &&
    Number.isFinite(Number(position[0])) &&
    Number.isFinite(Number(position[1]));
}

function validPolygonCoordinates(coords) {
  if (!Array.isArray(coords) || !coords.length) return false;
  return coords.every(ring =>
    Array.isArray(ring) && ring.length >= 4 && ring.every(finitePosition)
  );
}

function validGeometry(geometry) {
  if (!geometry) return false;
  if (geometry.type === "Polygon") {
    return validPolygonCoordinates(geometry.coordinates);
  }
  if (geometry.type === "MultiPolygon") {
    return Array.isArray(geometry.coordinates) &&
      geometry.coordinates.length > 0 &&
      geometry.coordinates.every(validPolygonCoordinates);
  }
  return false;
}

function sanitizeFeatureCollection(input, item) {
  if (!input || input.type !== "FeatureCollection" || !Array.isArray(input.features)) {
    throw new Error(`Invalid GeoJSON FeatureCollection for ${item.name || item.id}`);
  }
  const features = input.features.filter(feature =>
    feature?.type === "Feature" && validGeometry(feature.geometry)
  );
  if (!features.length) {
    throw new Error(`No valid Polygon/MultiPolygon features for ${item.name || item.id}`);
  }
  return {...input, features};
}

function itemCenter(item) {
  if (!item) return null;
  const rawLon = item.center_point_longitude ?? item.longitude;
  const rawLat = item.center_point_latitude ?? item.latitude;
  if (rawLon == null || rawLat == null || rawLon === "" || rawLat === "") return null;
  let lon = Number(rawLon);
  let lat = Number(rawLat);
  if (!Number.isFinite(lon) || !Number.isFinite(lat)) return null;

  // Swap if inverted (e.g. latitude in longitude slot)
  if (lon < 0 && lat > 90) {
    const tmp = lon;
    lon = lat;
    lat = tmp;
  }

  // Reject (0,0) Null Island in Atlantic Ocean
  if (Math.abs(lon) < 0.001 && Math.abs(lat) < 0.001) return null;

  return [lon, lat];
}

function walkCoordinates(coords, fn) {
  if (!Array.isArray(coords)) return coords;
  if (
    coords.length >= 2 &&
    typeof coords[0] === "number" &&
    typeof coords[1] === "number"
  ) return fn(coords);
  return coords.map(c => walkCoordinates(c, fn));
}

function geojsonCenter(fc) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  let found = false;
  for (const f of fc?.features || []) {
    walkCoordinates(f.geometry?.coordinates, p => {
      const x = Number(p[0]), y = Number(p[1]);
      if (Number.isFinite(x) && Number.isFinite(y)) {
        minX = Math.min(minX, x); maxX = Math.max(maxX, x);
        minY = Math.min(minY, y); maxY = Math.max(maxY, y);
        found = true;
      }
      return p;
    });
  }
  return found ? [(minX + maxX) / 2, (minY + maxY) / 2] : null;
}

function transformPosition(p, sourceCenter, targetCenter, rotateDeg, scale) {
  const lon = Number(p[0]), lat = Number(p[1]);
  const z = p.length > 2 ? Number(p[2]) : undefined;

  const mLat = 111320;
  const mLon = 111320 * Math.cos(sourceCenter[1] * Math.PI / 180);

  let x = (lon - sourceCenter[0]) * mLon;
  let y = (lat - sourceCenter[1]) * mLat;

  const s = Number.isFinite(Number(scale)) ? Number(scale) : 1;
  x *= s;
  y *= s;

  const a = Number(rotateDeg || 0) * Math.PI / 180;
  const xr = x * Math.cos(a) - y * Math.sin(a);
  const yr = x * Math.sin(a) + y * Math.cos(a);

  const targetMLon =
    111320 * Math.cos(targetCenter[1] * Math.PI / 180);

  const out = [
    targetCenter[0] + xr / targetMLon,
    targetCenter[1] + yr / mLat
  ];
  if (z !== undefined && Number.isFinite(z)) out.push(z * s);
  return out;
}

function prepareAssetGeoJSON(fc, item) {
  const mode = state.config?.settings?.placement_mode || "item_center";
  const target = itemCenter(item);

  if (mode === "native" || !target) {
    return {
      ...fc,
      features: (fc.features || []).map(f => ({
        ...f,
        properties: {
          ...(f.properties || {}),
          __asset_id: String(item.id),
          __asset_name: item.name
        }
      }))
    };
  }

  const source = geojsonCenter(fc);
  if (!source) return fc;

  return {
    ...fc,
    features: (fc.features || []).map(f => ({
      ...f,
      geometry: f.geometry?.coordinates ? {
        ...f.geometry,
        coordinates: walkCoordinates(
          f.geometry.coordinates,
          p => transformPosition(
            p,
            source,
            target,
            Number(item.rotate || 0),
            Number(item.scale ?? 1)
          )
        )
      } : f.geometry,
      properties: (() => {
        const props = {
          ...(f.properties || {}),
          __asset_id: String(item.id),
          __asset_name: item.name
        };
        const s = Number.isFinite(Number(item.scale)) ? Number(item.scale) : 1;
        for (const key of ["base_z", "top_z", "height", "z_min", "z_max"]) {
          if (Number.isFinite(Number(props[key]))) props[key] = Number(props[key]) * s;
        }
        return props;
      })()
    }))
  };
}

function representationLabels() {
  const labels = state.config?.settings?.display_labels || {};
  return {
    lod1_3: labels.lod1_3 || "LOD 1.3",
    glb: labels.glb || "GLB"
  };
}

function representationLabel(key) {
  return representationLabels()[key] || key;
}

function mergeFeatureCollections(assetRecords) {
  return {
    type: "FeatureCollection",
    features: assetRecords.flatMap(r => r.geojson?.features || [])
  };
}

function visibleOverviewAssets() {
  if (state.representation !== 'glb') return state.assets;
  return state.assets.filter(asset => !asset.item?.detail?.glb);
}

function detailAssets() {
  return state.itemRecords
    .filter(record => record.item?.detail?.glb)
    .map(record => {
      const loaded = state.assetById.get(String(record.item.id));
      if (loaded) {
        if (record.item.detail?.bytes && !loaded.glbBytes) {
          loaded.glbBytes = record.item.detail.bytes;
        }
        return loaded;
      }
      if (!record.detailAsset) {
        record.detailAsset = {
          item: record.item,
          raw: record.reps?.lod1_3?.raw || null,
          geojson: record.reps?.lod1_3?.geojson || {type:'FeatureCollection',features:[]},
          features: record.reps?.lod1_3?.features || 0,
          vertices: record.reps?.lod1_3?.vertices || 0,
          bytes: record.reps?.lod1_3?.bytes || 0,
          glbBytes: record.item.detail?.bytes || 0,
          ms: record.reps?.lod1_3?.ms || 0,
          sourceKey: 'lod1_3'
        };
      }
      return record.detailAsset;
    });
}

async function loadRepresentationRecord(record, key) {
  if (record.reps[key]) return record.reps[key];
  if (record.errors[key]) throw record.errors[key];

  const item = record.item;
  const url = item.geojson?.[key];
  if (!url) {
    const error = new Error(`Missing geojson.${key}`);
    record.errors[key] = error;
    throw error;
  }

  const timeoutMs = Number(state.config?.settings?.item_timeout_ms ?? 12000);
  try {
    const result = await fetchJsonMeasured(url, {timeoutMs});
    const clean = sanitizeFeatureCollection(result.data, item);
    const prepared = prepareAssetGeoJSON(clean, item);
    const rep = {
      item,
      url,
      raw: clean,
      geojson: prepared,
      bytes: result.bytes,
      ms: result.ms,
      features: prepared.features?.length || 0,
      vertices: countVertices(prepared),
      sourceKey: key,
      requestedKey: key,
      fallback: false
    };
    if (!rep.features) throw new Error(`No renderable features in ${url}`);
    record.reps[key] = rep;
    return rep;
  } catch (error) {
    record.errors[key] = error;
    throw error;
  }
}

function updateSelectedReference() {
  if (!state.selected) return;
  const id = String(state.selected.item.id);
  const replacement = state.assetById.get(id);
  if (replacement) {
    state.selected = replacement;
    selectedSummary.innerHTML = selectedItemHtml(replacement);
    return;
  }
  state.selected = null;
  selectedSummary.textContent = "Click a building to inspect its attributes.";
  assetCard.classList.remove("open");
}

function updateMetrics() {
  metricNodes.buildings.textContent = state.items.length.toLocaleString();
  metricNodes.loaded.textContent = state.loadMetrics.loaded.toLocaleString();
  if (metricNodes.failed) {
    metricNodes.failed.textContent = state.loadMetrics.failed.toLocaleString();
    metricNodes.failed.classList.toggle("metric-warning", state.loadMetrics.failed > 0);
  }
  metricNodes.features.textContent = state.loadMetrics.features.toLocaleString();
  metricNodes.vertices.textContent = state.loadMetrics.vertices.toLocaleString();
  metricNodes.bytes.textContent = formatBytes(state.loadMetrics.bytes);
  metricNodes.loadTime.textContent = formatTime(
    state.loadMetrics.configMs + state.loadMetrics.overviewMs
  );
}

async function activateGISRepresentation(key, {initial = false} = {}) {
  if (key !== 'lod1_3') return;
  state.representationBusy = true;
  document.querySelectorAll('.representation-btn').forEach(btn =>
    btn.classList.add('rep-loading')
  );

  const t0 = performance.now();
  const successful = [];
  const failedAssets = [];

  const settlements = await Promise.allSettled(
    state.itemRecords.map(record => loadRepresentationRecord(record, key))
  );

  settlements.forEach((settlement, index) => {
    const record = state.itemRecords[index];
    if (settlement.status === 'fulfilled') {
      successful.push({
        ...settlement.value,
        requestedKey:key,
        sourceKey:key,
        fallback:false
      });
    } else {
      failedAssets.push({item:record.item,error:settlement.reason});
    }
  });

  state.assets = successful;
  state.assetById.clear();
  successful.forEach(asset => state.assetById.set(String(asset.item.id), asset));
  state.failedAssets = failedAssets;
  state.fallbackAssets = [];
  state.gisRepresentation = key;
  state.representation = key;
  state.loadMetrics.overviewMs = performance.now() - t0;
  state.loadMetrics.loaded = successful.length;
  state.loadMetrics.failed = failedAssets.length;
  state.loadMetrics.fallback = 0;
  state.loadMetrics.bytes = successful.reduce((n,r) => n + r.bytes, 0);
  state.loadMetrics.features = successful.reduce((n,r) => n + r.features, 0);
  state.loadMetrics.vertices = successful.reduce((n,r) => n + r.vertices, 0);

  updateSelectedReference();
  updateMetrics();
  updateRepresentationControls();

  if (!initial && state.renderer) {
    await refreshRendererRepresentation();
  }

  if (!successful.length && state.items.length) {
    setStatus(`No items could be rendered for ${representationLabel(key)}.`);
  } else if (failedAssets.length) {
    setStatus(
      `${representationLabel(key)} active: ${successful.length}/${state.items.length} rendered, ` +
      `${failedAssets.length} skipped.`
    );
  } else {
    setStatus(`${representationLabel(key)} active: ${successful.length}/${state.items.length} rendered.`);
  }

  state.representationBusy = false;
  document.querySelectorAll('.representation-btn').forEach(btn =>
    btn.classList.remove('rep-loading')
  );
}

function hasGlbAssets() {
  return detailAssets().length > 0;
}

function updateRepresentationControls() {
  const isMapLibre = state.engine === 'maplibre';
  if (isMapLibre) {
    glbButton.style.display = 'none';
  } else {
    glbButton.style.display = '';
  }

  const labels = representationLabels();
  representationBadge.textContent = labels[state.representation] || state.representation;

  document.querySelectorAll('.representation-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.representation === state.representation);
  });

  glbButton.disabled = false;
  glbButton.classList.toggle('rep-loading', state.representationBusy);
  glbButton.classList.toggle('rep-unavailable', !hasGlbAssets());

  if (state.representation === 'glb') {
    representationHint.textContent = `GLB renders every configured model (${detailAssets().length} available).`;
  } else {
    representationHint.textContent = isMapLibre
      ? 'LOD 1.3 loads every valid GIS building.'
      : 'LOD 1.3 loads every valid GIS building. Switch to GLB to render all configured models.';
  }
}

async function changeRepresentation(key) {
  if (state.representationBusy) return;

  if (key === 'glb') {
    const candidates = detailAssets();
    if (!candidates.length) {
      setStatus('GLB is not configured for any item. Check item.detail.glb in data.json.');
      return;
    }

    state.representation = 'glb';
    updateRepresentationControls();
    setStatus(`Loading ${candidates.length} GLB model${candidates.length === 1 ? '' : 's'}...`);

    try {
      await state.renderer?.enterGlb?.(candidates);
      const totalGlbBytes = candidates.reduce((n, a) => n + (a.glbBytes || a.item?.detail?.bytes || 0), 0);
      if (totalGlbBytes > 0) {
        state.loadMetrics.bytes = totalGlbBytes;
        metricNodes.bytes.textContent = formatBytes(totalGlbBytes);
      }
      if (state.selected) showAssetCard(state.selected);
    } catch (error) {
      reportDetailError(null, error);
    }
    return;
  }

  if (key !== 'lod1_3') return;

  state.representation = 'lod1_3';
  state.gisRepresentation = 'lod1_3';
  updateRepresentationControls();

  if (state.engine === 'maplibre') {
    state.renderer?.leaveGlb?.();
  } else if (state.engine === 'deck') {
    state.renderer?.update?.();
  } else if (state.engine === 'cesium') {
    state.renderer?.leaveGlb?.();
  }

  const successful = state.itemRecords.map(r => r.reps.lod1_3).filter(Boolean);
  state.loadMetrics.bytes = successful.reduce((n, r) => n + r.bytes, 0);
  metricNodes.bytes.textContent = formatBytes(state.loadMetrics.bytes);
  if (state.selected) showAssetCard(state.selected);

  setStatus(`LOD 1.3 active: ${state.assets.length}/${state.items.length} rendered.`);
}

async function loadDataset() {
  const configT0 = performance.now();
  let rawData = null;
  try {
    const configResponse = await fetchJsonMeasured('./data.json', {timeoutMs:15000});
    rawData = configResponse.data;
  } catch (err) {
    console.warn('Could not load data.json; initializing empty catalog:', err);
    rawData = {
      items: [],
      settings: {
        default_engine: "maplibre",
        default_basemap: "big",
        enabled_representations: ["lod1_3", "glb"],
        big_osm_gap_fill: true
      }
    };
  }

  state.loadMetrics.configMs = performance.now() - configT0;
  state.config = (rawData && typeof rawData === 'object') ? rawData : { items: [], settings: {} };
  state.items = Array.isArray(state.config)
    ? state.config
    : (state.config.items || state.config.data?.items || []);
  if (!Array.isArray(state.items)) {
    state.items = [];
  }

  const s = state.config?.settings || {};
  state.engine = s.default_engine || 'maplibre';
  state.basemap = s.default_basemap || 'big';
  state.gisRepresentation = 'lod1_3';
  state.representation = 'lod1_3';
  basemapSelect.value = state.basemap;

  const enabledReps = new Set(s.enabled_representations || ['lod1_3','glb']);
  document.querySelectorAll('.representation-btn').forEach(btn => {
    btn.classList.toggle('hidden', !enabledReps.has(btn.dataset.representation));
  });

  state.itemRecords = state.items.map((item,index) => {
    if (!item || typeof item !== 'object') {
      item = {id:`item-${index+1}`,name:`Item ${index+1}`,geojson:{}};
      state.items[index] = item;
    }
    if (item.id == null) item.id = `item-${index+1}`;
    return {item,reps:{},errors:{}};
  });

  await activateGISRepresentation('lod1_3', {initial:true});
  renderBuildingsList();
}

function renderBuildingsList(filter = '') {
  const listContainer = document.getElementById('buildingsList');
  const countBadge = document.getElementById('buildingCountBadge');
  if (!listContainer) return;

  const items = state.items || [];
  if (countBadge) {
    countBadge.textContent = String(items.length);
  }

  const query = (filter || '').toLowerCase().trim();
  const matched = query
    ? items.filter(i => (i.name || '').toLowerCase().includes(query) || (i.id || '').toLowerCase().includes(query))
    : items;

  if (!matched.length) {
    listContainer.innerHTML = `<div class="empty-list-notice">${query ? 'No matching buildings found' : 'No models processed yet. Please upload an IFC/SKP model in the Converter tab.'}</div>`;
    return;
  }

  listContainer.innerHTML = matched.map(item => {
    const a = item.attributes || {};
    const floors = a.jumlah_lantai ? `${a.jumlah_lantai} Fl` : null;
    const height = a.tinggi != null ? `${Number(a.tinggi).toFixed(1)}m` : null;
    const area = a.luas != null ? `${Number(a.luas).toLocaleString()} m²` : null;
    const metaStr = [floors, height, area].filter(Boolean).join(' • ');

    const isSelected = state.selected && (String(state.selected.item?.id) === String(item.id));

    return `
      <div class="building-card ${isSelected ? 'active' : ''}" data-id="${item.id}" role="button" tabindex="0">
        <div class="building-card-top">
          <span class="building-name">${item.name || item.id}</span>
          <span class="building-type-tag">BIM</span>
        </div>
        ${metaStr ? `<div class="building-meta">${metaStr}</div>` : ''}
        <div class="building-card-bottom">
          <span class="building-geo">${Number(item.longitude || 0).toFixed(4)}, ${Number(item.latitude || 0).toFixed(4)}</span>
          <span class="building-target-btn">Target →</span>
        </div>
      </div>
    `;
  }).join('');

  listContainer.querySelectorAll('.building-card').forEach(card => {
    card.addEventListener('click', () => {
      focusBuilding(card.dataset.id);
    });
  });
}

function focusBuilding(id) {
  if (!id) return;
  const item = state.items.find(i => String(i.id) === String(id) || String(i.name) === String(id));
  if (!item) return;

  const center = itemCenter(item);
  if (center) {
    if (state.engine === 'maplibre' && state.renderer?.map) {
      state.renderer.map.flyTo({
        center: [center[0], center[1]],
        zoom: 17.5,
        pitch: 58,
        bearing: Number(item.rotate || 0),
        duration: 1000,
        essential: true
      });
    } else if (state.engine === 'deck' && state.renderer) {
      state.renderer.flyTo?.({
        longitude: center[0],
        latitude: center[1],
        zoom: 17.5,
        pitch: 58,
        bearing: Number(item.rotate || 0),
        duration: 1000
      });
    } else if (state.engine === 'cesium' && state.renderer?.viewer) {
      const dest = Cesium.Cartesian3.fromDegrees(center[0], center[1], 300);
      state.renderer.viewer.camera.flyTo({
        destination: dest,
        duration: 1.0
      });
    }
  }

  const asset = state.assets.find(a => String(a.item.id) === String(item.id)) ||
                state.assets.find(a => String(a.item.name) === String(item.name));
  if (asset) {
    showAssetCard(asset);
    state.renderer?.selectAsset?.(asset);
  }

  document.querySelectorAll('.building-card').forEach(card => {
    card.classList.toggle('active', card.dataset.id === String(item.id));
  });
}

async function reloadDataset(focusId) {
  try {
    setStatus('Updating building data...');
    await loadDataset();
    await refreshRendererRepresentation();
    renderBuildingsList();
    if (focusId) {
      focusBuilding(focusId);
    }
    setStatus('Ready');
  } catch (err) {
    console.error('Error reloading dataset:', err);
    setStatus(`Failed to load dataset: ${err.message}`);
  }
}

function selectedItemHtml(asset) {
  if (!asset) {
    return 'Click a building to inspect its attributes.';
  }
  const a = asset.item.attributes || {};
  const rows = [
    ['Name', asset.item.name],
    ['Function', a.fungsi],
    ['Address', a.alamat],
    ['Year', a.tahun],
    ['Area', a.luas != null ? `${a.luas} m²` : null],
    ['Height', a.tinggi != null ? `${a.tinggi} m` : null],
    ['Floors', a.jumlah_lantai],
    ['Latitude', asset.item.latitude],
    ['Longitude', asset.item.longitude]
  ].filter(([,v]) => v !== null && v !== undefined && v !== '');
  return rows.map(([k,v]) => `<div><b>${k}:</b> ${v}</div>`).join('');
}

function closeAssetCard(event) {
  event?.preventDefault?.();
  event?.stopPropagation?.();
  assetCard.classList.remove('open');
  state.selected = null;
  selectedSummary.textContent = 'Click a building to inspect its attributes.';
  if (state.renderer?.dragging) state.renderer.dragging = false;
  state.renderer?.map?.dragPan?.enable?.();
  state.renderer?.updateSelection?.();
  updateRepresentationControls();
}

function showAssetCard(asset) {
  state.selected = asset;
  selectedSummary.innerHTML = selectedItemHtml(asset);

  const a = asset.item.attributes || {};
  const rows = [
    ['Function', a.fungsi],
    ['Address', a.alamat],
    ['Year', a.tahun],
    ['Area', a.luas != null ? `${a.luas} m²` : null],
    ['Height', a.tinggi != null ? `${a.tinggi} m` : null],
    ['Floors', a.jumlah_lantai],
    ['Scale', asset.item.scale ?? 1],
    ['Rotate', `${asset.item.rotate ?? 0}°`]
  ].filter(([,v]) => v !== null && v !== undefined && v !== '');

  const isMapLibre = state.engine === 'maplibre';
  const isGlb = state.representation === 'glb';
  const sourceText = isGlb ? 'GLB 3D' : representationLabel(asset.sourceKey || state.gisRepresentation);
  const displayBytes = isGlb ? (asset.glbBytes || asset.item?.detail?.bytes || null) : asset.bytes;

  let repSwitchHtml = '';
  if (!isMapLibre) {
    if (isGlb) {
      repSwitchHtml = `
        <div class="asset-key">LOD 1.3</div>
        <div class="asset-value">
          <button id="btnSwitchToLod" type="button" class="btn-rep-toggle">Switch to LOD 1.3 (${formatBytes(asset.bytes)})</button>
        </div>`;
    } else if (asset.item.detail?.glb) {
      const glbKnownBytes = asset.glbBytes || asset.item.detail?.bytes;
      repSwitchHtml = `
        <div class="asset-key">GLB</div>
        <div class="asset-value">
          <button id="btnSwitchToGlb" type="button" class="btn-rep-toggle">Show GLB ${glbKnownBytes ? `(${formatBytes(glbKnownBytes)})` : ''}</button>
        </div>`;
    } else {
      repSwitchHtml = `
        <div class="asset-key">GLB</div>
        <div class="asset-value">Not configured</div>`;
    }
  }

  assetCard.innerHTML = `
    <div class="card-head">
      <div class="card-title">${asset.item.name}</div>
      <button class="card-close" type="button" aria-label="Close">×</button>
    </div>
    <div class="card-body">
      <div class="asset-grid">
        ${rows.map(([k,v]) =>
          `<div class="asset-key">${k}</div><div class="asset-value">${v}</div>`
        ).join('')}
      </div>
      <div class="card-metrics">
        <strong>Geometry metrics</strong>
        <div class="asset-grid">
          <div class="asset-key">Representation</div><div class="asset-value">${sourceText}</div>
          <div class="asset-key">${isGlb ? 'Triangles' : 'Features'}</div><div class="asset-value">${isGlb ? (asset.glbTriangles ? asset.glbTriangles.toLocaleString() : '–') : asset.features.toLocaleString()}</div>
          <div class="asset-key">Vertices</div><div class="asset-value">${isGlb ? (asset.glbVertices ? asset.glbVertices.toLocaleString() : '–') : asset.vertices.toLocaleString()}</div>
          <div class="asset-key">File size</div><div class="asset-value" id="cardMetricFileSize">${displayBytes ? formatBytes(displayBytes) : 'Loading...'}</div>
          <div class="asset-key">Load time</div><div class="asset-value">${formatTime(asset.ms)}</div>
          ${repSwitchHtml}
        </div>
      </div>
    </div>`;

  assetCard.classList.add('open');
  assetCard.querySelector('.card-close').onclick = closeAssetCard;

  const btnGlb = assetCard.querySelector('#btnSwitchToGlb');
  if (btnGlb) {
    btnGlb.onclick = () => changeRepresentation('glb');
  }
  const btnLod = assetCard.querySelector('#btnSwitchToLod');
  if (btnLod) {
    btnLod.onclick = () => changeRepresentation('lod1_3');
  }

  if (isGlb && !displayBytes) {
    resolveGlbSize(asset).then(b => {
      const el = document.getElementById('cardMetricFileSize');
      if (el && b) el.textContent = formatBytes(b);
    });
  } else if (!isGlb && asset.item.detail?.glb && !asset.glbBytes && !asset.item.detail?.bytes) {
    resolveGlbSize(asset).then(b => {
      const btn = assetCard.querySelector('#btnSwitchToGlb');
      if (btn && b) btn.textContent = `Show GLB (${formatBytes(b)})`;
    });
  }
  syncEditFields();
  updateRepresentationControls();

  state.renderer?.updateSelection?.();
}

function syncEditFields() {
  if (!drawingMode || !state.selected) return;
  const item = state.selected.item;
  editNodes.lat.value = item.latitude ?? '';
  editNodes.lon.value = item.longitude ?? '';
  editNodes.scale.value = item.scale ?? 1;
  editNodes.rotate.value = item.rotate ?? 0;
}

function getOsmBasemapConfig() {
  const s = state.config?.settings || {};
  return {
    id:'osm',
    label:'OpenStreetMap',
    caption:'© OpenStreetMap contributors',
    tile:s.osm_tile_url || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    maxZoom:Number(s.osm_max_zoom ?? 19),
    attribution:'© OpenStreetMap contributors'
  };
}

function getBigBasemapConfig() {
  const s = state.config?.settings || {};
  return {
    id:'big',
    label:'BIG Rupabumi Indonesia',
    caption:'Badan Informasi Geospasial',
    tile:s.big_tile_url ||
      'https://geoservices.big.go.id/rbi/rest/services/BASEMAP/' +
      'Rupabumi_Indonesia/MapServer/tile/{z}/{y}/{x}',
    minZoom:Number(s.big_min_zoom ?? 5),
    maxZoom:Number(s.big_max_zoom ?? 15),
    attribution:'Badan Informasi Geospasial'
  };
}

function getBasemapConfig() {
  if (state.basemap === 'osm') return getOsmBasemapConfig();
  return getBigBasemapConfig();
}

async function loadRasterTile({url,signal}) {
  const response = await fetch(url, {
    signal,
    mode:'cors',
    credentials:'omit',
    headers:{Accept:'image/png,image/jpeg,image/*;q=0.9,*/*;q=0.5'}
  });
  if (!response.ok) throw new Error(`Raster tile HTTP ${response.status}: ${url}`);
  const blob = await response.blob();
  if (signal?.aborted) return null;
  if ('createImageBitmap' in window) return createImageBitmap(blob);
  return await new Promise((resolve,reject) => {
    const objectUrl = URL.createObjectURL(blob);
    const image = new Image();
    image.onload = () => { URL.revokeObjectURL(objectUrl); resolve(image); };
    image.onerror = e => { URL.revokeObjectURL(objectUrl); reject(e); };
    image.src = objectUrl;
  });
}

function datasetBounds() {
  const sourceItems = state.assets.length ? state.assets.map(a => a.item) : state.items;
  const centers = sourceItems.map(itemCenter).filter(Boolean);
  if (!centers.length) return null;
  let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;
  for (const [x,y] of centers) {
    minX=Math.min(minX,x); minY=Math.min(minY,y);
    maxX=Math.max(maxX,x); maxY=Math.max(maxY,y);
  }
  return [[minX,minY],[maxX,maxY]];
}

function datasetCenter() {
  const bounds = datasetBounds();
  // Safe default: Monas, Jakarta Pusat (daratan Indonesia, bukan di laut)
  const defaultIndo = [106.827153, -6.175392];
  if (!bounds) return defaultIndo;
  const cLon = (bounds[0][0] + bounds[1][0]) / 2;
  const cLat = (bounds[0][1] + bounds[1][1]) / 2;
  if (!Number.isFinite(cLon) || !Number.isFinite(cLat) || (Math.abs(cLon) < 0.001 && Math.abs(cLat) < 0.001)) {
    return defaultIndo;
  }
  return [cLon, cLat];
}

function findAssetFromFeature(feature) {
  const id = feature?.properties?.__asset_id;
  return id != null ? state.assetById.get(String(id)) : null;
}

function reportDetailError(asset,error) {
  const name = asset?.item?.name || asset?.item?.id || 'GLB';
  console.error(`Detail model failed for ${name}`, error);
  if (state.representation === 'glb') {
    state.representation = state.gisRepresentation;
    updateRepresentationControls();
    if (state.engine === 'maplibre') state.renderer?.leaveGlb?.();
    else if (state.engine === 'deck') state.renderer?.update?.();
    else if (state.engine === 'cesium') state.renderer?.leaveGlb?.();
  }
  setStatus(`${name} failed; LOD 1.3 remains active. ${errorMessage(error)}`);
}

function deckScenegraphTransform(item, placement) {
  const [cx, cy] = placement.sourceCenterLocalM;
  const baseZ = Number(placement.baseZ || 0);
  const scale = Number.isFinite(Number(item.scale)) ? Number(item.scale) : 1;
  const angle = Number(item.detail?.rotate ?? item.rotate ?? 0) * Math.PI / 180;
  const c = Math.cos(angle);
  const sn = Math.sin(angle);

  // Column-major matrix: GLB (X, Y=up, Z=-north) -> centred local ENU,
  // then apply the same scale + planar yaw as prepareAssetGeoJSON().
  return [
    scale*c, scale*sn, 0, 0,
    0, 0, scale, 0,
    scale*sn, -scale*c, 0, 0,
    scale*(-cx*c + cy*sn),
    scale*(-cx*sn - cy*c),
    -scale*baseZ,
    1
  ];
}

class DeckRenderer {
  constructor(container) {
    this.container = container;
    this.instance = null;
    this.viewState = null;
    this.onContextMenu = (e) => e.preventDefault();
  }

  get deck() {
    return this.instance;
  }

  overviewLayer() {
    return new deck.GeoJsonLayer({
      id:`all-buildings-${state.gisRepresentation}`,
      data:mergeFeatureCollections(visibleOverviewAssets()),
      extruded:true,
      filled:true,
      stroked:true,
      wireframe:false,
      getElevation:f => {
        const p=f.properties||{};
        const baseZ=Number(p.base_z||0);
        const topZ=Number(p.top_z??p.height??0);
        return Math.max(0,topZ-baseZ);
      },
      getFillColor:f => {
        const selected = state.selected &&
          String(f.properties?.__asset_id) === String(state.selected.item.id);
        if (selected) return [242,174,73,225];
        const semantic=f.properties?.semantic_type;
        if (semantic==='RoofSurface') return [196,204,213,225];
        if (semantic==='GroundSurface') return [130,144,156,210];
        return [174,185,198,215];
      },
      getLineColor:[58,68,76,230],
      lineWidthMinPixels:1,
      pickable:true,
      onClick:({object}) => {
        const asset=findAssetFromFeature(object);
        if(asset)showAssetCard(asset);
      }
    });
  }

  rasterLayer(config,id,opacity=1) {
    const tileTemplate=config.tile;
    return new deck.TileLayer({
      id,
      data:tileTemplate,
      minZoom:config.minZoom??0,
      maxZoom:config.maxZoom,
      tileSize:256,
      opacity,
      maxRequests:12,
      getTileData:({index,signal}) => {
        const {x,y,z}=index;
        const url=tileTemplate.replace('{z}',z).replace('{x}',x).replace('{y}',y);
        return loadRasterTile({url,signal});
      },
      onTileError:error=>console.warn(`${id} tile failed`,error),
      renderSubLayers:props => {
        if(!props.data)return null;
        const box=props.tile.boundingBox;
        if(!box?.[0]||!box?.[1])return null;
        return new deck.BitmapLayer(props,{
          data:null,
          image:props.data,
          bounds:[box[0][0],box[0][1],box[1][0],box[1][1]]
        });
      }
    });
  }

  layers() {
    const osm = getOsmBasemapConfig();
    const big = getBigBasemapConfig();
    const layers = [];
    if (state.basemap === 'big') {
      layers.push(this.rasterLayer(big, 'basemap-big', 1));
    } else {
      layers.push(this.rasterLayer(osm, 'basemap-osm', 1));
    }
    layers.push(this.overviewLayer());

    if(state.representation==='glb'){
      for(const asset of detailAssets()){
      const item=asset.item;
      const center=itemCenter(item);
      const placement=asset.detailPlacement;
      if(center&&placement){
        const baseZ=Number(placement.baseZ||0);
        const itemScale=Number(item.scale??1);
        const altitude=Number(item.detail?.altitude ?? baseZ*itemScale);
        layers.push(new deck.ScenegraphLayer({
          id:`detail-${item.id}`,
          data:[{position:[0,0,0]}],
          scenegraph:item.detail.glb,
          coordinateSystem:deck.COORDINATE_SYSTEM.METER_OFFSETS,
          coordinateOrigin:[center[0],center[1],altitude],
          getPosition:d=>d.position,
          getTransformMatrix:deckScenegraphTransform(item,placement),
          getOrientation:()=>[0,0,0],
          sizeScale:1,
          _lighting:'pbr',
          pickable:false,
          onError:error=>console.error(`GLB failed for ${item.name}`,error)
        }));
      }
      }
    }
    return layers;
  }

  async init() {
    const [longitude,latitude]=datasetCenter();
    this.viewState={longitude,latitude,zoom:16.5,pitch:55,bearing:0,maxPitch:80};
    this.container.addEventListener('contextmenu', this.onContextMenu, true);
    this.instance=new deck.Deck({
      parent:this.container,
      views:[new deck.MapView({repeat:false, maxPitch:80})],
      viewState:this.viewState,
      onViewStateChange:({viewState})=>{
        this.viewState=viewState;
        this.instance?.setProps({viewState:this.viewState});
      },
      controller:{
        dragPan:true,
        dragRotate:true,
        inertia:true
      },
      parameters:{clearColor:[.035,.05,.062,1]},
      layers:this.layers()
    });
    setStatus(`Deck.gl active. ${getBasemapConfig().label}.`);
  }

  flyTo({longitude,latitude,zoom=17.5,pitch=58,bearing=0,duration=1000}){
    if(!this.instance)return;
    this.viewState={
      ...this.viewState,
      longitude,
      latitude,
      zoom,
      pitch,
      bearing,
      transitionDuration:duration,
      transitionInterpolator:new deck.FlyToInterpolator()
    };
    this.instance.setProps({viewState:this.viewState});
  }

  update(){this.instance?.setProps({layers:this.layers()});}
  updateSelection(){this.update();}
  selectAsset(){this.update();}
  clearDetail(){this.update();}
  async enterGlb(assets=detailAssets()){
    const placements=await Promise.allSettled(assets.map(asset=>detailPlacementForAsset(asset)));
    const loaded=placements.filter(result=>result.status==='fulfilled').length;
    if(!loaded)throw placements.find(result=>result.status==='rejected')?.reason || new Error('No GLB placement available');
    this.update();
    setStatus(`GLB active: ${loaded}/${assets.length} models aligned to LOD placement.`);
  }
  leaveGlb(){this.update();}
  async rebuild(){this.update();}
  reset(){
    const [longitude,latitude]=datasetCenter();
    this.flyTo({longitude,latitude,zoom:16.5,pitch:55,bearing:0,duration:400});
  }
  destroy(){
    this.container.removeEventListener('contextmenu', this.onContextMenu, true);
    this.instance?.finalize();
    this.instance=null;
    this.container.replaceChildren();
  }
}

function waitForMapEvent(map, event, timeoutMs = 8000) {
  return new Promise(resolve => {
    let done = false;
    const finish = (val) => {
      if (!done) {
        done = true;
        resolve(val);
      }
    };
    map.once(event, finish);
    if (timeoutMs > 0) {
      setTimeout(finish, timeoutMs);
    }
  });
}

class MapLibreRenderer {
  constructor(container){
    this.container=container;
    this.map=null;
    this.detailLayers=new Map();
    this.detailRoots=new Map();
    this.detailLoadToken=0;this.dragging=false;
    this.clickHandler=e=>{
      const feature=e.features?.[0];
      const asset=findAssetFromFeature(feature);
      if(asset)showAssetCard(asset);
    };
    this.mouseDownHandler=e=>{
      if(!drawingMode)return;
      const feature=e.features?.[0];
      const asset=findAssetFromFeature(feature);
      if(!asset)return;
      showAssetCard(asset);
      this.dragging=true;
      this.map.dragPan.disable();
    };
    this.mouseMoveHandler=e=>{
      if(!drawingMode||!this.dragging||!state.selected)return;
      state.selected.item.longitude=e.lngLat.lng;
      state.selected.item.latitude=e.lngLat.lat;
      state.selected.item.center_point_longitude=e.lngLat.lng;
      state.selected.item.center_point_latitude=e.lngLat.lat;
      refreshPreparedItem(state.selected.item.id);
      this.rebuildRepresentation().catch(console.error);
      syncEditFields();
    };
    this.stopDrag=()=>{
      if(!this.dragging)return;
      this.dragging=false;
      this.map.dragPan.enable();
    };
  }

  style(){
    const osm = getOsmBasemapConfig();
    const big = getBigBasemapConfig();
    return {
      version: 8,
      sources: {
        osm: { type: 'raster', tiles: [osm.tile], tileSize: 256, minzoom: 0, maxzoom: osm.maxZoom, attribution: osm.attribution },
        big: { type: 'raster', tiles: [big.tile], tileSize: 256, minzoom: big.minZoom, maxzoom: big.maxZoom, attribution: big.attribution }
      },
      layers: [
        { 
          id: 'basemap-osm', 
          type: 'raster', 
          source: 'osm', 
          layout: { visibility: state.basemap === 'osm' ? 'visible' : 'none' },
          paint: { 'raster-fade-duration': 0 } 
        },
        { 
          id: 'basemap-big', 
          type: 'raster', 
          source: 'big', 
          layout: { visibility: state.basemap === 'big' ? 'visible' : 'none' },
          paint: { 'raster-opacity': 1, 'raster-fade-duration': 0, 'raster-resampling': 'linear' } 
        }
      ]
    };
  }

  bindInteractions(layerId){
    try{this.map.off('click',layerId,this.clickHandler);}catch{}
    this.map.on('click',layerId,this.clickHandler);
    if(drawingMode){
      try{this.map.off('mousedown',layerId,this.mouseDownHandler);}catch{}
      this.map.on('mousedown',layerId,this.mouseDownHandler);
      this.map.off('mousemove',this.mouseMoveHandler);
      this.map.off('mouseup',this.stopDrag);
      this.map.off('mouseleave',this.stopDrag);
      this.map.on('mousemove',this.mouseMoveHandler);
      this.map.on('mouseup',this.stopDrag);
      this.map.on('mouseleave',this.stopDrag);
    }
  }

  addLod13(){
    this.map.addSource('buildings',{type:'geojson',data:mergeFeatureCollections(visibleOverviewAssets())});
    this.map.addLayer({
      id:'buildings-fill',
      type:'fill-extrusion',
      source:'buildings',
      paint:{
        'fill-extrusion-color':[
          'case',
          ['==',['get','__asset_id'],String(state.selected?.item.id??'')],
          '#f2ae49','#aeb9c6'
        ],
        'fill-extrusion-opacity':.88,
        'fill-extrusion-base':['coalesce',['get','base_z'],0],
        'fill-extrusion-height':['coalesce',['get','top_z'],['get','height'],0]
      }
    });
    this.bindInteractions('buildings-fill');
  }

  addRepresentation(){
    this.addLod13();
  }

  makeDetailLayer(asset, placement, loadToken, resolveReady, rejectReady){
    const url=asset.item.detail?.glb;
    const center=itemCenter(asset.item);
    if(!url||!center)return null;

    // The LOD 1.3 viewer placement is: source geometry centred at its own
    // source bbox centre -> scale -> yaw -> item lat/lon.  The GLB contains
    // the original IFC-local coordinates, so use metadata.anchor to subtract
    // that *same* LOD1.3 source centre before applying the identical placement.
    const [sourceCenterX,sourceCenterY]=placement.sourceCenterLocalM;
    const baseZ=Number(placement.baseZ||0);
    const itemScale=Number(asset.item.scale??1);
    const altitude=Number(asset.item.detail?.altitude ?? baseZ*itemScale);
    const merc=maplibregl.MercatorCoordinate.fromLngLat(center,altitude);
    const transform={
      translateX:merc.x,
      translateY:merc.y,
      translateZ:merc.z,
      // GLB generated by BIM2GIS is Y-up. Rx maps Y-up to map Z-up.
      rotateX:Math.PI/2,
      // IMPORTANT: item.rotate is a yaw around the GLB Y-up axis, not Z.
      // The previous Z rotation could tip a 270° model onto its side.
      rotateY:Number(asset.item.detail?.rotate ?? asset.item.rotate ?? 0)*Math.PI/180,
      rotateZ:0,
      scale:merc.meterInMercatorCoordinateUnits()*itemScale
    };
    const parent=this;

    const layerId=`glb-detail-${String(asset.item.id).replace(/[^A-Za-z0-9_-]/g,'-')}`;
    return {
      id:layerId,
      type:'custom',
      renderingMode:'3d',

      onAdd(map,gl){
        this.camera=new THREE.Camera();
        this.scene=new THREE.Scene();
        this.scene.add(new THREE.AmbientLight(0xffffff,1.7));
        const d1=new THREE.DirectionalLight(0xffffff,2.1);
        d1.position.set(0,-70,100).normalize();
        this.scene.add(d1);
        const d2=new THREE.DirectionalLight(0xffffff,1.0);
        d2.position.set(50,70,80).normalize();
        this.scene.add(d2);

        this.map=map;
        this.renderer=new THREE.WebGLRenderer({
          canvas:map.getCanvas(),
          context:gl,
          antialias:true
        });
        this.renderer.autoClear=false;

        // Fetch explicitly so a 404/HTML response/invalid GLB becomes a visible
        // error instead of looking like a MapLibre rendering failure.
        (async()=>{
          try{
            const response=await fetch(url,{cache:'no-store'});
            if(!response.ok){
              throw new Error(`${response.status} ${response.statusText}: ${url}`);
            }
            const buffer=await response.arrayBuffer();
            assertGlb2(buffer,url);
            asset.glbBytes = buffer.byteLength;
            if(loadToken!==parent.detailLoadToken)return;

            const loader=new GLTFLoader();
            const absoluteUrl=new URL(url,window.location.href).href;
            const resourcePath=absoluteUrl.slice(0,absoluteUrl.lastIndexOf('/')+1);
            loader.parse(
              buffer,
              resourcePath,
              gltf=>{
                if(loadToken!==parent.detailLoadToken)return;
                const root=gltf.scene;

                // glTF coordinates from the generator:
                //   Xg = Xlocal, Yg = Zlocal, Zg = -Ylocal
                // Therefore subtracting the exact LOD1.3 source centre means:
                //   Xg -= sourceCenterX
                //   Zg += sourceCenterY
                // and move the model base to zero before anchoring at baseZ.
                root.position.set(
                  -sourceCenterX,
                  -baseZ,
                  +sourceCenterY
                );

                let glbVerts = 0;
                let glbTris = 0;
                root.traverse(obj=>{
                  if(obj.isMesh){
                    obj.frustumCulled=false;
                    const geom = obj.geometry;
                    if (geom) {
                      const pos = geom.attributes.position;
                      if (pos) glbVerts += pos.count;
                      if (geom.index) glbTris += geom.index.count / 3;
                      else if (pos) glbTris += pos.count / 3;
                    }
                  }
                });
                if (glbVerts > 0) asset.glbVertices = glbVerts;
                if (glbTris > 0) asset.glbTriangles = Math.round(glbTris);
                root.updateMatrixWorld(true);

                parent.detailRoots.set(layerId,root);
                this.scene.add(root);
                map.triggerRepaint();
                resolveReady?.();
              },
              error=>{
                if(loadToken!==parent.detailLoadToken)return;
                rejectReady?.(error instanceof Error?error:new Error(String(error)));
              }
            );
          }catch(error){
            if(loadToken!==parent.detailLoadToken)return;
            rejectReady?.(error);
          }
        })();
      },

      render(gl,args){
        // This is the same proven custom-layer matrix path used by ARCA v0.6.
        const rotationX=new THREE.Matrix4().makeRotationAxis(
          new THREE.Vector3(1,0,0),transform.rotateX
        );
        const rotationY=new THREE.Matrix4().makeRotationAxis(
          new THREE.Vector3(0,1,0),transform.rotateY
        );
        const rotationZ=new THREE.Matrix4().makeRotationAxis(
          new THREE.Vector3(0,0,1),transform.rotateZ
        );
        const projection=new THREE.Matrix4().fromArray(
          args.defaultProjectionData.mainMatrix
        );
        const local=new THREE.Matrix4()
          .makeTranslation(
            transform.translateX,
            transform.translateY,
            transform.translateZ
          )
          .scale(new THREE.Vector3(
            transform.scale,
            -transform.scale,
            transform.scale
          ))
          .multiply(rotationX)
          .multiply(rotationY)
          .multiply(rotationZ);

        this.camera.projectionMatrix=projection.multiply(local);
        this.renderer.resetState();
        this.renderer.render(this.scene,this.camera);
        this.map.triggerRepaint();
      },

      onRemove(){
        this.scene?.traverse?.(object=>{
          object.geometry?.dispose?.();
          if(Array.isArray(object.material))object.material.forEach(material=>material.dispose?.());
          else object.material?.dispose?.();
        });
        this.renderer?.dispose?.();
        parent.detailRoots.delete(layerId);
      }
    };
  }

  async installDetail(asset, loadToken){
    if(!this.map?.isStyleLoaded()){
      throw new Error('MapLibre style is not ready for GLB');
    }

    const placement=await detailPlacementForAsset(asset);

    let timer;
    const ready=new Promise((resolve,reject)=>{
      timer=setTimeout(
        ()=>reject(new Error(`GLB timeout: ${asset.item.detail?.glb}`)),
        Number(state.config?.settings?.detail_timeout_ms ?? 20000)
      );
      const layer=this.makeDetailLayer(
        asset,
        placement,
        loadToken,
        ()=>{clearTimeout(timer);resolve();},
        error=>{clearTimeout(timer);reject(error);}
      );
      if(!layer){
        clearTimeout(timer);
        reject(new Error(`Cannot create GLB layer for ${asset.item.name}`));
        return;
      }
      this.detailLayers.set(layer.id,layer);
      try{
        this.map.addLayer(layer);
      }catch(error){
        clearTimeout(timer);
        reject(error);
      }
    });

    try{
      await ready;
    }catch(error){
      const failedLayerId=`glb-detail-${String(asset.item.id).replace(/[^A-Za-z0-9_-]/g,'-')}`;
      if(this.map?.getLayer(failedLayerId))this.map.removeLayer(failedLayerId);
      this.detailLayers.delete(failedLayerId);
      throw error;
    }
  }

  refreshOverviewVisibility(){
    const source=this.map?.getSource('buildings');
    if(source)source.setData(mergeFeatureCollections(visibleOverviewAssets()));
  }

  async enterGlb(assets=detailAssets()){
    this.clearDetail();
    this.refreshOverviewVisibility();
    const loadToken=this.detailLoadToken;
    const results=await Promise.allSettled(
      assets.map(asset=>this.installDetail(asset,loadToken))
    );
    const loaded=results.filter(result=>result.status==='fulfilled').length;
    const failed=results.length-loaded;
    if(!loaded){
      const firstFailure=results.find(result=>result.status==='rejected');
      throw firstFailure?.reason || new Error('No GLB model could be loaded');
    }
    setStatus(`GLB active: ${loaded}/${assets.length} models aligned to LOD placement${failed ? `; ${failed} failed` : ''}.`);
  }

  leaveGlb(){
    this.clearDetail();
    this.refreshOverviewVisibility();
    this.updateSelection();
  }

  clearDetail(){
    this.detailLoadToken=(this.detailLoadToken||0)+1;
    for(const layerId of this.detailLayers.keys()){
      if(this.map?.getLayer(layerId))this.map.removeLayer(layerId);
    }
    this.detailRoots.clear();
    this.detailLayers.clear();
  }

  async init(){
    const [lon,lat]=datasetCenter();
    this.map=new maplibregl.Map({
      container:this.container,
      style:this.style(),
      center:[lon,lat],
      zoom:16.5,
      pitch:55,
      bearing:0,
      maxPitch:80,
      attributionControl:false,
      canvasContextAttributes:{antialias:true}
    });
    this.map.on('error', event => {
      const message = event?.error?.message || '';
      if (state.basemap === 'big' && /tile|raster|image|source/i.test(message)) {
        setStatus(`BIG basemap tile error: ${message}`);
      }
    });
    this.map.addControl(new maplibregl.NavigationControl({visualizePitch:true}),'top-right');
    this.map.addControl(new maplibregl.AttributionControl({compact:true,customAttribution:getBasemapConfig().attribution}),'bottom-right');
    await waitForMapEvent(this.map,'style.load');
    this.map.resize();
    this.addRepresentation();
    if(state.representation==='glb')await this.enterGlb();
    setStatus(`MapLibre active. ${getBasemapConfig().label}.`);
  }

  async rebuild(){
    if (!this.map) return;
    const isBig = state.basemap === 'big';
    if (this.map.getLayer('basemap-big')) {
      this.map.setLayoutProperty('basemap-big', 'visibility', isBig ? 'visible' : 'none');
    }
    if (this.map.getLayer('basemap-osm')) {
      this.map.setLayoutProperty('basemap-osm', 'visibility', isBig ? 'none' : 'visible');
    }
    this.map.triggerRepaint();
  }

  async rebuildRepresentation(){
    this.update();
    if(state.representation==='glb')await this.enterGlb();
    this.map?.triggerRepaint();
  }
  update(){
    if(state.gisRepresentation==='lod1_3'){
      const source=this.map?.getSource('buildings');
      if(source)source.setData(mergeFeatureCollections(visibleOverviewAssets()));
    }
  }
  updateSelection(){
    if(state.gisRepresentation==='lod1_3'&&this.map?.getLayer('buildings-fill')){
      this.map.setPaintProperty('buildings-fill','fill-extrusion-color',[
        'case',['==',['get','__asset_id'],String(state.selected?.item.id??'')],
        '#f2ae49','#aeb9c6'
      ]);
    }
  }
  async selectAsset(asset){
    this.updateSelection();
  }
  reset(){
    const [lon,lat]=datasetCenter();
    this.map?.easeTo({center:[lon,lat],zoom:16.5,pitch:55,bearing:0,duration:400});
  }
  destroy(){this.map?.remove();this.map=null;this.container.replaceChildren();}
}

function cesiumGlbModelMatrix(item, placement, center) {
  const [cx, cy] = placement.sourceCenterLocalM;
  const baseZ = Number(placement.baseZ || 0);
  const scale = Number.isFinite(Number(item.scale)) ? Number(item.scale) : 1;
  const altitude = Number(item.detail?.altitude ?? baseZ * scale);
  const origin = Cesium.Cartesian3.fromDegrees(center[0], center[1], altitude);
  const enu = Cesium.Transforms.eastNorthUpToFixedFrame(origin);

  // GLB writer emits Xg=Xlocal, Yg=Zlocal, Zg=-Ylocal.
  // Convert that explicitly to ENU so Cesium does not need to guess axes.
  const axis = Cesium.Matrix4.fromArray([
    1,0,0,0,
    0,0,1,0,
    0,-1,0,0,
    0,0,0,1
  ]);
  const centerShift = Cesium.Matrix4.fromTranslation(
    new Cesium.Cartesian3(-cx, -cy, -baseZ)
  );
  const uniformScale = Cesium.Matrix4.fromUniformScale(scale);
  const angle = Number(item.detail?.rotate ?? item.rotate ?? 0) * Math.PI / 180;
  const yaw = Cesium.Matrix4.fromRotationTranslation(
    Cesium.Matrix3.fromRotationZ(angle),
    Cesium.Cartesian3.ZERO
  );

  const local = new Cesium.Matrix4();
  Cesium.Matrix4.multiply(centerShift, axis, local);
  Cesium.Matrix4.multiply(uniformScale, local, local);
  Cesium.Matrix4.multiply(yaw, local, local);
  const world = new Cesium.Matrix4();
  Cesium.Matrix4.multiply(enu, local, world);
  return world;
}

class CesiumRenderer {
  constructor(container){
    this.container=container;
    this.viewer=null;
    this.imagery=null;
    this.imagerySafety=null;
    this.entities=[];
    this.surfacePrimitive=null;
    this.detailModels=[];
  }

  clearOverview(){
    for(const entity of this.entities)this.viewer.entities.remove(entity);
    this.entities=[];
    if(this.surfacePrimitive){
      this.viewer.scene.primitives.remove(this.surfacePrimitive);
      this.surfacePrimitive=null;
    }
  }

  addLod13(){
    const fc=mergeFeatureCollections(visibleOverviewAssets());
    for(const f of fc.features||[]){
      const p=f.properties||{};
      const polygons=f.geometry?.type==='Polygon'?[f.geometry.coordinates]:f.geometry?.type==='MultiPolygon'?f.geometry.coordinates:[];
      for(const poly of polygons){
        if(!poly?.[0]?.length)continue;
        const outer=poly[0];
        const entity=this.viewer.entities.add({
          name:p.__asset_name||'Building',
          polygon:{
            hierarchy:new Cesium.PolygonHierarchy(Cesium.Cartesian3.fromDegreesArray(outer.flatMap(c=>[c[0],c[1]]))),
            height:Number(p.base_z||0),
            extrudedHeight:Number(p.top_z??p.height??0),
            material:Cesium.Color.fromCssColorString('#aeb9c6').withAlpha(.88),
            outline:true,
            outlineColor:Cesium.Color.DARKGRAY
          },
          properties:{assetId:String(p.__asset_id||'')}
        });
        this.entities.push(entity);
      }
    }
  }

  addOverview(){
    this.addLod13();
  }

  async rebuildOverview(){
    this.clearOverview();
    this.addOverview();
    if(state.representation!=='glb')this.clearDetail();
  }

  async replaceImagery(){
    if(this.imagery){this.viewer.imageryLayers.remove(this.imagery,true);this.imagery=null;}
    if(this.imagerySafety){this.viewer.imageryLayers.remove(this.imagerySafety,true);this.imagerySafety=null;}
    const b=getBasemapConfig();
    this.imagery=this.viewer.imageryLayers.addImageryProvider(
      new Cesium.UrlTemplateImageryProvider({
        url:b.tile,minimumLevel:b.minZoom??5,maximumLevel:b.maxZoom,credit:new Cesium.Credit(b.attribution)
      })
    );
    if(b.id==='big')this.imagery.alpha=1.0;
  }

  bindPicking(){
    this.viewer.screenSpaceEventHandler.setInputAction(m=>{
      const picked=this.viewer.scene.pick(m.position);
      const id = picked?.id?.assetId || picked?.id?.properties?.assetId?.getValue?.();
      if(id){
        const asset=state.assetById.get(String(id));
        if(asset)showAssetCard(asset);
      }
    },Cesium.ScreenSpaceEventType.LEFT_CLICK);
  }

  async init(){
    const [lon,lat]=datasetCenter();
    this.viewer=new Cesium.Viewer(this.container,{
      animation:false,timeline:false,baseLayerPicker:false,geocoder:false,
      homeButton:false,sceneModePicker:false,navigationHelpButton:false,
      fullscreenButton:false,selectionIndicator:false,infoBox:false,baseLayer:false
    });
    this.viewer.scene.globe.baseColor=Cesium.Color.fromCssColorString('#0c1115');
    await this.replaceImagery();
    this.addOverview();
    this.bindPicking();
    this.reset();
    if(state.representation==='glb')await this.enterGlb();
    setStatus(`CesiumJS active. ${getBasemapConfig().label}.`);
  }

  async addGlbAsset(asset){
    const url=asset.item.detail?.glb;
    const center=itemCenter(asset.item);
    if(!url||!center)return;
    const placement=await detailPlacementForAsset(asset);
    const modelMatrix=cesiumGlbModelMatrix(asset.item,placement,center);
    const model=await Cesium.Model.fromGltfAsync({
      url,
      modelMatrix,
      // Axis conversion is already encoded in modelMatrix above.
      upAxis:Cesium.Axis.Z,
      forwardAxis:Cesium.Axis.X
    });
    this.viewer.scene.primitives.add(model);
    this.detailModels.push(model);
  }
  async enterGlb(assets=detailAssets()){
    this.clearDetail();
    await this.rebuildOverview();
    const results=await Promise.allSettled(assets.map(asset=>this.addGlbAsset(asset)));
    const loaded=results.filter(result=>result.status==='fulfilled').length;
    if(!loaded)throw results.find(result=>result.status==='rejected')?.reason || new Error('No GLB model could be loaded');
    setStatus(`GLB active: ${loaded}/${assets.length} models aligned to LOD placement.`);
  }

  clearDetail(){
    for(const model of this.detailModels)this.viewer.scene.primitives.remove(model);
    this.detailModels=[];
  }
  selectAsset(){this.updateSelection();}
  leaveGlb(){ this.clearDetail();this.rebuildOverview(); }
  updateSelection(){}
  update(){}
  async rebuild(){await this.rebuildOverview();}
  reset(){
    if(!this.viewer)return;
    const [lon,lat]=datasetCenter();
    const center=Cesium.Cartesian3.fromDegrees(lon,lat,18);
    this.viewer.camera.lookAt(center,new Cesium.HeadingPitchRange(0,Cesium.Math.toRadians(-35),400));
    this.viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
  }
  destroy(){
    if(this.viewer&&!this.viewer.isDestroyed())this.viewer.destroy();
    this.viewer=null;this.container.replaceChildren();
  }
}

function refreshPreparedItem(itemId){
  const record=state.itemRecords.find(r=>String(r.item.id)===String(itemId));
  if(!record)return;
  for(const key of Object.keys(record.reps)){
    const rep=record.reps[key];
    rep.geojson=prepareAssetGeoJSON(rep.raw,record.item);
    rep.features=rep.geojson.features?.length||0;
    rep.vertices=countVertices(rep.geojson);
  }
  const active=state.assetById.get(String(itemId));
  if(active){
    const source=record.reps[active.sourceKey];
    if(source){
      Object.assign(active,source,{requestedKey:active.requestedKey,sourceKey:active.sourceKey,fallback:active.fallback});
    }
  }
}

const engineNames={maplibre:'MapLibre GL JS',deck:'Deck.gl',cesium:'CesiumJS'};

async function switchEngine(engine){
  if(state.renderer){state.renderer.destroy();state.renderer=null;}
  state.engine=engine;
  if(engine==='maplibre' && state.representation==='glb'){
    state.representation=state.gisRepresentation||'enhanced_lod1_3';
  }
  updateRepresentationControls();
  if(state.selected) showAssetCard(state.selected);
  viewerNode.replaceChildren();
  engineLabel.textContent=engineNames[engine];
  document.querySelectorAll('.engine-btn').forEach(btn=>{
    btn.classList.toggle('active',btn.dataset.engine===engine);
  });
  setStatus(`Starting ${engineNames[engine]}...`);
  try{
    if(engine==='maplibre')state.renderer=new MapLibreRenderer(viewerNode);
    if(engine==='deck')state.renderer=new DeckRenderer(viewerNode);
    if(engine==='cesium')state.renderer=new CesiumRenderer(viewerNode);
    await state.renderer.init();
  }catch(error){
    console.error(error);
    setStatus(`${engineNames[engine]} failed: ${error.message}`);
  }
}

async function refreshRendererRepresentation(){
  if(!state.renderer)return;
  try{
    if(state.engine==='maplibre')await state.renderer.rebuildRepresentation();
    else if(state.engine==='deck')state.renderer.update();
    else if(state.engine==='cesium')await state.renderer.rebuildOverview();
  }catch(error){
    console.error('Representation refresh failed',error);
    setStatus(`Representation refresh failed: ${errorMessage(error)}`);
  }
}

async function changeBasemap(value){
  state.basemap=value;
  const b=getBasemapConfig();
  basemapCaption.textContent=b.caption;
  if(!state.renderer)return;
  try{
    if(state.engine==='maplibre')await state.renderer.rebuild();
    else if(state.engine==='deck')state.renderer.update();
    else if(state.engine==='cesium')await state.renderer.replaceImagery();
  }catch(error){
    console.error('Basemap change failed',error);
    setStatus(`Basemap failed: ${errorMessage(error)}`);
  }
}

function exportDataJson(){
  const json=JSON.stringify(state.config,null,2);
  const blob=new Blob([json],{type:'application/json'});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');
  a.href=url;
  a.download='data.updated.json';
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}

document.querySelectorAll('.engine-btn').forEach(btn=>{
  btn.onclick=()=>switchEngine(btn.dataset.engine);
});

document.querySelectorAll('.representation-btn').forEach(btn=>{
  btn.onclick=()=>changeRepresentation(btn.dataset.representation);
});

const resetBtn = document.getElementById('resetView');
if (resetBtn) resetBtn.onclick = () => state.renderer?.reset();

if (typeof basemapSelect !== 'undefined' && basemapSelect) {
  basemapSelect.onchange = () => changeBasemap(basemapSelect.value);
}

const mobileToggle = document.getElementById('mobilePanelToggle');
if (mobileToggle) {
  mobileToggle.onclick = () => {
    document.getElementById('panel')?.classList.toggle('mobile-open');
  };
}

if(drawingMode){
  editNodes.section.classList.remove('hidden');
  editNodes.apply.onclick=async()=>{
    if(!state.selected)return;
    const item=state.selected.item;
    item.latitude=Number(editNodes.lat.value);
    item.longitude=Number(editNodes.lon.value);
    item.center_point_latitude=item.latitude;
    item.center_point_longitude=item.longitude;
    item.scale=Number(editNodes.scale.value||1);
    item.rotate=((Number(editNodes.rotate.value||0)%360)+360)%360;
    refreshPreparedItem(item.id);
    await refreshRendererRepresentation();
    showAssetCard(state.assetById.get(String(item.id))||state.selected);
  };
  editNodes.save.onclick=exportDataJson;
}

window.addEventListener('unhandledrejection',event=>{
  console.error(event.reason);
  setStatus(`Viewer error: ${event.reason?.message||event.reason}`);
});

try{
  await loadDataset();
  const b=getBasemapConfig();
  basemapCaption.textContent=b.caption;
  updateRepresentationControls();
  // Check if container is visible (not display:none). If hidden (SPA tab not yet shown),
  // defer engine init until notifyVisible() is called.
  const isVisible = viewerNode && viewerNode.offsetParent !== null;
  if(isVisible){
    await switchEngine(state.engine);
    if(state.failedAssets.length){
      setStatus(`Viewer active. ${state.loadMetrics.loaded}/${state.items.length} rendered; ${state.failedAssets.length} skipped.`);
    }
  } else {
    setStatus('Viewer ready. Switch to viewer tab to render map.');
  }
}catch(error){
  console.error('Viewer startup failed',error);
  setStatus(`Viewer startup failed: ${errorMessage(error)}`);
}

// Global exports for seamless SPA integration
let _engineInitialized = false;

window.ARCA_VIEWER = {
  focusBuilding,
  reloadDataset,
  renderBuildingsList,
  switchEngine,
  notifyVisible: async () => {
    if (!_engineInitialized) {
      _engineInitialized = true;
      try {
        await switchEngine(state.engine);
        if (state.engine === 'maplibre' && state.renderer?.map) {
          state.renderer.map.resize();
        }
        if (state.failedAssets.length) {
          setStatus(`Viewer active. ${state.loadMetrics.loaded}/${state.items.length} rendered; ${state.failedAssets.length} skipped.`);
        }
      } catch (err) {
        console.error('Engine init failed', err);
        setStatus(`Engine init failed: ${errorMessage(err)}`);
      }
    } else {
      if (state.engine === 'maplibre' && state.renderer?.map) {
        state.renderer.map.resize();
      } else if (state.engine === 'deck' && state.renderer?.instance) {
        state.renderer.instance.redraw(true);
      }
    }
  },
  resize: () => {
    if (state.engine === 'maplibre' && state.renderer?.map) {
      state.renderer.map.resize();
    } else if (state.engine === 'deck' && state.renderer?.instance) {
      state.renderer.instance.redraw(true);
    }
  },
  getState: () => state
};

const searchInput = document.getElementById('buildingSearchInput');
if (searchInput) {
  searchInput.addEventListener('input', (e) => {
    renderBuildingsList(e.target.value);
  });
}

const topResetBtn = document.getElementById('resetView');
if (topResetBtn) {
  topResetBtn.addEventListener('click', () => {
    state.renderer?.reset();
  });
}
