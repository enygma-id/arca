# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import numpy as np

from .step import TARGETS

NAME_SEMANTIC_RULES = (
    ("WindowSurface", ("window", "jendela", "glazing", "glass", "kaca")),
    ("DoorSurface", ("door", "pintu")),
    ("RoofSurface", ("roof", "atap", "canopy", "kanopi")),
    ("WallSurface", ("wall", "dinding", "partition", "curtain wall")),
    ("SlabSurface", ("slab", "floor", "lantai", "deck", "ceiling", "plafon")),
    ("ColumnSurface", ("column", "kolom", "pillar")),
    ("BeamSurface", ("beam", "balok", "girder")),
    ("StairSurface", ("stair", "tangga")),
    ("RailingSurface", ("railing", "handrail", "pagar")),
)


def area3(q: np.ndarray) -> float:
    if len(q) < 3:
        return 0.0

    a = np.zeros(3)
    for i in range(len(q)):
        a += np.cross(q[i], q[(i + 1) % len(q)])
    return float(np.linalg.norm(a) / 2.0)


def normal(q: np.ndarray) -> np.ndarray:
    if len(q) < 3:
        return np.array([0.0, 0.0, 1.0])

    n = np.cross(q[1] - q[0], q[2] - q[0])
    norm_val = np.linalg.norm(n)
    return n / norm_val if norm_val else np.array([0.0, 0.0, 1.0])


def ent(E: dict, r):
    return E[int(r)]


def point(E: dict, r) -> np.ndarray:
    _, a = ent(E, r)
    vals = list(map(float, a[0]))
    return np.array(vals + [0] * (3 - len(vals)), dtype=float)


def direction(E: dict, r, default) -> np.ndarray:
    if r is None:
        return np.array(default, dtype=float)

    _, a = ent(E, r)
    vals = list(map(float, a[0]))
    v = np.array(vals + [0] * (3 - len(vals)), dtype=float)
    n = np.linalg.norm(v)
    return v / n if n else np.array(default, dtype=float)


def axis3(E: dict, r) -> np.ndarray:
    if r is None:
        return np.eye(4)

    _, a = ent(E, r)
    loc = point(E, a[0])
    z = direction(E, a[1], [0, 0, 1])
    x = direction(E, a[2], [1, 0, 0])

    x = x - z * np.dot(x, z)
    x = x / (np.linalg.norm(x) or 1)
    y = np.cross(z, x)
    y = y / (np.linalg.norm(y) or 1)

    M = np.eye(4)
    M[:3, 0] = x
    M[:3, 1] = y
    M[:3, 2] = z
    M[:3, 3] = loc
    return M


def axis2(E: dict, r) -> np.ndarray:
    if r is None:
        return np.eye(4)

    _, a = ent(E, r)
    loc = point(E, a[0])
    x = direction(E, a[1], [1, 0, 0])
    x[2] = 0
    x = x / (np.linalg.norm(x) or 1)
    y = np.array([-x[1], x[0], 0.0])

    M = np.eye(4)
    M[:3, 0] = x
    M[:3, 1] = y
    M[:3, 2] = [0, 0, 1]
    M[:3, 3] = loc
    return M


def localplacement(E: dict, r, memo: dict = None) -> np.ndarray:
    memo = {} if memo is None else memo

    if r is None:
        return np.eye(4)

    rid = int(r)
    if rid in memo:
        return memo[rid]

    if rid not in E:
        return np.eye(4)

    typ, a = ent(E, r)
    if typ != "IFCLOCALPLACEMENT":
        return np.eye(4)

    parent = localplacement(E, a[0], memo) if a[0] else np.eye(4)
    M = parent @ axis3(E, a[1])
    memo[rid] = M
    return M


def transform_operator(E: dict, r) -> np.ndarray:
    if r is None:
        return np.eye(4)

    typ, a = ent(E, r)
    if typ not in (
        "IFCCARTESIANTRANSFORMATIONOPERATOR3D",
        "IFCCARTESIANTRANSFORMATIONOPERATOR3DNONUNIFORM",
    ):
        return np.eye(4)

    axis1 = a[0] if len(a) > 0 else None
    axis2r = a[1] if len(a) > 1 else None
    origin = a[2] if len(a) > 2 else None
    scale = float(a[3] or 1.0) if len(a) > 3 else 1.0
    axis3r = a[4] if len(a) > 4 else None

    x = direction(E, axis1, [1, 0, 0])
    y = direction(E, axis2r, [0, 1, 0])
    z = direction(E, axis3r, [0, 0, 1])
    loc = point(E, origin) if origin else np.zeros(3)

    M = np.eye(4)
    M[:3, 0] = x * scale
    M[:3, 1] = y * scale
    M[:3, 2] = z * scale
    M[:3, 3] = loc
    return M


