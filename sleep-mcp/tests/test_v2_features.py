"""Unit test komprehensif untuk fitur Sleep-MCP v2 (Self-Learning & Hybrid Engine).

Mencakup:
1. Embedding lokal (fastembed + fallback hash, dimensi 384, serialisasi biner).
2. sqlite-vec virtual table insertion & cosine distance query.
3. Hybrid Search (BM25 + sqlite-vec + Reciprocal Rank Fusion RRF).
4. Feedback Loop (nilai_solusi: reward/punishment confidence & hit/miss count).
5. Causal Graph (relasi_solusi: edge SUPERSEDED & deteksi peringatan usang).
6. Memory Decay (peluruhan otomatis solusi idle/tak terpakai).
7. Cross-Project Knowledge Transfer (pencarian fallback berbasis kesamaan stack).
8. Self-Assessment Dashboard (metrik hit rate, success rate, tren evolusi).
"""

from __future__ import annotations

import sqlite3
from typing import Iterator

import pytest

from src.db import init_db, koneksi, transaksi
from src.embedding import (
    DIMENSI_VEKTOR,
    batch_embed,
    bytes_ke_vector,
    generate_embedding,
    simpan_vektor_solusi,
    vector_ke_bytes,
)
from src.fts_search import (
    cari_lintas_proyek,
    cari_solusi_fts_conn,
    cari_vektor_solusi_conn,
    reciprocal_rank_fusion,
)
from src.mcp_server import baca_ktp_proyek, nilai_solusi
from src.services import hitung_self_assessment_proyek, perbarui_solusi, tambah_solusi
from src.consolidator import (
    ekspor_memori_tim,
    impor_memori_tim,
    kompaksi_antrean_lama,
    local_rule_based_distiller,
    perbarui_log_pembelajaran,
    simpan_arsip_deduplikasi,
    terapkan_memory_decay,
)
from src.tokenizer_utils import batasi_kalimat, enforce_hard_limit_ktp, hitung_token, pecah_kalimat


@pytest.fixture
def temp_v2_db(tmp_path) -> Iterator[str]:
    """Fixture database terisolasi untuk suite v2."""
    db_file = tmp_path / "test_sleep_v2.db"
    db_path = str(db_file)
    init_db(db_path)
    yield db_path


# ---------------------------------------------------------------------------
# 1. Test Embedding Generator & Serialisasi Biner
# ---------------------------------------------------------------------------
def test_embedding_generation_and_serialization():
    teks = "koneksi database timeout pada PostgreSQL asyncpg"
    vec = generate_embedding(teks)
    assert len(vec) == DIMENSI_VEKTOR, f"Dimensi embedding wajib {DIMENSI_VEKTOR}"
    assert all(isinstance(x, float) for x in vec)

    # Serialisasi biner struct pack float32
    raw_bytes = vector_ke_bytes(vec)
    assert len(raw_bytes) == DIMENSI_VEKTOR * 4, "Ukuran byte harus 384 * 4 = 1536 byte"

    vec_kembali = bytes_ke_vector(raw_bytes)
    assert len(vec_kembali) == DIMENSI_VEKTOR
    assert pytest.approx(vec[0], abs=1e-5) == vec_kembali[0]

    # Batch embed
    batch = batch_embed(["cors error fastapi", "jwt token expired"])
    assert len(batch) == 2
    assert len(batch[0]) == DIMENSI_VEKTOR
    assert len(batch[1]) == DIMENSI_VEKTOR


# ---------------------------------------------------------------------------
# 2. Test sqlite-vec Insertion & Cosine Distance Search
# ---------------------------------------------------------------------------
def test_sqlite_vec_insertion_and_search(temp_v2_db: str):
    with koneksi(temp_v2_db) as conn:
        with transaksi(conn):
            conn.execute(
                """
                INSERT INTO laci_arsip (id, kode_proyek, tag_masalah, solusi_paten)
                VALUES (1, 'toko-online', '#cors, #fastapi', 'Tambahkan CORSMiddleware dengan allow_origins.'),
                       (2, 'toko-online', '#koneksi-db, #postgres', 'Tingkatkan parameter pool_size pada asyncpg.')
                """
            )
            simpan_vektor_solusi(conn, 1, "#cors, #fastapi", "Tambahkan CORSMiddleware dengan allow_origins.")
            simpan_vektor_solusi(conn, 2, "#koneksi-db, #postgres", "Tingkatkan parameter pool_size pada asyncpg.")

        # Cari dengan semantik semirip mungkin dengan id 1
        hasil_vec = cari_vektor_solusi_conn(conn, "toko-online", "cross origin resource sharing blocked in browser", limit=2)
        assert len(hasil_vec) >= 1
        assert hasil_vec[0]["id"] == 1
        assert hasil_vec[0]["skor_jarak_vektor"] >= 0.0


