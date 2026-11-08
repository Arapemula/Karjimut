"""Lapisan layanan data Sleep-MCP (tanpa dependensi GUI sehingga mudah diuji).

Dipakai oleh Aplikasi Desktop (CustomTkinter) untuk:
  * Dual Sustainability Card (Metrik A & B),
  * CRUD Laci Arsip Solusi dan update KTP manual,
  * Manajemen proyek: ganti nama / gabung / hapus (dengan alias otomatis agar
    nama folder lama tetap diarahkan ke memori yang benar).
"""

from __future__ import annotations

import sqlite3
from typing import Any

from .config import (
    AKTIVITAS_READ_KTP,
    AKTIVITAS_SEARCH_SOLUSI,
    AKTIVITAS_SLEEP,
    AKTIVITAS_WRITE_LOG,
    STATUS_PROCESSING,
    setup_logging,
)
from .consolidator import ekspor_memori_tim, terapkan_ktp_baru
from .db import normalisasi_kode_proyek, transaksi
from .fts_search import normalisasi_tag
from .tokenizer_utils import batasi_kalimat

logger = setup_logging("sleep_mcp.services")

# ---------------------------------------------------------------------------
# Query Statis Bebas f-string SQL (Aman terhadap Static Analysis / Bandit B608)
# ---------------------------------------------------------------------------
_SQL_METRIK_AGREGAT_ALL = """
    SELECT jenis_aktivitas,
           COUNT(*) AS jumlah_panggilan,
           COALESCE(SUM(token_mentah_setara), 0) AS total_mentah,
           COALESCE(SUM(token_aktual_terpakai), 0) AS total_aktual
    FROM log_metrik_token
    GROUP BY jenis_aktivitas
"""

_SQL_METRIK_AGREGAT_BY_PROYEK = """
    SELECT jenis_aktivitas,
           COUNT(*) AS jumlah_panggilan,
           COALESCE(SUM(token_mentah_setara), 0) AS total_mentah,
           COALESCE(SUM(token_aktual_terpakai), 0) AS total_aktual
    FROM log_metrik_token
    WHERE kode_proyek = ?
    GROUP BY jenis_aktivitas
"""

_SQL_METRIK_HISTORY_ALL = """
    SELECT id, kode_proyek, jenis_aktivitas, token_mentah_setara, token_aktual_terpakai, waktu_catat
    FROM log_metrik_token
    ORDER BY id DESC LIMIT 30
"""

_SQL_METRIK_HISTORY_BY_PROYEK = """
    SELECT id, kode_proyek, jenis_aktivitas, token_mentah_setara, token_aktual_terpakai, waktu_catat
    FROM log_metrik_token
    WHERE kode_proyek = ?
    ORDER BY id DESC LIMIT 30
"""


