# ARCA Security Policy

## Reporting a vulnerability

Do **not** report suspected vulnerabilities through a public GitHub issue, public discussion, pull request description, or other public channel.

Use [GitHub Private Vulnerability Reporting](https://github.com/enygma-id/arca/security/advisories/new) when the reporting form is available. The [repository security page](https://github.com/enygma-id/arca/security) lists published advisories and the current reporting policy. If private reporting is disabled, contact PT Enygma Solusi Negeri through an established private business channel and clearly mark the report as security-sensitive. Never move exploit details to a public issue as a fallback.

See [GitHub's instructions for privately reporting vulnerabilities](https://docs.github.com/en/code-security/security-advisories/working-with-repository-security-advisories/privately-reporting-a-security-vulnerability) for the reporting process.

Do not include credentials, private BIM/CAD files, confidential infrastructure models, production secrets, or personal data in public messages.

## What to include

A useful private report should include:

- affected version, commit, or environment configuration;
- input file or processing component involved (IFC, SKP, ATAP GeoJSON, or web server);
- reproduction steps or minimal malformed sample file;
- expected and observed behavior;
- security impact (e.g., path traversal, memory exhaustion, denial-of-service);
- whether exploitation requires authentication, network position, or crafted input; and
- suggested remediation if known.

## Sensitive information

Never publish:

- access keys, tokens, or credentials;
- private keys or certificates;
- confidential BIM/IFC models or proprietary CAD designs;
- sensitive geographic or infrastructure location data; or
- exploit details before coordinated disclosure is complete.

## Relevant security areas

Potential areas of focus for ARCA include:

- arbitrary code execution;
- path traversal during archive decompression or output writing;
- malicious or malformed SKP/IFC/GeoJSON input parsing;
- memory exhaustion or CPU denial-of-service through crafted geometry;
- unsafe archive/file handling;
- dependency or supply-chain compromise; and
- cross-site scripting (XSS) or header injection in the local studio web viewer.

## Response process

The Project Steward or designated security maintainers may:

1. acknowledge the report privately;
2. reproduce and assess impact;
3. prepare a fix in a restricted branch or private fork when necessary;
4. coordinate release timing;
5. request a CVE where appropriate; and
6. publish a security advisory after a reasonable remediation window.

## Supported versions

A formal supported-version matrix will be published when ARCA begins stable tagged releases. Supported versions and security-fix windows will be defined by published release notices.

## Good-faith research

Good-faith security research is welcome when it avoids privacy harm, data destruction, service disruption, credential misuse, unauthorized persistence, or unnecessary access to third-party systems.