def test_vector_search_project_isolation(temp_v2_db: str):
    """Memverifikasi tidak ada shadowing/leakage vektor antar proyek berbeda (multi-tenancy)."""
    with koneksi(temp_v2_db) as conn:
        with transaksi(conn):
            # Proyek A memiliki solusi yang sangat dekat dengan query
            conn.execute("INSERT INTO laci_arsip (id, kode_proyek, tag_masalah, solusi_paten) VALUES (101, 'proyek-A', '#jwt', 'Atur secret key JWT yang aman.')")
            simpan_vektor_solusi(conn, 101, "#jwt", "Atur secret key JWT yang aman.")

            # Proyek B memiliki solusi yang mirip tapi milik proyek B
            conn.execute("INSERT INTO laci_arsip (id, kode_proyek, tag_masalah, solusi_paten) VALUES (201, 'proyek-B', '#jwt-auth', 'Validasi token JWT pada header Authorization.')")
            simpan_vektor_solusi(conn, 201, "#jwt-auth", "Validasi token JWT pada header Authorization.")

        # Cari pada proyek B: wajib hanya mengembalikan hasil milik proyek-B
        hasil_b = cari_vektor_solusi_conn(conn, "proyek-B", "jwt secret token", limit=5)
        assert len(hasil_b) == 1
        assert hasil_b[0]["id"] == 201
        assert hasil_b[0]["kode_proyek"] == "proyek-B"


# ---------------------------------------------------------------------------
# 3. Test Hybrid Search (BM25 + Vector + RRF)
# ---------------------------------------------------------------------------
def test_hybrid_search_rrf(temp_v2_db: str):
    with koneksi(temp_v2_db) as conn:
        with transaksi(conn):
            conn.execute(
                """
                INSERT INTO laci_arsip (id, kode_proyek, tag_masalah, solusi_paten, confidence)
                VALUES (10, 'proyek-hybrid', '#alembic, #multiple-heads', 'Jalankan alembic merge heads -m merge.', 0.9),
                       (20, 'proyek-hybrid', '#redis-timeout, #cache', 'Perbesar socket_timeout pada client Redis.', 0.7)
                """
            )
            simpan_vektor_solusi(conn, 10, "#alembic, #multiple-heads", "Jalankan alembic merge heads -m merge.")
            simpan_vektor_solusi(conn, 20, "#redis-timeout, #cache", "Perbesar socket_timeout pada client Redis.")

        # Pencarian dengan sinonim semantik
        hasil = cari_solusi_fts_conn(conn, "proyek-hybrid", "database migration branch conflict heads", limit=2)
        assert len(hasil) >= 1
        assert hasil[0]["id"] == 10
        assert hasil[0].get("skor_rrf") is not None or hasil[0].get("skor_bm25") is not None


