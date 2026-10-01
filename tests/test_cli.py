# SPDX-License-Identifier: AGPL-3.0-only
import subprocess
import sys


def test_cli_help():
    res = subprocess.run([sys.executable, "-m", "arca", "--help"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "ARCA" in res.stdout
    assert "serve" in res.stdout
    assert "run" in res.stdout
    assert "inspect" in res.stdout


def test_cli_subcommands_help():
    for sub in ["serve", "run", "inspect"]:
        res = subprocess.run([sys.executable, "-m", "arca", sub, "--help"], capture_output=True, text=True)
        assert res.returncode == 0
        assert "--help" in res.stdout or "usage:" in res.stdout.lower()
