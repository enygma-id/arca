# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape as xml_escape

import numpy as np

from .georef import GeoreferenceContext, latlon_to_utm_wgs84

CITYGML_SEMANTIC_MAP = {
    "RoofSurface": "RoofSurface",
    "WallSurface": "WallSurface",
    "GroundSurface": "GroundSurface",
    "SlabSurface": "OuterFloorSurface",
    "DoorSurface": "WallSurface",
    "WindowSurface": "WallSurface",
    "ColumnSurface": "WallSurface",
    "BeamSurface": "WallSurface",
    "StairSurface": "WallSurface",
    "RailingSurface": "WallSurface",
    "GenericSurface": "WallSurface",
}


class CityGMLWriter:
    """CityGML 2.0 XML writer (OGC standard for 3D city models, QGIS, FME, ArcGIS)."""

    def __init__(
        self,
        root: Path,
        dataset: str,
        filename: str = "building.gml",
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

        # Resolve CRS
        srs_name = "urn:ogc:def:crs:OGC:1.3:CRS84"
        if georef and georef.crs_epsg:
            m = re.search(r"\d+", str(georef.crs_epsg))
            if m:
                srs_name = f"urn:ogc:def:crs:EPSG::{m.group(0)}"
        elif anchor_lat != 0.0 or anchor_lon != 0.0:
            utm_epsg, _, _, _ = latlon_to_utm_wgs84(anchor_lat, anchor_lon)
            srs_name = f"urn:ogc:def:crs:EPSG::{utm_epsg}"

        g_min = np.array([np.inf, np.inf, np.inf], dtype=float)
        g_max = np.array([-np.inf, -np.inf, -np.inf], dtype=float)
        local_min_z = float(self.local_min[2])

        # Group triangles by semantic surface
        surfaces: dict[str, list[tuple[tuple[float, float, float], ...]]] = {}

        for sem, tri, _ in self.triangles:
            p0 = self._transform_point(tri[0], anchor_lon, anchor_lat, georef)
            p1 = self._transform_point(tri[1], anchor_lon, anchor_lat, georef)
            p2 = self._transform_point(tri[2], anchor_lon, anchor_lat, georef)

            cj_sem = CITYGML_SEMANTIC_MAP.get(sem, "WallSurface")
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

            surfaces.setdefault(cj_sem, []).append(pts)

        measured_height = round(float(g_max[2] - g_min[2]), 2)
        out_path = self.root / self.filename
        safe_bldg_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", self.dataset)

        total_triangles = sum(len(tri_list) for tri_list in surfaces.values())

        # Stream XML output to prevent memory overhead
        with open(out_path, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(
                '<core:CityModel xmlns:core="http://www.opengis.net/citygml/2.0"\n'
                '                xmlns:bldg="http://www.opengis.net/citygml/building/2.0"\n'
                '                xmlns:gml="http://www.opengis.net/gml"\n'
                '                xmlns:xlink="http://www.w3.org/1999/xlink"\n'
                '                xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n'
                '                xsi:schemaLocation="http://www.opengis.net/citygml/building/2.0 '
                'http://schemas.opengis.net/citygml/building/2.0/building.xsd">\n'
            )
            f.write(
                f'  <gml:boundedBy>\n'
                f'    <gml:Envelope srsName="{srs_name}">\n'
                f'      <gml:lowerCorner>{g_min[0]:.3f} {g_min[1]:.3f} {g_min[2]:.3f}</gml:lowerCorner>\n'
                f'      <gml:upperCorner>{g_max[0]:.3f} {g_max[1]:.3f} {g_max[2]:.3f}</gml:upperCorner>\n'
                f'    </gml:Envelope>\n'
                f'  </gml:boundedBy>\n'
            )
            f.write('  <core:cityObjectMember>\n')
            f.write(f'    <bldg:Building gml:id="bldg_{safe_bldg_id}">\n')
            if self.building_name:
                f.write(f'      <gml:name>{xml_escape(self.building_name)}</gml:name>\n')
            f.write(
                f'      <bldg:measuredHeight uom="urn:ogc:def:uom:OGC:1.0:metre">{measured_height:.2f}</bldg:measuredHeight>\n'
            )
            if storey_count > 0:
                f.write(f'      <bldg:storeysAboveGround>{storey_count}</bldg:storeysAboveGround>\n')

            poly_idx = 0
            for sem_name, tris in sorted(surfaces.items()):
                f.write('      <bldg:boundedBy>\n')
                f.write(f'        <bldg:{sem_name} gml:id="{sem_name}_{safe_bldg_id}">\n')
                f.write('          <bldg:lod2MultiSurface>\n')
                f.write(f'            <gml:MultiSurface srsName="{srs_name}">\n')

                for p0, p1, p2 in tris:
                    poly_idx += 1
                    f.write('              <gml:surfaceMember>\n')
                    f.write(f'                <gml:Polygon gml:id="poly_{safe_bldg_id}_{poly_idx}">\n')
                    f.write('                  <gml:exterior>\n')
                    f.write('                    <gml:LinearRing>\n')
                    # LinearRing in GML must close (p0, p1, p2, p0)
                    f.write(
                        f'                      <gml:posList>'
                        f'{p0[0]:.3f} {p0[1]:.3f} {p0[2]:.3f} '
                        f'{p1[0]:.3f} {p1[1]:.3f} {p1[2]:.3f} '
                        f'{p2[0]:.3f} {p2[1]:.3f} {p2[2]:.3f} '
                        f'{p0[0]:.3f} {p0[1]:.3f} {p0[2]:.3f}'
                        f'</gml:posList>\n'
                    )
                    f.write('                    </gml:LinearRing>\n')
                    f.write('                  </gml:exterior>\n')
                    f.write('                </gml:Polygon>\n')
                    f.write('              </gml:surfaceMember>\n')

                f.write('            </gml:MultiSurface>\n')
                f.write('          </bldg:lod2MultiSurface>\n')
                f.write(f'        </bldg:{sem_name}>\n')
                f.write('      </bldg:boundedBy>\n')

            f.write('    </bldg:Building>\n')
            f.write('  </core:cityObjectMember>\n')
            f.write('</core:CityModel>\n')

        if legacy_manifests:
            legacy_path = self.root / f"{self.dataset}.gml"
            import shutil
            shutil.copyfile(out_path, legacy_path)

        return {
            "file": out_path.name,
            "path": str(out_path),
            "bytes": out_path.stat().st_size,
            "triangles_count": total_triangles,
            "surfaces_count": len(surfaces),
            "lod": "2.0",
            "measured_height": measured_height,
        }
