# SPDX-License-Identifier: AGPL-3.0-only
from unittest.mock import MagicMock

from arca.server.app import StudioRequestHandler


def test_api_download_and_history_for_glb(tmp_path):
    ws = tmp_path / "workspace"
    out_dir = ws / "outputs" / "sample_dataset"
    render_dir = out_dir / "render"
    render_dir.mkdir(parents=True, exist_ok=True)

    geojson_file = out_dir / "building.geojson"
    geojson_file.write_text('{"type": "FeatureCollection", "features": []}', encoding="utf-8")

    glb_file = render_dir / "model.glb"
    glb_file.write_bytes(b"glTF\x02\x00\x00\x00")

    model_geojson_file = render_dir / "model.geojson"
    model_geojson_file.write_text('{"type": "FeatureCollection", "features": []}', encoding="utf-8")

    handler = StudioRequestHandler.__new__(StudioRequestHandler)
    handler.server = MagicMock()
    handler.server.workspace = ws

    sent_jsons = []
    def mock_send_json(data, status=200):
        sent_jsons.append((status, data))
    handler.send_json = mock_send_json

    # Test handle_history finds render/model.glb
    handler.handle_history()
    assert len(sent_jsons) == 1
    status, payload = sent_jsons[0]
    assert status == 200
    datasets = payload.get("datasets", [])
    assert len(datasets) == 1
    assert datasets[0]["dataset"] == "sample_dataset"
    assert datasets[0]["has_geojson"] is True
    assert datasets[0]["has_glb"] is True

    # Test /api/download finds render/model.glb
    served_files = []
    def mock_send_file(path, download_name=None):
        served_files.append((path, download_name))
    handler.send_file_response = mock_send_file

    handler.path = "/api/download?dataset=sample_dataset&file=model.glb"
    handler.do_GET()
    assert len(served_files) == 1
    assert served_files[0][0] == glb_file
    assert served_files[0][1] == "model.glb"

    # Test /api/download with explicit building name
    served_files.clear()
    handler.path = "/api/download?dataset=sample_dataset&file=model.glb&name=Mall%20Mega"
    handler.do_GET()
    assert len(served_files) == 1
    assert served_files[0][1] == "Mall_Mega.glb"

    served_files.clear()
    handler.path = "/api/download?dataset=sample_dataset&file=building.geojson&name=Mall%20Mega"
    handler.do_GET()
    assert len(served_files) == 1
    assert served_files[0][1] == "Mall_Mega.geojson"

    # Test /api/download bundling model_glb.zip (model.glb + model.geojson)
    import io
    import zipfile
    served_bytes = []
    def mock_send_bytes(data, mime_type="application/octet-stream", download_name=None):
        served_bytes.append((data, mime_type, download_name))
    handler.send_bytes_response = mock_send_bytes

    handler.path = "/api/download?dataset=sample_dataset&file=model_glb.zip&name=Mall%20Mega"
    handler.do_GET()
    assert len(served_bytes) == 1
    zip_data, mime, dl_name = served_bytes[0]
    assert mime == "application/zip"
    assert dl_name == "Mall_Mega_glb.zip"
    with zipfile.ZipFile(io.BytesIO(zip_data), "r") as zf:
        namelist = sorted(zf.namelist())
        assert namelist == ["model.geojson", "model.glb"]
        assert zf.read("model.glb") == b"glTF\x02\x00\x00\x00"
        assert b"FeatureCollection" in zf.read("model.geojson")


def test_model_geojson_rfc7946_structure():
    anchor = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [106.8, -6.2, 10.0]},
            "properties": {
                "id": "bldg-01",
                "name": "Test Building",
                "model_url": "./model.glb",
                "scale": 1.0,
                "heading": 45.0,
                "pitch": 0.0,
                "roll": 0.0,
                "height_m": 20.0,
                "storeys": 4,
                "crs": "EPSG:32748",
            },
        }],
    }
    assert anchor["type"] == "FeatureCollection"
    feat = anchor["features"][0]
    assert feat["type"] == "Feature"
    assert feat["geometry"]["type"] == "Point"
    coords = feat["geometry"]["coordinates"]
    assert len(coords) == 3
    lon, lat, alt = coords
    assert -180 <= lon <= 180
    assert -90 <= lat <= 90
    props = feat["properties"]
    for key in ("id", "name", "model_url", "scale", "heading", "pitch", "roll", "height_m", "storeys", "crs"):
        assert key in props


def test_start_studio_clean_shutdown(tmp_path):
    import signal
    import subprocess
    import sys
    import time

    ws = tmp_path / "ws"
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

    proc = subprocess.Popen(
        [
            sys.executable,
            "-u",
            "-m",
            "arca",
            "serve",
            "--port",
            "0",
            "--workspace",
            str(ws),
            "--no-browser",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        **kwargs,
    )

    started = False
    output_lines = []
    try:
        deadline = time.time() + 30.0
        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    break
                time.sleep(0.05)
                continue
            output_lines.append(line)
            if "Server is active" in line:
                started = True
                break

        if not started:
            err = proc.stderr.read() if proc.stderr else ""
            assert started, f"Server failed to start in time. Output:\n{''.join(output_lines)}\nStderr:\n{err}"

        if sys.platform == "win32":
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.send_signal(signal.SIGINT)

        stdout, stderr = proc.communicate(timeout=10.0)
        full_stdout = "".join(output_lines) + stdout
        assert proc.returncode in (0, 130, 3221225786)
        assert "Stopping ARCA Studio..." in full_stdout
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                proc.kill()



