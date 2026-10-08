# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import math
import re
import zipfile
from pathlib import Path
from typing import Optional

from .georef import (
    degrees_to_compound_dms,
    find_metadata_json,
    latlon_to_utm_wgs84,
    parse_metadata_json,
)
from .step import split_top


class ArcaInputError(ValueError):
    """Raised when an input model file is corrupt, truncated, or invalid."""
    pass

try:
    from openskp import SkpFile
    from openskp.export import ifc as openskp_ifc
    HAS_OPENSKP = True
except ImportError:
    HAS_OPENSKP = False


def detect_input_format(path: Path) -> str:
    """Detect whether input file is SketchUp (.skp) or IFC (.ifc)."""
    ext = path.suffix.lower()
    if ext == ".skp":
        return "SKP"
    if ext == ".ifc":
        return "IFC"
    try:
        with open(path, "rb") as f:
            header = f.read(512)
            if header.startswith(b"SketchUp Model"):
                return "SKP"
            if b"ISO-10303-21" in header or b"FILE_DESCRIPTION" in header:
                return "IFC"
            if header.startswith(b"PK\x03\x04"):
                try:
                    with zipfile.ZipFile(path, "r") as zf:
                        if "model.dat" in zf.namelist():
                            return "SKP"
                except Exception:
                    pass
    except Exception:
        pass
    return "UNKNOWN"


IFC_CLASS_MAP = (
    (("wall", "dinding"), ("IFCWALL", "IfcWall")),
    (("door", "pintu"), ("IFCDOOR", "IfcDoor")),
    (("window", "jendela"), ("IFCWINDOW", "IfcWindow")),
    (("slab", "floor", "lantai", "pelat"), ("IFCSLAB", "IfcSlab")),
    (("column", "pillar", "kolom", "tiang"), ("IFCCOLUMN", "IfcColumn")),
    (("beam", "joist", "balok"), ("IFCBEAM", "IfcBeam")),
    (("roof", "atap"), ("IFCROOF", "IfcRoof")),
)


def bilingual_classifier(name: str, layer: str = "") -> tuple[str, str]:
    """Bilingual EN/ID IFC semantic element classifier."""
    text = f"{name} {layer}".lower()
    for keywords, result in IFC_CLASS_MAP:
        if any(kw in text for kw in keywords):
            return result
    return "IFCBUILDINGELEMENTPROXY", "IfcBuildingElementProxy"


def restore_skp_orientation_for_ifc(scene) -> int:
    """
    Restore original SketchUp/IFC Z-up basis from OpenSKP's glTF-style Y-up scene.
    Scene:   (X_skp, Z_skp, -Y_skp)
    Inverse: (X_scene, -Z_scene, Y_scene)

    Only applies to OpenSKP < 1.3.0. In OpenSKP >= 1.3.0, openskp_ifc.export()
    internally performs the (x, -z, y) transformation. Applying it again causes
    a 90-degree pitch tilt.
    """
    try:
        from importlib.metadata import version
        ver = version("openskp")
        major, minor = [int(x) for x in ver.split(".")[:2]]
        if (major, minor) >= (1, 3):
            return 0
    except Exception:
        pass

    vertex_count = 0
    for prim in getattr(scene, "glb_primitives", []):
        positions = getattr(prim, "positions", None)
        if not positions or len(positions) % 3 != 0:
            continue
        for i in range(0, len(positions), 3):
            x = positions[i]
            y = positions[i + 1]
            z = positions[i + 2]
            positions[i] = x
            positions[i + 1] = -z
            positions[i + 2] = y
            vertex_count += 1
    return vertex_count


