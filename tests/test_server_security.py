# SPDX-License-Identifier: AGPL-3.0-only
import io
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from arca.server.app import (
    MultipartStreamReader,
    StudioRequestHandler,
    get_max_upload_bytes,
    is_safe_dataset_id,
    safe_resolve_child,
)


def test_safe_resolve_child(tmp_path):
    base = tmp_path / "sandbox"
    base.mkdir()
    child_file = base / "valid.txt"
    child_file.write_text("hello", encoding="utf-8")

    sub_dir = base / "nested"
    sub_dir.mkdir()
    nested_file = sub_dir / "doc.json"
    nested_file.write_text("{}", encoding="utf-8")

    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("secret", encoding="utf-8")

    # Valid children
    assert safe_resolve_child(base, "valid.txt") == child_file.resolve()
    assert safe_resolve_child(base, "nested/doc.json") == nested_file.resolve()

    # Rejection of empty or invalid types
    assert safe_resolve_child(base, "") is None
    assert safe_resolve_child(base, None) is None

    # Path traversal attempts
    assert safe_resolve_child(base, "../outside.txt") is None
    assert safe_resolve_child(base, "..\\outside.txt") is None
    assert safe_resolve_child(base, "nested/../../outside.txt") is None
    assert safe_resolve_child(base, "nested/../nested/doc.json") is None  # '..' segment strictly rejected
    assert safe_resolve_child(base, "/etc/passwd") is None
    assert safe_resolve_child(base, "\\windows\\system32") is None
    assert safe_resolve_child(base, "C:\\autoexec.bat") is None
    assert safe_resolve_child(base, "valid.txt\x00extra") is None

    # Symlink escape test
    symlink_outside = base / "escape_symlink"
    try:
        symlink_outside.symlink_to(outside_file)
        assert safe_resolve_child(base, "escape_symlink") is None
    except (OSError, NotImplementedError):
        pass


def test_is_safe_dataset_id():
    # Valid slugs
    assert is_safe_dataset_id("sample_mall_123") is True
    assert is_safe_dataset_id("dataset1") is True
    assert is_safe_dataset_id("a") is True

    # Invalid / dangerous slugs
    assert is_safe_dataset_id("") is False
    assert is_safe_dataset_id(None) is False
    assert is_safe_dataset_id("../escape") is False
    assert is_safe_dataset_id("..") is False
    assert is_safe_dataset_id("folder/child") is False
    assert is_safe_dataset_id("folder\\child") is False
    assert is_safe_dataset_id("dataset\x00") is False
    assert is_safe_dataset_id("dataset with space") is False
    assert is_safe_dataset_id("UpperCase") is False
    assert is_safe_dataset_id("a" * 129) is False  # length > 128


def test_get_max_upload_bytes(monkeypatch):
    monkeypatch.delenv("ARCA_MAX_UPLOAD_BYTES", raising=False)
    assert get_max_upload_bytes() == 4 * 1024 * 1024 * 1024

    monkeypatch.setenv("ARCA_MAX_UPLOAD_BYTES", "1048576")
    assert get_max_upload_bytes() == 1048576

    monkeypatch.setenv("ARCA_MAX_UPLOAD_BYTES", "invalid")
    with pytest.raises(ValueError, match="Invalid ARCA_MAX_UPLOAD_BYTES"):
        get_max_upload_bytes()

    monkeypatch.setenv("ARCA_MAX_UPLOAD_BYTES", "-100")
    with pytest.raises(ValueError, match="Invalid ARCA_MAX_UPLOAD_BYTES"):
        get_max_upload_bytes()


def create_mock_handler(workspace: Path):
    handler = StudioRequestHandler.__new__(StudioRequestHandler)
    handler.server = MagicMock()
    handler.server.workspace = workspace
    handler.server.is_shutting_down = False

    errors = []
    def mock_send_error(code, msg=""):
        errors.append((code, msg))
    handler.send_error = mock_send_error

    jsons = []
    def mock_send_json(data, status=200):
        jsons.append((status, data))
    handler.send_json = mock_send_json

    files = []
    def mock_send_file(path, download_name=None):
        files.append((path, download_name))
    handler.send_file_response = mock_send_file

    bytes_resp = []
    def mock_send_bytes(data, mime_type="", download_name=None):
        bytes_resp.append((data, mime_type, download_name))
    handler.send_bytes_response = mock_send_bytes

    return handler, errors, jsons, files, bytes_resp