# ---------------------------------------------------------------------------
# Metrik Keberlanjutan Dua Lapis
# ---------------------------------------------------------------------------
def hitung_metrik_proyek(conn: sqlite3.Connection, kode_proyek: str) -> dict[str, Any]:
    """Menghitung Dual Sustainability Card (Metrik A & Metrik B) langsung dari SQLite."""
    kode_filter: str | None = None
    if kode_proyek:
        try:
            kode_filter = normalisasi_kode_proyek(kode_proyek)
        except ValueError:
            kode_filter = None

    if kode_filter is not None:
        rows = conn.execute(_SQL_METRIK_AGREGAT_BY_PROYEK, (kode_filter,)).fetchall()
        history_rows = conn.execute(_SQL_METRIK_HISTORY_BY_PROYEK, (kode_filter,)).fetchall()
    else:
        rows = conn.execute(_SQL_METRIK_AGREGAT_ALL).fetchall()
        history_rows = conn.execute(_SQL_METRIK_HISTORY_ALL).fetchall()

    breakdown: dict[str, dict[str, int]] = {
        a: {"count": 0, "mentah": 0, "aktual": 0}
        for a in (AKTIVITAS_READ_KTP, AKTIVITAS_WRITE_LOG, AKTIVITAS_SEARCH_SOLUSI, AKTIVITAS_SLEEP)
    }
    t_baseline = t_aktif_mcp = t_sleep_llm = 0
    for r in rows:
        akt = r["jenis_aktivitas"]
        if akt in breakdown:
            breakdown[akt] = {
                "count": int(r["jumlah_panggilan"]),
                "mentah": int(r["total_mentah"]),
                "aktual": int(r["total_aktual"]),
            }
        if akt in (AKTIVITAS_READ_KTP, AKTIVITAS_WRITE_LOG, AKTIVITAS_SEARCH_SOLUSI):
            t_baseline += int(r["total_mentah"])
            t_aktif_mcp += int(r["total_aktual"])
        elif akt == AKTIVITAS_SLEEP:
            t_sleep_llm += int(r["total_aktual"])

    if t_baseline == 0 and breakdown[AKTIVITAS_SLEEP]["mentah"] > 0:
        t_baseline = breakdown[AKTIVITAS_SLEEP]["mentah"]

    efisiensi = max(0.0, ((t_baseline - t_aktif_mcp) / t_baseline) * 100.0) if t_baseline > 0 else 0.0
    t_total_mcp = t_aktif_mcp + t_sleep_llm
    net = t_baseline - t_total_mcp
    net_persen = (net / t_baseline) * 100.0 if t_baseline > 0 else 0.0
    return {
        "t_baseline": t_baseline,
        "t_aktif_mcp": t_aktif_mcp,
        "t_sleep_llm": t_sleep_llm,
        "t_total_mcp": t_total_mcp,
        "efisiensi_aktif_persen": round(efisiensi, 2),
        "metrik_a_tercapai": efisiensi > 60.0,
        "net_savings_tokens": net,
        "net_savings_persen": round(net_persen, 2),
        "bep_tercapai": net > 0,
        "status_bep": "SURPLUS (BEP Tercapai)" if net > 0 else "INVESTASI (Pra-BEP)",
        "breakdown": breakdown,
        "history": [dict(hr) for hr in history_rows],
    }


# ---------------------------------------------------------------------------
# KTP Proyek
# ---------------------------------------------------------------------------
def simpan_ktp_manual(conn: sqlite3.Connection, kode_proyek: str, teks: str, max_tokens: int | None = 0) -> dict[str, Any]:
    """Menyimpan KTP hasil suntingan manual (Elastic Core / bounded token + snapshot rollback + sinkronisasi tim)."""
    kode = normalisasi_kode_proyek(kode_proyek)
    with transaksi(conn):
        info = terapkan_ktp_baru(conn, kode, teks, max_tokens)
        ekspor_memori_tim(conn, kode)
        return info


# ---------------------------------------------------------------------------
# Laci Arsip Solusi (CRUD) dengan Sinkronisasi Vektor & Pembelajaran
# ---------------------------------------------------------------------------
def tambah_solusi(conn: sqlite3.Connection, kode_proyek: str, tag_masalah: str, solusi_paten: str) -> int:
    from .log_parser import bersihkan_injeksi_memori

    kode = normalisasi_kode_proyek(kode_proyek)
    tags = normalisasi_tag(tag_masalah)
    solusi = batasi_kalimat(bersihkan_injeksi_memori(solusi_paten), 2)
    if not tags or not solusi:
        raise ValueError("Tag masalah dan isi solusi wajib diisi.")
    tag_str = ", ".join(tags)
    pre_vec = None
    aktif_backend = None
    try:
        from .embedding import generate_embedding, get_active_embedding_backend, simpan_vektor_solusi
        pre_vec = generate_embedding(f"{tag_str} {solusi}")
        aktif_backend = get_active_embedding_backend()
    except Exception as exc:
        logger.debug("Precompute embedding tambah_solusi dilewati: %s", exc)
    with transaksi(conn):
        cur = conn.execute(
            "INSERT INTO laci_arsip (kode_proyek, tag_masalah, solusi_paten) VALUES (?, ?, ?)",
            (kode, tag_str, solusi),
        )
        new_id = int(cur.lastrowid)
        if pre_vec is not None:
            try:
                simpan_vektor_solusi(conn, new_id, tag_str, solusi, precomputed_vec=pre_vec, backend=aktif_backend)
            except (sqlite3.Error, RuntimeError, ValueError, OSError) as exc:
                logger.warning("Gagal menyinkronkan vektor untuk solusi baru #%d: %s", new_id, exc)
    ekspor_memori_tim(conn, kode)
    return new_id