def extract_skp_georeference(
    skp_path: Path,
    fallback_lon: Optional[float] = None,
    fallback_lat: Optional[float] = None,
    fallback_crs: Optional[str] = None,
    fallback_rotate: float = 0.0,
    metadata_info: Optional[dict] = None,
) -> dict:
    """Extract georeference metadata from SketchUp model or companion metadata."""
    info = {
        "source": "fallback",
        "latitude": fallback_lat if fallback_lat is not None else -7.98098,
        "longitude": fallback_lon if fallback_lon is not None else 112.6304,
        "elevation": 0.0,
        "north_angle": fallback_rotate,
        "crs": fallback_crs,
        "has_georef": False,
    }

    # 1. Companion Metadata JSON (<name>.json, metadata.json, etc.)
    if metadata_info is None:
        meta_file = find_metadata_json(skp_path)
        if meta_file:
            metadata_info = parse_metadata_json(meta_file)

    if metadata_info and metadata_info.get("has_georef"):
        info["latitude"] = metadata_info["latitude"]
        info["longitude"] = metadata_info["longitude"]
        if metadata_info.get("elevation") is not None:
            info["elevation"] = float(metadata_info["elevation"])
        if metadata_info.get("rotate") is not None:
            info["north_angle"] = float(metadata_info["rotate"])
        if metadata_info.get("crs"):
            info["crs"] = str(metadata_info["crs"])
        fpath = metadata_info.get("file_path")
        info["source"] = f"metadata_json:{Path(fpath).name}" if fpath else "metadata_json"
        info["has_georef"] = True

    if not info["has_georef"] and HAS_OPENSKP:
        # 2. Legacy SKP attributes (openskp.legacy)
        try:
            import openskp.legacy as l

            if l.is_legacy(str(skp_path)):
                with open(skp_path, "rb") as f:
                    ar = l._Archive(f)
                    l._preamble(ar)
                    l._read_relationship(ar)
                    for obj in ar.slots:
                        if isinstance(obj, dict):
                            entries = obj.get("entries", {})
                            lat = entries.get("Latitude") or entries.get("latitude")
                            lon = entries.get("Longitude") or entries.get("longitude")
                            if lat is not None and lon is not None:
                                info["latitude"] = float(lat)
                                info["longitude"] = float(lon)
                                if "NorthAngle" in entries:
                                    info["north_angle"] = float(entries["NorthAngle"])
                                info["source"] = f"skp_legacy_attr:{obj.get('name', 'GeoReference')}"
                                info["has_georef"] = True
                                break
        except Exception:
            pass

    if not info["has_georef"]:
        # 3. Modern zip-based SKP
        try:
            if zipfile.is_zipfile(skp_path):
                with zipfile.ZipFile(skp_path, "r") as zf:
                    for name in zf.namelist():
                        if name.endswith((".xml", ".txt", ".json")):
                            content = zf.read(name).decode("utf-8", errors="ignore")
                            m_lat = re.search(r'Latitude[\"\'\s:=]+([+-]?\d+\.?\d*)', content, re.I)
                            m_lon = re.search(r'Longitude[\"\'\s:=]+([+-]?\d+\.?\d*)', content, re.I)
                            if m_lat and m_lon:
                                info["latitude"] = float(m_lat.group(1))
                                info["longitude"] = float(m_lon.group(1))
                                m_angle = re.search(r'NorthAngle[\"\'\s:=]+([+-]?\d+\.?\d*)', content, re.I)
                                if m_angle:
                                    info["north_angle"] = float(m_angle.group(1))
                                info["source"] = f"skp_zip_xml:{name}"
                                info["has_georef"] = True
                                break
        except Exception:
            pass

    # CLI overrides take priority
    if fallback_lat is not None:
        info["latitude"] = fallback_lat
        info["has_georef"] = True
        info["source"] = "cli_override"
    if fallback_lon is not None:
        info["longitude"] = fallback_lon
        info["has_georef"] = True
        info["source"] = "cli_override"
    if fallback_crs is not None:
        info["crs"] = fallback_crs
    if fallback_rotate != 0.0:
        info["north_angle"] = fallback_rotate

    # Compute projected UTM Easting & Northing
    epsg_num, zone_str, easting, northing = latlon_to_utm_wgs84(info["latitude"], info["longitude"])
    if not info["crs"]:
        info["crs"] = f"EPSG:{epsg_num}"
    info["utm_zone"] = zone_str
    info["easting"] = easting
    info["northing"] = northing
    return info


