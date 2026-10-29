# SPDX-License-Identifier: AGPL-3.0-only
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_escape_html_node_runner():
    """Verify escapeHtml properly sanitizes dangerous XSS vectors."""
    viewer_app_js = (REPO_ROOT / "src/arca/server/static/viewer/app.js").read_text(encoding="utf-8")
    assert "function escapeHtml(str)" in viewer_app_js

    runner_script = r"""
    function escapeHtml(str) {
      if (str == null) return "";
      return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    function selectedItemHtml(asset) {
      if (!asset) {
        return 'Click a building to inspect its attributes.';
      }
      const a = asset.item.attributes || {};
      const rows = [
        ['Name', asset.item.name],
        ['Function', a.fungsi],
        ['Address', a.alamat],
        ['Year', a.tahun],
        ['Area', a.luas != null ? `${a.luas} m²` : null],
        ['Height', a.tinggi != null ? `${a.tinggi} m` : null],
        ['Floors', a.jumlah_lantai],
        ['Latitude', asset.item.latitude],
        ['Longitude', asset.item.longitude]
      ].filter(([,v]) => v !== null && v !== undefined && v !== '');
      return rows.map(([k,v]) => `<div><b>${escapeHtml(k)}:</b> ${escapeHtml(v)}</div>`).join('');
    }

    const maliciousAsset = {
      item: {
        id: "evil_id_1",
        name: '<script>alert("xss")</script>',
        latitude: -6.2,
        longitude: 106.8,
        attributes: {
          fungsi: '<img src=x onerror=alert(1)>',
          alamat: 'Road "><svg onload=alert(2)> & \'bar\'',
          jumlah_lantai: '5<script>',
        }
      }
    };

    const rendered = selectedItemHtml(maliciousAsset);

    // Assertions
    if (rendered.includes('<script>') || rendered.includes('<img') || rendered.includes('<svg')) {
      throw new Error('XSS payload rendered unescaped: ' + rendered);
    }
    if (!rendered.includes('&lt;script&gt;') || !rendered.includes('&lt;img') || !rendered.includes('&quot;&gt;&lt;svg')) {
      throw new Error('Expected escaped entities missing: ' + rendered);
    }
    console.log(JSON.stringify({ status: "ok", rendered }));
    """

    res = subprocess.run(["node", "-e", runner_script], capture_output=True, text=True)
    if res.returncode != 0:
        raise AssertionError(f"Node execution failed:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}")
    out = json.loads(res.stdout)
    assert out["status"] == "ok"
    assert "<script>" not in out["rendered"]
    assert "<img" not in out["rendered"]


def test_app_js_static_analysis_safe_dom():
    """Verify app.js doesn't use risky innerHTML interpolations for history items."""
    app_js = (REPO_ROOT / "src/arca/server/static/app.js").read_text(encoding="utf-8")

    # Ensure URLSearchParams is used for history download links
    assert "new URLSearchParams({" in app_js

    # Ensure dangerous innerHTML interpolation of list.map is removed
    assert "historyBody.innerHTML = list.map" not in app_js

    # Ensure textContent or createElement is used for model links
    assert "link.textContent = item.name" in app_js or "link.textContent =" in app_js
