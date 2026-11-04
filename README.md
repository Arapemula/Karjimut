<p align="center">
  <img src="sleep-mcp/assets/karjimut_banner.png" alt="Karjimut Logo" width="680" style="border-radius: 16px;" />
</p>

<h1 align="center">Karjimut </h1>

<p align="center">
  <strong>Arsitektur Memori Dua Lapis Berbasis Model Context Protocol (MCP) dengan Konsolidasi Fase Idle, Elastic Core, dan Sinkronisasi Multi-Tim untuk Efisiensi Token Lintas Agentic AI</strong>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.10%2B-blue.svg" alt="Python 3.10+"></a>
  <a href="https://modelcontextprotocol.io/"><img src="https://img.shields.io/badge/MCP-1.2.0%2B-green.svg" alt="MCP Spec"></a>
  <a href="https://sqlite.org/wal.html"><img src="https://img.shields.io/badge/SQLite-WAL%20%2B%20FTS5%20BM25-orange.svg" alt="SQLite WAL"></a>
  <a href="https://github.com/Arapemula/Karjimut"><img src="https://img.shields.io/badge/Tests-26%2F26%20Passed-brightgreen.svg" alt="Tests 26/26 Passed"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
</p>

<p align="center">
  Dikembangkan oleh <strong>Naufal Arhab Fadhil Muhammad</strong>
</p>

---

## 🌟 Mengapa Karjimut?

Autonomous AI Coding Agent modern (*Antigravity IDE*, *Cursor*, *Claude Code*, *Cline*, *Windsurf*) menderita tiga masalah struktural ketika mengerjakan proyek perangkat lunak jangka panjang:
1. **Pembengkakan Context Window ($O(N)$)**: Seluruh riwayat percakapan dan log *trial-and-error* terus ditumpuk hingga melampaui batas token dan menguras kuota API.
2. **Context Rot & Amnesia Lintas Sesi**: Saat sesi baru dibuka atau *context compaction* terjadi, agen lupa aturan arsitektur inti dan mengulangi *bug* yang sama.
3. **Isolasi Memori Antar-Developer**: Memori lokal agen di satu komputer tidak terdistribusi ke rekan satu tim.

**Karjimut** menyelesaikan ketiganya melalui **Arsitektur Memori Dua Lapis Berbasis Model Context Protocol (MCP)** yang dikombinasikan dengan **Konsolidasi Fase Idle (*7-Step Sleep Cycle*)** — terinspirasi dari konsolidasi memori biologis manusia saat tidur.

---

## 🧠 Arsitektur Memori Dua Lapis (v2.0)

