# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any


def safe_slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return value or "generic"


def write_json(path: Path, obj: Any):
    path.write_text(
        json.dumps(obj, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_json_compact(path: Path, obj: Any):
    path.write_text(
        json.dumps(obj, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def clean_previous_outputs(root: Path) -> list[str]:
    removed = []

    for name in (
        "triangles.geojson",
        "surfaces.geojson",
        "openings.geojson",
        "objects.json",
        "objects.geojson",
        "building.geojson",
    ):
        p = root / name
        if p.exists() and p.is_file():
            p.unlink()
            removed.append(str(p))

    for dirname in (
        "triangles",
        "lod3",
        "lod1_3",
        "lod2_2",
        "render",
        "envelope",
    ):
        p = root / dirname
        if p.exists() and p.is_dir():
            shutil.rmtree(p)
            removed.append(str(p))

    return removed
