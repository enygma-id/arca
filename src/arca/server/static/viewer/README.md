# ARCA 3D Multi-Engine Viewer

Folder ini berisi implementasi **3D GIS Multi-Engine Viewer** yang mendukung **MapLibre GL JS**, **Deck.gl**, dan **CesiumJS**.

Untuk dokumentasi lengkap arsitektur dan settingan teknis layer:
👉 Lihat panduan lengkap di: [`docs/viewer-guide.md`](../../../../docs/viewer-guide.md)

---

## File Penting:

- `app.js`: Implementasi kode render untuk 3 engine:
  - `DeckRenderer` (Deck.gl `GeoJsonLayer` & `ScenegraphLayer`)
  - `MaplibreRenderer` (MapLibre `fill-extrusion` & custom Three.js GLB layer)
  - `CesiumRenderer` (CesiumJS WGS84 globe & ENU transform matrix)
- `viewer.html`: Layout viewport 3D, panel layer switcher, dan kartu inspeksi atribut.
- `styles.css`: Styling antarmuka viewer.
- `data.json`: Katalog dataset bangunan yang sedang aktif.