# ---------------------------------------------------------------------------
# 4. Test Feedback Loop (nilai_solusi: Reward & Punishment)
# ---------------------------------------------------------------------------
def test_feedback_loop_nilai_solusi(temp_v2_db: str, monkeypatch):
    monkeypatch.setenv("SLEEP_MCP_DB_PATH", temp_v2_db)

    with koneksi(temp_v2_db) as conn:
        with transaksi(conn):
            conn.execute(
                """
                INSERT INTO laci_arsip (id, kode_proyek, tag_masalah, solusi_paten, confidence, hit_count, miss_count)
                VALUES (50, 'app-belajar', '#memory-leak', 'Gunakan weakref pada cyclic object.', 0.70, 0, 0),
                       (51, 'app-belajar', '#cache-ttl', 'Gunakan TTL 300 detik pada Redis.', 0.90, 2, 0)
                """
            )
            perbarui_log_pembelajaran(conn, "app-belajar")

    # 1. Feedback BERHASIL (Reward) pada solusi #50 (0.70 -> 0.80)
    resp_sukses = nilai_solusi(kode_proyek="app-belajar", id_solusi=50, berhasil=True)
    assert "BERHASIL" in resp_sukses
    assert "0.7 -> 0.8" in resp_sukses

    with koneksi(temp_v2_db) as conn:
        row = conn.execute("SELECT confidence, hit_count, miss_count FROM laci_arsip WHERE id = 50").fetchone()
        assert pytest.approx(row["confidence"], 0.01) == 0.80
        assert row["hit_count"] == 1
        assert row["miss_count"] == 0
        eval_1 = hitung_self_assessment_proyek(conn, "app-belajar")
        # Rata-rata proyek: (0.80 + 0.90) / 2 = 0.85 (naik dari awal 0.80 -> tren_positif True)
        assert pytest.approx(eval_1["avg_confidence"], 0.005) == 0.85
        assert eval_1["tren_positif"] is True

    # 2. Feedback GAGAL (Punishment) pada solusi #50 (0.80 -> 0.65)
    resp_gagal = nilai_solusi(kode_proyek="app-belajar", id_solusi=50, berhasil=False)
    assert "GAGAL" in resp_gagal

    with koneksi(temp_v2_db) as conn:
        row2 = conn.execute("SELECT confidence, hit_count, miss_count FROM laci_arsip WHERE id = 50").fetchone()
        assert pytest.approx(row2["confidence"], 0.01) == 0.65
        assert row2["hit_count"] == 1
        assert row2["miss_count"] == 1
        eval_2 = hitung_self_assessment_proyek(conn, "app-belajar")
        # Rata-rata proyek: (0.65 + 0.90) / 2 = 0.775 (turun di bawah awal 0.80 -> tren_positif False)
        assert pytest.approx(eval_2["avg_confidence"], 0.005) == 0.775
        assert eval_2["tren_positif"] is False


# ---------------------------------------------------------------------------
# 5. Test Causal Graph (Relasi SUPERSEDED)
# ---------------------------------------------------------------------------
def test_causal_graph_superseded(temp_v2_db: str):
    with koneksi(temp_v2_db) as conn:
        with transaksi(conn):
            conn.execute(
                """
                INSERT INTO laci_arsip (id, kode_proyek, tag_masalah, solusi_paten)
                VALUES (1, 'graf-proyek', '#jwt-auth', 'Solusi lama: simpan token di localStorage.'),
                       (2, 'graf-proyek', '#jwt-auth, #security', 'Solusi baru: simpan token di HttpOnly cookie.')
                """
            )
            # Catat relasi bahwa solusi #2 me-supersede solusi #1
            conn.execute(
                "INSERT INTO relasi_solusi (source_id, target_id, relasi) VALUES (2, 1, 'SUPERSEDED')"
            )

        hasil = cari_solusi_fts_conn(conn, "graf-proyek", "localStorage token jwt", limit=2)
        assert len(hasil) >= 1
        solusi_lama = next(h for h in hasil if h["id"] == 1)
        assert "telah diperbarui oleh Solusi #2" in solusi_lama["solusi_paten"]
        assert solusi_lama.get("superseded_by") == 2


# ---------------------------------------------------------------------------
# 6. Test Memory Decay
# ---------------------------------------------------------------------------
def test_memory_decay(temp_v2_db: str):
    with koneksi(temp_v2_db) as conn:
        with transaksi(conn):
            # Solusi yang last_hit-nya dibuat 30 hari lalu
            conn.execute(
                """
                INSERT INTO laci_arsip (id, kode_proyek, tag_masalah, solusi_paten, confidence, last_hit)
                VALUES (99, 'decay-proyek', '#old-bug', 'Solusi kuno.', 0.70, datetime('now', '-30 days'))
                """
            )

        decayed = terapkan_memory_decay(conn, "decay-proyek", hari_threshold=14, faktor_decay=0.90)
        assert decayed == 1

        row = conn.execute("SELECT confidence, is_stale FROM laci_arsip WHERE id = 99").fetchone()
        assert row["confidence"] < 0.70


