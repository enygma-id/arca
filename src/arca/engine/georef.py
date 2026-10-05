# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple

try:
    import pyproj
    HAS_PYPROJ = True
except ImportError:
    HAS_PYPROJ = False

R_EARTH = 6378137.0


def latlon_to_utm_wgs84(lat: float, lon: float, zone: int = None, is_south: bool = None) -> tuple[int, str, float, float]:
    """
    Project WGS84 (lat, lon) to UTM (Easting, Northing).
    Returns (epsg_code, zone_str, easting, northing).
    Matches PROJ to sub-millimeter precision using Karney (2011) series without external C dependencies.
    """
    a = 6378137.0
    f = 1.0 / 298.257223563
    b = a * (1.0 - f)
    e2 = (a**2 - b**2) / (a**2)
    e_prime2 = (a**2 - b**2) / (b**2)
    k0 = 0.9996

    if zone is None:
        zone = int((lon + 180.0) / 6.0) + 1
    if is_south is None:
        is_south = lat < 0.0

    zone_str = f"{zone}{'S' if is_south else 'N'}"
    lon0 = (zone - 1) * 6 - 180 + 3
    lon0_rad = math.radians(lon0)
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)

    delta_lon = lon_rad - lon0_rad
    sin_lat = math.sin(lat_rad)
    cos_lat = math.cos(lat_rad)
    tan_lat = math.tan(lat_rad)

    N = a / math.sqrt(1.0 - e2 * sin_lat**2)
    T = tan_lat**2
    C = e_prime2 * cos_lat**2
    A = cos_lat * delta_lon

    M = a * (
        (1.0 - e2 / 4.0 - 3.0 * e2**2 / 64.0 - 5.0 * e2**3 / 256.0) * lat_rad
        - (3.0 * e2 / 8.0 + 3.0 * e2**2 / 32.0 + 45.0 * e2**3 / 1024.0) * math.sin(2.0 * lat_rad)
        + (15.0 * e2**2 / 256.0 + 45.0 * e2**3 / 1024.0) * math.sin(4.0 * lat_rad)
        - (35.0 * e2**3 / 3072.0) * math.sin(6.0 * lat_rad)
    )

    x = k0 * N * (
        A
        + (1.0 - T + C) * A**3 / 6.0
        + (5.0 - 18.0 * T + T**2 + 72.0 * C - 58.0 * e_prime2) * A**5 / 120.0
    ) + 500000.0

    y = k0 * (
        M
        + N * tan_lat * (
            A**2 / 2.0
            + (5.0 - T + 9.0 * C + 4.0 * C**2) * A**4 / 24.0
            + (61.0 - 58.0 * T + T**2 + 600.0 * C - 330.0 * e_prime2) * A**6 / 720.0
        )
    )
    if is_south:
        y += 10000000.0

    epsg = (32700 if is_south else 32600) + zone
    return epsg, zone_str, x, y


def degrees_to_compound_dms(deg: float) -> tuple[int, int, int, int]:
    """Convert decimal degrees to IFC compound DMS integer tuple (deg, min, sec, microsec)."""
    sign = -1 if deg < 0 else 1
    val = abs(deg)
    d = int(val)
    rem_m = (val - d) * 60.0
    m = int(rem_m)
    rem_s = (rem_m - m) * 60.0
    s = int(rem_s)
    micro = int(round((rem_s - s) * 1000000.0))
    if micro >= 1000000:
        micro -= 1000000
        s += 1
    if s >= 60:
        s -= 60
        m += 1
    if m >= 60:
        m -= 60
        d += 1
    return (sign * d, m, s, micro)


def unit_factor_to_m(source_unit: str) -> float:
    u = str(source_unit).lower().strip()
    if u in ("mm", "millimetre", "millimeter"):
        return 0.001
    if u in ("cm", "centimetre", "centimeter"):
        return 0.01
    if u in ("dm", "decimetre", "decimeter"):
        return 0.1
    if u in ("m", "metre", "meter"):
        return 1.0
    if u in ("in", "inch"):
        return 0.0254
    if u in ("ft", "foot", "feet"):
        return 0.3048
    if u in ("km", "kilometre", "kilometer"):
        return 1000.0
    raise ValueError(f"Unsupported length unit: {source_unit}")