| Lapisan Memori | Kapasitas Token | Karakteristik & Peran | Primitif MCP |
| :--- | :--- | :--- | :--- |
| **Lapis 1: KTP Proyek**<br>(*Elastic Core Project Identity*) | **Elastic Core** (`KTP_MAX_TOKENS=0` default: fleksibel mengikuti skala proyek; atau opsional batas keras $\le 150$ token) | Menyimpan identitas aplikasi, *tech stack*, struktur direktori inti, dan aturan arsitektur wajib yang selalu terkompresi tanpa duplikasi ($O(1)$ per sesi). | **Tool:** `baca_ktp_proyek(kode_proyek)`<br>**Resource:** `karjimut://{kode_proyek}/ktp` |
| **Lapis 2: Laci Arsip Solusi**<br>(*On-Demand Solution Vault*) | **0 Token di awal sesi**<br>(Hanya diambil saat dibutuhkan) | Menyimpan intisari solusi paten atas *error* teknis/*bug*, dilengkapi *multi-tag* gejala, *1-hop causal graph*, dan bobot *confidence score*. | **Tool:** `cari_laci_solusi(kode_proyek, kata_kunci)` |

Selama sesi koding berlangsung, agen AI mencatat setiap *milestone* secara asinkron ($< 10\text{ ms}$) menggunakan tool `titip_catatan_kerja(kode_proyek, ringkasan_aksi)` ke dalam `antrean_mentah`. Saat pengguna tidak aktif ($\ge 5$ menit), **Idle Watcher** memicu **Sleep Cycle** di latar belakang tanpa mengganggu alur kerja.

---

## 🚀 Fitur Unggulan Karjimut v2.0

- **⚡ Elastic Core Mode (`KTP_MAX_TOKENS=0`)**: Memori Lapis 1 (KTP Proyek) tidak lagi dipotong paksa pada proyek berskala besar, namun tetap dirangkum secara padat oleh *Sleep Cycle* agar bebas dari polusi log mentah. Tetap mendukung mode batas keras ($\le 150$ token) bila dikonfigurasi.
- **🤝 Multi-Team Git Sync (`.karjimut/team_memory.jsonl`)**: Menyinkronkan KTP Proyek dan solusi *bug* paten lintas anggota tim melalui format JSON Lines yang ramah `git merge` — bebas konflik file biner SQLite! Mendukung *backward compatibility* otomatis dengan folder `.sleep-mcp/`.
- **🧹 Self-Cleaning Memory & Confidence Decay**: Solusi lama yang usang otomatis ditandai dengan `supersedes_id` saat arsitektur berubah, sementara solusi yang sering berhasil dipakai mendapat kenaikan `confidence_score` pada perankingan pencarian.
- **🕸️ 1-Hop Causal Graph (Relasi Lapis 1 $\leftrightarrow$ Lapis 2)**: Setiap aturan di KTP Proyek dapat menautkan referensi langsung (`[Solusi #ID]`) ke solusi teknis di Laci Arsip.
- **🔍 Hybrid Search Dwibahasa (FTS5 Okapi BM25 + Vector ONNX RRF)**: Menggabungkan pencarian leksikal eksak kode error (`SQLITE_BUSY`, `#nextjs-15`) dengan pencarian semantik *multilingual* (`paraphrase-multilingual-MiniLM-L12-v2` via *FastEmbed* ONNX CPU) menggunakan *Reciprocal Rank Fusion* (RRF).
- **🖥️ Aplikasi Desktop Native (CustomTkinter)**: Dilengkapi *1-Column Auto-Detect API Key Wizard* (mendukung Google Gemini, Groq, OpenRouter, Anthropic Claude, OpenAI, hingga mode 100% *Offline Rule-Based Distiller*), editor KTP Proyek dengan *1-Click Rollback*, CRUD Laci Solusi, dan Dashboard Metrik Penghematan Token (Metrik A & Metrik B).

---

## 📂 Struktur Repositori Distribusi

```text
Karjimut/
|-- README.md                       # Dokumentasi utama & panduan Quick Start
|-- GEMINI.md                       # Aturan Otomatis Tiga Mandat (Antigravity IDE)
|-- .cursorrules                    # Aturan Otomatis Tiga Mandat (Cursor IDE)
|-- .agents/rules/sleep-mcp-auto.md # Aturan Otomatis Workspace Agent
|-- sleep-mcp/
    |-- assets/                     # Banner resmi, logo maskot, dan ikon desktop (.ico)
    |   |-- karjimut_banner.png
    |   |-- karjimut_logo.png
    |   |-- karjimut.ico
    |-- rules_template/             # Template Bootstrap Rules untuk proyek baru
        |-- .cursorrules            # Template aturan otomatis untuk Cursor
        |-- antigravity_rules.md    # Template aturan otomatis untuk Antigravity
```

> **Catatan Distribusi:**
> Seluruh mesin inti Karjimut (*FastMCP Server*, *CustomTkinter Native Desktop GUI*, *SQLite WAL FTS5 + Hybrid Search*, dan *7-Step Sleep Cycle*) didistribusikan secara terkompilasi melalui paket Python di PyPI (`pip install karjimut` atau `uvx karjimut`).

---

## ⚡ Cara Menjalankan (Quick Start)

### 1. Instalasi Instan via Package Manager (Rekomendasi)
```bash
pip install karjimut
```
Atau jalankan langsung tanpa instalasi manual menggunakan **`uvx`**:
```bash
uvx karjimut
```

### 2. Membuka Aplikasi Desktop Native (CustomTkinter)
Cukup ketik perintah berikut di terminal:
```bash
karjimut
```
Aplikasi GUI Karjimut akan langsung terbuka dengan panduan wizard setup API Key otomatis.

### 3. Konfigurasi MCP Server di IDE (Cursor / Antigravity / Claude Desktop)
Cukup tambahkan konfigurasi berikut ke file `mcp_config.json` di IDE Anda:

**Opsi A (Via Perintah Global `karjimut`):**
```json
{
  "mcpServers": {
    "karjimut": {
      "command": "karjimut",
      "args": ["mcp"]
    }
  }
}
```

**Opsi B (Zero-Install via `uvx`):**
```json
{
  "mcpServers": {
    "karjimut": {
      "command": "uvx",
      "args": ["karjimut", "mcp"]
    }
  }
}
```
*(MCP Server dan background Idle Watcher akan otomatis aktif bersamaan).*

---

## 🤖 Tiga Mandat Otomatis (Mode Vibecoder Zero-Prompt)

Dengan memasang file `GEMINI.md` atau `.cursorrules` di root proyek, AI Agent akan menjalankan siklus memori **100% otomatis di balik layar** tanpa perlu diperintah manual oleh pengguna:
1. **Mandat 1 — Inisialisasi Awal Sesi**: Otomatis memanggil `baca_ktp_proyek(kode_proyek, path_workspace)` pada giliran pertama sesi baru (sekaligus mengimpor `.karjimut/team_memory.jsonl` terbaru dari Git).
2. **Mandat 2 — Pencatatan Milestone Otomatis**: Otomatis memanggil `titip_catatan_kerja(kode_proyek, ringkasan_aksi, path_workspace)` setiap selesai membangun fitur atau memperbaiki *bug*.
3. **Mandat 3 — Pencarian Solusi Saat Error**: Otomatis memanggil `cari_laci_solusi(kode_proyek, kata_kunci, path_workspace)` saat menemui *error* terminal sebelum mencoba *trial-and-error*.

---

## 🧪 Verifikasi & Pengujian (26 Automated Unit Tests)

Seluruh komponen diuji menggunakan `pytest` (26 kasus uji: `UT-01` s.d. `UT-26`):
- **`UT-01` s.d. `UT-09`**: SQLite WAL Mode, Trigger FTS5 otomatis, pencarian BM25 dengan simbol `#`/`-`, *Stale Lock Sweeper* ($>180\text{s}$), *Hard-Limit Enforcement*, *1-Step Rollback*, Deduplikasi Jaccard ($\ge 0.5$), *Offline Rule-Based Distiller*, dan konkurensi *multi-thread* bebas `SQLITE_BUSY`.
- **`UT-10` s.d. `UT-21`**: Resolusi `path_workspace`, *rename/merge* proyek dengan `alias_proyek`, proteksi anti-IDOR lintas proyek, *Cross-Process File Lock*, *Auto-Detect API Key* 6 provider, *Self-Healing Model Selector*, lokalisasi ID/EN (`i18n`), dan pencarian hibrida vektor ONNX + BM25 (RRF).
- **`UT-22` s.d. `UT-26` (Fitur Karjimut v2.0)**:
  - `UT-22`: *Elastic Core Mode* (`max_tokens=0`) mempertahankan seluruh aturan proyek besar tanpa pemotongan paksa.
  - `UT-23`: *1-Hop Causal Graph Links* menautkan referensi `[Solusi #ID]` dari KTP Proyek ke Laci Arsip.
  - `UT-24`: *Self-Cleaning Memory* (`supersedes_id`) mendeprekasi solusi usang saat arsitektur diperbarui.
  - `UT-25`: *Multi-Team Git Sync* mengekspor dan mengimpor `.karjimut/team_memory.jsonl` lintas komputer secara idempoten.
  - `UT-26`: *Confidence Score Weighting* memprioritaskan solusi dengan histori keberhasilan tertinggi.

---

## 📄 Lisensi

Hak Cipta © 2026 **Naufal Arhab Fadhil Muhammad**. Dilisensikan di bawah [MIT License](LICENSE).
