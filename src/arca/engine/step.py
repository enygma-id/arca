# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import re
import time
from collections import Counter
from pathlib import Path
from typing import Counter as CounterType
from typing import Tuple


class Ref(int):
    pass


TARGETS = {
    "IFCWALL": "WallSurface",
    "IFCWALLSTANDARDCASE": "WallSurface",
    "IFCROOF": "RoofSurface",
    "IFCSLAB": "SlabSurface",
    "IFCDOOR": "DoorSurface",
    "IFCWINDOW": "WindowSurface",
    "IFCCOLUMN": "ColumnSurface",
    "IFCBEAM": "BeamSurface",
    "IFCBUILDINGELEMENTPROXY": "GenericSurface",
    "IFCPLATE": "GenericSurface",
    "IFCMEMBER": "GenericSurface",
    "IFCCURTAINWALL": "WallSurface",
    "IFCSTAIR": "GenericSurface",
    "IFCRAILING": "GenericSurface",
    "IFCFURNISHINGELEMENT": "GenericSurface",
}

OPENING_TYPES = {"IFCDOOR", "IFCWINDOW"}

GEOM_TYPES = {
    "IFCCARTESIANPOINT",
    "IFCCARTESIANPOINTLIST3D",
    "IFCDIRECTION",
    "IFCAXIS2PLACEMENT2D",
    "IFCAXIS2PLACEMENT3D",
    "IFCLOCALPLACEMENT",
    "IFCCARTESIANTRANSFORMATIONOPERATOR3D",
    "IFCCARTESIANTRANSFORMATIONOPERATOR3DNONUNIFORM",
    "IFCPRODUCTDEFINITIONSHAPE",
    "IFCSHAPEREPRESENTATION",
    "IFCREPRESENTATIONMAP",
    "IFCTRIANGULATEDFACESET",
    "IFCPOLYGONALFACESET",
    "IFCINDEXEDPOLYGONALFACE",
    "IFCINDEXEDPOLYGONALFACEWITHVOIDS",
    "IFCFACETEDBREP",
    "IFCCLOSEDSHELL",
    "IFCFACE",
    "IFCFACEOUTERBOUND",
    "IFCFACEBOUND",
    "IFCPOLYLOOP",
    "IFCEXTRUDEDAREASOLID",
    "IFCRECTANGLEPROFILEDEF",
    "IFCARBITRARYCLOSEDPROFILEDEF",
    "IFCPOLYLINE",
    "IFCMAPPEDITEM",
    "IFCBOOLEANCLIPPINGRESULT",
    "IFCBOOLEANRESULT",
}

GEOREF_TYPES = {
    "IFCPROJECTEDCRS",
    "IFCMAPCONVERSION",
    "IFCSITE",
    "IFCSIUNIT",
    "IFCCONVERSIONBASEDUNIT",
    "IFCUNITASSIGNMENT",
    "IFCPROJECT",
    "IFCGEOMETRICREPRESENTATIONCONTEXT",
    "IFCMEASUREWITHUNIT",
    "IFCDIMENSIONALEXPONENTS",
}


def split_top(s: str) -> list[str]:
    """Split comma-separated STEP arguments at nesting depth zero, O(n)."""
    out = []
    depth = 0
    ins = False
    start = 0
    i = 0
    n = len(s)

    while i < n:
        ch = s[i]
        if ch == "'":
            if ins and i + 1 < n and s[i + 1] == "'":
                i += 2
                continue
            ins = not ins
        elif not ins:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == "," and depth == 0:
                out.append(s[start:i].strip())
                start = i + 1
        i += 1

    tail = s[start:].strip()
    if tail or s.endswith(","):
        out.append(tail)
    return out


def parse_val(s: str):
    s = s.strip()
    if s in ("$", "*"):
        return None
    if s.startswith("#"):
        return Ref(int(s[1:]))
    if s.startswith("(") and s.endswith(")"):
        inner = s[1:-1]
        if not inner:
            return []
        return [parse_val(x) for x in split_top(inner)]
    if s.startswith("'") and s.endswith("'"):
        return s[1:-1].replace("''", "'")
    if s.startswith(".") and s.endswith("."):
        return s.strip(".")

    try:
        return float(s)
    except ValueError:
        return s


ENTITY_RE = re.compile(
    r"^\s*#(\d+)\s*=\s*([A-Z0-9_]+)\s*\((.*)\)\s*;\s*$",
    re.S | re.I,
)


def iter_step_statements(path: Path):
    """
    Yield STEP entity statements without reading the entire IFC into memory.
    """
    buf = []
    collecting = False

    with path.open("r", encoding="utf-8", errors="ignore", buffering=1024 * 1024) as f:
        for line in f:
            stripped = line.lstrip()
            if not collecting:
                if not stripped.startswith("#"):
                    continue
                buf = [stripped]
                collecting = True
            else:
                buf.append(line)

            if line.rstrip().endswith(";"):
                yield "".join(buf)
                buf = []
                collecting = False

    if buf:
        yield "".join(buf)


def keep_entity_type(typ: str) -> bool:
    return typ in GEOM_TYPES or typ in TARGETS or typ in GEOREF_TYPES


def load_ifc(path: Path, progress_every: int = 25000) -> Tuple[dict, CounterType]:
    """
    Parse only entities needed for supported geometry/product traversal.
    Returns: (entities, raw_type_counts)
    """
    ents = {}
    counts = Counter()
    parsed = 0
    kept = 0
    t0 = time.perf_counter()

    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"[1/5] Parsing IFC: {path}")
    print(f"      File size : {size_mb:.2f} MB")

    for stmt in iter_step_statements(path):
        m = ENTITY_RE.match(stmt)
        if not m:
            continue

        rid = int(m.group(1))
        typ = m.group(2).upper()
        args_raw = m.group(3)

        counts[typ] += 1
        parsed += 1

        if keep_entity_type(typ):
            ents[rid] = (typ, [parse_val(x) for x in split_top(args_raw)])
            kept += 1

        if progress_every and parsed % progress_every == 0:
            dt = time.perf_counter() - t0
            print(
                f"      {parsed:,} STEP entities scanned | "
                f"{kept:,} geometry/product entities kept | {dt:.1f}s"
            )

    dt = time.perf_counter() - t0
    print(
        f"      Done: {parsed:,} entities scanned, "
        f"{kept:,} retained in {dt:.1f}s"
    )
    print(
        "      Geometry entities: "
        f"IfcTriangulatedFaceSet={counts.get('IFCTRIANGULATEDFACESET', 0):,}, "
        f"IfcPolygonalFaceSet={counts.get('IFCPOLYGONALFACESET', 0):,}, "
        f"IfcFacetedBrep={counts.get('IFCFACETEDBREP', 0):,}, "
        f"IfcExtrudedAreaSolid={counts.get('IFCEXTRUDEDAREASOLID', 0):,}"
    )

    return ents, counts