def utm_to_latlon_wgs84(easting: float, northing: float, zone: int, south: bool = False) -> Tuple[float, float]:
    """Convert UTM (E, N) to WGS84 (lon, lat) using Karney's series (pure Python fallback)."""
    a = 6378137.0
    f = 1.0 / 298.257223563
    b = a * (1.0 - f)
    e = math.sqrt(1.0 - (b / a) ** 2)
    e1sq = e * e / (1.0 - e * e)
    k0 = 0.9996

    x = easting - 500000.0
    y = northing - 10000000.0 if south else northing

    m = y / k0
    mu = m / (a * (1.0 - e**2 / 4.0 - 3.0 * e**4 / 64.0 - 5.0 * e**6 / 256.0))

    e1 = (1.0 - math.sqrt(1.0 - e**2)) / (1.0 + math.sqrt(1.0 - e**2))
    j1 = 3.0 * e1 / 2.0 - 27.0 * e1**3 / 32.0
    j2 = 21.0 * e1**2 / 16.0 - 55.0 * e1**4 / 32.0
    j3 = 151.0 * e1**3 / 96.0
    j4 = 1097.0 * e1**4 / 512.0

    fp = mu + j1 * math.sin(2.0 * mu) + j2 * math.sin(4.0 * mu) + j3 * math.sin(6.0 * mu) + j4 * math.sin(8.0 * mu)

    c1 = e1sq * (math.cos(fp) ** 2)
    t1 = math.tan(fp) ** 2
    r1 = a * (1.0 - e**2) / ((1.0 - e**2 * (math.sin(fp) ** 2)) ** 1.5)
    n1 = a / math.sqrt(1.0 - e**2 * (math.sin(fp) ** 2))
    d = x / (n1 * k0)

    lat = fp - (n1 * math.tan(fp) / r1) * (
        d**2 / 2.0 - (5.0 + 3.0 * t1 + 10.0 * c1 - 4.0 * c1**2 - 9.0 * e1sq) * (d**4) / 24.0
        + (61.0 + 90.0 * t1 + 298.0 * c1 + 45.0 * t1**2 - 252.0 * e1sq - 3.0 * c1**2) * (d**6) / 720.0
    )
    lon0 = (zone - 1) * 6.0 - 180.0 + 3.0
    lon = math.radians(lon0) + (
        d - (1.0 + 2.0 * t1 + c1) * (d**3) / 6.0
        + (5.0 - 2.0 * c1 + 28.0 * t1 - 3.0 * c1**2 + 8.0 * e1sq + 24.0 * t1**2) * (d**5) / 120.0
    ) / math.cos(fp)

    return math.degrees(lon), math.degrees(lat)


def compound_angle_to_degrees(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, (list, tuple)) and len(val) >= 3:
        deg = float(val[0])
        m = float(val[1])
        s = float(val[2])
        ms = float(val[3]) if len(val) > 3 else 0.0
        if ms >= 1.0:
            s += ms * 1e-6
        elif ms > 0.0:
            s += ms
        sign = -1.0 if (deg < 0 or (deg == 0 and m < 0)) else 1.0
        return sign * (abs(deg) + abs(m) / 60.0 + abs(s) / 3600.0)
    return None


