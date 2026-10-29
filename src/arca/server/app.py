# SPDX-License-Identifier: AGPL-3.0-only
"""
ARCA Studio Web Server
Provides web-based UI for model ingestion (IFC & SKP) and 3D GIS visualization.
Pure Python standard library implementation.
"""

from __future__ import annotations

import io
import json
import math
import mimetypes
import os
import re
import shutil
import signal
import socketserver
import sys
import tempfile
import threading
import time
import uuid
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .. import __version__

# Safety constants for filesystem and upload bounds (P-01 & P-02)
DEFAULT_MAX_UPLOAD_BYTES = 4 * 1024 * 1024 * 1024  # 4 GiB default limit
ALLOWED_DOWNLOAD_FILES = {
    "model_glb.zip",
    "model.zip",
    "building.geojson",
    "building.city.json",
    "building.gml",
    "model.glb",
    "model.geojson",
    "metadata.json",
    "manifest.json",
}


def get_max_upload_bytes() -> int:
    env_val = os.environ.get("ARCA_MAX_UPLOAD_BYTES", "").strip()
    if not env_val:
        return DEFAULT_MAX_UPLOAD_BYTES
    try:
        val = int(env_val)
        if val <= 0:
            raise ValueError()
        return val
    except ValueError as err:
        raise ValueError(
            f"Invalid ARCA_MAX_UPLOAD_BYTES: '{env_val}'. Must be a positive integer."
        ) from err


def is_safe_dataset_id(dataset_id: str) -> bool:
    """Validate dataset_id as a single safe directory name matching safe_slug format."""
    if not dataset_id or not isinstance(dataset_id, str):
        return False
    if len(dataset_id) > 128:
        return False
    return bool(re.fullmatch(r"[a-z0-9_]+", dataset_id))


def safe_resolve_child(base_dir: Path, user_path: str) -> Path | None:
    """
    Resolve user_path relative to base_dir, ensuring containment inside base_dir.
    Rejects empty paths, absolute paths (POSIX/Windows), segments with '..' or '.',
    NUL bytes, and symlink escapes outside base_dir.
    """
    if not user_path or not isinstance(user_path, str) or "\x00" in user_path:
        return None

    if user_path.startswith(("/", "\\")) or re.match(r"^[a-zA-Z]:", user_path):
        return None

    segments = re.split(r"[/\\]+", user_path)
    for seg in segments:
        if seg in ("..", "."):
            return None

    clean_segments = [s for s in segments if s]
    if not clean_segments:
        return None

    try:
        base_resolved = base_dir.resolve(strict=False)
        target = (base_resolved / Path(*clean_segments)).resolve(strict=False)
        target.relative_to(base_resolved)
        if target == base_resolved:
            return None
        return target
    except (ValueError, RuntimeError):
        return None