def product_info(E: dict, pid: int) -> dict:
    typ, a = E[pid]
    return {
        "type": typ,
        "guid": a[0] if len(a) > 0 else None,
        "name": a[2] if len(a) > 2 else None,
        "placement": a[5] if len(a) > 5 else None,
        "representation": a[6] if len(a) > 6 else None,
        "args": a,
    }


def rep_shape_items(E: dict, product_rep) -> list:
    if product_rep is None or int(product_rep) not in E:
        return []

    typ, a = ent(E, product_rep)
    out = []

    if typ == "IFCPRODUCTDEFINITIONSHAPE":
        reps = a[2] or []
        for sr in reps:
            if int(sr) not in E:
                continue

            st, sa = ent(E, sr)
            if st != "IFCSHAPEREPRESENTATION":
                continue

            identifier = sa[1] if len(sa) > 1 else None
            rep_type = sa[2] if len(sa) > 2 else None

            if identifier == "Body" or rep_type in (
                "Brep",
                "SweptSolid",
                "Clipping",
                "MappedRepresentation",
                "Tessellation",
                "SurfaceModel",
            ):
                out.extend(sa[3] or [])

    elif typ == "IFCSHAPEREPRESENTATION":
        out.extend(a[3] or [])

    return out


def profile_poly(E: dict, r) -> np.ndarray:
    typ, a = ent(E, r)

    if typ == "IFCRECTANGLEPROFILEDEF":
        M = axis2(E, a[2])
        xd, yd = float(a[3]), float(a[4])
        pts = np.array(
            [
                [-xd / 2, -yd / 2, 0, 1],
                [xd / 2, -yd / 2, 0, 1],
                [xd / 2, yd / 2, 0, 1],
                [-xd / 2, yd / 2, 0, 1],
            ],
            dtype=float,
        )
        return (M @ pts.T).T[:, :3]

    if typ == "IFCARBITRARYCLOSEDPROFILEDEF":
        curve = a[2]
        ct, ca = ent(E, curve)
        if ct == "IFCPOLYLINE":
            return np.array([point(E, p) for p in ca[0]], dtype=float)

    raise NotImplementedError(typ)


def extruded_faces(E: dict, r) -> list[np.ndarray]:
    _, a = ent(E, r)
    poly = profile_poly(E, a[0])
    M = axis3(E, a[1])
    d = direction(E, a[2], [0, 0, 1])
    depth = float(a[3])

    base = (M @ np.c_[poly, np.ones(len(poly))].T).T[:, :3]
    top = base + d * depth

    if np.linalg.norm(base[0] - base[-1]) < 1e-9:
        base = base[:-1]
        top = top[:-1]

    faces = [base, top[::-1]]
    n = len(base)

    for i in range(n):
        faces.append(
            np.array(
                [base[i], base[(i + 1) % n], top[(i + 1) % n], top[i]],
                dtype=float,
            )
        )

    return faces


def brep_faces(E: dict, r) -> list[np.ndarray]:
    _, a = ent(E, r)
    st, sa = ent(E, a[0])
    faces = []

    if st != "IFCCLOSEDSHELL":
        return faces

    for fr in sa[0]:
        ft, fa = ent(E, fr)
        if ft != "IFCFACE":
            continue

        for br in fa[0]:
            bt, ba = ent(E, br)
            if bt not in ("IFCFACEOUTERBOUND", "IFCFACEBOUND"):
                continue

            lt, la = ent(E, ba[0])
            if lt != "IFCPOLYLOOP":
                continue

            q = np.array([point(E, p) for p in la[0]], dtype=float)
            if len(q) >= 3:
                faces.append(q)

            if bt == "IFCFACEOUTERBOUND":
                break

    return faces


def point_list_3d(E: dict, r) -> np.ndarray:
    typ, a = ent(E, r)
    if typ != "IFCCARTESIANPOINTLIST3D":
        raise ValueError(f"Expected IFCCARTESIANPOINTLIST3D, got {typ}")

    coords = a[0] or []
    if not coords:
        return np.empty((0, 3), dtype=float)

    arr = np.asarray(coords, dtype=float)
    if arr.ndim != 2:
        raise ValueError("Invalid IfcCartesianPointList3D coordinate array")

    if arr.shape[1] == 2:
        arr = np.c_[arr, np.zeros(len(arr))]
    elif arr.shape[1] > 3:
        arr = arr[:, :3]

    return arr