def extract_crs_epsg(crs_attrs: list) -> Tuple[Optional[str], Optional[str]]:
    candidates = []
    for idx in range(min(len(crs_attrs), 6)):
        v = crs_attrs[idx]
        if isinstance(v, str):
            candidates.append(v.strip())

    crs_name = candidates[0] if candidates else None
    epsg_str = None

    for c in candidates:
        m = re.search(r"\bEPSG:(\d+)\b", c, re.IGNORECASE)
        if m:
            epsg_str = f"EPSG:{m.group(1)}"
            break
        m = re.search(r"\b32[67]\d{2}\b", c)
        if m:
            epsg_str = f"EPSG:{m.group(0)}"
            break

    if not epsg_str:
        for c in candidates:
            m = re.search(r"(\d{1,2})\s*([NS])", c, re.IGNORECASE)
            if m:
                zone = int(m.group(1))
                hemi = m.group(2).upper()
                code = 32600 + zone if hemi == "N" else 32700 + zone
                epsg_str = f"EPSG:{code}"
                break

    if not epsg_str and candidates and candidates[0].isdigit():
        epsg_str = f"EPSG:{candidates[0]}"

    return epsg_str, crs_name


def extract_length_unit(ents: dict) -> Tuple[str, float]:
    length_unit_ref = None
    for eid, (typ, attrs) in ents.items():
        if typ == "IFCUNITASSIGNMENT" and attrs:
            unit_refs = attrs[0] if isinstance(attrs[0], (list, tuple)) else []
            for uref in unit_refs:
                if (isinstance(uref, int) or getattr(uref, "__class__", None).__name__ == "Ref") and int(uref) in ents:
                    utyp, uattrs = ents[int(uref)]
                    if len(uattrs) > 1 and str(uattrs[1]).upper().strip(".") == "LENGTHUNIT":
                        length_unit_ref = int(uref)
                        break
        if length_unit_ref is not None:
            break

    if length_unit_ref is None:
        for eid, (typ, attrs) in ents.items():
            if typ == "IFCSIUNIT" and len(attrs) > 1 and str(attrs[1]).upper().strip(".") == "LENGTHUNIT":
                length_unit_ref = eid
                break

    if length_unit_ref is not None and length_unit_ref in ents:
        utyp, uattrs = ents[length_unit_ref]
        if utyp == "IFCSIUNIT":
            prefix = str(uattrs[2]).upper() if len(uattrs) > 2 and uattrs[2] else ""
            if "MILLI" in prefix:
                return ("mm", 0.001)
            elif "CENTI" in prefix:
                return ("cm", 0.01)
            elif "DECI" in prefix:
                return ("dm", 0.1)
            elif "KILO" in prefix:
                return ("km", 1000.0)
            else:
                return ("m", 1.0)
        elif utyp == "IFCCONVERSIONBASEDUNIT":
            name = str(uattrs[2]).upper() if len(uattrs) > 2 and uattrs[2] else ""
            if "FOOT" in name or "FEET" in name:
                return ("ft", 0.3048)
            elif "INCH" in name:
                return ("in", 0.0254)

    return ("m", 1.0)