def perbarui_solusi(
    conn: sqlite3.Connection, kode_proyek: str, solusi_id: int, tag_masalah: str, solusi_paten: str
) -> dict[str, Any]:
    from .log_parser import bersihkan_injeksi_memori

    kode = normalisasi_kode_proyek(kode_proyek)
    tags = normalisasi_tag(tag_masalah)
    solusi = batasi_kalimat(bersihkan_injeksi_memori(solusi_paten), 2)
    if not tags or not solusi:
        raise ValueError("Tag masalah dan isi solusi wajib diisi.")
    tag_str = ", ".join(tags)
    sid = int(solusi_id)
    pre_vec = None
    aktif_backend = None
    try:
        from .embedding import generate_embedding, get_active_embedding_backend, simpan_vektor_solusi
        pre_vec = generate_embedding(f"{tag_str} {solusi}")
        aktif_backend = get_active_embedding_backend()
    except Exception as exc:
        logger.debug("Precompute embedding perbarui_solusi dilewati: %s", exc)
    with transaksi(conn):
        cur = conn.execute(
            """
            UPDATE laci_arsip SET tag_masalah = ?, solusi_paten = ?, waktu_dibuat = CURRENT_TIMESTAMP
            WHERE id = ? AND kode_proyek = ?
            """,
            (tag_str, solusi, sid, kode),
        )
        if cur.rowcount == 0:
            raise LookupError(f"Solusi #{solusi_id} tidak ditemukan pada proyek '{kode}'.")
        if pre_vec is not None:
            try:
                simpan_vektor_solusi(conn, sid, tag_str, solusi, precomputed_vec=pre_vec, backend=aktif_backend)
            except (sqlite3.Error, RuntimeError, ValueError, OSError) as exc:
                logger.warning("Gagal memperbarui vektor untuk solusi #%d: %s", sid, exc)
    ekspor_memori_tim(conn, kode)
    return {"id": sid, "kode_proyek": kode, "tag_masalah": tag_str, "solusi_paten": solusi}


def hapus_solusi(conn: sqlite3.Connection, kode_proyek: str, solusi_id: int) -> None:
    kode = normalisasi_kode_proyek(kode_proyek)
    sid = int(solusi_id)
    with transaksi(conn):
        cur = conn.execute("DELETE FROM laci_arsip WHERE id = ? AND kode_proyek = ?", (sid, kode))
        if cur.rowcount == 0:
            raise LookupError(f"Solusi #{solusi_id} tidak ditemukan pada proyek '{kode}'.")
        try:
            from .embedding import hapus_vektor_solusi
            hapus_vektor_solusi(conn, sid)
        except (sqlite3.Error, RuntimeError, ValueError, OSError) as exc:
            logger.warning("Gagal menghapus vektor untuk solusi #%d: %s", sid, exc)


def hitung_self_assessment_proyek(conn: sqlite3.Connection, kode_proyek: str) -> dict[str, Any]:
    """Menghitung metrik evaluasi pembelajaran mandiri untuk tab Dashboard GUI."""
    kode = normalisasi_kode_proyek(kode_proyek)
    row_stats = conn.execute(
        """
        SELECT 
            COUNT(*) AS total_solusi,
            COALESCE(AVG(confidence), 0.7) AS avg_conf,
            COALESCE(SUM(hit_count), 0) AS total_hit,
            COALESCE(SUM(miss_count), 0) AS total_miss,
            COALESCE(SUM(CASE WHEN confidence >= 0.85 THEN 1 ELSE 0 END), 0) AS total_proven,
            COALESCE(SUM(CASE WHEN is_stale = 1 THEN 1 ELSE 0 END), 0) AS total_stale
        FROM laci_arsip
        WHERE kode_proyek = ?
        """,
        (kode,),
    ).fetchone()

    total_solusi = int(row_stats["total_solusi"])
    avg_conf = round(float(row_stats["avg_conf"]), 3)
    total_hit = int(row_stats["total_hit"])
    total_miss = int(row_stats["total_miss"])
    total_proven = int(row_stats["total_proven"])
    total_stale = int(row_stats["total_stale"])
    total_eval = total_hit + total_miss

    hit_rate = round((total_hit / total_eval) * 100.0, 1) if total_eval > 0 else 0.0
    success_rate = round((total_proven / max(1, total_solusi)) * 100.0, 1)

    history_logs = conn.execute(
        """
        SELECT id, total_pencarian, total_hit, total_sukses, total_gagal, confidence_rata2, waktu_catat
        FROM log_pembelajaran
        WHERE kode_proyek = ?
        ORDER BY id DESC LIMIT 20
        """,
        (kode,),
    ).fetchall()

    tren_positif = True
    if len(history_logs) >= 2:
        conf_now = float(history_logs[0]["confidence_rata2"])
        conf_prev = float(history_logs[1]["confidence_rata2"])
        tren_positif = conf_now >= conf_prev

    return {
        "kode_proyek": kode,
        "total_solusi": total_solusi,
        "avg_confidence": avg_conf,
        "avg_conf": avg_conf,
        "total_hit": total_hit,
        "total_miss": total_miss,
        "hit_rate_persen": hit_rate,
        "hit_rate": hit_rate,
        "success_rate_persen": success_rate,
        "total_proven": total_proven,
        "total_stale": total_stale,
        "tren_positif": tren_positif,
        "riwayat": [dict(r) for r in history_logs],
    }


