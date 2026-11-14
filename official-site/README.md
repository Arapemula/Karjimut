# Karjimut (`sleep-mcp` v2.0.13) — Official Website

Folder `official-site/` ini berisi kode sumber **Official Website Karjimut** yang terpisah sepenuhnya dari paket utama Python (`sleep-mcp/`).

## Struktur File
- [`index.html`](file:///c:/Users/ASUS/OneDrive/Desktop/Skripsi/official-site/index.html) — Halaman utama *Official Site* dengan dwibahasa (`EN` / `ID`), simulasi *Dashboard Telemetry*, *7-Step Sleep Cycle Explorer*, dan *6-Stage Hybrid Search Sandbox*.
- [`styles.css`](file:///c:/Users/ASUS/OneDrive/Desktop/Skripsi/official-site/styles.css) — Implementasi penuh *Design Tokens* (`#0a0a0a` canvas, `#141414` card, `#1e1e1e` 48px blueprint grid, `#6798ff` soft indigo spark, tipografi `Inter` & `JetBrains Mono`, dan *zero drop-shadows*).
- [`app.js`](file:///c:/Users/ASUS/OneDrive/Desktop/Skripsi/official-site/app.js) — Logika interaktif (switcher CLI, tab telemetri, *1-Click Rollback* KTP, simulasi *Sleep Cycle*, *Sandbox Hybrid Search* + *Self-Learning*, dan *toggle* bahasa EN/ID).
- [`STYLE_REFERENCE.md`](file:///c:/Users/ASUS/OneDrive/Desktop/Skripsi/official-site/STYLE_REFERENCE.md) — Dokumen spesifikasi sistem desain resmi Karjimut.

## Cara Menjalankan Lokal
Anda dapat membuka [`index.html`](file:///c:/Users/ASUS/OneDrive/Desktop/Skripsi/official-site/index.html) langsung di browser, atau menjalankan server statis lokal:

```powershell
python -m http.server 8080 --directory official-site
```
Lalu buka `http://localhost:8080` di browser Anda.
