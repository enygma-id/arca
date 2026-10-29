# ARCA — Rekonsiliasi dokumen lisensi (Mac)

**Baseline:** clone ARCA Anda yang telah memiliki lima dokumen upstream hasil fetch dan `docs/compliance/UPSTREAM_FETCH_EVIDENCE.json`.

## Langkah
1. Ekstrak overlay ZIP ini, salin isinya ke **root clone ARCA** menggunakan Finder. Tidak perlu menghapus file apa pun. Hanya menambah skrip baru pada `tools/compliance/` dan launcher di root.
2. Buka Terminal di root ARCA. Jalankan uji tanpa mengubah repositori:
   ```bash
   python3 tools/compliance/reconcile_upstream_licenses.py
   ```
   Harus muncul `PREFLIGHT OK`.
3. Terapkan pembaruan:
   ```bash
   python3 tools/compliance/reconcile_upstream_licenses.py --apply
   ```
   Alternatif: `bash RECONCILE_LICENSES_MAC.command`.
4. Di GitHub Desktop, tinjau 7 file perubahan dan 2 file laporan baru, serta skrip/README jika ingin di-commit. Jangan langsung push tanpa review.
5. Buka `docs/compliance/RECONCILIATION_REPORT.md` dan `docs/compliance/RECONCILIATION_EVIDENCE.json`. Verifikasi bahwa lima file berstatus `FETCHED_TAGGED_SOURCE`.

## Perubahan yang dilakukan
- `THIRD_PARTY_NOTICES.md` — tautan ke lisensi upstream yang sudah terarsip; tetap menandai bundle-review pending.
- `third-party/MANIFEST.json` — SHA-256 dokumen lisensi dan Cesium ThirdParty, tanpa menghapus inventaris hash vendor.
- `third-party/README.md` dan `third-party/cesium/README.md` — status dan lokasi dokumen yang benar.
- `third-party/maplibre-gl/UPSTREAM_NOTICES_STATUS.md` dan `third-party/deck.gl/UPSTREAM_NOTICES_STATUS.md` — tidak lagi mengklaim teks upstream belum diunduh.
- `docs/compliance/ARCA_LICENSE_REGISTER.csv` — baris frontend tetap `NEEDS_VERIFICATION`, tapi memiliki bukti file dan hash.
- `docs/compliance/RECONCILIATION_REPORT.md` + `RECONCILIATION_EVIDENCE.json` — catatan hasil otomatis.

## Batas
Tidak ada pengunduhan jaringan. Script **menolak** bekerja bila file upstream yang diverifikasi tidak ada, SHA-256 salah, `ThirdParty.json` bukan JSON valid, atau hash vendor tidak cocok. Tidak mengubah `LICENSE` AGPL, `uv.lock`, converter, viewer, server, atau aset. Backup dibuat di temporary directory macOS dan lokasinya dicetak. Pemeriksaan hukum atas komposisi bundle dan native wheels tetap diperlukan.
