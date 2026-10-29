#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
python3 tools/compliance/reconcile_upstream_licenses.py --apply