# ---------------------------------------------------------------------------
# Manajemen Proyek (Query Statis Terpetakan per Tabel)
# ---------------------------------------------------------------------------
_TABEL_PROYEK = (
    "antrean_mentah",
    "ktp_proyek",
    "laci_arsip",
    "log_metrik_token",
    "peta_workspace",
    "log_pembelajaran",
)

_SQL_COUNT_BY_PROYEK: dict[str, str] = {
    "antrean_mentah": "SELECT COUNT(*) FROM antrean_mentah WHERE kode_proyek = ?",
    "ktp_proyek": "SELECT COUNT(*) FROM ktp_proyek WHERE kode_proyek = ?",
    "laci_arsip": "SELECT COUNT(*) FROM laci_arsip WHERE kode_proyek = ?",
    "log_metrik_token": "SELECT COUNT(*) FROM log_metrik_token WHERE kode_proyek = ?",
    "peta_workspace": "SELECT COUNT(*) FROM peta_workspace WHERE kode_proyek = ?",
    "log_pembelajaran": "SELECT COUNT(*) FROM log_pembelajaran WHERE kode_proyek = ?",
}

_SQL_UPDATE_KODE_PROYEK: dict[str, str] = {
    "antrean_mentah": "UPDATE antrean_mentah SET kode_proyek = ? WHERE kode_proyek = ?",
    "ktp_proyek": "UPDATE ktp_proyek SET kode_proyek = ? WHERE kode_proyek = ?",
    "laci_arsip": "UPDATE laci_arsip SET kode_proyek = ? WHERE kode_proyek = ?",
    "log_metrik_token": "UPDATE log_metrik_token SET kode_proyek = ? WHERE kode_proyek = ?",
    "peta_workspace": "UPDATE peta_workspace SET kode_proyek = ? WHERE kode_proyek = ?",
    "log_pembelajaran": "UPDATE log_pembelajaran SET kode_proyek = ? WHERE kode_proyek = ?",
}

_SQL_DELETE_BY_PROYEK: dict[str, str] = {
    "antrean_mentah": "DELETE FROM antrean_mentah WHERE kode_proyek = ?",
    "ktp_proyek": "DELETE FROM ktp_proyek WHERE kode_proyek = ?",
    "laci_arsip": "DELETE FROM laci_arsip WHERE kode_proyek = ?",
    "log_metrik_token": "DELETE FROM log_metrik_token WHERE kode_proyek = ?",
    "peta_workspace": "DELETE FROM peta_workspace WHERE kode_proyek = ?",
    "log_pembelajaran": "DELETE FROM log_pembelajaran WHERE kode_proyek = ?",
}


def _ada_batch_aktif(conn: sqlite3.Connection, kode: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM antrean_mentah WHERE kode_proyek = ? AND status_rangkum = ? LIMIT 1",
        (kode, STATUS_PROCESSING),
    ).fetchone() is not None