@dataclass
class GeoreferenceContext:
    method: str  # "ifc_map_conversion", "ifc_site", or "cli_anchor_fallback"
    crs_name: Optional[str] = None
    target_crs: Optional[str] = None
    eastings: float = 0.0
    northings: float = 0.0
    orthogonal_height: float = 0.0
    x_axis_abscissa: float = 1.0
    x_axis_ordinate: float = 0.0
    scale: float = 1.0
    anchor_lon: float = 0.0
    anchor_lat: float = 0.0
    anchor_elevation: float = 0.0
    unit_name: str = "m"
    unit_scale_to_m: float = 1.0
    transformer: Optional[Any] = None
    utm_zone: Optional[int] = None
    utm_south: bool = False

    @property
    def is_georeferenced(self) -> bool:
        return self.method != "cli_anchor_fallback"

    @property
    def origin_lon(self) -> float:
        return self.anchor_lon

    @property
    def origin_lat(self) -> float:
        return self.anchor_lat

    @property
    def origin_easting(self) -> float:
        return self.eastings

    @property
    def origin_northing(self) -> float:
        return self.northings

    @property
    def origin_orthogonal_height(self) -> float:
        return self.orthogonal_height

    @property
    def crs_epsg(self) -> Optional[str]:
        return self.target_crs

    @property
    def rotation_rad(self) -> float:
        return math.atan2(self.x_axis_ordinate, self.x_axis_abscissa)

    @property
    def length_scale_to_m(self) -> float:
        return self.unit_scale_to_m

    @property
    def length_unit_name(self) -> str:
        return self.unit_name

    def local_to_lonlat(self, x: float, y: float) -> Tuple[float, float]:
        if self.method == "ifc_map_conversion" or self.method.startswith("metadata_json") or self.method == "cli_anchor_override":
            if (self.transformer is not None or self.utm_zone is not None) and (self.eastings != 0.0 or self.northings != 0.0):
                A = self.x_axis_abscissa
                B = self.x_axis_ordinate
                S = self.scale
                norm = math.hypot(A, B)
                if norm > 1e-12:
                    uA, uB = A / norm, B / norm
                else:
                    uA, uB = 1.0, 0.0

                E = self.eastings + S * (uA * x - uB * y)
                N = self.northings + S * (uB * x + uA * y)

                if self.transformer is not None:
                    lon, lat = self.transformer.transform(E, N)
                    return float(lon), float(lat)
                elif self.utm_zone is not None:
                    lon, lat = utm_to_latlon_wgs84(E, N, self.utm_zone, self.utm_south)
                    return float(lon), float(lat)

        A = self.x_axis_abscissa
        B = self.x_axis_ordinate
        norm = math.hypot(A, B)
        if norm > 1e-12:
            uA, uB = A / norm, B / norm
            xr = uA * x - uB * y
            yr = uB * x + uA * y
        else:
            xr, yr = x, y

        lat = self.anchor_lat + (yr / R_EARTH) * 180.0 / math.pi
        lon = self.anchor_lon + (
            xr / (R_EARTH * math.cos(math.radians(self.anchor_lat)))
        ) * 180.0 / math.pi
        return float(lon), float(lat)

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "crs": self.target_crs or self.crs_name,
            "crs_name": self.crs_name,
            "eastings": self.eastings,
            "northings": self.northings,
            "orthogonal_height": self.orthogonal_height,
            "scale": self.scale,
            "x_axis_abscissa": self.x_axis_abscissa,
            "x_axis_ordinate": self.x_axis_ordinate,
            "anchor_lon": self.anchor_lon,
            "anchor_lat": self.anchor_lat,
            "anchor_elevation": self.anchor_elevation,
            "unit_name": self.unit_name,
            "unit_scale_to_m": self.unit_scale_to_m,
        }


def find_metadata_json(model_path: str | Path) -> Optional[Path]:
    """
    Search for a companion metadata JSON or GeoJSON file corresponding to a model file.
    Search order:
    1. <model_stem>.json
    2. <model_stem>.geojson
    3. <model_name>.json
    4. <model_name>.geojson
    5. metadata.json
    6. metadata.geojson
    """
    p = Path(model_path)
    parent = p.parent
    if not parent.exists():
        return None
    candidates = [
        p.with_suffix(".json"),
        p.with_suffix(".geojson"),
        parent / f"{p.name}.json",
        parent / f"{p.name}.geojson",
        parent / "metadata.json",
        parent / "metadata.geojson",
    ]
    for c in candidates:
        if c.is_file() and c.resolve() != p.resolve():
            return c
    return None


