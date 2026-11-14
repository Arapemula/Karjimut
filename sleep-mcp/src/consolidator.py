"""Engine Sleep Cycle (Konsolidasi Fase Idle) Karjimut.

Alur 7 langkah bebas race condition:
  1. Stale/Zombie Lock Sweeper      -> reset status 1 berusia > 3 menit ke 0 (`consolidator.py`).
  2. Atomic Batch Locking           -> BEGIN IMMEDIATE + UPDATE ... WHERE id IN (...) AND status=0 (`consolidator.py`).
  3. Pengambilan konteks            -> KTP saat ini, daftar arsip eksisting, isi log batch (`consolidator.py`).
  4. Distilasi LLM / Lokal          -> `llm_distiller.py` & `ktp_manager.py` (dengan pra-filter `log_parser.py`).
  5. Hard-limit + snapshot KTP      -> `ktp_manager.py`.
  6. Deduplikasi laci_arsip         -> `archive_manager.py`.
  7. Finalisasi & metrik            -> status 2 (atau kembali 0 jika error) + log SLEEP_CONSOLIDATION.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from .archive_manager import (
    ambil_team_secret,
    audit_berkas_team_memory,
    auto_bootstrap_workspace,
    ekspor_memori_tim,
    gabung_solusi_paten,
    hitung_signature_tim,
    impor_memori_tim,
    kompaksi_antrean_lama,
    perbarui_log_pembelajaran,
    simpan_arsip_deduplikasi,
    terapkan_memory_decay,
    validasi_skema_team_memory,
    verifikasi_signature_tim,
)
from .config import (
    AKTIVITAS_SLEEP,
    STATUS_PENDING,
    STATUS_PROCESSED,
    STATUS_PROCESSING,
    get_settings,
    setup_logging,
)
from .db import catat_metrik, koneksi, normalisasi_kode_proyek, transaksi
from .embedding import sinkron_vektor_laci_arsip
from .ktp_manager import (
    identitas_bermakna,
    local_rule_based_distiller,
    rollback_ktp,
    susun_ktp_terbatas,
    terapkan_ktp_baru,
    urai_ktp,
)
from .llm_distiller import (
    SYSTEM_PROMPT_CONSOLIDATOR,
    SYSTEM_PROMPT_KOMPRESI,
    distilasi,
    ekstrak_json,
    panggil_llm_json,
    susun_user_prompt,
    validasi_output_distiller,
)
from .log_parser import (
    JACCARD_THRESHOLD,
    KAMUS_GEJALA,
    KAMUS_TEKNOLOGI,
    MAX_CHARS_PER_LOG_PROMPT,
    MAX_TAG_PER_ARSIP,
    MIN_TAG_OVERLAP,
    STOPWORDS_ATURAN,
    _RE_GAGAL,
    _RE_PROMPT_BREAKOUT,
    _RE_PROMPT_INJECTION,
    _RE_SOLUSI_KATA,
    _RE_SOLUSI_MARKER,
    bangun_tag_gejala,
    bersihkan_injeksi_memori,
    deteksi_direktori,
    deteksi_teknologi,
    gabung_aturan,
    jaccard_similarity,
    layak_masuk_laci_arsip,
    pisahkan_noise,
    ringkas_stack_trace,
    sanitasi_pesan_error,
)

logger = setup_logging("sleep_mcp.consolidator")

DistillerFn = Callable[[dict[str, Any]], tuple[str, dict[str, Any], int, int]]


@dataclass
class HasilKonsolidasi:
    kode_proyek: str
    status: str  # SUCCESS | NO_PENDING | ERROR
    pesan: str = ""
    mode_distiller: str = ""  # LLM | LOCAL_RULE_BASED
    stale_lock_direset: int = 0
    batch_ids: list[int] = field(default_factory=list)
    jumlah_log: int = 0
    token_mentah_setara: int = 0
    token_prompt: int = 0
    token_completion: int = 0
    ktp_baru: str = ""
    jumlah_token_ktp: int = 0
    versi_ktp: int = 0
    arsip_insert: int = 0
    arsip_update: int = 0
    detail_arsip: list[dict[str, Any]] = field(default_factory=list)
    durasi_detik: float = 0.0

    @property
    def token_aktual_terpakai(self) -> int:
        return self.token_prompt + self.token_completion

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["token_aktual_terpakai"] = self.token_aktual_terpakai
        return data


# ===========================================================================
# LANGKAH 1 & 2: Stale Lock Sweeper + Atomic Batch Locking
# ===========================================================================
def sweep_stale_locks(conn: sqlite3.Connection, menit: int = 3) -> int:
    """Langkah 1: reset baris zombie (status 1 dengan waktu_kunci > N menit) ke status 0."""
    cur = conn.execute(
        """
        UPDATE antrean_mentah
        SET status_rangkum = 0, waktu_kunci = NULL
        WHERE status_rangkum = 1 AND waktu_kunci <= datetime('now', ?)
        """,
        (f"-{int(menit)} minutes",),
    )
    jumlah = cur.rowcount or 0
    if jumlah:
        logger.warning("Stale Lock Sweeper mereset %d baris zombie.", jumlah)
    return jumlah


def kunci_batch_atomik(
    conn: sqlite3.Connection, kode_proyek: str, batch_limit: int = 200
) -> tuple[list[int], str | None]:
    """Langkah 2: kunci batch log pending secara atomik di dalam transaksi IMMEDIATE."""
    sedang_diproses = conn.execute(
        "SELECT 1 FROM antrean_mentah WHERE kode_proyek = ? AND status_rangkum = 1 LIMIT 1",
        (kode_proyek,),
    ).fetchone()
    if sedang_diproses is not None:
        return [], None

    rows = conn.execute(
        """
        SELECT id FROM antrean_mentah
        WHERE kode_proyek = ? AND status_rangkum = 0
        ORDER BY id ASC
        LIMIT ?
        """,
        (kode_proyek, int(batch_limit)),
    ).fetchall()
    batch_ids = [int(r["id"]) for r in rows]
    if not batch_ids:
        return [], None
    placeholder = ",".join("?" for _ in batch_ids)
    conn.execute(
        f"""
        UPDATE antrean_mentah
        SET status_rangkum = 1, waktu_kunci = CURRENT_TIMESTAMP
        WHERE id IN ({placeholder}) AND status_rangkum = 0
        """,
        batch_ids,
    )
    terkunci = conn.execute(
        f"""
        SELECT id, waktu_kunci FROM antrean_mentah
        WHERE id IN ({placeholder}) AND status_rangkum = 1
        ORDER BY id
        """,
        batch_ids,
    ).fetchall()
    ids_final = [int(r["id"]) for r in terkunci]
    waktu_kunci = terkunci[0]["waktu_kunci"] if terkunci else None
    return ids_final, waktu_kunci


def _lepas_kunci_batch(conn: sqlite3.Connection, batch_ids: list[int], waktu_kunci: str | None) -> int:
    """Mengembalikan batch milik siklus ini ke status 0 (dipakai saat terjadi error)."""
    if not batch_ids:
        return 0
    placeholder = ",".join("?" for _ in batch_ids)
    params: list[Any] = list(batch_ids)
    filter_kunci = ""
    if waktu_kunci is not None:
        filter_kunci = " AND waktu_kunci = ?"
        params.append(waktu_kunci)
    cur = conn.execute(
        f"""
        UPDATE antrean_mentah
        SET status_rangkum = 0, waktu_kunci = NULL
        WHERE id IN ({placeholder}) AND status_rangkum = 1{filter_kunci}
        """,
        params,
    )
    return cur.rowcount or 0


# ===========================================================================
# LANGKAH 3: Pengambilan konteks sebelumnya
# ===========================================================================
def ambil_konteks(conn: sqlite3.Connection, kode_proyek: str, batch_ids: list[int]) -> dict[str, Any]:
    """Langkah 3: KTP saat ini, daftar arsip eksisting, dan isi log pada batch."""
    ktp_row = conn.execute(
        "SELECT ringkasan_inti, versi_ktp FROM ktp_proyek WHERE kode_proyek = ?", (kode_proyek,)
    ).fetchone()
    arsip_rows = conn.execute(
        "SELECT id, tag_masalah, solusi_paten FROM laci_arsip WHERE kode_proyek = ? ORDER BY id",
        (kode_proyek,),
    ).fetchall()
    placeholder = ",".join("?" for _ in batch_ids) or "NULL"
    log_rows = conn.execute(
        f"""
        SELECT id, isi_log, estimasi_token_mentah, waktu_masuk
        FROM antrean_mentah WHERE id IN ({placeholder}) ORDER BY id
        """,
        batch_ids,
    ).fetchall()
    return {
        "kode_proyek": kode_proyek,
        "ktp_lama": ktp_row["ringkasan_inti"] if ktp_row else "",
        "versi_ktp": int(ktp_row["versi_ktp"]) if ktp_row else 0,
        "arsip_eksisting": [dict(r) for r in arsip_rows],
        "log_batch": [dict(r) for r in log_rows],
        "token_mentah_setara": sum(int(r["estimasi_token_mentah"]) for r in log_rows),
    }


# ===========================================================================
# Orkestrasi Sleep Cycle (Langkah 1-7)
# ===========================================================================
def jalankan_sleep_cycle(
    kode_proyek: str,
    db_path: str | None = None,
    paksa_lokal: bool | None = None,
    batch_limit: int | None = None,
    distiller: DistillerFn | None = None,
    simpan_snapshot: bool = True,
) -> HasilKonsolidasi:
    """Menjalankan satu Sleep Cycle lengkap untuk ``kode_proyek``."""
    s = get_settings()
    kode = normalisasi_kode_proyek(kode_proyek)
    mulai = time.perf_counter()
    hasil = HasilKonsolidasi(kode_proyek=kode, status="NO_PENDING")

    with koneksi(db_path) as conn:
        with transaksi(conn):
            hasil.stale_lock_direset = sweep_stale_locks(conn, s.stale_lock_minutes)
            batch_ids, waktu_kunci = kunci_batch_atomik(conn, kode, batch_limit or s.sleep_batch_limit)
        if not batch_ids:
            hasil.pesan = "Tidak ada log pending untuk dikonsolidasi."
            hasil.durasi_detik = round(time.perf_counter() - mulai, 4)
            return hasil

        hasil.batch_ids = batch_ids
        hasil.jumlah_log = len(batch_ids)
        try:
            konteks = ambil_konteks(conn, kode, batch_ids)
            hasil.token_mentah_setara = konteks["token_mentah_setara"]

            if distiller is not None:
                mode, distilat, tp, tc = distiller(konteks)
                distilat = validasi_output_distiller(distilat)
            else:
                mode, distilat, tp, tc = distilasi(konteks, s, paksa_lokal)
            hasil.mode_distiller, hasil.token_prompt, hasil.token_completion = mode, tp, tc

            with transaksi(conn):
                placeholder = ",".join("?" for _ in batch_ids)
                masih_terkunci = conn.execute(
                    f"SELECT COUNT(*) FROM antrean_mentah WHERE id IN ({placeholder}) "
                    f"AND status_rangkum = 1 AND waktu_kunci = ?",
                    [*batch_ids, waktu_kunci],
                ).fetchone()[0]
                if masih_terkunci != len(batch_ids):
                    raise RuntimeError("Kunci batch kedaluwarsa (direset Stale Lock Sweeper); siklus dibatalkan.")

                info_ktp = terapkan_ktp_baru(
                    conn,
                    kode,
                    distilat["ktp_proyek_baru"],
                    s.ktp_max_tokens,
                    simpan_snapshot=simpan_snapshot,
                )
                hasil.ktp_baru = info_ktp["ringkasan_inti"]
                hasil.jumlah_token_ktp = info_ktp["jumlah_token"]
                hasil.versi_ktp = info_ktp["versi_ktp"]

                for item in distilat["arsip_solusi"]:
                    detail = simpan_arsip_deduplikasi(conn, kode, item, sync_vektor=False)
                    hasil.detail_arsip.append(detail)
                    if detail["aksi"] == "INSERT":
                        hasil.arsip_insert += 1
                    elif detail["aksi"] == "UPDATE":
                        hasil.arsip_update += 1

                conn.execute(
                    f"UPDATE antrean_mentah SET status_rangkum = {STATUS_PROCESSED} "
                    f"WHERE id IN ({placeholder}) AND status_rangkum = {STATUS_PROCESSING}",
                    batch_ids,
                )
                catat_metrik(conn, kode, AKTIVITAS_SLEEP, hasil.token_mentah_setara, tp + tc)

                decay_count = terapkan_memory_decay(conn, kode)
                if decay_count > 0:
                    logger.debug("[%s] Memory decay diterapkan pada %d solusi.", kode, decay_count)
                kompaksi_antrean_lama(conn, kode)
                perbarui_log_pembelajaran(conn, kode)

            # Operasi berat (ONNX embedding & I/O file JSON tim) dijalankan DI LUAR transaksi BEGIN IMMEDIATE
            # agar tidak pernah menahan write-lock SQLite.
            sinkron_vektor_laci_arsip(conn, limit=50)
            ekspor_memori_tim(conn, kode)
            hasil.status = "SUCCESS"
            hasil.pesan = (
                f"Sleep Cycle selesai: {len(batch_ids)} log dirangkum, KTP v{hasil.versi_ktp} "
                f"({hasil.jumlah_token_ktp} token), arsip +{hasil.arsip_insert} baru / {hasil.arsip_update} diperbarui."
            )
            logger.info("[%s] %s", kode, hasil.pesan)
        except Exception as exc:
            try:
                with transaksi(conn):
                    _lepas_kunci_batch(conn, batch_ids, waktu_kunci)
            except sqlite3.Error as exc_db:
                logger.error("Gagal melepas kunci batch: %s", exc_db)
            hasil.status = "ERROR"
            hasil.pesan = f"Sleep Cycle gagal, batch dikembalikan ke pending: {sanitasi_pesan_error(exc)}"
            logger.error("[%s] %s", kode, hasil.pesan)
        hasil.durasi_detik = round(time.perf_counter() - mulai, 4)
        return hasil


def _status_pending_ada(conn: sqlite3.Connection, kode: str) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM antrean_mentah WHERE kode_proyek = ? AND status_rangkum = ? LIMIT 1",
            (kode, STATUS_PENDING),
        ).fetchone()
    )


def jalankan_sleep_cycle_tuntas(
    kode_proyek: str, db_path: str | None = None, **kwargs: Any
) -> list[HasilKonsolidasi]:
    """Menjalankan Sleep Cycle berulang sampai antrean pending proyek habis."""
    hasil_list: list[HasilKonsolidasi] = []
    kode = normalisasi_kode_proyek(kode_proyek)
    for idx in range(100):
        hasil = jalankan_sleep_cycle(
            kode,
            db_path=db_path,
            simpan_snapshot=(idx == 0),
            **kwargs,
        )
        hasil_list.append(hasil)
        if hasil.status != "SUCCESS":
            break
        with koneksi(db_path) as conn:
            if not _status_pending_ada(conn, kode):
                break
    return hasil_list


__all__ = [
    "DistillerFn",
    "HasilKonsolidasi",
    "JACCARD_THRESHOLD",
    "KAMUS_GEJALA",
    "KAMUS_TEKNOLOGI",
    "MAX_CHARS_PER_LOG_PROMPT",
    "MAX_TAG_PER_ARSIP",
    "MIN_TAG_OVERLAP",
    "STOPWORDS_ATURAN",
    "SYSTEM_PROMPT_CONSOLIDATOR",
    "SYSTEM_PROMPT_KOMPRESI",
    "_RE_GAGAL",
    "_RE_PROMPT_BREAKOUT",
    "_RE_PROMPT_INJECTION",
    "_RE_SOLUSI_KATA",
    "_RE_SOLUSI_MARKER",
    "ambil_konteks",
    "ambil_team_secret",
    "audit_berkas_team_memory",
    "auto_bootstrap_workspace",
    "bangun_tag_gejala",
    "bersihkan_injeksi_memori",
    "deteksi_direktori",
    "deteksi_teknologi",
    "distilasi",
    "ekspor_memori_tim",
    "ekstrak_json",
    "gabung_aturan",
    "gabung_solusi_paten",
    "hitung_signature_tim",
    "identitas_bermakna",
    "impor_memori_tim",
    "jaccard_similarity",
    "jalankan_sleep_cycle",
    "jalankan_sleep_cycle_tuntas",
    "kompaksi_antrean_lama",
    "kunci_batch_atomik",
    "layak_masuk_laci_arsip",
    "local_rule_based_distiller",
    "panggil_llm_json",
    "perbarui_log_pembelajaran",
    "pisahkan_noise",
    "ringkas_stack_trace",
    "rollback_ktp",
    "sanitasi_pesan_error",
    "simpan_arsip_deduplikasi",
    "susun_ktp_terbatas",
    "susun_user_prompt",
    "sweep_stale_locks",
    "terapkan_ktp_baru",
    "terapkan_memory_decay",
    "urai_ktp",
    "validasi_output_distiller",
    "validasi_skema_team_memory",
    "verifikasi_signature_tim",
]