# ---------------------------------------------------------------------------
# 7. Test Cross-Project Knowledge Transfer
# ---------------------------------------------------------------------------
def test_cross_project_search(temp_v2_db: str):
    with koneksi(temp_v2_db) as conn:
        with transaksi(conn):
            # Proyek A: backend-api (punya solusi CORS)
            conn.execute(
                "INSERT INTO ktp_proyek (kode_proyek, ringkasan_inti, jumlah_token) VALUES ('backend-api', 'Stack: FastAPI, Python, PostgreSQL.', 30)"
            )
            conn.execute(
                "INSERT INTO laci_arsip (id, kode_proyek, tag_masalah, solusi_paten) VALUES (101, 'backend-api', '#cors', 'Atur allow_origins=* pada FastAPI middleware.')"
            )

            # Proyek B: mobile-api (stack serupa, belum ada solusi di laci arsip)
            conn.execute(
                "INSERT INTO ktp_proyek (kode_proyek, ringkasan_inti, jumlah_token) VALUES ('mobile-api', 'Stack: FastAPI, Python, Redis.', 30)"
            )

        # Cari di mobile-api untuk kata kunci CORS
        hasil_transfer = cari_solusi_fts_conn(conn, "mobile-api", "#cors", limit=2, cari_eksternal=True)
        assert len(hasil_transfer) >= 1
        assert hasil_transfer[0].get("lintas_proyek") is True
        assert hasil_transfer[0].get("proyek_asal") == "backend-api"
        assert "[Diadopsi dari Proyek 'backend-api']" in hasil_transfer[0]["solusi_paten"]


# ---------------------------------------------------------------------------
# 8. Test Self-Assessment Dashboard Service
# ---------------------------------------------------------------------------
def test_self_assessment_service(temp_v2_db: str):
    with koneksi(temp_v2_db) as conn:
        with transaksi(conn):
            conn.execute(
                """
                INSERT INTO laci_arsip (id, kode_proyek, tag_masalah, solusi_paten, confidence, hit_count, miss_count)
                VALUES (1, 'eval-proyek', '#tag1', 'Solusi 1', 0.90, 5, 1),
                       (2, 'eval-proyek', '#tag2', 'Solusi 2', 0.80, 3, 0)
                """
            )
            perbarui_log_pembelajaran(conn, "eval-proyek")

        metrik = hitung_self_assessment_proyek(conn, "eval-proyek")
        assert metrik["total_solusi"] == 2
        assert metrik["total_hit"] == 8
        assert metrik["total_miss"] == 1
        assert metrik["hit_rate_persen"] == round((8 / 9) * 100.0, 1)
        assert metrik["total_proven"] >= 1
        assert len(metrik["riwayat"]) >= 1


# ---------------------------------------------------------------------------
# 9. Test Elastic Core Mode (Tanpa Pemotongan untuk Proyek Besar)
# ---------------------------------------------------------------------------
def test_elastic_core_ktp_unlimited():
    """Memverifikasi mode Elastic Core (max_tokens=0) mempertahankan 100% aturan & stack proyek besar."""
    log_besar = [
        {
            "isi_log": (
                "Identitas: Platform ERP Multi-Tenant berskala enterprise untuk manufaktur, logistik, dan akuntansi real-time. "
                "Stack: Python, FastAPI, PostgreSQL, Redis, Celery, Docker, Kubernetes, React, TypeScript, Tailwind. "
                "Struktur: src/api/, src/services/, src/models/, src/workers/, migrations/versions/, tests/integration/. "
                "Aturan: (1) Wajib menerapkan Row-Level Security (RLS) PostgreSQL pada setiap tenant_id; "
                "(2) Seluruh mutasi jurnal akuntansi wajib idempotent menggunakan idempotency_key; "
                "(3) Dilarang memanggil layanan pihak ketiga di dalam transaksi database terbuka; "
                "(4) Semua endpoint publik wajib melewati rate limiter berbasis Redis token bucket; "
                "(5) Setiap skema request dan response wajib divalidasi ketat dengan Pydantic v2; "
                "(6) Worker Celery wajib mengaktifkan acks_late=True dan reject_on_worker_lost=True; "
                "(7) Log audit keamanan wajib menyertakan trace_id, actor_id, dan ip_address."
            )
        }
    ]
    hasil = local_rule_based_distiller("erp-enterprise", "", [], log_besar, max_tokens=0)
    ktp_baru = hasil["ktp_proyek_baru"]
    teks_final, jml_token = enforce_hard_limit_ktp(ktp_baru, max_tokens=0)

    assert jml_token > 150, "KTP proyek besar pada mode Elastic Core harus bisa melampaui 150 token tanpa dipotong!"
    assert "Row-Level Security" in teks_final
    assert "idempotency_key" in teks_final
    assert "acks_late=True" in teks_final
    assert "trace_id" in teks_final
    assert "Kubernetes" in teks_final
    assert "migrations/versions/" in teks_final


