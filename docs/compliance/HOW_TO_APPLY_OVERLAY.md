# Apply the ARCA licensing overlay

The ZIP has **repository-relative paths at its root**, not a wrapper folder. Do **not** extract inside an additional `overlay/` directory inside your Git checkout.

From a clone root (`README.md`, `LICENSE`, `src/` and `third-party/` visible):

```bash
# Recommended: create a branch and confirm a clean tree first
git switch -c chore/licensing-evidence-2026-10-29
# Optional safety: git status --short

# Extract the overlay zip using its actual local path:
unzip -o /absolute/path/ARCA_LICENSING_OVERLAY_2026-10-29.zip -d .

python -m json.tool third-party/MANIFEST.json >/dev/null
git diff --check
git diff -- THIRD_PARTY_NOTICES.md third-party/MANIFEST.json third-party/README.md
git status --short
```

**Do not copy or delete** original `third-party/**/LICENSE*` as part of this overlay. The incomplete full upstream MapLibre/Cesium/Deck notices remain explicitly flagged, with exact retrieval instructions in `UPSTREAM_LICENSE_FETCH.md`. Continue human/legal review before publicly claiming all license obligations are closed. No modification to source code or Community `AGPL-3.0-only` is authorized by this package.