class MultipartStreamReader:
    """Bounded, streaming multipart parser that writes uploaded file parts to disk."""

    def __init__(
        self,
        stream,
        boundary: bytes,
        max_bytes: int,
        temp_dir: Path,
        expected_length: int | None = None,
        chunk_size: int = 64 * 1024,
    ):
        self.stream = stream
        self.boundary = boundary
        self.max_bytes = max_bytes
        self.temp_dir = temp_dir
        self.expected_length = expected_length
        self.chunk_size = chunk_size
        self.total_read = 0
        self.buffer = bytearray()
        self.delimiter = b"--" + boundary
        self.created_files: list[Path] = []

    def _read_chunk(self) -> bytes:
        if self.expected_length is not None and self.total_read >= self.expected_length:
            return b""
        to_read = self.chunk_size
        if self.expected_length is not None:
            to_read = min(to_read, self.expected_length - self.total_read)
        if self.total_read + to_read > self.max_bytes:
            to_read = self.max_bytes - self.total_read + 1
        chunk = self.stream.read(to_read)
        if not chunk:
            return b""
        self.total_read += len(chunk)
        if self.total_read > self.max_bytes:
            raise OverflowError("Upload limit exceeded")
        return chunk

    def _fill_buffer(self, min_bytes: int = 1) -> bool:
        while len(self.buffer) < min_bytes:
            chunk = self._read_chunk()
            if not chunk:
                return False
            self.buffer.extend(chunk)
        return True

    def _find_boundary(self) -> tuple[int, int] | None:
        target = b"\r\n" + self.delimiter
        pos = 0
        while True:
            idx = self.buffer.find(target, pos)
            if idx == -1:
                return None
            after_idx = idx + len(target)
            if len(self.buffer) < after_idx + 2:
                self._fill_buffer(after_idx + 2)
            after = bytes(self.buffer[after_idx : after_idx + 2])
            if after.startswith(b"\r\n") or after == b"--":
                consumed = len(target) + (2 if after.startswith(b"\r\n") else 0)
                return idx, consumed
            pos = idx + 1

    def parse(self) -> tuple[dict[str, str], dict[str, dict[str, any]]]:
        try:
            while self.delimiter not in self.buffer:
                if not self._fill_buffer(len(self.buffer) + 1):
                    raise ValueError("No boundary found in multipart payload")

            idx = self.buffer.find(self.delimiter)
            del self.buffer[: idx + len(self.delimiter)]

            fields: dict[str, str] = {}
            files: dict[str, dict[str, any]] = {}

            while True:
                if not self._fill_buffer(2):
                    break
                if self.buffer.startswith(b"--"):
                    break
                if self.buffer.startswith(b"\r\n"):
                    del self.buffer[:2]
                elif self.buffer.startswith(b"\n"):
                    del self.buffer[:1]

                while b"\r\n\r\n" not in self.buffer and b"\n\n" not in self.buffer:
                    if not self._fill_buffer(len(self.buffer) + 1):
                        raise ValueError("Incomplete headers in multipart part")

                crlf_pos = self.buffer.find(b"\r\n\r\n")
                lf_pos = self.buffer.find(b"\n\n")
                if crlf_pos != -1 and (lf_pos == -1 or crlf_pos <= lf_pos):
                    hdr_raw = bytes(self.buffer[:crlf_pos])
                    del self.buffer[: crlf_pos + 4]
                else:
                    hdr_raw = bytes(self.buffer[:lf_pos])
                    del self.buffer[: lf_pos + 2]

                hdr_text = hdr_raw.decode("utf-8", errors="replace")
                disp_m = re.search(
                    r'Content-Disposition:\s*form-data;\s*name="([^"]+)"(?:;\s*filename="([^"]*)")?',
                    hdr_text,
                    re.IGNORECASE,
                )
                if not disp_m:
                    continue

                field_name = disp_m.group(1)
                filename = disp_m.group(2)
                target_len = len(b"\r\n" + self.delimiter) + 4

                if filename is not None and filename.strip():
                    safe_fn = Path(filename.strip()).name
                    ext = Path(safe_fn).suffix.lower()
                    tf = tempfile.NamedTemporaryFile(dir=self.temp_dir, suffix=ext, delete=False)
                    tmp_path = Path(tf.name)
                    self.created_files.append(tmp_path)
                    try:
                        while True:
                            match = self._find_boundary()
                            if match is not None:
                                b_pos, consumed = match
                                tf.write(self.buffer[:b_pos])
                                del self.buffer[: b_pos + consumed]
                                break
                            if len(self.buffer) > target_len:
                                keep = target_len
                                to_write = len(self.buffer) - keep
                                tf.write(self.buffer[:to_write])
                                del self.buffer[:to_write]
                            if not self._fill_buffer(len(self.buffer) + 1):
                                raise ValueError("Unexpected EOF in multipart file body")
                    finally:
                        tf.close()

                    files[field_name] = {
                        "filename": safe_fn,
                        "path": tmp_path,
                        "size": tmp_path.stat().st_size,
                    }
                else:
                    val_buf = bytearray()
                    while True:
                        match = self._find_boundary()
                        if match is not None:
                            b_pos, consumed = match
                            val_buf.extend(self.buffer[:b_pos])
                            del self.buffer[: b_pos + consumed]
                            break
                        if len(self.buffer) > target_len:
                            keep = target_len
                            to_write = len(self.buffer) - keep
                            val_buf.extend(self.buffer[:to_write])
                            del self.buffer[:to_write]
                        if not self._fill_buffer(len(self.buffer) + 1):
                            raise ValueError("Unexpected EOF in multipart field body")
                    fields[field_name] = val_buf.decode("utf-8", errors="replace")[:512].strip()

            if self.expected_length is not None:
                while self.total_read < self.expected_length:
                    chunk = self._read_chunk()
                    if not chunk:
                        break

            if self.expected_length is not None and self.total_read < self.expected_length:
                raise ValueError("Short read: client sent fewer bytes than Content-Length")

            return fields, files
        except Exception:
            for p in self.created_files:
                if p.exists():
                    try:
                        p.unlink()
                    except OSError:
                        pass
            raise


_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _new_job() -> dict:
    return {"status": "pending", "events": [], "result": None, "lock": threading.Lock()}


def _job_emit(job: dict, event: dict) -> None:
    with job["lock"]:
        job["events"].append(event)



MIME_MAP = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".geojson": "application/geo+json; charset=utf-8",
    ".gml": "application/gml+xml; charset=utf-8",
    ".glb": "model/gltf-binary",
    ".gltf": "model/gltf+json",
    ".ifc": "text/plain; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".wasm": "application/wasm",
}


def _static_dir() -> Path:
    return Path(__file__).resolve().parent / "static"


def parse_multipart(body: bytes, content_type: str):
    m = re.search(r"boundary=([^\s;]+)", content_type)
    if not m:
        raise ValueError("No boundary found in Content-Type header")
    boundary = m.group(1).strip('"\'').encode()
    delimiter = b"--" + boundary
    parts = body.split(delimiter)

    fields: dict[str, str] = {}
    files: dict[str, dict[str, any]] = {}

    for part in parts:
        if not part or part == b"--\r\n" or part == b"--":
            continue
        if part.startswith(b"\r\n"):
            part = part[2:]
        if part.endswith(b"\r\n"):
            part = part[:-2]

        header_end = part.find(b"\r\n\r\n")
        if header_end == -1:
            continue

        header_bytes = part[:header_end]
        content_bytes = part[header_end + 4 :]
        header_text = header_bytes.decode("utf-8", errors="replace")

        disp_match = re.search(
            r'Content-Disposition:\s*form-data;\s*name="([^"]+)"(?:;\s*filename="([^"]+)")?',
            header_text,
            re.IGNORECASE,
        )
        if not disp_match:
            continue

        field_name = disp_match.group(1)
        filename = disp_match.group(2)

        if filename is not None and filename.strip():
            files[field_name] = {
                "filename": filename.strip(),
                "data": content_bytes,
            }
        else:
            fields[field_name] = content_bytes.decode("utf-8", errors="replace").strip()

    return fields, files