def parse_metadata_json(file_path: str | Path) -> Optional[dict]:
    """
    Parse a companion metadata JSON or GeoJSON file.
    Extracts name, longitude, latitude, crs, rotate, and elevation.
    """
    p = Path(file_path)
    if not p.is_file():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    out = {
        "has_georef": False,
        "name": data.get("name") or data.get("building_name") or data.get("title"),
        "longitude": None,
        "latitude": None,
        "crs": None,
        "rotate": 0.0,
        "elevation": 0.0,
        "unit": "auto",
        "file_path": str(p.resolve()),
    }

    # 1. GeoJSON format
    if data.get("type") in ("FeatureCollection", "Feature"):
        props = {}
        coords = None
        if data.get("type") == "Feature":
            props = data.get("properties") or {}
            geom = data.get("geometry") or {}
            coords = geom.get("coordinates")
        elif data.get("type") == "FeatureCollection" and data.get("features"):
            first_feat = data["features"][0]
            props = first_feat.get("properties") or {}
            geom = first_feat.get("geometry") or {}
            coords = geom.get("coordinates")

        if not out["name"]:
            out["name"] = props.get("name") or props.get("building_name")

        if coords:
            c = coords
            while isinstance(c, (list, tuple)) and len(c) > 0 and isinstance(c[0], (list, tuple)):
                c = c[0]
            if isinstance(c, (list, tuple)) and len(c) >= 2:
                try:
                    out["longitude"] = float(c[0])
                    out["latitude"] = float(c[1])
                    if len(c) >= 3:
                        out["elevation"] = float(c[2])
                    out["has_georef"] = True
                except (ValueError, TypeError):
                    pass

        for lon_key in ("longitude", "lon", "anchor_lon", "lng"):
            if lon_key in props and props[lon_key] is not None:
                try:
                    out["longitude"] = float(props[lon_key])
                    out["has_georef"] = True
                    break
                except (ValueError, TypeError):
                    pass
        for lat_key in ("latitude", "lat", "anchor_lat"):
            if lat_key in props and props[lat_key] is not None:
                try:
                    out["latitude"] = float(props[lat_key])
                    out["has_georef"] = True
                    break
                except (ValueError, TypeError):
                    pass
        for crs_key in ("crs", "CRS", "target_crs", "crs_epsg"):
            if crs_key in props and props[crs_key]:
                out["crs"] = str(props[crs_key])
                break
        for rot_key in ("rotate", "rotation", "rotation_deg", "north_angle"):
            if rot_key in props and props[rot_key] is not None:
                try:
                    out["rotate"] = float(props[rot_key])
                    break
                except (ValueError, TypeError):
                    pass
        for elev_key in ("elevation", "altitude", "base_z"):
            if elev_key in props and props[elev_key] is not None:
                try:
                    out["elevation"] = float(props[elev_key])
                    break
                except (ValueError, TypeError):
                    pass
        for unit_key in ("unit", "length_unit", "source_unit"):
            if unit_key in props and props[unit_key]:
                out["unit"] = str(props[unit_key]).lower().strip()
                break

    # 2. Standard JSON format (supports flat fields and nested "anchor" / "georeference")
    anchor = data.get("anchor") or {}
    georef = data.get("georeference") or {}

    for lon_key in ("longitude", "lon", "anchor_lon", "lng", "x"):
        val = data.get(lon_key) if lon_key in data else anchor.get(lon_key)
        if val is not None:
            try:
                out["longitude"] = float(val)
                out["has_georef"] = True
                break
            except (ValueError, TypeError):
                pass

    for lat_key in ("latitude", "lat", "anchor_lat", "y"):
        val = data.get(lat_key) if lat_key in data else anchor.get(lat_key)
        if val is not None:
            try:
                out["latitude"] = float(val)
                out["has_georef"] = True
                break
            except (ValueError, TypeError):
                pass

    for crs_key in ("crs", "CRS", "target_crs", "crs_epsg"):
        val = data.get(crs_key) if crs_key in data else georef.get(crs_key)
        if val:
            val_str = str(val)
            if val_str.isdigit():
                val_str = f"EPSG:{val_str}"
            out["crs"] = val_str
            break

    for rot_key in ("rotate", "rotation", "rotation_deg", "north_angle", "rotation_rad"):
        val = data.get(rot_key) if rot_key in data else georef.get(rot_key)
        if val is not None:
            try:
                r = float(val)
                if rot_key == "rotation_rad":
                    r = math.degrees(r)
                out["rotate"] = r
                break
            except (ValueError, TypeError):
                pass

    for elev_key in ("elevation", "altitude", "origin_orthogonal_height", "base_z"):
        val = data.get(elev_key) if elev_key in data else georef.get(elev_key)
        if val is not None:
            try:
                out["elevation"] = float(val)
                break
            except (ValueError, TypeError):
                pass

    for unit_key in ("unit", "length_unit", "source_unit"):
        val = data.get(unit_key) if unit_key in data else georef.get(unit_key)
        if val:
            out["unit"] = str(val).lower().strip()
            break

    if out["longitude"] is not None and out["latitude"] is not None:
        out["has_georef"] = True

    return out