def ringkasan_proyek(conn: sqlite3.Connection, kode_proyek: str) -> dict[str, Any]:
    """Jumlah baris data per tabel untuk satu proyek (dipakai dialog konfirmasi hapus)."""
    kode = normalisasi_kode_proyek(kode_proyek)
    counts = {
        tabel: int(conn.execute(_SQL_COUNT_BY_PROYEK[tabel], (kode,)).fetchone()[0])
        for tabel in _TABEL_PROYEK
    }
    return {
        **counts,
        "ada_ktp": counts["ktp_proyek"] > 0,
        "jumlah_solusi": counts["laci_arsip"],
        "jumlah_log": counts["antrean_mentah"],
        "jumlah_metrik": counts["log_metrik_token"],
    }


def gabung_atau_ganti_nama_proyek(conn: sqlite3.Connection, sumber: str, target: str) -> dict[str, Any]:
    """Mengganti nama proyek ``sumber`` menjadi ``target`` (atau menggabungkannya bila target sudah ada).

    Seluruh data (antrean, arsip, metrik, peta workspace) dipindahkan. KTP sumber
    dipindahkan hanya bila target belum punya KTP; jika target sudah punya KTP,
    KTP target dipertahankan. Alias ``sumber -> target`` dicatat sehingga agent
    yang masih memakai nama folder lama tetap diarahkan ke memori yang benar.
    """
    src = normalisasi_kode_proyek(sumber)
    dst = normalisasi_kode_proyek(target)
    if src == dst:
        raise ValueError("Nama proyek sumber dan tujuan sama.")
    with transaksi(conn):
        if _ada_batch_aktif(conn, src) or _ada_batch_aktif(conn, dst):
            raise RuntimeError("Sleep Cycle sedang berjalan pada proyek ini. Coba lagi beberapa saat.")
        ktp_target_ada = conn.execute("SELECT 1 FROM ktp_proyek WHERE kode_proyek = ?", (dst,)).fetchone() is not None
        ktp_dibuang = False
        if ktp_target_ada:
            ktp_dibuang = conn.execute("SELECT 1 FROM ktp_proyek WHERE kode_proyek = ?", (src,)).fetchone() is not None
            conn.execute("DELETE FROM ktp_proyek WHERE kode_proyek = ?", (src,))
        dipindah: dict[str, int] = {}
        for tabel in _TABEL_PROYEK:
            cur = conn.execute(_SQL_UPDATE_KODE_PROYEK[tabel], (dst, src))
            dipindah[tabel] = cur.rowcount or 0
        conn.execute("UPDATE alias_proyek SET kode_proyek = ? WHERE kode_proyek = ?", (dst, src))
        conn.execute("DELETE FROM alias_proyek WHERE alias = ?", (dst,))
        conn.execute("INSERT OR REPLACE INTO alias_proyek (alias, kode_proyek) VALUES (?, ?)", (src, dst))
    return {
        "sumber": src,
        "target": dst,
        "kode_asal": src,
        "kode_tujuan": dst,
        "dipindah": dipindah,
        "ktp_sumber_dibuang": ktp_dibuang,
    }


def hapus_proyek(conn: sqlite3.Connection, kode_proyek: str) -> dict[str, int]:
    """Menghapus PERMANEN seluruh data satu proyek. Pemanggil wajib meminta konfirmasi pengguna."""
    kode = normalisasi_kode_proyek(kode_proyek)
    solusi_ids = [
        int(r["id"])
        for r in conn.execute("SELECT id FROM laci_arsip WHERE kode_proyek = ?", (kode,)).fetchall()
    ]
    with transaksi(conn):
        if _ada_batch_aktif(conn, kode):
            raise RuntimeError("Sleep Cycle sedang berjalan pada proyek ini. Coba lagi beberapa saat.")
        terhapus: dict[str, int] = {}
        for tabel in _TABEL_PROYEK:
            cur = conn.execute(_SQL_DELETE_BY_PROYEK[tabel], (kode,))
            terhapus[tabel] = cur.rowcount or 0
        conn.execute("DELETE FROM alias_proyek WHERE alias = ? OR kode_proyek = ?", (kode, kode))
    if solusi_ids:
        from .embedding import hapus_vektor_solusi
        for sid in solusi_ids:
            try:
                hapus_vektor_solusi(conn, sid)
            except (sqlite3.Error, RuntimeError, ValueError, OSError) as exc:
                logger.warning("Gagal menghapus vektor untuk solusi #%d pada hapus_proyek: %s", sid, exc)
    return terhapus
