# A-03 — Asset provenance review (proposed)

Current asset binaries are distributed in the ZIP, but original production/design records were not provided. ARCA ownership is declared by Enygma; creator files and original exports should be attached when available. **No ownership contradiction is claimed.**

| Asset path | Audit action | Evidence status |
|---|---|---|
| `docs/assets/arca-dark.png` | Request source/export history and Enygma owner declaration; classify brand or software asset | `HUMAN_DOCUMENT_REQUEST` |
| `docs/assets/arca-light.png` | Request source/export history and Enygma owner declaration; classify brand or software asset | `HUMAN_DOCUMENT_REQUEST` |
| `src/arca/server/static/assets/apple-touch-icon.png` | Request source/export history and Enygma owner declaration; classify brand or software asset | `HUMAN_DOCUMENT_REQUEST` |
| `src/arca/server/static/assets/favicon-16x16.png` | Request source/export history and Enygma owner declaration; classify brand or software asset | `HUMAN_DOCUMENT_REQUEST` |
| `src/arca/server/static/assets/favicon-32x32.png` | Request source/export history and Enygma owner declaration; classify brand or software asset | `HUMAN_DOCUMENT_REQUEST` |
| `src/arca/server/static/assets/favicon-64x64.png` | Request source/export history and Enygma owner declaration; classify brand or software asset | `HUMAN_DOCUMENT_REQUEST` |
| `src/arca/server/static/assets/favicon.ico` | Request source/export history and Enygma owner declaration; classify brand or software asset | `HUMAN_DOCUMENT_REQUEST` |
| `src/arca/server/static/assets/logo-256.png` | Request source/export history and Enygma owner declaration; classify brand or software asset | `HUMAN_DOCUMENT_REQUEST` |
| `src/arca/server/static/assets/logo.png` | Request source/export history and Enygma owner declaration; classify brand or software asset | `HUMAN_DOCUMENT_REQUEST` |

## Samples

- `samples/arca-sample-area-01/LICENSE-DATA.md`: Enygma declares synthetic IFC, CC-BY-4.0.
- `samples/arca-sample-area-02/LICENSE-DATA.md`: Enygma declares synthetic SKP + JSON, CC-BY-4.0.
- 3/3 sample SHA-256 manifest checks passed, which validates bytes against the repository declaration, **not** factual originality.
- Keep human-generated original source/project records internally where available. Do not change sample license without Enygma authorization.