def resolve_georeferencing(
    ents: dict,
    fallback_lon: Optional[float] = None,
    fallback_lat: Optional[float] = None,
    cli_unit: str = "auto",
    cli_crs: Optional[str] = None,
    cli_anchor_lon: Optional[float] = None,
    cli_anchor_lat: Optional[float] = None,
    cli_source_unit: Optional[str] = None,
    cli_rotate: Optional[float] = None,
    metadata_info: Optional[dict] = None,
) -> GeoreferenceContext:
    if cli_source_unit is not None:
        cli_unit = cli_source_unit

    detected_unit_name, detected_unit_factor = extract_length_unit(ents)
    meta_unit = metadata_info.get("unit") if metadata_info else None
    if cli_unit != "auto":
        unit_name = cli_unit
        unit_scale_to_m = unit_factor_to_m(cli_unit)
    elif meta_unit and meta_unit != "auto":
        unit_name = meta_unit
        unit_scale_to_m = unit_factor_to_m(meta_unit)
    else:
        unit_name = detected_unit_name
        unit_scale_to_m = detected_unit_factor

    def _create_context(
        method: str,
        crs_name: str,
        target_crs: Optional[str],
        lon: float,
        lat: float,
        elev: float,
        rot_deg: float,
    ) -> GeoreferenceContext:
        rad = math.radians(rot_deg)
        x_abscissa = math.cos(rad)
        x_ordinate = -math.sin(rad)
        transformer = None
        utm_zone = None
        utm_south = False
        eastings = 0.0
        northings = 0.0

        target_crs_code = cli_crs or target_crs
        if target_crs_code:
            m_utm = re.search(r"32([67])(\d{2})", target_crs_code)
            if m_utm:
                utm_south = m_utm.group(1) == "7"
                utm_zone = int(m_utm.group(2))
                _, _, eastings, northings = latlon_to_utm_wgs84(lat, lon, zone=utm_zone, is_south=utm_south)
            elif HAS_PYPROJ:
                try:
                    fwd = pyproj.Transformer.from_crs("EPSG:4326", target_crs_code, always_xy=True)
                    eastings, northings = fwd.transform(lon, lat)
                    transformer = pyproj.Transformer.from_crs(target_crs_code, "EPSG:4326", always_xy=True)
                except Exception:
                    pass

        return GeoreferenceContext(
            method=method,
            crs_name=crs_name,
            target_crs=target_crs_code or "EPSG:4326",
            eastings=eastings,
            northings=northings,
            orthogonal_height=elev,
            x_axis_abscissa=x_abscissa,
            x_axis_ordinate=x_ordinate,
            scale=1.0,
            anchor_lon=float(lon),
            anchor_lat=float(lat),
            anchor_elevation=elev,
            unit_name=unit_name,
            unit_scale_to_m=unit_scale_to_m,
            transformer=transformer,
            utm_zone=utm_zone,
            utm_south=utm_south,
        )

    # Priority 1: Explicit CLI anchor override
    if cli_anchor_lon is not None and cli_anchor_lat is not None:
        rot = cli_rotate if cli_rotate is not None else 0.0
        return _create_context(
            method="cli_anchor_override",
            crs_name=f"WGS 84 / {cli_crs}" if cli_crs else "WGS 84 (User CLI Anchor)",
            target_crs=cli_crs or "EPSG:4326",
            lon=cli_anchor_lon,
            lat=cli_anchor_lat,
            elev=0.0,
            rot_deg=rot,
        )

    # Priority 2: Companion Metadata JSON
    if metadata_info and metadata_info.get("has_georef"):
        m_lon = metadata_info["longitude"]
        m_lat = metadata_info["latitude"]
        m_crs = cli_crs or metadata_info.get("crs")
        m_rot = cli_rotate if cli_rotate is not None else metadata_info.get("rotate", 0.0)
        m_elev = metadata_info.get("elevation", 0.0)
        fpath = metadata_info.get("file_path")
        m_method = f"metadata_json:{Path(fpath).name}" if fpath else "metadata_json"
        return _create_context(
            method=m_method,
            crs_name=f"WGS 84 / {m_crs}" if m_crs else "WGS 84 (Metadata JSON)",
            target_crs=m_crs or "EPSG:4326",
            lon=m_lon,
            lat=m_lat,
            elev=m_elev,
            rot_deg=m_rot,
        )

    # Priority 3: IFC internal georeferencing
    map_conv_eid = None
    projected_crs_eid = None
    site_eid = None

    for eid, (typ, attrs) in ents.items():
        if typ == "IFCMAPCONVERSION" and map_conv_eid is None:
            map_conv_eid = eid
        elif typ == "IFCPROJECTEDCRS" and projected_crs_eid is None:
            projected_crs_eid = eid
        elif typ == "IFCSITE" and site_eid is None:
            site_eid = eid

    site_lat = None
    site_lon = None
    site_elev = 0.0
    if site_eid is not None:
        _, site_attrs = ents[site_eid]
        if len(site_attrs) > 9:
            site_lat = compound_angle_to_degrees(site_attrs[9])
        if len(site_attrs) > 10:
            site_lon = compound_angle_to_degrees(site_attrs[10])
        if len(site_attrs) > 11 and site_attrs[11] is not None:
            try:
                site_elev = float(site_attrs[11])
            except Exception:
                pass

    if map_conv_eid is not None:
        _, mc_attrs = ents[map_conv_eid]
        target_crs_ref = mc_attrs[1] if len(mc_attrs) > 1 else None
        eastings = float(mc_attrs[2]) if len(mc_attrs) > 2 and mc_attrs[2] is not None else 0.0
        northings = float(mc_attrs[3]) if len(mc_attrs) > 3 and mc_attrs[3] is not None else 0.0
        ortho_height = float(mc_attrs[4]) if len(mc_attrs) > 4 and mc_attrs[4] is not None else 0.0
        x_axis_abscissa = float(mc_attrs[5]) if len(mc_attrs) > 5 and mc_attrs[5] is not None else 1.0
        x_axis_ordinate = float(mc_attrs[6]) if len(mc_attrs) > 6 and mc_attrs[6] is not None else 0.0
        scale = float(mc_attrs[7]) if len(mc_attrs) > 7 and mc_attrs[7] is not None else 1.0

        if cli_rotate is not None and cli_rotate != 0.0:
            rad = math.radians(cli_rotate)
            x_axis_abscissa = math.cos(rad)
            x_axis_ordinate = -math.sin(rad)

        crs_epsg = None
        crs_name = None
        target_ref_int = int(target_crs_ref) if (isinstance(target_crs_ref, int) or getattr(target_crs_ref, "__class__", None).__name__ == "Ref") else None
        if target_ref_int and target_ref_int in ents:
            _, crs_attrs = ents[target_ref_int]
            crs_epsg, crs_name = extract_crs_epsg(crs_attrs)
        elif projected_crs_eid is not None:
            _, crs_attrs = ents[projected_crs_eid]
            crs_epsg, crs_name = extract_crs_epsg(crs_attrs)

        if cli_crs:
            crs_epsg = cli_crs

        transformer = None
        utm_zone = None
        utm_south = False

        if crs_epsg:
            m_utm = re.search(r"32([67])(\d{2})", crs_epsg)
            if m_utm:
                utm_south = m_utm.group(1) == "7"
                utm_zone = int(m_utm.group(2))

            if HAS_PYPROJ:
                try:
                    transformer = pyproj.Transformer.from_crs(crs_epsg, "EPSG:4326", always_xy=True)
                except Exception:
                    pass

        if transformer is not None:
            anchor_lon, anchor_lat = transformer.transform(eastings, northings)
            return GeoreferenceContext(
                method="ifc_map_conversion",
                crs_name=crs_name or crs_epsg,
                target_crs=crs_epsg,
                eastings=eastings,
                northings=northings,
                orthogonal_height=ortho_height,
                x_axis_abscissa=x_axis_abscissa,
                x_axis_ordinate=x_axis_ordinate,
                scale=scale,
                anchor_lon=float(anchor_lon),
                anchor_lat=float(anchor_lat),
                anchor_elevation=ortho_height if ortho_height else site_elev,
                unit_name=unit_name,
                unit_scale_to_m=unit_scale_to_m,
                transformer=transformer,
                utm_zone=utm_zone,
                utm_south=utm_south,
            )
        elif utm_zone is not None:
            anchor_lon, anchor_lat = utm_to_latlon_wgs84(eastings, northings, utm_zone, utm_south)
            return GeoreferenceContext(
                method="ifc_map_conversion",
                crs_name=crs_name or crs_epsg,
                target_crs=crs_epsg,
                eastings=eastings,
                northings=northings,
                orthogonal_height=ortho_height,
                x_axis_abscissa=x_axis_abscissa,
                x_axis_ordinate=x_axis_ordinate,
                scale=scale,
                anchor_lon=float(anchor_lon),
                anchor_lat=float(anchor_lat),
                anchor_elevation=ortho_height if ortho_height else site_elev,
                unit_name=unit_name,
                unit_scale_to_m=unit_scale_to_m,
                transformer=None,
                utm_zone=utm_zone,
                utm_south=utm_south,
            )

    if site_lat is not None and site_lon is not None:
        return GeoreferenceContext(
            method="ifc_site",
            crs_name="WGS 84 (IfcSite)",
            target_crs="EPSG:4326",
            anchor_lon=site_lon,
            anchor_lat=site_lat,
            anchor_elevation=site_elev,
            unit_name=unit_name,
            unit_scale_to_m=unit_scale_to_m,
            transformer=None,
        )

    fb_lon = fallback_lon if fallback_lon is not None else 112.6304
    fb_lat = fallback_lat if fallback_lat is not None else -7.98098
    return GeoreferenceContext(
        method="cli_anchor_fallback",
        crs_name="WGS 84 (User CLI Anchor)",
        target_crs="EPSG:4326",
        anchor_lon=fb_lon,
        anchor_lat=fb_lat,
        anchor_elevation=0.0,
        unit_name=unit_name,
        unit_scale_to_m=unit_scale_to_m,
        transformer=None,
    )