def test_download_security_restrictions(tmp_path):
    ws = tmp_path / "workspace"
    out_dir = ws / "outputs" / "my_dataset"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "building.geojson").write_text("{}", encoding="utf-8")
    (out_dir / "secret.py").write_text("SECRET=123", encoding="utf-8")

    handler, errors, jsons, files, bytes_resp = create_mock_handler(ws)

    # 1. Missing parameters
    handler.path = "/api/download"
    handler.do_GET()
    assert len(errors) == 1 and errors[0][0] == 400

    # 2. Dataset traversal attempt
    errors.clear()
    handler.path = "/api/download?dataset=../outside&file=building.geojson"
    handler.do_GET()
    assert len(errors) == 1 and errors[0][0] == 400

    # 3. File traversal attempt
    errors.clear()
    handler.path = "/api/download?dataset=my_dataset&file=../../etc/passwd"
    handler.do_GET()
    assert len(errors) == 1 and errors[0][0] == 400

    # 4. File outside allowlist
    errors.clear()
    handler.path = "/api/download?dataset=my_dataset&file=secret.py"
    handler.do_GET()
    assert len(errors) == 1 and errors[0][0] == 400

    # 5. Non-existent dataset
    errors.clear()
    handler.path = "/api/download?dataset=non_existent&file=building.geojson"
    handler.do_GET()
    assert len(errors) == 1 and errors[0][0] == 404

    # 6. Allowed file download succeeds
    errors.clear()
    handler.path = "/api/download?dataset=my_dataset&file=building.geojson"
    handler.do_GET()
    assert len(errors) == 0
    assert len(files) == 1
    assert files[0][0] == out_dir / "building.geojson"


def test_static_and_viewer_traversal_rejection(tmp_path):
    ws = tmp_path / "workspace"
    handler, errors, jsons, files, bytes_resp = create_mock_handler(ws)

    # Static path traversal
    handler.path = "/static/../secret.txt"
    handler.do_GET()
    assert len(errors) == 1 and errors[0][0] == 400

    # Viewer path traversal
    errors.clear()
    handler.path = "/viewer/../../app.py"
    handler.do_GET()
    assert len(errors) == 1 and errors[0][0] == 400

    # Multilod path traversal
    errors.clear()
    handler.path = "/multilod/../../etc/passwd"
    handler.do_GET()
    assert len(errors) == 1 and errors[0][0] == 400

    # Data path traversal
    errors.clear()
    handler.path = "/data/../../secret"
    handler.do_GET()
    assert len(errors) == 1 and errors[0][0] == 400


def test_delete_security_and_atomic_update(tmp_path):
    ws = tmp_path / "workspace"
    outputs = ws / "outputs"
    target_out = outputs / "target_dataset"
    target_out.mkdir(parents=True, exist_ok=True)
    (target_out / "building.geojson").write_text("{}", encoding="utf-8")

    multilod = ws / "viewer" / "multilod"
    target_lod = multilod / "target_dataset"
    target_lod.mkdir(parents=True, exist_ok=True)
    (target_lod / "lod1.geojson").write_text("{}", encoding="utf-8")

    data_json_path = ws / "viewer" / "data.json"
    data_json_path.parent.mkdir(parents=True, exist_ok=True)
    catalog = {
        "items": [
            {"id": "target_dataset", "name": "Target"},
            {"id": "other_dataset", "name": "Other"},
        ]
    }
    data_json_path.write_text(json.dumps(catalog), encoding="utf-8")

    handler, errors, jsons, files, bytes_resp = create_mock_handler(ws)

    # 1. Traversal attempt in delete query
    handler.path = "/api/delete?dataset=../escape"
    handler.handle_delete()
    assert len(jsons) == 1
    assert jsons[0][0] == 400
    assert outputs.exists()

    # 2. Legitimate delete
    jsons.clear()
    handler.path = "/api/delete?dataset=target_dataset"
    handler.handle_delete()
    assert len(jsons) == 1
    assert jsons[0][0] == 200
    assert not target_out.exists()
    assert not target_lod.exists()
    assert outputs.exists()  # Ensure parent was not deleted
    assert multilod.exists()

    # Verify atomic update of data.json
    updated_catalog = json.loads(data_json_path.read_text(encoding="utf-8"))
    assert len(updated_catalog["items"]) == 1
    assert updated_catalog["items"][0]["id"] == "other_dataset"


