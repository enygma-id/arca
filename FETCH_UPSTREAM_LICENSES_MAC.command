#!/bin/bash
set -u
cd "$(dirname "$0")" || exit 1
printf '%s\n' 'ARCA - official upstream legal document fetcher' ''
if command -v python3 >/dev/null 2>&1; then
  python3 tools/compliance/fetch_upstream_licenses.py --repo-root .
  status=$?
else
  echo 'ERROR: python3 is not installed; no changes made.'
  status=2
fi
printf '\n%s\n' 'See docs/compliance/UPSTREAM_FETCH_REPORT.md and UPSTREAM_FETCH_EVIDENCE.json'
if [ "${ARCA_NONINTERACTIVE:-0}" != 1 ]; then
  printf 'Press Return to close this window...'
  read -r _
fi
exit "$status"
