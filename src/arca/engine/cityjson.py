# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Optional

import numpy as np

from .georef import GeoreferenceContext, latlon_to_utm_wgs84
from .utils import write_json_compact

CITYJSON_SEMANTIC_MAP = {
    "RoofSurface": "RoofSurface",
    "WallSurface": "WallSurface",
    "GroundSurface": "GroundSurface",
    "SlabSurface": "OuterFloorSurface",
    "DoorSurface": "Door",
    "WindowSurface": "Window",
    "ColumnSurface": "WallSurface",
    "BeamSurface": "WallSurface",
    "StairSurface": "WallSurface",
    "RailingSurface": "WallSurface",
    "GenericSurface": "WallSurface",
}


class CityJSONWriter:
    """CityJSON 1.1 writer for 3D GIS visualization (ninja.cityjson.org, QGIS)."""

    def __init__(
        self,
        root: Path,
        dataset: str,
        filename: str = "building.city.json",
        building_name: str | None = None,
    ):
        self.root = root
        self.dataset = dataset
        self.filename = filename
        self.building_name = building_name or dataset
        self.triangles: list[tuple[str, np.ndarray, int]] = []
        self.local_min = np.array([np.inf, np.inf, np.inf], dtype=float)
        self.local_max = np.array([-np.inf, -np.inf, -np.inf], dtype=float)

    def add_triangle(self, semantic: str, tri_m: np.ndarray, object_id: int = 1):
        tri = np.asarray(tri_m, dtype=np.float64).reshape(3, 3)
        self.local_min = np.minimum(self.local_min, tri.min(axis=0))
        self.local_max = np.maximum(self.local_max, tri.max(axis=0))
        self.triangles.append((semantic, tri, object_id))

    def _transform_point(
        self,
        pt: np.ndarray,
        anchor_lon: float,
        anchor_lat: float,
        georef: Optional[GeoreferenceContext] = None,
    ) -> tuple[float, float, float]:
        x, y, z = float(pt[0]), float(pt[1]), float(pt[2])
        if georef is not None and (georef.eastings != 0.0 or georef.northings != 0.0):
            A = georef.x_axis_abscissa
            B = georef.x_axis_ordinate
            S = georef.scale
            norm = math.hypot(A, B)
            uA, uB = (A / norm, B / norm) if norm > 1e-12 else (1.0, 0.0)
            E = georef.eastings + S * (uA * x - uB * y)
            N = georef.northings + S * (uB * x + uA * y)
            H = georef.orthogonal_height + z
            return E, N, H

        if anchor_lat is not None and anchor_lon is not None and (anchor_lat != 0.0 or anchor_lon != 0.0):
            _, _, utm_e, utm_n = latlon_to_utm_wgs84(anchor_lat, anchor_lon)
            A = georef.x_axis_abscissa if georef else 1.0
            B = georef.x_axis_ordinate if georef else 0.0
            norm = math.hypot(A, B)
            uA, uB = (A / norm, B / norm) if norm > 1e-12 else (1.0, 0.0)
            E = utm_e + (uA * x - uB * y)
            N = utm_n + (uB * x + uA * y)
            H = (georef.anchor_elevation if georef else 0.0) + z
            return E, N, H

        return x, y, z

    def finalize(
        self,
        anchor_lon: float = 0.0,
        anchor_lat: float = 0.0,
        georef: Optional[GeoreferenceContext] = None,
        storey_count: int = 0,
        legacy_manifests: bool = False,
    ) -> Optional[dict]:
        if not self.triangles:
            return None

        crs_uri = None
        if georef and georef.crs_epsg:
            m = re.search(r"\d+", str(georef.crs_epsg))
            if m:
                crs_uri = f"https://www.opengis.net/def/crs/EPSG/0/{m.group(0)}"
        elif anchor_lat != 0.0 or anchor_lon != 0.0:
            utm_epsg, _, _, _ = latlon_to_utm_wgs84(anchor_lat, anchor_lon)
            crs_uri = f"https://www.opengis.net/def/crs/EPSG/0/{utm_epsg}"

        transformed_triangles = []
        g_min = np.array([np.inf, np.inf, np.inf], dtype=float)
        g_max = np.array([-np.inf, -np.inf, -np.inf], dtype=float)

        local_min_z = float(self.local_min[2])

        for sem, tri, _ in self.triangles:
            p0 = self._transform_point(tri[0], anchor_lon, anchor_lat, georef)
            p1 = self._transform_point(tri[1], anchor_lon, anchor_lat, georef)
            p2 = self._transform_point(tri[2], anchor_lon, anchor_lat, georef)

            cj_sem = CITYJSON_SEMANTIC_MAP.get(sem, "WallSurface")
            if sem == "SlabSurface":
                e1 = tri[1] - tri[0]
                e2 = tri[2] - tri[0]
                n = np.cross(e1, e2)
                norm_len = np.linalg.norm(n)
                if norm_len > 1e-12:
                    nz = n[2] / norm_len
                    if nz < -0.7 and tri[:, 2].mean() <= local_min_z + 0.25:
                        cj_sem = "GroundSurface"

            pts = (p0, p1, p2)
            for p in pts:
                g_min = np.minimum(g_min, p)
                g_max = np.maximum(g_max, p)
            transformed_triangles.append((cj_sem, pts))

        scale = [0.001, 0.001, 0.001]
        translate = [round(float(g_min[0]), 3), round(float(g_min[1]), 3), round(float(g_min[2]), 3)]

        vertex_map: dict[tuple[int, int, int], int] = {}
        vertices: list[list[int]] = []

        def _get_v_idx(pt: tuple[float, float, float]) -> int:
            ix = int(round((pt[0] - translate[0]) / scale[0]))
            iy = int(round((pt[1] - translate[1]) / scale[1]))
            iz = int(round((pt[2] - translate[2]) / scale[2]))
            key = (ix, iy, iz)
            idx = vertex_map.get(key)
            if idx is None:
                idx = len(vertices)
                vertices.append([ix, iy, iz])
                vertex_map[key] = idx
            return idx

        surface_types: list[dict] = []
        surface_type_to_idx: dict[str, int] = {}

        boundaries: list[list[list[int]]] = []
        values: list[int] = []

        for cj_sem, (p0, p1, p2) in transformed_triangles:
            i0 = _get_v_idx(p0)
            i1 = _get_v_idx(p1)
            i2 = _get_v_idx(p2)
            if i0 == i1 or i1 == i2 or i0 == i2:
                continue

            if cj_sem not in surface_type_to_idx:
                surface_type_to_idx[cj_sem] = len(surface_types)
                surface_types.append({"type": cj_sem})

            boundaries.append([[i0, i1, i2]])
            values.append(surface_type_to_idx[cj_sem])

        if not boundaries:
            return None

        building_id = f"Building_{self.dataset}"
        measured_height = round(float(g_max[2] - g_min[2]), 2)

        attributes: dict = {
            "dataset": self.dataset,
            "measuredHeight": measured_height,
        }
        if self.building_name:
            attributes["name"] = self.building_name
        if storey_count > 0:
            attributes["storeysAboveGround"] = storey_count

        metadata: dict = {
            "datasetTitle": self.building_name,
            "geographicalExtent": [
                round(float(g_min[0]), 3),
                round(float(g_min[1]), 3),
                round(float(g_min[2]), 3),
                round(float(g_max[0]), 3),
                round(float(g_max[1]), 3),
                round(float(g_max[2]), 3),
            ],
        }
        if crs_uri:
            metadata["referenceSystem"] = crs_uri

        cityjson = {
            "type": "CityJSON",
            "version": "1.1",
            "CityObjects": {
                building_id: {
                    "type": "Building",
                    "attributes": attributes,
                    "geometry": [
                        {
                            "type": "MultiSurface",
                            "lod": "2.0",
                            "boundaries": boundaries,
                            "semantics": {
                                "surfaces": surface_types,
                                "values": values,
                            },
                        }
                    ],
                }
            },
            "vertices": vertices,
            "transform": {
                "scale": scale,
                "translate": translate,
            },
            "metadata": metadata,
        }

        out_path = self.root / self.filename
        write_json_compact(out_path, cityjson)

        if legacy_manifests:
            legacy_path = self.root / f"{self.dataset}.city.json"
            write_json_compact(legacy_path, cityjson)

        return {
            "file": out_path.name,
            "path": str(out_path),
            "bytes": out_path.stat().st_size,
            "vertices_count": len(vertices),
            "triangles_count": len(boundaries),
            "surfaces_count": len(surface_types),
            "lod": "2.0",
            "measured_height": measured_height,
        }