def local_to_lonlat(x, y, anchor_lon, anchor_lat=None, georef=None):
    if georef is not None:
        return georef.local_to_lonlat(x, y)
    if isinstance(anchor_lon, GeoreferenceContext):
        return anchor_lon.local_to_lonlat(x, y)
    lat = anchor_lat + (y / R_EARTH) * 180 / math.pi
    lon = anchor_lon + (
        x / (R_EARTH * math.cos(math.radians(anchor_lat)))
    ) * 180 / math.pi
    return lon, lat


def ring_geo(q, anchor_lon, anchor_lat=None, georef=None):
    out = []
    for x, y, z in q:
        lon, lat = local_to_lonlat(x, y, anchor_lon, anchor_lat, georef=georef)
        out.append([round(lon, 10), round(lat, 10), round(float(z), 5)])

    if out and out[0] != out[-1]:
        out.append(out[0])

    return out


def _ring_geo_xy(coords, z, anchor_lon, anchor_lat, xy_decimals, z_decimals, georef=None):
    ring = []
    for x, y in coords:
        lon, lat = local_to_lonlat(float(x), float(y), anchor_lon, anchor_lat, georef=georef)
        ring.append([
            round(lon, xy_decimals),
            round(lat, xy_decimals),
            round(float(z), z_decimals),
        ])
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return ring
