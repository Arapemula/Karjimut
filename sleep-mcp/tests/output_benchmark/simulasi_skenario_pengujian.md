# LAPORAN BENCHMARK EMPIRIS SISTEM KARJIMUT

**Sistem:**
*Karjimut: Two-Tier Memory Architecture with Idle Consolidation and Elastic Core*

- **Waktu Pengukuran:** 2026-11-08 16:23:16
- **Tokenizer Aktual:** `tiktoken/cl100k_base` (Tanpa angka estimasi manual)
- **Database Engine:** SQLite 3 WAL Mode + FTS5 BM25 + `sqlite-vec` Hybrid RRF

---

## 1. Skenario 1: Pengukuran Empiris Efisiensi Token & Overhead Sistem (40 Langkah / 5 Sesi)

| Sesi   | Langkah | Baseline A (Kumulatif) | Baseline B (Fresh) | Aktif MCP | Sleep Overhead | Static Overhead | Net Savings (Full) | Status BEP             |
| ------ | ------- | ---------------------- | ------------------ | --------- | -------------- | --------------- | ------------------ | ---------------------- |
| Sesi 1 | 1-8     | 2,057                  | 2,057              | 468       | 1,105          | 486             | -2                 | Investasi Awal         |
| Sesi 2 | 9-16    | 3,819                  | 1,958              | 531       | 1,193          | 486             | 1,607              | BEP Tercapai (Surplus) |
| Sesi 3 | 17-24   | 5,602                  | 2,515              | 677       | 1,277          | 486             | 4,769              | BEP Tercapai (Surplus) |
| Sesi 4 | 25-32   | 7,237                  | 2,235              | 693       | 1,394          | 486             | 9,433              | BEP Tercapai (Surplus) |
| Sesi 5 | 33-40   | 8,723                  | 2,106              | 646       | 1,325          | 486             | 15,699             | BEP Tercapai (Surplus) |

### Analisis Kuantitatif Skenario 1:
1. **Perhitungan Token Murni (`tiktoken`):** Seluruh langkah kerja dihitung langsung dari teks interaksi mentah menggunakan `hitung_token()` tanpa nilai estimasi manual.
2. **Transparansi Static System Overhead:**
   - File Aturan Otomatis (`antigravity_rules.md` / `.cursorrules`): **304 token** (1x pasang, bebas duplikasi).
   - Skema 4 Tool MCP Inti (`baca_ktp_proyek`, `titip_catatan_kerja`, `cari_laci_solusi`, `nilai_solusi`): **182 token**.
   - Total Static Overhead per Sesi: **486 token**.
3. **Efisiensi Context Window Aktif:** Rata-rata mencapai **86.86%** terhadap Baseline A (Full Transcript) dan menghemat **1,562 token** terhadap Baseline B (Fresh Session + Cold Re-Orientation & Recurring Bug Retry).
4. **Net Token Savings (Termasuk Sleep + Static Overhead):** Penghematan bersih mencapai **15,699 token (57.22%)** setelah dikurangi seluruh biaya konsolidasi idle dan biaya skema MCP/aturan.

---

## 2. Skenario 2: Pengujian Retensi Aturan, Unlearning, & Ketahanan Noise ($N=10$ Aturan + 6 Noise)

| No | Aturan Arsitektur                                                                         | Kata Kunci Verifikasi                                 | Status di Sesi 3            |
| -- | ----------------------------------------------------------------------------------------- | ----------------------------------------------------- | --------------------------- |
| 1  | Wajib menggunakan connection pool PostgreSQL dengan library asyncpg.                      | 'asyncpg' / 'connection pool'                         | TERPATUHI (Retained)        |
| 2  | Dilarang menggunakan raw SQL query tanpa parameterized binding untuk cegah SQL injection. | 'parameterized' / 'sql injection'                     | TERPATUHI (Retained)        |
| 3  | Wajib validasi seluruh skema request dan response menggunakan Pydantic v2.                | 'pydantic' / 'skema'                                  | TERPATUHI (Retained)        |
| 4  | Endpoint API wajib menerapkan rate limiting maksimal 100 request per menit.               | 'rate limit' / '100'                                  | TERPATUHI (Retained)        |
| 5  | Wajib menyertakan header correlation-id pada setiap logging format JSON.                  | 'correlation-id' / 'json'                             | TERPATUHI (Retained)        |
| 6  | Transaksi mutasi saldo wajib bersifat idempotent menggunakan header Idempotency-Key.      | 'idempotent' / 'idempotency-key'                      | TERPATUHI (Retained)        |
| 7  | Dilarang memanggil HTTP API pihak ketiga di dalam blok transaksi database terbuka.        | 'pihak ketiga' / 'transaksi database'                 | TERPATUHI (Retained)        |
| 8  | Worker Celery wajib mengaktifkan acks_late=True pada antrean pembayaran.                  | 'acks_late' / 'celery'                                | TERPATUHI (Retained)        |
| 9  | Semua endpoint wajib memakai OAuth2 Bearer JWT dengan rotasi refresh token.               | 'oauth2' / 'bearer jwt'                               | TERPATUHI (Retained)        |
| 10 | Semua endpoint wajib memakai Basic Auth untuk autentikasi internal.                       | 'basic auth' / 'autentikasi internal' (Wajib Dicabut) | TERHAPUS BERSIH (Unlearned) |