def test_multipart_streaming_stress_chunk_boundaries(tmp_path):
    boundary = b"boundary123"
    binary_content = b"IFC-BINARY-\x00\x01\x02\r\n--boundary123_NOT\r\nMIDDLE-\xff\xfe-END"
    payload = (
        b"--boundary123\r\n"
        b'Content-Disposition: form-data; name="dataset_name"\r\n\r\n'
        b"My Test Model\r\n"
        b"--boundary123\r\n"
        b'Content-Disposition: form-data; name="file"; filename="test.ifc"\r\n'
        b"Content-Type: application/octet-stream\r\n\r\n"
        + binary_content
        + b"\r\n--boundary123--\r\n"
    )

    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()

    # Test with very small chunk size to verify buffer slicing across all boundaries
    reader = MultipartStreamReader(
        stream=io.BytesIO(payload),
        boundary=boundary,
        max_bytes=1024 * 1024,
        temp_dir=temp_dir,
        expected_length=len(payload),
        chunk_size=5,
    )
    fields, files = reader.parse()

    assert fields["dataset_name"] == "My Test Model"
    assert "file" in files
    assert files["file"]["filename"] == "test.ifc"
    tmp_file = files["file"]["path"]
    assert tmp_file.exists()
    assert tmp_file.read_bytes() == binary_content

    # Clean up
    tmp_file.unlink()


def test_multipart_streaming_overflow_cleanup(tmp_path):
    boundary = b"boundary123"
    payload = (
        b"--boundary123\r\n"
        b'Content-Disposition: form-data; name="file"; filename="large.ifc"\r\n'
        b"Content-Type: application/octet-stream\r\n\r\n"
        b"A" * 5000
        + b"\r\n--boundary123--\r\n"
    )

    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()

    reader = MultipartStreamReader(
        stream=io.BytesIO(payload),
        boundary=boundary,
        max_bytes=1000,  # limit lower than payload
        temp_dir=temp_dir,
        expected_length=len(payload),
        chunk_size=256,
    )

    with pytest.raises(OverflowError):
        reader.parse()

    # Verify that temporary files were cleaned up on abort
    assert list(temp_dir.iterdir()) == []


def test_handle_inspect_security_and_cleanup(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCA_MAX_UPLOAD_BYTES", "500")
    ws = tmp_path / "workspace"
    handler, errors, jsons, files, bytes_resp = create_mock_handler(ws)

    # 1. Missing Content-Type
    handler.headers = {}
    handler.handle_inspect()
    assert jsons[-1][0] == 400

    # 2. Content-Length exceeding limit (413)
    handler.headers = {
        "Content-Type": "multipart/form-data; boundary=bnd",
        "Content-Length": "1000",
    }
    handler.handle_inspect()
    assert jsons[-1][0] == 413

    # 3. Unsupported extension
    payload = (
        b"--bnd\r\n"
        b'Content-Disposition: form-data; name="file"; filename="script.exe"\r\n'
        b"Content-Type: application/octet-stream\r\n\r\n"
        b"MZ..."
        b"\r\n--bnd--\r\n"
    )
    handler.headers = {
        "Content-Type": "multipart/form-data; boundary=bnd",
        "Content-Length": str(len(payload)),
    }
    handler.rfile = io.BytesIO(payload)
    handler.handle_inspect()
    assert jsons[-1][0] == 400
    assert "not supported" in jsons[-1][1]["error"]

    # Verify temp dir has no leftover files
    temp_dir = ws / "temp"
    if temp_dir.exists():
        assert list(temp_dir.iterdir()) == []
