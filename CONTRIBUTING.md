# Contributing to ARCA

Thank you for contributing to ARCA.

ARCA is an open-source GIS-native research and engineering project founded and
stewarded by Enygma.

## Before You Start

1. Search existing Issues and Pull Requests.
2. For bugs, provide a reproducible source case where legally shareable.
3. For substantial algorithmic or architectural changes, open an Issue or
   design discussion first.
4. State whether the change affects:
   - source parsing;
   - geometry;
   - semantic extraction;
   - representation profiles;
   - spatial reference;
   - numerical output;
   - file layout;
   - default parameters.
5. Verify license compatibility for new dependencies.
6. Do not introduce code or model data of uncertain provenance.

## Pull Requests

A Pull Request should:

- explain the problem and proposed solution;
- identify affected modules;
- link related Issues;
- document user-visible or scientific behavior changes;
- include tests where reasonably possible;
- include before/after results for material geometry changes;
- update documentation;
- disclose new third-party dependencies;
- avoid unrelated refactoring.

## Representation Claims

Do not upgrade a representation label simply because an output looks more
detailed.

Claims such as LOD2.x, LOD3, standards conformance, semantic equivalence, or
georeferencing accuracy require explicit evidence and review.

## Contributor License Agreement

External contributions may require explicit acceptance of
[`CLA.md`](./CLA.md) through an auditable mechanism designated by the project.

## AI-Assisted Contributions

AI-assisted development is permitted, but contributors remain responsible for:

- correctness;
- provenance;
- licensing;
- security;
- tests;
- validation;
- final acceptance.

See [`AI_USAGE.md`](./AI_USAGE.md).
