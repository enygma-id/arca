# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import json
import shutil
import struct
from pathlib import Path
from typing import Optional

import numpy as np

from .georef import GeoreferenceContext
from .utils import write_json_compact


class GLBWriter:
    """Minimal glTF 2.0/GLB writer for browser rendering.

    IFC/source geometry is local Z-up (X east/local, Y north/local, Z up).
    glTF is written Y-up using:
        X_gltf =  X_local
        Y_gltf =  Z_local
        Z_gltf = -Y_local

    Vertices are intentionally duplicated per triangle so architectural hard
    edges keep flat normals.
    """

    MATERIALS = {
        "RoofSurface": [0.72, 0.34, 0.24, 1.0],
        "WallSurface": [0.72, 0.76, 0.80, 1.0],
        "SlabSurface": [0.55, 0.58, 0.62, 1.0],
        "DoorSurface": [0.34, 0.22, 0.14, 1.0],
        "WindowSurface": [0.24, 0.52, 0.70, 0.72],
        "ColumnSurface": [0.58, 0.61, 0.65, 1.0],
        "BeamSurface": [0.50, 0.53, 0.57, 1.0],
        "GenericSurface": [0.66, 0.69, 0.72, 1.0],
    }

    def __init__(self, root: Path, dataset: str, filename: str = "model.glb"):
        self.root = root
        self.dataset = dataset
        self.render_dir = root / "render"
        if self.render_dir.exists():
            shutil.rmtree(self.render_dir)
        self.render_dir.mkdir(parents=True, exist_ok=True)
        self.filename = filename
        self.states = {}
        self.total_triangles = 0
        self.object_ranges = {}
        self.local_min = np.array([np.inf, np.inf, np.inf], dtype=float)
        self.local_max = np.array([-np.inf, -np.inf, -np.inf], dtype=float)

    @staticmethod
    def _to_gltf_xyz(tri_m: np.ndarray) -> np.ndarray:
        tri = np.asarray(tri_m, dtype=np.float64).reshape(3, 3)
        return np.column_stack((tri[:, 0], tri[:, 2], -tri[:, 1]))

    def add_triangle(self, semantic: str, tri_m: np.ndarray, object_id: int):
        tri_local = np.asarray(tri_m, dtype=np.float64).reshape(3, 3)
        self.local_min = np.minimum(self.local_min, tri_local.min(axis=0))
        self.local_max = np.maximum(self.local_max, tri_local.max(axis=0))
        tri = self._to_gltf_xyz(tri_local)
        e1 = tri[1] - tri[0]
        e2 = tri[2] - tri[0]
        n = np.cross(e1, e2)
        norm = float(np.linalg.norm(n))
        if norm <= 1e-12:
            return
        n = n / norm

        st = self.states.setdefault(semantic, {
            "positions": [],
            "normals": [],
            "triangles": 0,
            "objects": {},
        })
        first = st["triangles"]
        st["positions"].extend(tri.tolist())
        st["normals"].extend([n.tolist(), n.tolist(), n.tolist()])
        st["triangles"] += 1
        self.total_triangles += 1

        obj = st["objects"].setdefault(str(object_id), [first, 0])
        obj[1] += 1

    @staticmethod
    def _pad4(data: bytes, pad_byte: bytes = b"\x00") -> bytes:
        padding = (-len(data)) % 4
        return data + pad_byte * padding

    def finalize(self, anchor_lon: float, anchor_lat: float, georef: Optional[GeoreferenceContext] = None):
        if self.total_triangles <= 0:
            return None

        bin_blob = bytearray()
        buffer_views = []
        accessors = []
        materials = []
        primitives = []
        semantic_manifest = {}

        def append_float32_vec3(values):
            arr = np.asarray(values, dtype="<f4").reshape(-1, 3)
            while len(bin_blob) % 4:
                bin_blob.append(0)
            offset = len(bin_blob)
            raw = arr.tobytes(order="C")
            bin_blob.extend(raw)
            bv_index = len(buffer_views)
            buffer_views.append({
                "buffer": 0,
                "byteOffset": offset,
                "byteLength": len(raw),
                "target": 34962,
            })
            return arr, bv_index

        for semantic, st in sorted(self.states.items()):
            if not st["triangles"]:
                continue

            pos, pos_bv = append_float32_vec3(st["positions"])
            nor, nor_bv = append_float32_vec3(st["normals"])

            pos_acc = len(accessors)
            accessors.append({
                "bufferView": pos_bv,
                "componentType": 5126,
                "count": int(len(pos)),
                "type": "VEC3",
                "min": [float(v) for v in pos.min(axis=0)],
                "max": [float(v) for v in pos.max(axis=0)],
            })
            nor_acc = len(accessors)
            accessors.append({
                "bufferView": nor_bv,
                "componentType": 5126,
                "count": int(len(nor)),
                "type": "VEC3",
            })

            rgba = self.MATERIALS.get(semantic, self.MATERIALS["GenericSurface"])
            mat_idx = len(materials)
            materials.append({
                "name": semantic,
                "doubleSided": True,
                "pbrMetallicRoughness": {
                    "baseColorFactor": rgba,
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.86,
                },
                "alphaMode": "BLEND" if rgba[3] < 1.0 else "OPAQUE",
            })

            primitives.append({
                "attributes": {"POSITION": pos_acc, "NORMAL": nor_acc},
                "material": mat_idx,
                "mode": 4,
                "extras": {"semantic_type": semantic},
            })
            semantic_manifest[semantic] = {
                "triangles": int(st["triangles"]),
                "vertices": int(len(pos)),
                "objects": st["objects"],
            }

        gltf = {
            "asset": {
                "version": "2.0",
                "generator": "ARCA BIM2GIS Engine",
            },
            "scene": 0,
            "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0, "name": self.dataset}],
            "meshes": [{"name": self.dataset, "primitives": primitives}],
            "materials": materials,
            "buffers": [{"byteLength": len(bin_blob)}],
            "bufferViews": buffer_views,
            "accessors": accessors,
            "extras": {
                "coordinate_system": {
                    "source_local": "X east/local, Y north/local, Z up",
                    "gltf": "Y-up",
                    "anchor_wgs84": {"lon": anchor_lon, "lat": anchor_lat},
                },
                "source": "IFC product geometry",
            },
        }

        json_bytes = json.dumps(
            gltf, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        json_padded = self._pad4(json_bytes, b" ")
        bin_padded = self._pad4(bytes(bin_blob), b"\x00")
        total_length = 12 + 8 + len(json_padded) + 8 + len(bin_padded)

        path = self.render_dir / self.filename
        with path.open("wb") as f:
            f.write(struct.pack("<4sII", b"glTF", 2, total_length))
            f.write(struct.pack("<II", len(json_padded), 0x4E4F534A))
            f.write(json_padded)
            f.write(struct.pack("<II", len(bin_padded), 0x004E4942))
            f.write(bin_padded)

        manifest = {
            "version": 2,
            "dataset": self.dataset,
            "format": "glTF 2.0 binary (GLB)",
            "file": self.filename,
            "bytes": path.stat().st_size,
            "triangles": int(self.total_triangles),
            "anchor": {
                "lon": anchor_lon,
                "lat": anchor_lat,
                "mode": (
                    f"IFC georeferenced ({georef.method})"
                    if georef and georef.method != "cli_anchor_fallback"
                    else "local model anchored to WGS84"
                ),
            },
            "georeferencing": georef.to_dict() if georef else None,
            "bounds_local_m": {
                "min": [round(float(v), 6) for v in self.local_min],
                "max": [round(float(v), 6) for v in self.local_max],
            },
            "coordinate_system": {
                "source_local": "X east/local, Y north/local, Z up",
                "gltf": "Y-up",
                "anchor_wgs84": {"lon": anchor_lon, "lat": anchor_lat},
                "crs": (georef.target_crs or georef.crs_name) if georef else None,
            },
            "semantics": semantic_manifest,
            "note": "GLB generated directly from supported IFC product geometry.",
        }
        write_json_compact(self.render_dir / "manifest.json", manifest)
        return manifest
