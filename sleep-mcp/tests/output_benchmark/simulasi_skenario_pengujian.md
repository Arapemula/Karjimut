# LAPORAN SIMULASI BENCHMARK SISTEM KARJIMUT

**Sistem:**
*Karjimut: Two-Tier Memory Architecture with Idle Consolidation and Elastic Core*

- **Waktu Simulasi:** 2026-11-05 18:17:40
- **Tokenizer:** tiktoken/cl100k_base
- **Database Engine:** SQLite 3 WAL Mode with FTS5 BM25

---

## 1. Skenario 1: Pengujian Efisiensi Token (40 Langkah / 5 Sesi)

| Sesi   | Langkah | Baseline (Token) | Aktif MCP | Efisiensi Aktif | Overhead Sleep | Net Savings (Tokens) | Net Savings (%) | Status BEP             |
| ------ | ------- | ---------------- | --------- | --------------- | -------------- | -------------------- | --------------- | ---------------------- |
| Sesi 1 | 1-8     | 1,115            | 465       | 58.3%           | 998            | -348                 | -31.21%         | Investasi Awal         |
| Sesi 2 | 9-16    | 2,395            | 482       | 79.87%          | 1,035          | 530                  | 15.1%           | BEP Tercapai (Surplus) |
| Sesi 3 | 17-24   | 3,655            | 490       | 86.59%          | 1,065          | 2,630                | 36.71%          | BEP Tercapai (Surplus) |
| Sesi 4 | 25-32   | 5,075            | 483       | 90.48%          | 1,076          | 6,146                | 50.21%          | BEP Tercapai (Surplus) |
| Sesi 5 | 33-40   | 6,400            | 493       | 92.3%           | 1,129          | 10,924               | 58.61%          | BEP Tercapai (Surplus) |

### Indikator Target Skenario 1:
1. **Efisiensi Context Window Aktif (Metrik A):** Rata-rata mencapai **81.51%** (Target Evaluasi: > 60%).
2. **Efisiensi Token Total Sistem (Net Token Savings - Metrik B):** Penghematan bersih mencapai **10,924 token (58.61%)**.
3. **Break-Even Point (BEP):** Titik impas tercapai sejak **Sesi 2** di mana total token yang dihemat telah melampaui biaya komputasi konsolidasi fase idle (*Sleep Consolidation Overhead*).

---

## 2. Skenario 2: Pengujian Konsistensi Konteks & Kepatuhan Mandat

| No | Aturan Arsitektur                                                                         | Kata Kunci Verifikasi             | Status Retensi di Sesi 3  |
| -- | ----------------------------------------------------------------------------------------- | --------------------------------- | ------------------------- |
| 1  | Wajib menggunakan connection pool PostgreSQL dengan library asyncpg.                      | 'asyncpg' / 'connection pool'     | TERPATUHI (100% Retained) |
| 2  | Dilarang menggunakan raw SQL query tanpa parameterized binding untuk cegah SQL injection. | 'parameterized' / 'sql injection' | TERPATUHI (100% Retained) |
| 3  | Wajib validasi seluruh skema request dan response menggunakan Pydantic v2.                | 'pydantic' / 'skema'              | TERPATUHI (100% Retained) |
| 4  | Endpoint API wajib menerapkan rate limiting maksimal 100 request per menit.               | 'rate limit' / '100'              | TERPATUHI (100% Retained) |
| 5  | Wajib menyertakan header correlation-id pada setiap logging format JSON.                  | 'correlation-id' / 'json'         | TERPATUHI (100% Retained) |

### Indikator Target Skenario 2:
1. **Rule Retention Rate:** **100.0% (5/5 aturan dipertahankan)** setelah melewati 2 siklus konsolidasi tidur tanpa menyebutkan ulang aturan tersebut pada sesi ke-3.
2. **Hard-Limit Token KTP Proyek:**
   - Sesi 1: `115 token` (<= 150)
   - Sesi 2: `122 token` (<= 150)
   - Sesi 3: `122 token` (<= 150)
   - Status: **Mematuhi batas keras <= 150 token**.

---

## 3. Skenario 3: Pengujian Kecepatan Solusi & Akurasi FTS5 BM25

| No | Nama Bug / Error         | Baseline Retry | Baseline Waktu | Sleep-MCP Steps   | Sleep-MCP Waktu | Speedup | Top-3 BM25 Match |
| -- | ------------------------ | -------------- | -------------- | ----------------- | --------------- | ------- | ---------------- |
| 1  | CORS Origin Blocked      | 4 steps        | 42.5s          | 1 step (One-Shot) | 0.2123s         | 200.2x  | VALID (Top-1)    |
| 2  | Database Pool Timeout    | 5 steps        | 58.0s          | 1 step (One-Shot) | 0.0459s         | 1263.6x | VALID (Top-1)    |
| 3  | JWT Token Expired        | 3 steps        | 31.0s          | 1 step (One-Shot) | 0.0333s         | 930.9x  | VALID (Top-1)    |
| 4  | Alembic Multiple Heads   | 4 steps        | 45.0s          | 1 step (One-Shot) | 0.0365s         | 1232.9x | VALID (Top-1)    |
| 5  | Redis Connection Refused | 3 steps        | 28.5s          | 1 step (One-Shot) | 0.0439s         | 649.2x  | VALID (Top-1)    |

### Indikator Target Skenario 3:
1. **One-Shot Resolution:** AI Agent Sleep-MCP menyelesaikan bug dalam **1 langkah langsung** (0 retry steps) dibandingkan AI Agent standar yang membutuhkan rata-rata **3.8 langkah trial-and-error**.
2. **Akurasi Top-3 BM25:** Mencapai **100.0%** di mana seluruh solusi paten berhasil di-retrieve secara tepat pada peringkat teratas meskipun kalimat query error pengguna bervariasi.
3. **Deduplikasi Laci Arsip:** Terbukti **0 duplikasi baris** (seluruh entri tersimpan dalam 5 baris master melalui deduplikasi deterministik ID Target & Jaccard similarity).