# ---------------------------------------------------------------------------
# 10. Test Cold-Start Workspace Auto-Scanner & Git-Native Multi-Team Sync
# ---------------------------------------------------------------------------
def test_cold_start_bootstrap_and_git_team_sync(temp_v2_db: str, tmp_path, monkeypatch):
    """Memverifikasi auto-bootstrap dari manifest workspace & sinkronisasi .sleep-mcp/team_memory.json."""
    monkeypatch.setenv("SLEEP_MCP_DB_PATH", temp_v2_db)
    ws_dir = tmp_path / "tim-proyek"
    ws_dir.mkdir(parents=True, exist_ok=True)
    (ws_dir / "pyproject.toml").write_text(
        '[project]\nname = "tim-proyek"\ndescription = "Layanan pembayaran mikro berbasis FastAPI dan Redis"\n'
        'dependencies = ["fastapi", "sqlalchemy", "redis", "pytest"]\n',
        encoding="utf-8",
    )
    (ws_dir / "src").mkdir()
    (ws_dir / "tests").mkdir()

    # 1. Cold-Start: panggil baca_ktp_proyek pada DB kosong -> otomatis memindai manifest workspace
    respons_awal = baca_ktp_proyek("tim-proyek", path_workspace=str(ws_dir))
    assert "Layanan pembayaran mikro" in respons_awal
    assert "FastAPI" in respons_awal
    assert "src/" in respons_awal

    # 2. Tambahkan solusi & aturan dari Anggota Tim A lalu ekspor ke .sleep-mcp/team_memory.json
    with koneksi(temp_v2_db) as conn:
        with transaksi(conn):
            conn.execute(
                """
                UPDATE ktp_proyek
                SET ringkasan_inti = 'Proyek tim-proyek: Layanan pembayaran mikro. Stack: FastAPI, Redis. Aturan: (1) Wajib tanda tangan HMAC-SHA256 pada webhook.'
                WHERE kode_proyek = 'tim-proyek'
                """
            )
            conn.execute(
                """
                INSERT INTO laci_arsip (kode_proyek, tag_masalah, solusi_paten, confidence, is_stale)
                VALUES ('tim-proyek', '#webhook-hmac, #signature', 'Gunakan hmac.compare_digest pada header X-Signature.', 0.85, 0)
                """
            )
            # Ekspor awal dengan path_workspace eksplisit (menginisialisasi .karjimut & .sleep-mcp)
            file_tim_init = ekspor_memori_tim(conn, "tim-proyek", str(ws_dir))
            assert file_tim_init is not None
            # Uji ekspor otomatis berikutnya tanpa parameter path_workspace (mengambil dari peta_workspace.waktu_dibuat)
            file_tim = ekspor_memori_tim(conn, "tim-proyek")
            assert file_tim is not None
            assert (ws_dir / ".karjimut" / "team_memory.json").is_file()
            assert (ws_dir / ".sleep-mcp" / "team_memory.json").is_file()

    # 3. Simulasikan Anggota Tim B dengan DB lokal baru yang melakukan git pull
    db_tim_b = str(tmp_path / "db_tim_b.db")
    init_db(db_tim_b)
    with koneksi(db_tim_b) as conn:
        with transaksi(conn):
            hasil_impor = impor_memori_tim(conn, "tim-proyek", str(ws_dir))
            assert hasil_impor["ktp_merged"] is True
            assert hasil_impor["solusi_baru"] == 1
        hasil_cari = cari_solusi_fts_conn(conn, "tim-proyek", "#webhook-hmac", limit=2)
        assert len(hasil_cari) == 1
        assert "compare_digest" in hasil_cari[0]["solusi_paten"]
        assert pytest.approx(float(hasil_cari[0]["confidence"]), 0.01) == 0.85


