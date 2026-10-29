# ARCA Community — Release License Gates (human review)

## Applied by this overlay (inventory corrections only)

- [x] Keep root `LICENSE` and ARCA code `AGPL-3.0-only` unchanged.
- [x] Add CesiumJS **1.145** as actual remote runtime used in both Studio and Viewer to manifest/notices.
- [x] Disclose Deck.gl CDN fallback and local-vendor roles.
- [x] Record local SHA-256 of 10 vendored assets with explicit scope **local integrity only**.
- [x] Document incomplete MapLibre and Deck.gl licenses rather than silently claim fulfillment.
- [x] Document wheel/platform-native requirements and BIG/OSM map service distinctions.
- [x] Retain `CLA.md` as a draft; do not replace legal terms or change Enterprise scope.

## Still required **before claiming complete legal clearance**

- [ ] Obtain full **CesiumJS 1.145** official tagged `LICENSE.md`, bundled third-party notices as applicable; identify whether and how to redistribute notice with remote dependency.
- [ ] Obtain and preserve complete **MapLibre GL JS v6.9.0** license/attributions, including inherited component notices.
- [ ] Verify **Deck.gl v9.3.7** official bundle/module licenses and dependent notices; replace abbreviated synopsis only after proof.
- [ ] Match vendored Three.js/MapLibre/Deck.gl file origins to exact releases (not only local hashes).
- [ ] Resolve per-OS Python wheel and native dependency inventories, including LGPL obligations where applicable.
- [ ] Preserve documented map attribution and obtain any necessary permissions before tile rehosting/bulk redistribution. Existing interactive viewer use is a separate question.
- [ ] Enygma owner review of supplied branding origins and sample data assertions (if internal evidence is needed).
- [ ] Qualified counsel review/final adoption of draft CLA **before** reliance for new external contributors and alternative relicensing rights.
- [ ] Record responsible human release acceptance and unresolved conditions.

**This checklist is not legal certification.** OPEN items mean source evidence/approval is still pending, not proof of violation. No new project management, authentication, API platform, viewer refactor, or Enterprise feature is required by this licensing overlay.
