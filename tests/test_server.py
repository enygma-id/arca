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