# ---------------------------------------------------------------------------
# 11. Test Hot-Buffer Search Fallback (Antrean Mentah Belum Dirangkum)
# ---------------------------------------------------------------------------
def test_hot_buffer_search_fallback(temp_v2_db: str):
    """Memverifikasi solusi yang baru masuk antrean_mentah (status=0) langsung ditemukan sebelum Sleep Cycle."""
    with koneksi(temp_v2_db) as conn:
        with transaksi(conn):
            conn.execute(
                """
                INSERT INTO antrean_mentah (kode_proyek, isi_log, estimasi_token_mentah, status_rangkum)
                VALUES ('proyek-cepat', 'Solusi: Atasi error sqlite terkunci dengan PRAGMA busy_timeout=5000 #sqlite-terkunci #busy-timeout', 25, 0)
                """
            )

        hasil = cari_solusi_fts_conn(conn, "proyek-cepat", "sqlite database locked busy_timeout", limit=2)
        assert len(hasil) == 1
        assert hasil[0]["metode"] == "HOT_BUFFER"
        assert "busy_timeout=5000" in hasil[0]["solusi_paten"]


# ---------------------------------------------------------------------------
# 12. Test Self-Cleaning Memory: Rule Unlearning, Auto-Supersede, & Compaction
# ---------------------------------------------------------------------------
def test_self_cleaning_unlearning_and_auto_supersede(temp_v2_db: str):
    """Memverifikasi pencabutan aturan usang, migrasi stack, auto-supersede solusi gagal, & kompaksi log."""
    ktp_lama = (
        "Proyek app-evolusi: Sistem backend transaksi. "
        "Stack: Python, Flask, SQLite. "
        "Aturan: (1) Semua endpoint wajib memakai Basic Auth; (2) Wajib format respons JSON standar."
    )
    log_evolusi = [
        {
            "isi_log": (
                "Migrasi dari Flask ke FastAPI untuk performa async. "
                "Hapus aturan: Semua endpoint wajib memakai Basic Auth. "
                "Aturan: Semua endpoint wajib memakai OAuth2 Bearer JWT."
            )
        }
    ]
    distilat = local_rule_based_distiller("app-evolusi", ktp_lama, [], log_evolusi, max_tokens=0)
    ktp_baru = distilat["ktp_proyek_baru"]
    assert "FastAPI" in ktp_baru
    assert "Flask" not in ktp_baru
    assert "Basic Auth" not in ktp_baru
    assert "OAuth2 Bearer JWT" in ktp_baru
    assert "format respons JSON standar" in ktp_baru

    # Uji Auto-Supersede pada solusi yang gagal (confidence < 0.45)
    with koneksi(temp_v2_db) as conn:
        with transaksi(conn):
            conn.execute(
                """
                INSERT INTO laci_arsip (id, kode_proyek, tag_masalah, solusi_paten, confidence, is_stale)
                VALUES (77, 'app-evolusi', '#koneksi-db, #timeout', 'Solusi lama gagal: matikan pool.', 0.30, 1)
                """
            )
            res = simpan_arsip_deduplikasi(
                conn,
                "app-evolusi",
                {
                    "id_arsip_target": None,
                    "tag_masalah": "#koneksi-db, #timeout",
                    "solusi_paten": "Aktifkan pool_pre_ping=True dan pool_recycle=1800 pada SQLAlchemy engine.",
                },
            )
            assert res["aksi"] == "INSERT"
            assert res["supersedes_id"] == 77
            assert "matikan pool" not in res["solusi_paten"]

            # Pastikan relasi SUPERSEDED tercatat otomatis
            rel = conn.execute(
                "SELECT source_id, target_id FROM relasi_solusi WHERE target_id = 77 AND relasi = 'SUPERSEDED'"
            ).fetchone()
            assert rel is not None
            assert int(rel["source_id"]) == int(res["id"])

            # Uji kompaksi antrean_mentah lama
            for i in range(6):
                conn.execute(
                    "INSERT INTO antrean_mentah (kode_proyek, isi_log, estimasi_token_mentah, status_rangkum) VALUES ('app-evolusi', ?, 40, 2)",
                    (f"Log lama ke-{i}",),
                )
            terkompaksi = kompaksi_antrean_lama(conn, "app-evolusi", max_processed_rows=2)
            assert terkompaksi == 4
            total_tok = conn.execute(
                "SELECT SUM(estimasi_token_mentah) FROM antrean_mentah WHERE kode_proyek = 'app-evolusi'"
            ).fetchone()[0]
            assert total_tok == 240  # Estimasi token historis tetap utuh 100%