### Analisis Kuantitatif Skenario 2:
1. **Rule Retention & Unlearning Accuracy:** **100.0% (10/10)** — seluruh 9 aturan aktif dipertahankan dan 1 aturan usang (`Basic Auth`) berhasil dicabut (*unlearned*).
2. **Noise Rejection Rate (Filter Changelog/Milestone):** **100.0%** — catatan rilis versi, pembersihan workspace, dan status unit test tidak mengotori bagian `Aturan:` pada KTP Proyek.
3. **Evaluasi Ukuran Token KTP (Mode Elastic vs Mode Bounded):**
   - Mode Default **Elastic Core (`KTP_MAX_TOKENS=0` + `MAX_ATURAN_KTP=12`)**: Sesi 1 = `157 token`, Sesi 2 = `239 token`, Sesi 3 = `239 token`.
   - Mode Opsional **Hard-Limit Bounded (`KTP_MAX_TOKENS=150`)**: `139 token` ($\le 150$ token: **True**).

---

## 3. Skenario 3: Pengukuran Latensi Riil (`perf_counter`) & Akurasi Hybrid Search ($N=25$ Query)

| No | Kasus Uji Query                          | Linear Scan (Aktual) | Karjimut Hybrid (Aktual) | Rasio Latensi | Hasil Retrieval | Metode    |
| -- | ---------------------------------------- | -------------------- | ------------------------ | ------------- | --------------- | --------- |
| 1  | CORS Origin Blocked (Trace EN)           | 309.94 ms            | 147.79 ms                | 2.10x         | VALID (Top-1)   | FTS5_BM25 |
| 2  | Database Pool Timeout (Trace EN)         | 190.49 ms            | 85.11 ms                 | 2.24x         | VALID (Top-1)   | FTS5_BM25 |
| 3  | JWT Token Expired (Trace EN)             | 178.93 ms            | 59.68 ms                 | 3.00x         | VALID (Top-1)   | FTS5_BM25 |
| 4  | Alembic Multiple Heads (Trace EN)        | 152.89 ms            | 54.90 ms                 | 2.79x         | VALID (Top-1)   | FTS5_BM25 |
| 5  | Redis Connection Refused (Trace EN)      | 137.31 ms            | 91.70 ms                 | 1.50x         | VALID (Top-1)   | FTS5_BM25 |
| 6  | CORS Preflight Header (Bilingual ID)     | 128.77 ms            | 91.70 ms                 | 1.40x         | VALID (Top-1)   | FTS5_BM25 |
| 7  | Koneksi Database Terkunci (Bilingual ID) | 119.17 ms            | 94.17 ms                 | 1.27x         | VALID (Top-1)   | FTS5_BM25 |
| 8  | Sesi Login Kedaluwarsa (Bilingual ID)    | 135.38 ms            | 71.71 ms                 | 1.89x         | VALID (Top-1)   | FTS5_BM25 |
| 9  | Konflik Cabang Migrasi (Bilingual ID)    | 115.98 ms            | 61.83 ms                 | 1.88x         | VALID (Top-1)   | FTS5_BM25 |
| 10 | Port Redis Ditolak (Bilingual ID)        | 133.75 ms            | 56.25 ms                 | 2.38x         | VALID (Top-1)   | FTS5_BM25 |
| 11 | CORS Tag Lookup                          | 20.66 ms             | 30.39 ms                 | 0.68x         | VALID (Top-1)   | FTS5_BM25 |
| 12 | DB Pool Tag Lookup                       | 21.11 ms             | 36.95 ms                 | 0.57x         | VALID (Top-1)   | FTS5_BM25 |
| 13 | JWT Auth Tag Lookup                      | 23.13 ms             | 52.09 ms                 | 0.44x         | VALID (Top-1)   | FTS5_BM25 |
| 14 | Alembic Tag Lookup                       | 22.78 ms             | 50.07 ms                 | 0.46x         | VALID (Top-1)   | FTS5_BM25 |
| 15 | Redis Tag Lookup                         | 36.81 ms             | 31.56 ms                 | 1.17x         | VALID (Top-1)   | FTS5_BM25 |

### Analisis Kuantitatif Skenario 3:
1. **Akurasi Retrieval pada $N=15$ Query Positif (ID & EN):**
   - **Precision@1 (Top-1 Accuracy):** **100.0%**
   - **Recall@3 (Top-3 Accuracy):** **100.0% (15/15)**
   - **Mean Reciprocal Rank (MRR):** **1.0**
2. **Ketahanan Terhadap False Positive pada $N=10$ Query Negatif & Lintas Proyek:**
   - **Out-of-Domain Rejection Rate (True Negative Rate):** **100.0% (10/10 ditolak tepat, termasuk query `"ruff No module named ruff"`)**
   - **False Positive Rate (FPR):** **0.0%**
3. **Deduplikasi Deterministik Laci Arsip:** Terbukti **0 duplikasi baris** (tetap `5` baris solusi master pada proyek uji).
