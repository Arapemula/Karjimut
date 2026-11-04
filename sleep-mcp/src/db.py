"""Lapisan akses database SQLite Sleep-MCP.

* Setiap koneksi WAJIB menjalankan PRAGMA WAL, synchronous NORMAL,
  busy_timeout 5000 ms, dan foreign_keys ON karena file database diakses
  bersamaan oleh beberapa proses: MCP Server (+Idle Watcher) dan aplikasi Desktop GUI.
* Koneksi dibuka dalam mode autocommit (``isolation_level=None``) sehingga
  transaksi dikendalikan secara eksplisit melalui :func:`transaksi`
  (``BEGIN IMMEDIATE`` untuk operasi tulis yang harus atomik).
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import JENIS_AKTIVITAS_VALID, get_settings, setup_logging

logger = setup_logging("sleep_mcp.db")

try:
    import sqlite_vec
    _HAVE_SQLITE_VEC = True
except ImportError:
    sqlite_vec = None
    _HAVE_SQLITE_VEC = False

PRAGMA_KONEKSI: tuple[str, ...] = (
    "PRAGMA journal_mode=WAL;",
    "PRAGMA synchronous=NORMAL;",
    "PRAGMA busy_timeout=5000;",
    "PRAGMA foreign_keys=ON;",
)

# Setelah journal_mode=WAL terinisialisasi pada header file DB, koneksi berikutnya
# cukup mengeksekusi PRAGMA sesi ringan tanpa memicu lock penulisan header WAL ulang.
PRAGMA_SESI_CEPAT: tuple[str, ...] = (
    "PRAGMA synchronous=NORMAL;",
    "PRAGMA busy_timeout=5000;",
    "PRAGMA foreign_keys=ON;",
)

DDL_TABEL: tuple[str, ...] = (
    # 1. Antrean log mentah (state machine konsolidasi)
    """
    CREATE TABLE IF NOT EXISTS antrean_mentah (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kode_proyek TEXT NOT NULL,
        isi_log TEXT NOT NULL,
        estimasi_token_mentah INTEGER NOT NULL DEFAULT 0,
        waktu_masuk TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        waktu_kunci TIMESTAMP NULL,
        status_rangkum INTEGER NOT NULL DEFAULT 0
        -- status_rangkum: 0 = pending, 1 = processing, 2 = processed
    );
    """,
    # 2. Lapis 1 - KTP Proyek (Core Project Identity)
    """
    CREATE TABLE IF NOT EXISTS ktp_proyek (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kode_proyek TEXT NOT NULL UNIQUE,
        ringkasan_inti TEXT NOT NULL,
        ringkasan_sebelumnya TEXT NULL,
        jumlah_token INTEGER NOT NULL,
        versi_ktp INTEGER NOT NULL DEFAULT 1,
        waktu_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    # 3. Lapis 2 - Laci Arsip Solusi (On-Demand Solution Vault) dengan Learning State
    """
    CREATE TABLE IF NOT EXISTS laci_arsip (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kode_proyek TEXT NOT NULL,
        tag_masalah TEXT NOT NULL,
        solusi_paten TEXT NOT NULL,
        confidence REAL NOT NULL DEFAULT 0.7,
        hit_count INTEGER NOT NULL DEFAULT 0,
        miss_count INTEGER NOT NULL DEFAULT 0,
        last_hit TIMESTAMP NULL,
        is_stale INTEGER NOT NULL DEFAULT 0,
        waktu_dibuat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    # 4. Tabel virtual FTS5 (external content) dengan dukungan karakter # dan -
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS laci_arsip_fts USING fts5(
        kode_proyek,
        tag_masalah,
        solusi_paten,
        content='laci_arsip',
        content_rowid='id',
        tokenize="unicode61 tokenchars '#-'"
    );
    """,
    # 5. Audit metrik token (Dual Sustainability Card & Skenario Pengujian)
    """
    CREATE TABLE IF NOT EXISTS log_metrik_token (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kode_proyek TEXT NOT NULL,
        jenis_aktivitas TEXT NOT NULL,
        -- 'TOOL_READ_KTP', 'TOOL_WRITE_LOG', 'TOOL_SEARCH_SOLUSI', 'SLEEP_CONSOLIDATION'
        token_mentah_setara INTEGER NOT NULL DEFAULT 0,
        token_aktual_terpakai INTEGER NOT NULL DEFAULT 0,
        waktu_catat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    # 6. Alias proyek: nama lama (mis. folder yang di-rename) -> kode proyek kanonik
    """
    CREATE TABLE IF NOT EXISTS alias_proyek (
        alias TEXT PRIMARY KEY,
        kode_proyek TEXT NOT NULL,
        waktu_dibuat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    # 7. Peta workspace: hash path folder -> kode proyek (mencegah tabrakan nama folder)
    """
    CREATE TABLE IF NOT EXISTS peta_workspace (
        path_hash TEXT PRIMARY KEY,
        path_workspace TEXT NOT NULL,
        kode_proyek TEXT NOT NULL,
        waktu_dibuat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    # 8. Relasi kausal dan supersesi antar solusi (Causal Graph Edges)
    """
    CREATE TABLE IF NOT EXISTS relasi_solusi (
        source_id INTEGER NOT NULL,
        target_id INTEGER NOT NULL,
        relasi TEXT CHECK(relasi IN ('CAUSED_BY', 'SUPPORTS', 'SUPERSEDED')) NOT NULL,
        weight REAL DEFAULT 1.0,
        waktu_dibuat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (source_id, target_id, relasi),
        FOREIGN KEY (source_id) REFERENCES laci_arsip(id) ON DELETE CASCADE,
        FOREIGN KEY (target_id) REFERENCES laci_arsip(id) ON DELETE CASCADE
    );
    """,
    # 9. Audit metrik pembelajaran dan evaluasi berkala (Self-Assessment)
    """
    CREATE TABLE IF NOT EXISTS log_pembelajaran (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kode_proyek TEXT NOT NULL,
        total_pencarian INTEGER DEFAULT 0,
        total_hit INTEGER DEFAULT 0,
        total_sukses INTEGER DEFAULT 0,
        total_gagal INTEGER DEFAULT 0,
        confidence_rata2 REAL DEFAULT 0.0,
        waktu_catat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
)

DDL_TRIGGER: tuple[str, ...] = (
    """
    CREATE TRIGGER IF NOT EXISTS laci_arsip_ai AFTER INSERT ON laci_arsip BEGIN
        INSERT INTO laci_arsip_fts(rowid, kode_proyek, tag_masalah, solusi_paten)
        VALUES (new.id, new.kode_proyek, new.tag_masalah, new.solusi_paten);
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS laci_arsip_ad AFTER DELETE ON laci_arsip BEGIN
        INSERT INTO laci_arsip_fts(laci_arsip_fts, rowid, kode_proyek, tag_masalah, solusi_paten)
        VALUES ('delete', old.id, old.kode_proyek, old.tag_masalah, old.solusi_paten);
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS laci_arsip_au AFTER UPDATE ON laci_arsip BEGIN
        INSERT INTO laci_arsip_fts(laci_arsip_fts, rowid, kode_proyek, tag_masalah, solusi_paten)
        VALUES ('delete', old.id, old.kode_proyek, old.tag_masalah, old.solusi_paten);
        INSERT INTO laci_arsip_fts(rowid, kode_proyek, tag_masalah, solusi_paten)
        VALUES (new.id, new.kode_proyek, new.tag_masalah, new.solusi_paten);
    END;
    """,
)

DDL_INDEKS: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_antrean_proyek_status ON antrean_mentah(kode_proyek, status_rangkum);",
    "CREATE INDEX IF NOT EXISTS idx_antrean_status_kunci ON antrean_mentah(status_rangkum, waktu_kunci);",
    "CREATE INDEX IF NOT EXISTS idx_laci_proyek ON laci_arsip(kode_proyek);",
    "CREATE INDEX IF NOT EXISTS idx_laci_proyek_confidence ON laci_arsip(kode_proyek, confidence);",
    "CREATE INDEX IF NOT EXISTS idx_metrik_proyek_jenis ON log_metrik_token(kode_proyek, jenis_aktivitas);",
    "CREATE INDEX IF NOT EXISTS idx_relasi_target ON relasi_solusi(target_id, relasi);",
    "CREATE INDEX IF NOT EXISTS idx_relasi_source ON relasi_solusi(source_id, relasi);",
    "CREATE INDEX IF NOT EXISTS idx_log_pembelajaran_proyek ON log_pembelajaran(kode_proyek);",
)

_init_lock = threading.Lock()
_initialized_paths: set[str] = set()

_KODE_PROYEK_INVALID = re.compile(r"[^a-z0-9_.\-]+")


def normalisasi_kode_proyek(kode_proyek: str) -> str:
    """Menyeragamkan kode proyek (slug lowercase) agar konsisten lintas agent.

    Contoh: ``"  Toko Online "`` -> ``"toko-online"``.
    """
    if kode_proyek is None:
        raise ValueError("kode_proyek wajib diisi.")
    slug = str(kode_proyek).strip().lower().replace(" ", "-")
    slug = _KODE_PROYEK_INVALID.sub("-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    if not slug:
        raise ValueError("kode_proyek tidak boleh kosong.")
    return slug[:100]


def hash_path_workspace(path_workspace: str) -> str:
    """Hash stabil (16 hex) dari path folder workspace (case-insensitive di Windows)."""
    norm = os.path.normcase(os.path.normpath(str(path_workspace).strip())).replace("\\", "/").rstrip("/")
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]


def _ikuti_alias(conn: sqlite3.Connection, kode: str) -> str:
    """Mengikuti rantai alias (maks. 5 lompatan) menuju kode proyek kanonik."""
    for _ in range(5):
        row = conn.execute("SELECT kode_proyek FROM alias_proyek WHERE alias = ?", (kode,)).fetchone()
        if row is None or row["kode_proyek"] == kode:
            break
        kode = row["kode_proyek"]
    return kode


def resolve_proyek(
    conn: sqlite3.Connection, kode_proyek: str, path_workspace: str | None = None
) -> str:
    """Menentukan kode proyek kanonik dari nama folder (+ path workspace opsional).

    * Alias (hasil rename/gabung di GUI) selalu diikuti.
    * Jika ``path_workspace`` diberikan dan sudah terdaftar -> memakai kode yang tersimpan.
    * Jika nama yang sama sudah dipakai folder LAIN yang masih ada di disk ->
      terjadi tabrakan nama, kode diberi sufiks hash path (``nama-ab12cd``).
    * Jika folder lama sudah tidak ada (dipindah/di-rename) -> memori proyek dipakai ulang.
    """
    kode = _ikuti_alias(conn, normalisasi_kode_proyek(kode_proyek))
    path = (path_workspace or "").replace("\x00", "").strip()
    if not path:
        return kode
    h = hash_path_workspace(path)
    row = conn.execute("SELECT kode_proyek FROM peta_workspace WHERE path_hash = ?", (h,)).fetchone()
    if row is not None:
        return _ikuti_alias(conn, row["kode_proyek"])
    pemakai = conn.execute(
        "SELECT path_workspace FROM peta_workspace WHERE kode_proyek = ? AND path_hash <> ?", (kode, h)
    ).fetchall()
    if pemakai:
        ada_lama = any(Path(p["path_workspace"]).exists() for p in pemakai)
        ada_baru = Path(path).exists()
        if ada_lama or not ada_baru:
            kode = f"{kode[:90]}-{h[:6]}"
    conn.execute(
        "INSERT OR IGNORE INTO peta_workspace (path_hash, path_workspace, kode_proyek) VALUES (?, ?, ?)",
        (h, path, kode),
    )
    return kode


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Membuka koneksi SQLite dengan PRAGMA konkurensi wajib dan memuat sqlite-vec."""
    path = db_path or get_settings().db_path
    sudah_init = path in _initialized_paths and path != ":memory:"
    if path != ":memory:" and not sudah_init:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        path,
        timeout=5.0,
        isolation_level=None,  # autocommit; transaksi eksplisit via transaksi()
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    if _HAVE_SQLITE_VEC:
        try:
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
        except Exception as exc:
            logger.debug("Info sqlite-vec load: %s", exc)
    pragmas = PRAGMA_SESI_CEPAT if sudah_init else PRAGMA_KONEKSI
    for pragma in pragmas:
        conn.execute(pragma)
    return conn


@contextmanager
def koneksi(db_path: str | None = None, init: bool = True) -> Iterator[sqlite3.Connection]:
    """Context manager koneksi; otomatis memastikan skema ada dan menutup koneksi."""
    path = db_path or get_settings().db_path
    if init:
        pastikan_db(path)
    conn = get_connection(path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaksi(conn: sqlite3.Connection, immediate: bool = True) -> Iterator[sqlite3.Connection]:
    """Transaksi eksplisit. ``BEGIN IMMEDIATE`` langsung mengambil write-lock
    sehingga operasi baca-lalu-tulis (mis. Atomic Batch Locking) bebas race."""
    conn.execute("BEGIN IMMEDIATE;" if immediate else "BEGIN;")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK;")
        raise
    else:
        conn.execute("COMMIT;")


def _migrasi_skema_v2(conn: sqlite3.Connection) -> None:
    """Migrasi aman untuk menambahkan kolom pembelajaran ke laci_arsip jika belum ada."""
    try:
        rows = conn.execute("PRAGMA table_info(laci_arsip)").fetchall()
        cols = {row["name"] for row in rows}
        if cols and "confidence" not in cols:
            conn.execute("ALTER TABLE laci_arsip ADD COLUMN confidence REAL NOT NULL DEFAULT 0.7;")
        if cols and "hit_count" not in cols:
            conn.execute("ALTER TABLE laci_arsip ADD COLUMN hit_count INTEGER NOT NULL DEFAULT 0;")
        if cols and "miss_count" not in cols:
            conn.execute("ALTER TABLE laci_arsip ADD COLUMN miss_count INTEGER NOT NULL DEFAULT 0;")
        if cols and "last_hit" not in cols:
            conn.execute("ALTER TABLE laci_arsip ADD COLUMN last_hit TIMESTAMP NULL;")
        if cols and "is_stale" not in cols:
            conn.execute("ALTER TABLE laci_arsip ADD COLUMN is_stale INTEGER NOT NULL DEFAULT 0;")
    except Exception as exc:
        logger.warning("Gagal migrasi kolom laci_arsip: %s", exc)


def init_db(db_path: str | None = None) -> str:
    """Membuat tabel relasional + virtual FTS5 + trigger + sqlite-vec + index."""
    path = db_path or get_settings().db_path
    conn = get_connection(path)
    try:
        with transaksi(conn):
            for ddl in DDL_TABEL:
                conn.execute(ddl)
            _migrasi_skema_v2(conn)
            for ddl in DDL_TRIGGER:
                conn.execute(ddl)
            for ddl in DDL_INDEKS:
                conn.execute(ddl)
            if _HAVE_SQLITE_VEC:
                try:
                    conn.execute(
                        """
                        CREATE VIRTUAL TABLE IF NOT EXISTS laci_arsip_vec USING vec0(
                            id INTEGER PRIMARY KEY,
                            embedding float[384] distance_metric=cosine
                        );
                        """
                    )
                    conn.execute(
                        """
                        CREATE TRIGGER IF NOT EXISTS laci_arsip_vec_ad AFTER DELETE ON laci_arsip BEGIN
                            DELETE FROM laci_arsip_vec WHERE id = old.id;
                        END;
                        """
                    )
                except Exception as exc:
                    logger.warning("Inisialisasi laci_arsip_vec dilewati: %s", exc)
    finally:
        conn.close()
    with _init_lock:
        _initialized_paths.add(path)
    return path


def pastikan_db(db_path: str | None = None) -> str:
    """Menjalankan :func:`init_db` sekali per path per proses (idempoten)."""
    path = db_path or get_settings().db_path
    if path in _initialized_paths and (path == ":memory:" or Path(path).exists()):
        return path
    return init_db(path)


def catat_metrik(
    conn: sqlite3.Connection,
    kode_proyek: str,
    jenis_aktivitas: str,
    token_mentah_setara: int,
    token_aktual_terpakai: int,
) -> int:
    """Menyimpan satu baris audit token ke ``log_metrik_token``."""
    if jenis_aktivitas not in JENIS_AKTIVITAS_VALID:
        raise ValueError(f"jenis_aktivitas tidak dikenal: {jenis_aktivitas}")
    cur = conn.execute(
        """
        INSERT INTO log_metrik_token (kode_proyek, jenis_aktivitas, token_mentah_setara, token_aktual_terpakai)
        VALUES (?, ?, ?, ?)
        """,
        (kode_proyek, jenis_aktivitas, max(0, int(token_mentah_setara)), max(0, int(token_aktual_terpakai))),
    )
    return int(cur.lastrowid)


def rebuild_fts(db_path: str | None = None) -> None:
    """Membangun ulang indeks FTS5 dari tabel konten (utilitas pemeliharaan)."""
    with koneksi(db_path) as conn:
        conn.execute("INSERT INTO laci_arsip_fts(laci_arsip_fts) VALUES ('rebuild');")


def daftar_proyek(conn: sqlite3.Connection) -> list[str]:
    """Seluruh kode_proyek yang pernah tercatat di salah satu tabel."""
    rows = conn.execute(
        """
        SELECT kode_proyek FROM ktp_proyek
        UNION SELECT kode_proyek FROM antrean_mentah
        UNION SELECT kode_proyek FROM laci_arsip
        UNION SELECT kode_proyek FROM log_metrik_token
        ORDER BY kode_proyek
        """
    ).fetchall()
    return [r["kode_proyek"] for r in rows]