# ---------------------------------------------------------------------------
# 13. Test Bilingual Synonym Search (ID <-> EN) & Code-Safe Sentence Splitter
# ---------------------------------------------------------------------------
def test_bilingual_synonym_search_and_code_safe_splitter(temp_v2_db: str):
    """Memverifikasi ekspansi sinonim ID <-> EN serta pemecah kalimat yang aman terhadap backtick/file."""
    teks_kode = (
        "Jalankan perintah `python run.py --transport stdio` pada file `src/config.py` v2.0. "
        "Pastikan variabel lingkungan `.env` sudah dimuat dengan benar."
    )
    kalimat = pecah_kalimat(teks_kode)
    assert len(kalimat) == 2
    assert "`python run.py --transport stdio`" in kalimat[0]
    assert "`src/config.py`" in kalimat[0]
    assert batasi_kalimat(teks_kode, 1) == "Jalankan perintah `python run.py --transport stdio` pada file `src/config.py` v2.0."

    with koneksi(temp_v2_db) as conn:
        with transaksi(conn):
            conn.execute(
                """
                INSERT INTO laci_arsip (id, kode_proyek, tag_masalah, solusi_paten)
                VALUES (301, 'bilingual-app', '#koneksi-db, #terkunci', 'Aktifkan mode WAL pada SQLite untuk mencegah database terkunci.')
                """
            )
        # Query dalam bahasa Inggris harus menemukan tag/solusi berbahasa Indonesia
        hasil = cari_solusi_fts_conn(conn, "bilingual-app", "database connection locked", limit=2)
        assert len(hasil) == 1
        assert hasil[0]["id"] == 301


# ---------------------------------------------------------------------------
# 14. Test Zero-Setup Auto-Injector MCP Config
# ---------------------------------------------------------------------------
def test_zero_setup_auto_injector_mcp_config(tmp_path):
    """Memverifikasi injeksi otomatis konfigurasi MCP JSON secara aman tanpa merusak server lain."""
    import json
    from src.run import _get_mcp_server_config, _inject_mcp_into_json

    cfg_file = tmp_path / "mock_ide_config.json"
    server_cfg = _get_mcp_server_config()
    assert "command" in server_cfg
    assert "args" in server_cfg

    # Injeksi ke file baru
    sukses = _inject_mcp_into_json(cfg_file, server_cfg)
    assert sukses is True
    assert cfg_file.exists()

    data = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert "mcpServers" in data
    assert "karjimut" in data["mcpServers"]
    assert data["mcpServers"]["karjimut"]["command"] == server_cfg["command"]

    # Injeksi kedua dengan server lain yang sudah ada sebelumnya
    data["mcpServers"]["existing_tool"] = {"command": "node", "args": ["index.js"]}
    cfg_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    sukses_2 = _inject_mcp_into_json(cfg_file, server_cfg)
    assert sukses_2 is True
    data_2 = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert "karjimut" in data_2["mcpServers"]
    assert "existing_tool" in data_2["mcpServers"]
    assert data_2["mcpServers"]["existing_tool"]["command"] == "node"