def inject_georeference_into_step(
    ifc_path: Path,
    out_path: Path,
    lat: float,
    lon: float,
    elev: float = 0.0,
    epsg_code: str = "EPSG:32750",
    zone_str: str = "50S",
    easting: float = 0.0,
    northing: float = 0.0,
    north_angle: float = 0.0,
):
    """Inject standard buildingSMART IfcProjectedCRS, IfcMapConversion, and IfcSite into STEP file."""
    content = ifc_path.read_text(encoding="utf-8", errors="replace")
    entity_ids = [int(m) for m in re.findall(r"#(\d+)=", content)]
    max_id = max(entity_ids) if entity_ids else 100
    crs_id = max_id + 1
    map_id = max_id + 2

    ctx_match = re.search(r"#(\d+)=IFCGEOMETRICREPRESENTATIONCONTEXT\(", content)
    ctx_id = ctx_match.group(1) if ctx_match else "12"

    unit_match = re.search(r"#(\d+)=IFCSIUNIT\(\*\,\.LENGTHUNIT\.", content)
    unit_id = unit_match.group(1) if unit_match else "$"

    lat_tuple = degrees_to_compound_dms(lat)
    lon_tuple = degrees_to_compound_dms(lon)
    lat_str = f"({lat_tuple[0]},{lat_tuple[1]},{lat_tuple[2]},{lat_tuple[3]})"
    lon_str = f"({lon_tuple[0]},{lon_tuple[1]},{lon_tuple[2]},{lon_tuple[3]})"

    site_m = re.search(r"(#\d+=IFCSITE\()(.*)(\);)", content)
    if site_m:
        prefix = site_m.group(1)
        args = split_top(site_m.group(2))
        suffix = site_m.group(3)
        if len(args) >= 12:
            args[9] = lat_str
            args[10] = lon_str
            args[11] = f"{elev:.6f}"
            new_site = prefix + ",".join(args) + suffix
            content = content[:site_m.start()] + new_site + content[site_m.end():]

    rad = math.radians(north_angle)
    x_abscissa = math.cos(rad)
    x_ordinate = -math.sin(rad)

    unit_ref = f"#{unit_id}" if unit_id != "$" else "$"
    injected = (
        f"#{crs_id}=IFCPROJECTEDCRS('{epsg_code}','WGS 84 / UTM zone {zone_str}',$,$,'UTM','{zone_str}',{unit_ref});\n"
        f"#{map_id}=IFCMAPCONVERSION(#{ctx_id},#{crs_id},{easting:.6f},{northing:.6f},{elev:.6f},{x_abscissa:.8f},{x_ordinate:.8f},1.0);\n"
        "ENDSEC;"
    )
    last_endsec = content.rfind("ENDSEC;")
    if last_endsec != -1:
        content = content[:last_endsec] + injected + content[last_endsec + 7:]
    else:
        content = content.replace("ENDSEC;", injected, 1)
    out_path.write_text(content, encoding="utf-8")


def convert_skp_to_georef_ifc(
    skp_path: Path,
    out_ifc_path: Path,
    georef: dict,
    schema: str = "IFC4",
    progress_cb=None,
) -> Path:
    """Convert SketchUp model (.skp) to IFC4 with buildingSMART georeferencing."""
    if not HAS_OPENSKP:
        raise RuntimeError(
            "Package 'openskp' is required for SKP conversion. Run: pip install openskp"
        )

    def _skp_log(msg: str, pct: int | None = None):
        if progress_cb is not None:
            ev = {"type": "progress", "message": msg, "step": 0, "total": 5}
            if pct is not None:
                ev["pct"] = pct
            progress_cb(ev)
        else:
            print(msg)

    out_ifc_path.parent.mkdir(parents=True, exist_ok=True)
    _skp_log(f"      [SKP->IFC] Reading SketchUp file: {skp_path.name}", pct=4)
    skp = SkpFile.open(str(skp_path))

    _skp_log("      [SKP->IFC] Building geometry scene & triangulation (OpenSKP)...", pct=8)
    try:
        scene = skp.build_scene()
    except Exception as exc:
        err_str = str(exc)
        if "not a zip file" in err_str.lower() or "badzipfile" in err_str.lower():
            raise ArcaInputError(
                f"File '{skp_path.name}' corrupt or incomplete (truncated). "
                "The SketchUp ZIP container is missing or cut off midway during transfer/download. "
                "Please re-copy/download the full file and verify file size."
            ) from exc
        raise
    prims = getattr(scene, "glb_primitives", [])
    _skp_log(f"      [SKP->IFC] Detected {len(prims):,} mesh primitive(s)", pct=11)

    _skp_log("      [SKP->IFC] Correcting coordinate orientation (glTF Y-up -> IFC Z-up)...", pct=13)
    v_count = restore_skp_orientation_for_ifc(scene)
    _skp_log(f"      [SKP->IFC] Coordinate orientation corrected ({v_count:,} vertices)", pct=14)

    _skp_log("      [SKP->IFC] Converting semantic elements (bilingual ID/EN) & exporting IFC4...", pct=16)
    openskp_ifc.export(
        scene,
        str(out_ifc_path),
        scale=1000.0,
        schema=schema,
        classifier=bilingual_classifier,
    )

    _skp_log("      [SKP->IFC] Injecting buildingSMART georeferencing (IFCMAPCONVERSION, IFCPROJECTEDCRS)...", pct=18)
    inject_georeference_into_step(
        ifc_path=out_ifc_path,
        out_path=out_ifc_path,
        lat=georef["latitude"],
        lon=georef["longitude"],
        elev=georef["elevation"],
        epsg_code=georef["crs"],
        zone_str=georef["utm_zone"],
        easting=georef["easting"],
        northing=georef["northing"],
        north_angle=georef["north_angle"],
    )
    _skp_log(f"      [SKP->IFC] Generated intermediate IFC: {out_ifc_path.name}", pct=19)
    return out_ifc_path