class StudioRequestHandler(BaseHTTPRequestHandler):
    server_version = f"ARCA-Studio/{__version__}"

    @property
    def workspace(self) -> Path:
        return self.server.workspace  # type: ignore

    @property
    def static_dir(self) -> Path:
        return _static_dir()

    def log_message(self, format, *args):
        sys.stderr.write(f"[{time.strftime('%H:%M:%S')}] {self.address_string()} - {format % args}\n")

    def send_json(self, data, status=200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_file_response(self, file_path: Path, download_name: str | None = None):
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, f"File not found: {file_path.name}")
            return

        ext = file_path.suffix.lower()
        if ext in MIME_MAP:
            mime_type = MIME_MAP[ext]
        else:
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if mime_type is None:
                mime_type = "application/octet-stream"

        file_size = file_path.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(file_size))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        if download_name:
            safe_name = re.sub(r'[\r\n"\']', '', download_name)
            self.send_header("Content-Disposition", f'attachment; filename="{safe_name}"')
        self.end_headers()

        if self.command != "HEAD":
            try:
                with open(file_path, "rb") as f:
                    shutil.copyfileobj(f, self.wfile)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def send_bytes_response(self, data: bytes, mime_type: str = "application/octet-stream", download_name: str | None = None):
        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        if download_name:
            safe_name = re.sub(r'[\r\n"\']', '', download_name)
            self.send_header("Content-Disposition", f'attachment; filename="{safe_name}"')
        self.end_headers()

        if self.command != "HEAD":
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def do_HEAD(self):
        self.do_GET()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def send_empty_catalog(self):
        catalog = json.dumps({
            "items": [],
            "settings": {
                "default_engine": "maplibre",
                "default_basemap": "osm",
                "display_lod": "LOD 1.3",
                "enabled_representations": ["lod1_3", "glb"],
                "big_osm_gap_fill": False,
            }
        })
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(catalog.encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/api/status":
            self.send_json({
                "status": "ok",
                "version": __version__,
                "license": "AGPL-3.0-only",
                "source_url": "https://github.com/enygma-id/arca",
                "engine": "ARCA Studio",
            })
            return

        if path == "/api/history":
            self.handle_history()
            return

        if path == "/api/download":
            qs = parse_qs(parsed.query)
            dataset = qs.get("dataset", [""])[0]
            filename = qs.get("file", [""])[0]
            custom_name = qs.get("name", [""])[0]
            if not dataset or not filename:
                self.send_error(400, "Missing dataset or file parameter")
                return

            if not is_safe_dataset_id(dataset):
                self.send_error(400, "Invalid dataset parameter")
                return

            if filename not in ALLOWED_DOWNLOAD_FILES:
                self.send_error(400, "Invalid or unsupported file parameter")
                return

            dataset_dir = safe_resolve_child(self.workspace / "outputs", dataset)
            if dataset_dir is None or not dataset_dir.exists() or not dataset_dir.is_dir() or dataset_dir.is_symlink():
                self.send_error(404, f"Dataset not found: {dataset}")
                return

            safe_filename = filename
            building_name = custom_name.strip()
            if not building_name:
                meta_file = dataset_dir / "metadata.json"
                if meta_file.exists() and not meta_file.is_symlink():
                    try:
                        with open(meta_file, "r", encoding="utf-8") as mf:
                            mdata = json.load(mf)
                            building_name = str(mdata.get("name") or mdata.get("building_name") or "").strip()
                    except Exception:
                        pass
            if not building_name:
                manifest_file = dataset_dir / "manifest.json"
                if manifest_file.exists() and not manifest_file.is_symlink():
                    try:
                        with open(manifest_file, "r", encoding="utf-8") as mf:
                            mdata = json.load(mf)
                            building_name = str(mdata.get("name") or "").strip()
                    except Exception:
                        pass

            clean_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', building_name).strip("._") if building_name else dataset

            if safe_filename in ("model_glb.zip", "model.zip"):
                glb_file = safe_resolve_child(dataset_dir / "render", "model.glb")
                if glb_file is None or not glb_file.exists() or glb_file.is_symlink():
                    glb_file = safe_resolve_child(dataset_dir, "model.glb")
                if glb_file is None or not glb_file.exists() or glb_file.is_symlink():
                    self.send_error(404, f"GLB model not found in dataset {dataset}")
                    return

                geojson_file = safe_resolve_child(dataset_dir / "render", "model.geojson")
                if geojson_file is None or not geojson_file.exists() or geojson_file.is_symlink():
                    geojson_file = safe_resolve_child(dataset_dir, "model.geojson")

                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    zf.write(glb_file, arcname="model.glb")
                    if geojson_file is not None and geojson_file.exists() and not geojson_file.is_symlink():
                        zf.write(geojson_file, arcname="model.geojson")
                    else:
                        meta_file = dataset_dir / "metadata.json"
                        if meta_file.exists() and not meta_file.is_symlink():
                            try:
                                with open(meta_file, "r", encoding="utf-8") as mf:
                                    meta = json.load(mf)
                                anchor = meta.get("anchor", {})
                                georef = meta.get("georeference", {})
                                synth = {
                                    "type": "FeatureCollection",
                                    "features": [{
                                        "type": "Feature",
                                        "geometry": {
                                            "type": "Point",
                                            "coordinates": [
                                                anchor.get("lon", 0.0),
                                                anchor.get("lat", 0.0),
                                                round(float(georef.get("origin_orthogonal_height", 0.0)), 3),
                                            ],
                                        },
                                        "properties": {
                                            "id": dataset,
                                            "name": building_name or dataset,
                                            "model_url": "./model.glb",
                                            "scale": 1.0,
                                            "heading": round(math.degrees(float(georef.get("rotation_rad", 0.0))), 6) if "rotation_rad" in georef else 0.0,
                                            "pitch": 0.0,
                                            "roll": 0.0,
                                            "height_m": round(float(meta.get("summary", {}).get("max_height_m", 0.0)), 3),
                                            "storeys": meta.get("plateau_count", 0),
                                            "crs": georef.get("crs_epsg") or "EPSG:4326",
                                        },
                                    }],
                                }
                                zf.writestr("model.geojson", json.dumps(synth, indent=2))
                            except Exception:
                                pass

                download_name = f"{clean_name}_glb.zip"
                self.send_bytes_response(buf.getvalue(), mime_type="application/zip", download_name=download_name)
                return

            target = safe_resolve_child(dataset_dir, safe_filename)
            if target is None or not target.exists() or not target.is_file() or target.is_symlink():
                target = safe_resolve_child(dataset_dir / "render", safe_filename)
            if target is None or not target.exists() or not target.is_file() or target.is_symlink():
                self.send_error(404, f"File {filename} not found in dataset {dataset}")
                return

            if safe_filename.endswith(".city.json"):
                download_name = f"{clean_name}.city.json" if building_name else safe_filename
            elif safe_filename == "building.gml" or safe_filename.endswith(".gml"):
                download_name = f"{clean_name}.gml" if building_name else safe_filename
            else:
                download_name = f"{clean_name}{Path(safe_filename).suffix}" if building_name else safe_filename
            self.send_file_response(target, download_name=download_name)
            return

        if path.startswith("/api/jobs/") and path.endswith("/events"):
            job_id = path[len("/api/jobs/"):-len("/events")]
            self.handle_job_events(job_id)
            return

        # 1. Root studio UI & Favicon
        if path == "/" or path == "/index.html":
            index_file = self.static_dir / "index.html"
            self.send_file_response(index_file)
            return

        if path == "/favicon.ico":
            fav_file = self.static_dir / "assets" / "favicon.ico"
            if not fav_file.exists():
                fav_file = self.static_dir / "favicon.ico"
            if fav_file.exists() and fav_file.is_file():
                self.send_file_response(fav_file)
                return

        # 2. Static studio assets (/static/...)
        if path.startswith("/static/"):
            rel = path[len("/static/") :].lstrip("/")
            if not rel:
                self.send_error(400, "Invalid path")
                return
            target = safe_resolve_child(self.static_dir, rel)
            if target is None:
                self.send_error(400, "Invalid path")
                return
            if target.exists() and target.is_file():
                self.send_file_response(target)
                return
            self.send_error(404, f"File not found: {rel}")
            return

        # 3. Viewer routes (/viewer/...)
        if path == "/viewer" or path == "/viewer/":
            viewer_html = self.static_dir / "viewer" / "viewer.html"
            self.send_file_response(viewer_html)
            return

        if path.startswith("/viewer/"):
            rel = path[len("/viewer/") :].lstrip("/")
            if not rel:
                self.send_error(400, "Invalid path")
                return
            ws_target = safe_resolve_child(self.workspace / "viewer", rel)
            pkg_target = safe_resolve_child(self.static_dir / "viewer", rel)
            if ws_target is None or pkg_target is None:
                self.send_error(400, "Invalid path")
                return
            # Check workspace viewer first (for dynamically generated files)
            if ws_target.exists() and ws_target.is_file():
                self.send_file_response(ws_target)
                return
            # Fallback to package bundled viewer
            if pkg_target.exists() and pkg_target.is_file():
                self.send_file_response(pkg_target)
                return
            if rel == "data.json":
                self.send_empty_catalog()
                return
            self.send_error(404, f"Resource not found: {path}")
            return

        # 4. Direct viewer fallbacks (multilod, data.json, data/)
        if path == "/data.json":
            ws_data = self.workspace / "viewer" / "data.json"
            if ws_data.exists() and ws_data.is_file() and not ws_data.is_symlink():
                self.send_file_response(ws_data)
                return
            pkg_data = self.static_dir / "viewer" / "data.json"
            if pkg_data.exists() and pkg_data.is_file():
                self.send_file_response(pkg_data)
                return
            self.send_empty_catalog()
            return

        if path.startswith("/multilod/"):
            rel = path[len("/multilod/") :].lstrip("/")
            if not rel:
                self.send_error(400, "Invalid path")
                return
            ws_ml = safe_resolve_child(self.workspace / "viewer" / "multilod", rel)
            pkg_ml = safe_resolve_child(self.static_dir / "viewer" / "multilod", rel)
            if ws_ml is None or pkg_ml is None:
                self.send_error(400, "Invalid path")
                return
            if ws_ml.exists() and ws_ml.is_file():
                self.send_file_response(ws_ml)
                return
            if pkg_ml.exists() and pkg_ml.is_file():
                self.send_file_response(pkg_ml)
                return
            self.send_error(404, f"Resource not found: {path}")
            return

        if path.startswith("/data/"):
            rel = path[len("/data/") :].lstrip("/")
            if not rel:
                self.send_error(400, "Invalid path")
                return
            pkg_d = safe_resolve_child(self.static_dir / "viewer" / "data", rel)
            if pkg_d is None:
                self.send_error(400, "Invalid path")
                return
            if pkg_d.exists() and pkg_d.is_file():
                self.send_file_response(pkg_d)
                return
            self.send_error(404, f"Resource not found: {path}")
            return

        self.send_error(404, f"Resource not found: {path}")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/api/convert":
            self.handle_convert()
            return
        elif path == "/api/inspect":
            self.handle_inspect()
            return
        elif path == "/api/delete":
            self.handle_delete()
            return

        self.send_error(404, f"Unknown POST endpoint: {path}")

    def handle_history(self):
        history = []
        outputs_dir = self.workspace / "outputs"
        if outputs_dir.exists():
            for d in sorted(outputs_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                if d.is_dir() and not d.name.startswith("."):
                    geojson_file = d / "building.geojson"
                    glb_file = d / "render" / "model.glb"
                    if not glb_file.exists():
                        glb_file = d / "model.glb"
                    cityjson_file = d / "building.city.json"
                    citygml_file = d / "building.gml"
                    meta_file = d / "metadata.json"

                    item = {
                        "dataset": d.name,
                        "has_geojson": geojson_file.exists(),
                        "has_glb": glb_file.exists(),
                        "has_cityjson": cityjson_file.exists(),
                        "has_citygml": citygml_file.exists(),
                        "mtime": d.stat().st_mtime,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(d.stat().st_mtime)),
                    }

                    if meta_file.exists():
                        try:
                            with open(meta_file, "r", encoding="utf-8") as mf:
                                meta = json.load(mf)
                            item["name"] = meta.get("name") or meta.get("building_name") or d.name
                            item["source_format"] = meta.get("source_format", "BIM")
                            item["storeys"] = meta.get("plateau_count", 0)
                            summary = meta.get("summary", {})
                            item["height_m"] = summary.get("max_height_m", 0)
                            item["footprint_m2"] = summary.get("footprint_area_m2", 0)
                        except Exception:
                            pass
                    else:
                        item["name"] = d.name

                    history.append(item)

        self.send_json({"datasets": history})

    def handle_delete(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        dataset_id = qs.get("dataset", [None])[0]

        if not dataset_id:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                try:
                    body = json.loads(self.rfile.read(content_length).decode("utf-8"))
                    dataset_id = body.get("dataset")
                except Exception:
                    pass

        if not dataset_id or not is_safe_dataset_id(str(dataset_id)):
            self.send_json({"success": False, "error": "Invalid or missing dataset parameter"}, status=400)
            return

        dataset_id = str(dataset_id)
        deleted_items = []

        # 1. Remove from workspace/outputs (immediate child, not root, non-symlink dir)
        outputs_root = (self.workspace / "outputs").resolve(strict=False)
        out_dir = outputs_root / dataset_id
        if out_dir.parent == outputs_root and out_dir != outputs_root and not out_dir.is_symlink() and out_dir.is_dir():
            shutil.rmtree(out_dir, ignore_errors=True)
            deleted_items.append("outputs")

        # 2. Remove from workspace/viewer/multilod (immediate child, not root, non-symlink dir)
        multilod_root = (self.workspace / "viewer" / "multilod").resolve(strict=False)
        viewer_lod = multilod_root / dataset_id
        if viewer_lod.parent == multilod_root and viewer_lod != multilod_root and not viewer_lod.is_symlink() and viewer_lod.is_dir():
            shutil.rmtree(viewer_lod, ignore_errors=True)
            deleted_items.append("viewer_multilod")

        # 3. Remove from workspace/viewer/data.json using atomic write (ponytail: atomic replace via tempfile in same dir)
        data_json_path = self.workspace / "viewer" / "data.json"
        if data_json_path.exists() and not data_json_path.is_symlink() and data_json_path.is_file():
            try:
                with open(data_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                items = data.get("items", [])
                new_items = [it for it in items if str(it.get("id")) != dataset_id]
                if len(new_items) != len(items):
                    data["items"] = new_items
                    data_json_path.parent.mkdir(parents=True, exist_ok=True)
                    with tempfile.NamedTemporaryFile("w", dir=data_json_path.parent, delete=False, encoding="utf-8") as tf:
                        json.dump(data, tf, indent=2, ensure_ascii=False)
                        tf.flush()
                        os.fsync(tf.fileno())
                        temp_name = tf.name
                    os.replace(temp_name, data_json_path)
                    deleted_items.append("data_json")
            except Exception:
                pass



        self.send_json({
            "success": True,
            "deleted": dataset_id,
            "actions": deleted_items
        })

    def handle_inspect(self):
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self.send_json({"success": False, "error": "Content-Type must be multipart/form-data"}, status=400)
            return

        m = re.search(r"boundary=([^\s;]+)", content_type)
        if not m:
            self.send_json({"success": False, "error": "Missing boundary in Content-Type header"}, status=400)
            return
        boundary = m.group(1).strip("\"'").encode()

        cl_str = self.headers.get("Content-Length")
        if cl_str is None:
            self.send_json({"success": False, "error": "Missing Content-Length header"}, status=400)
            return
        try:
            content_length = int(cl_str)
            if content_length <= 0:
                raise ValueError()
        except ValueError:
            self.send_json({"success": False, "error": "Invalid Content-Length header"}, status=400)
            return

        try:
            max_bytes = get_max_upload_bytes()
        except ValueError as exc:
            self.send_json({"success": False, "error": str(exc)}, status=500)
            return

        if content_length > max_bytes:
            self.send_json({"success": False, "error": f"Payload too large. Exceeds limit of {max_bytes} bytes."}, status=413)
            return

        temp_dir = self.workspace / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        reader = MultipartStreamReader(
            stream=self.rfile,
            boundary=boundary,
            max_bytes=max_bytes,
            temp_dir=temp_dir,
            expected_length=content_length,
        )

        files: dict[str, dict[str, any]] = {}
        try:
            fields, files = reader.parse()
        except OverflowError:
            self.send_json({"success": False, "error": f"Payload too large. Exceeds limit of {max_bytes} bytes."}, status=413)
            return
        except Exception as exc:
            self.send_json({"success": False, "error": f"Failed to parse upload: {exc}"}, status=400)
            return

        try:
            if "file" not in files:
                self.send_json({"success": False, "error": "No file uploaded (field 'file' required)"}, status=400)
                return

            uploaded_file = files["file"]
            original_name = uploaded_file["filename"]
            tmp_path = uploaded_file["path"]

            ext = Path(original_name).suffix.lower()
            if ext not in {".ifc", ".skp"}:
                self.send_json({"success": False, "error": f"Format '{ext}' not supported. Must be .ifc or .skp"}, status=400)
                return

            tmp_meta_path = None
            if "metadata" in files:
                meta_name = files["metadata"]["filename"]
                meta_ext = Path(meta_name).suffix.lower()
                if meta_ext in {".json", ".geojson"}:
                    tmp_meta_path = files["metadata"]["path"]

            from .. import engine
            try:
                res = engine.inspect_model_file(tmp_path, metadata_path=tmp_meta_path)
                res["filename"] = original_name
                self.send_json({"success": True, "data": res})
            except Exception as exc:
                self.send_json({"success": False, "error": f"Failed to inspect model: {exc}"}, status=500)
        finally:
            for fl in files.values():
                p = fl.get("path")
                if p and isinstance(p, Path) and p.exists():
                    try:
                        p.unlink()
                    except OSError:
                        pass

    def handle_convert(self):
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self.send_json({"success": False, "error": "Content-Type must be multipart/form-data"}, status=400)
            return

        m = re.search(r"boundary=([^\s;]+)", content_type)
        if not m:
            self.send_json({"success": False, "error": "Missing boundary in Content-Type header"}, status=400)
            return
        boundary = m.group(1).strip("\"'").encode()

        cl_str = self.headers.get("Content-Length")
        if cl_str is None:
            self.send_json({"success": False, "error": "Missing Content-Length header"}, status=400)
            return
        try:
            content_length = int(cl_str)
            if content_length <= 0:
                raise ValueError()
        except ValueError:
            self.send_json({"success": False, "error": "Invalid Content-Length header"}, status=400)
            return

        try:
            max_bytes = get_max_upload_bytes()
        except ValueError as exc:
            self.send_json({"success": False, "error": str(exc)}, status=500)
            return

        if content_length > max_bytes:
            self.send_json({"success": False, "error": f"Payload too large. Exceeds limit of {max_bytes} bytes."}, status=413)
            return

        temp_dir = self.workspace / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        reader = MultipartStreamReader(
            stream=self.rfile,
            boundary=boundary,
            max_bytes=max_bytes,
            temp_dir=temp_dir,
            expected_length=content_length,
        )

        files: dict[str, dict[str, any]] = {}
        try:
            fields, files = reader.parse()
        except OverflowError:
            self.send_json({"success": False, "error": f"Payload too large. Exceeds limit of {max_bytes} bytes."}, status=413)
            return
        except Exception as exc:
            self.send_json({"success": False, "error": f"Failed to parse upload: {exc}"}, status=400)
            return

        try:
            if "file" not in files:
                self.send_json({"success": False, "error": "No file uploaded (field 'file' required)"}, status=400)
                return

            uploaded_file = files["file"]
            original_name = uploaded_file["filename"]
            src_file_path = uploaded_file["path"]

            ext = Path(original_name).suffix.lower()
            if ext not in {".ifc", ".skp"}:
                self.send_json({"success": False, "error": f"Format '{ext}' not supported. Must be .ifc or .skp"}, status=400)
                return

            from .. import engine

            raw_stem = Path(original_name).stem
            safe_stem = engine.safe_slug(raw_stem)
            dataset_name = fields.get("dataset_name", "").strip()[:128]
            dataset_id = engine.safe_slug(dataset_name) if dataset_name else safe_stem
            if not is_safe_dataset_id(dataset_id):
                self.send_json({"success": False, "error": f"Invalid dataset name '{dataset_name}'"}, status=400)
                return

            uploads_dir = self.workspace / "uploads"
            uploads_dir.mkdir(parents=True, exist_ok=True)
            saved_input = uploads_dir / f"{dataset_id}_{int(time.time())}{ext}"
            shutil.move(str(src_file_path), str(saved_input))

            saved_meta = None
            if "metadata" in files:
                uploaded_meta = files["metadata"]
                meta_name = uploaded_meta["filename"]
                meta_src_path = uploaded_meta["path"]
                meta_ext = Path(meta_name).suffix.lower()
                if meta_ext in {".json", ".geojson"}:
                    meta_slug = engine.safe_slug(Path(meta_name).stem)
                    saved_meta = uploads_dir / f"{meta_slug}_{int(time.time())}{meta_ext}"
                    shutil.move(str(meta_src_path), str(saved_meta))

            out_dir = self.workspace / "outputs" / dataset_id
            out_dir.mkdir(parents=True, exist_ok=True)

            generate_mode = fields.get("generate", "all").strip().lower()
            if generate_mode not in {"all", "lod1.3", "glb", "cityjson", "citygml"}:
                generate_mode = "all"

            anchor_lon = fields.get("anchor_lon", "").strip()
            anchor_lat = fields.get("anchor_lat", "").strip()
            crs = fields.get("crs", "").strip() or None
            rotate_str = fields.get("rotate", "").strip()
            unit_str = fields.get("source_unit", "auto").strip()

            fallback_lon = float(anchor_lon) if anchor_lon else None
            fallback_lat = float(anchor_lat) if anchor_lat else None
            rotate_deg = float(rotate_str) if rotate_str else 0.0

            viewer_workspace = self.workspace / "viewer"
            viewer_workspace.mkdir(parents=True, exist_ok=True)
            ws_data_json = viewer_workspace / "data.json"
            if not ws_data_json.exists():
                pkg_data_json = self.static_dir / "viewer" / "data.json"
                if pkg_data_json.exists():
                    shutil.copyfile(pkg_data_json, ws_data_json)
                else:
                    ws_data_json.write_text('{"items": []}', encoding="utf-8")

            parser = engine.build_parser()
            args_list = [
                str(saved_input),
                "--out", str(out_dir),
                "--generate", generate_mode,
                "--source-unit", unit_str,
                "--rotate", str(rotate_deg),
                "--viewer-root", str(viewer_workspace),
            ]
            if fallback_lon is not None and fallback_lat is not None:
                args_list.extend(["--anchor-lon", str(fallback_lon), "--anchor-lat", str(fallback_lat)])
            if crs:
                args_list.extend(["--crs", crs])
            if saved_meta:
                args_list.extend(["--metadata", str(saved_meta)])

            args = parser.parse_args(args_list)

            job_id = uuid.uuid4().hex
            job = _new_job()
            with _jobs_lock:
                _jobs[job_id] = job

            _job_emit(job, {"type": "queued", "job_id": job_id})

            def _worker():
                _job_emit(job, {"type": "started"})
                start_t = time.time()
                metadata = {}
                err_msg = None

                def _cb(event):
                    _job_emit(job, event)

                try:
                    metadata = engine.process_one(
                        args=args,
                        input_path=saved_input,
                        out_dir=out_dir,
                        batch=False,
                        dataset=dataset_id,
                        progress_cb=_cb,
                    )
                    if not isinstance(metadata, dict):
                        metadata = {}
                except Exception as exc:
                    import traceback
                    err_msg = f"{exc}\n{traceback.format_exc()}"

                elapsed_sec = round(time.time() - start_t, 2)

                if err_msg:
                    _job_emit(job, {"type": "error", "message": err_msg, "elapsed_sec": elapsed_sec})
                    _job_emit(job, {"type": "close"})
                    return

                geojson_file = out_dir / "building.geojson"
                glb_file = out_dir / "render" / "model.glb"
                if not glb_file.exists():
                    glb_file = out_dir / "model.glb"
                cityjson_file = out_dir / "building.city.json"
                citygml_file = out_dir / "building.gml"

                summary = {
                    "dataset": dataset_id,
                    "format": metadata.get("source_format", ext.lstrip(".").upper()),
                    "crs": metadata.get("georeference", {}).get("crs_epsg") or metadata.get("crs", "EPSG:4326"),
                    "georef_method": metadata.get("georeference", {}).get("method", "fallback"),
                    "anchor": [
                        metadata.get("anchor", {}).get("lon"),
                        metadata.get("anchor", {}).get("lat"),
                    ],
                    "storeys": metadata.get("plateau_count", 0),
                    "height_m": metadata.get("summary", {}).get("max_height_m", 0),
                    "footprint_m2": metadata.get("summary", {}).get("footprint_area_m2", 0),
                    "total_floor_area_m2": metadata.get("summary", {}).get("total_floor_area_m2", 0),
                    "elapsed_sec": elapsed_sec,
                }

                b_name = metadata.get("name") or metadata.get("building_name") or saved_input.stem
                clean_b_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', str(b_name).strip())
                files_info = {}
                if geojson_file.exists():
                    files_info["geojson"] = {
                        "url": f"/api/download?dataset={dataset_id}&file=building.geojson&name={clean_b_name}",
                        "size": geojson_file.stat().st_size,
                        "name": f"{clean_b_name}.geojson",
                    }
                if glb_file.exists():
                    files_info["glb"] = {
                        "url": f"/api/download?dataset={dataset_id}&file=model_glb.zip&name={clean_b_name}",
                        "size": glb_file.stat().st_size,
                        "name": f"{clean_b_name}_glb.zip",
                    }
                if cityjson_file.exists():
                    files_info["cityjson"] = {
                        "url": f"/api/download?dataset={dataset_id}&file=building.city.json&name={clean_b_name}",
                        "size": cityjson_file.stat().st_size,
                        "name": f"{clean_b_name}.city.json",
                    }
                if citygml_file.exists():
                    files_info["citygml"] = {
                        "url": f"/api/download?dataset={dataset_id}&file=building.gml&name={clean_b_name}",
                        "size": citygml_file.stat().st_size,
                        "name": f"{clean_b_name}.gml",
                    }

                _job_emit(job, {
                    "type": "result",
                    "success": True,
                    "dataset": dataset_id,
                    "summary": summary,
                    "files": files_info,
                    "viewer_url": f"/viewer/viewer.html?dataset={dataset_id}",
                })
                _job_emit(job, {"type": "close"})

            t = threading.Thread(target=_worker, daemon=True)
            t.start()

            self.send_json({"success": True, "job_id": job_id})
        finally:
            for fl in files.values():
                p = fl.get("path")
                if p and isinstance(p, Path) and p.exists():
                    try:
                        p.unlink()
                    except OSError:
                        pass

    def handle_job_events(self, job_id: str):
        with _jobs_lock:
            job = _jobs.get(job_id)
        if job is None:
            self.send_error(404, "Job not found")
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        cursor = 0
        try:
            while not getattr(self.server, "is_shutting_down", False):
                with job["lock"]:
                    pending = job["events"][cursor:]
                    cursor = len(job["events"])
                for event in pending:
                    data = json.dumps(event)
                    self.wfile.write(f"data: {data}\n\n".encode())
                    self.wfile.flush()
                    if event.get("type") == "close":
                        return
                time.sleep(0.1)
        except (BrokenPipeError, ConnectionResetError):
            pass


class StudioServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        host, _ = self.server_address[:2]
        self.server_name = host
        self.server_port = self.socket.getsockname()[1]

    def __init__(self, server_address, RequestHandlerClass, workspace: Path):
        super().__init__(server_address, RequestHandlerClass)
        self.workspace = workspace.expanduser().resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.is_shutting_down = False


def start_studio(
    host: str = "127.0.0.1",
    port: int = 8080,
    workspace: Path | None = None,
    open_browser: bool = True,
):
    if workspace is None:
        workspace = Path.cwd() / "arca_workspace"

    stop_event = threading.Event()

    def _sig_handler(signum, frame):
        stop_event.set()

    orig_sigint = None
    orig_sigterm = None
    orig_sigbreak = None
    try:
        orig_sigint = signal.signal(signal.SIGINT, _sig_handler)
        orig_sigterm = signal.signal(signal.SIGTERM, _sig_handler)
        if hasattr(signal, "SIGBREAK"):
            orig_sigbreak = signal.signal(signal.SIGBREAK, _sig_handler)
    except (ValueError, AttributeError):
        pass

    server = StudioServer((host, port), StudioRequestHandler, workspace=workspace)
    port = server.server_port
    url = f"http://{'localhost' if host in {'127.0.0.1', '0.0.0.0'} else host}:{port}/"

    server_thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.2},
        daemon=True,
    )
    server_thread.start()

    if open_browser:
        def _opener():
            if not stop_event.wait(timeout=1.0):
                webbrowser.open(url)
        threading.Thread(target=_opener, daemon=True).start()

    print("=" * 68, flush=True)
    print(f"  ARCA Studio v{__version__}", flush=True)
    print(f"  Web UI Ingestion : {url}", flush=True)
    print(f"  3D GIS Viewer    : {url}viewer/viewer.html", flush=True)
    print(f"  Workspace Folder : {workspace}", flush=True)
    print("=" * 68, flush=True)
    print("  Server is active. Tekan Ctrl+C untuk keluar.\n", flush=True)

    try:
        while not stop_event.is_set():
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        print("\nStopping ARCA Studio...", flush=True)
        server.is_shutting_down = True
        stop_event.set()
        try:
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            if hasattr(signal, "SIGBREAK"):
                signal.signal(signal.SIGBREAK, signal.SIG_IGN)
        except (ValueError, AttributeError):
            pass
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2.0)
        if orig_sigint is not None:
            try:
                signal.signal(signal.SIGINT, orig_sigint)
            except (ValueError, AttributeError):
                pass
        if orig_sigterm is not None:
            try:
                signal.signal(signal.SIGTERM, orig_sigterm)
            except (ValueError, AttributeError):
                pass
        if orig_sigbreak is not None:
            try:
                signal.signal(signal.SIGBREAK, orig_sigbreak)
            except (ValueError, AttributeError):
                pass