def triangulated_faces(E: dict, r) -> list[np.ndarray]:
    _, a = ent(E, r)

    coords_ref = a[0]
    coord_index = a[3] if len(a) > 3 else None

    if coords_ref is None or coord_index is None:
        return []

    coords = point_list_3d(E, coords_ref)
    faces = []

    for idxs in coord_index:
        if not idxs or len(idxs) < 3:
            continue

        indices = np.asarray(idxs, dtype=int) - 1
        if np.any(indices < 0) or np.any(indices >= len(coords)):
            continue

        q = coords[indices]
        if len(q) == 3:
            faces.append(q)
        else:
            for j in range(1, len(q) - 1):
                faces.append(np.array([q[0], q[j], q[j + 1]], dtype=float))

    return faces


def polygonal_faces(E: dict, r) -> list[np.ndarray]:
    _, a = ent(E, r)

    coords_ref = a[0]
    face_refs = a[2] if len(a) > 2 else None

    if coords_ref is None or not face_refs:
        return []

    coords = point_list_3d(E, coords_ref)
    faces = []

    for fr in face_refs:
        if int(fr) not in E:
            continue

        ft, fa = ent(E, fr)
        if ft not in ("IFCINDEXEDPOLYGONALFACE", "IFCINDEXEDPOLYGONALFACEWITHVOIDS"):
            continue

        idxs = fa[0] if fa else None
        if not idxs or len(idxs) < 3:
            continue

        indices = np.asarray(idxs, dtype=int) - 1
        if np.any(indices < 0) or np.any(indices >= len(coords)):
            continue

        faces.append(coords[indices])

    return faces


def item_faces(E: dict, r, T: np.ndarray = None, depth: int = 0) -> list[np.ndarray]:
    if T is None:
        T = np.eye(4)

    if r is None or depth > 30 or int(r) not in E:
        return []

    typ, a = ent(E, r)
    local = []

    if typ == "IFCTRIANGULATEDFACESET":
        local = triangulated_faces(E, r)
    elif typ == "IFCPOLYGONALFACESET":
        local = polygonal_faces(E, r)
    elif typ == "IFCFACETEDBREP":
        local = brep_faces(E, r)
    elif typ == "IFCEXTRUDEDAREASOLID":
        try:
            local = extruded_faces(E, r)
        except Exception:
            local = []
    elif typ == "IFCMAPPEDITEM":
        src, target = a[0], a[1]
        if int(src) not in E:
            return []

        mt, ma = ent(E, src)
        if mt == "IFCREPRESENTATIONMAP":
            origin = axis3(E, ma[0])
            mapped_rep = ma[1]
            mapT = transform_operator(E, target) @ np.linalg.inv(origin)

            out = []
            for ir in rep_shape_items(E, mapped_rep):
                out.extend(item_faces(E, ir, T @ mapT, depth + 1))
            return out
    elif typ in ("IFCBOOLEANCLIPPINGRESULT", "IFCBOOLEANRESULT"):
        return item_faces(E, a[1], T, depth + 1)
    else:
        return []

    out = []
    for q in local:
        if len(q) < 3:
            continue
        qq = (T @ np.c_[q, np.ones(len(q))].T).T[:, :3]
        out.append(qq)

    return out


def infer_product_semantic(typ: str, pinfo: dict, faces_m: list[np.ndarray]):
    native = TARGETS.get(typ, "GenericSurface")
    if native != "GenericSurface":
        return native, "ifc_class", 1.0

    name = str(pinfo.get("name") or "").strip().lower()
    for semantic, words in NAME_SEMANTIC_RULES:
        if any(w in name for w in words):
            return semantic, "name_hint", 0.90

    if not faces_m:
        return "GenericSurface", "fallback", 0.0

    pts = np.vstack(faces_m)
    mn = pts.min(axis=0)
    mx = pts.max(axis=0)
    dx, dy, dz = (mx - mn).tolist()
    horizontal_area = 0.0
    vertical_area = 0.0
    total_area = 0.0

    for q in faces_m:
        a = area3(q)
        if a <= 0:
            continue
        total_area += a
        nz = abs(float(normal(q)[2]))
        if nz >= 0.82:
            horizontal_area += a
        elif nz <= 0.28:
            vertical_area += a

    if total_area <= 0:
        return "GenericSurface", "fallback", 0.0

    hr = horizontal_area / total_area
    vr = vertical_area / total_area
    plan_max = max(dx, dy)
    plan_min = min(dx, dy)

    if dz <= 0.45 and plan_max >= 1.0 and hr >= 0.45:
        return "SlabSurface", "geometry_heuristic", 0.62

    if dz >= 1.5 and plan_max <= 1.5 and plan_min <= 1.5:
        return "ColumnSurface", "geometry_heuristic", 0.58

    if dz >= 1.5 and plan_min <= 0.55 and vr >= 0.45:
        return "WallSurface", "geometry_heuristic", 0.60

    return "GenericSurface", "fallback", 0.0
