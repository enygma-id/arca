<!-- SPDX-License-Identifier: AGPL-3.0-only -->
# Branch ruleset templates

These files are reviewed inputs for a repository administrator, not automation
that changes settings. Before applying, compare existing rulesets and update an
existing matching ruleset instead of creating duplicates.

```sh
gh api repos/enygma-id/arca/rulesets
gh api -X POST repos/enygma-id/arca/rulesets --input docs/security/rulesets/main.json
gh api -X POST repos/enygma-id/arca/rulesets --input docs/security/rulesets/beta.json
```

For an existing ruleset, use `gh api -X PUT repos/enygma-id/arca/rulesets/ID`
with the corresponding `--input` file after verifying its ID.

The main ruleset requires 1 approving review, approval of the latest push,
resolved conversations, and up-to-date core CI checks. No bypass actors are
configured. Beta only blocks deletion and non-fast-forward pushes.

The 10 CI status check names configured for main:

- `test (ubuntu-latest, py3.12)`
- `test (ubuntu-latest, py3.10)`
- `test (windows-latest, py3.12)`
- `test (windows-latest, py3.10)`
- `samples-e2e (ubuntu-latest, py3.12)`
- `uv-workflow (ubuntu-latest)`
- `uv-workflow (windows-latest)`
- `uv-workflow (macos-latest)`
- `audit (security dependencies)`
- `Analyze (python)`
