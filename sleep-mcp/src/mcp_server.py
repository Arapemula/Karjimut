"""Server FastMCP Karjimut: 4 MCP Tools utama (+3 alias ramah pengguna) + MCP Resource pasif.

Primitif MCP:
1. Tool `baca_ktp_proyek(kode_proyek: str) -> str`
   - Inisialisasi awal sesi: mengambil KTP Proyek (Lapis 1, Elastic Core).
   - Menghitung token mentah setara dan mencatat metrik ke `log_metrik_token`.
2. Resource Pasif `mcp://karjimut/ktp/{kode_proyek}` (serta alias `mcp://sleep-mcp/ktp/{kode_proyek}`)
   - Menyediakan isi KTP Proyek untuk klien yang mendukung resource auto-attachment.
3. Tool `titip_catatan_kerja(kode_proyek: str, ringkasan_aksi: str) -> str`
   - Pencatatan milestone aksi kerja ke `antrean_mentah` secara cepat (non-blocking).
4. Tool `cari_laci_solusi(kode_proyek: str, kata_kunci: str) -> str`
   - Pencarian on-demand solusi paten (Lapis 2) via Hybrid Search (BM25 + Vector RRF).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import (
    AKTIVITAS_READ_KTP,
    AKTIVITAS_SEARCH_SOLUSI,
    AKTIVITAS_WRITE_LOG,
    STATUS_PENDING,
    STATUS_PROCESSED,
    get_settings,
    setup_logging,
)
from .consolidator import (
    _RE_PROMPT_BREAKOUT,
    _RE_PROMPT_INJECTION,
    auto_bootstrap_workspace,
    impor_memori_tim,
    perbarui_log_pembelajaran,
)
from .db import (
    catat_metrik,
    koneksi,
    normalisasi_kode_proyek,
    pastikan_db,
    resolve_proyek,
    transaksi,
)
from .fts_search import cari_solusi_fts_conn
from .idle_watcher import IdleWatcherDaemon
from .log_parser import bersihkan_injeksi_memori, normalisasi_spasi, sanitasi_pesan_error
from .tokenizer_utils import hitung_token

logger = setup_logging("sleep_mcp.server")

# Inisialisasi FastMCP Server
mcp = FastMCP(
    "Karjimut",
    instructions=(
        "Karjimut — Two-Tier Autonomous Memory Engine via Model Context Protocol. "
        "Gunakan nama folder workspace aktif (lowercase kebab-case) sebagai `kode_proyek` dan path absolutnya sebagai `path_workspace`. "
        "1) Panggil `baca_ktp_proyek(kode_proyek, path_workspace)` secara OTOMATIS di awal sesi koding baru. "
        "2) Panggil `titip_catatan_kerja(kode_proyek, ringkasan_aksi, path_workspace)` secara OTOMATIS setiap selesai membuat fitur, mengedit kode, atau memperbaiki bug. "
        "3) Panggil `cari_laci_solusi(kode_proyek, kata_kunci, path_workspace)` secara OTOMATIS setiap menemui error sebelum trial-and-error. "
        "4) Panggil `nilai_solusi(kode_proyek, id_solusi, berhasil)` setelah mencoba solusi dari Laci Arsip."
    ),
)


# Global background watcher jika diaktifkan via embedded mode
_embedded_watcher: IdleWatcherDaemon | None = None

# Batas keamanan ukuran input MCP Tool (mencegah Resource Exhaustion / Denial of Wallet)
MAX_LOG_CHARS = 8000
MAX_QUERY_CHARS = 500
MAX_ESTIMASI_TOKEN = 50000


# ---------------------------------------------------------------------------
# 1. MCP Tool: baca_ktp_proyek
# ---------------------------------------------------------------------------
@mcp.tool(
    name="baca_ktp_proyek",
    description=(
        "Panggil otomatis di awal sesi koding baru. Mengambil KTP Proyek (Lapis 1, Elastic Core: "
        "identitas, stack, struktur, aturan wajib). Gunakan nama folder workspace aktif sebagai `kode_proyek` "
        "dan path absolutnya sebagai `path_workspace`."
    ),
)
def baca_ktp_proyek(kode_proyek: str, path_workspace: str | None = None) -> str:
    """Mengambil KTP Proyek terbaru dan mencatat metrik penghematan token ke log_metrik_token."""
    settings = get_settings()
    try:
        normalisasi_kode_proyek(kode_proyek)
    except ValueError as exc:
        return f"[Karjimut] Parameter kode_proyek tidak valid: {exc}"

    perlu_sinkron_vektor = False
    peringatan_tim = ""
    with koneksi(settings.db_path) as conn:
        with transaksi(conn):
            kode = resolve_proyek(conn, kode_proyek, path_workspace)

        # Operasi I/O sistem berkas (baca/tulis team_memory.json & scan manifest) dijalankan
        # DI LUAR transaksi BEGIN IMMEDIATE agar tidak menahan write-lock SQLite.
        if path_workspace:
            info_impor = impor_memori_tim(conn, kode, path_workspace)
            if info_impor.get("solusi_baru", 0) > 0 or info_impor.get("solusi_update", 0) > 0:
                perlu_sinkron_vektor = True
            peringatan_tim = str(info_impor.get("peringatan_keamanan") or "").strip()

        ktp_row = conn.execute(
            """
            SELECT ringkasan_inti, jumlah_token, versi_ktp, waktu_update
            FROM ktp_proyek
            WHERE kode_proyek = ?
            """,
            (kode,),
        ).fetchone()

        if ktp_row is None and path_workspace:
            auto_bootstrap_workspace(conn, kode, path_workspace)

        with transaksi(conn):
            ktp_row = conn.execute(
                """
                SELECT ringkasan_inti, jumlah_token, versi_ktp, waktu_update
                FROM ktp_proyek
                WHERE kode_proyek = ?
                """,
                (kode,),
            ).fetchone()

            # Hitung total token mentah setara dari log yang sudah berstatus processed
            token_mentah_row = conn.execute(
                """
                SELECT COALESCE(SUM(estimasi_token_mentah), 0) AS total_mentah
                FROM antrean_mentah
                WHERE kode_proyek = ? AND status_rangkum = ?
                """,
                (kode, STATUS_PROCESSED),
            ).fetchone()
            token_mentah_setara = int(token_mentah_row["total_mentah"] if token_mentah_row else 0)

            total_pending_row = conn.execute(
                "SELECT COUNT(*) AS jml FROM antrean_mentah WHERE kode_proyek = ? AND status_rangkum = ?",
                (kode, STATUS_PENDING),
            ).fetchone()
            total_pending = int(total_pending_row["jml"] if total_pending_row else 0)

            pending_rows = conn.execute(
                """
                SELECT id, isi_log
                FROM antrean_mentah
                WHERE kode_proyek = ? AND status_rangkum = ?
                ORDER BY id DESC
                LIMIT 2
                """,
                (kode, STATUS_PENDING),
            ).fetchall()

            if ktp_row is None:
                respons = (
                    f"[KTP Proyek '{kode}': Baru Diinisialisasi]\n"
                    f"Belum ada memori terangkum untuk proyek '{kode}'. "
                    f"Silakan kerjakan tugas Anda dan catat milestone dengan titip_catatan_kerja()."
                )
            else:
                info_token = (
                    f"{ktp_row['jumlah_token']} (Elastic)"
                    if settings.ktp_max_tokens <= 0
                    else f"{ktp_row['jumlah_token']}/{settings.ktp_max_tokens}"
                )
                respons = (
                    f"[KTP Proyek: {kode} | Versi: {ktp_row['versi_ktp']} | "
                    f"Token: {info_token} | Update: {ktp_row['waktu_update']}]\n"
                    f"{ktp_row['ringkasan_inti']}"
                )
                if pending_rows:
                    cuplikan = "; ".join(
                        f"#{r['id']}: {str(r['isi_log']).splitlines()[0][:100]}" for r in pending_rows
                    )
                    respons += f"\n[Hot-Buffer Pending ({total_pending} catatan): {cuplikan}]"
            if peringatan_tim:
                respons += f"\n{peringatan_tim}"
            token_aktual = hitung_token(respons)

            catat_metrik(
                conn,
                kode_proyek=kode,
                jenis_aktivitas=AKTIVITAS_READ_KTP,
                token_mentah_setara=token_mentah_setara,
                token_aktual_terpakai=token_aktual,
            )

        if perlu_sinkron_vektor:
            from .embedding import sinkron_vektor_laci_arsip

            sinkron_vektor_laci_arsip(conn, limit=50)

    return respons


# ---------------------------------------------------------------------------
# 2. MCP Resource Pasif: mcp://karjimut/ktp/{kode_proyek} (+ alias sleep-mcp)
# ---------------------------------------------------------------------------
@mcp.resource(
    "mcp://karjimut/ktp/{kode_proyek}",
    name="karjimut_ktp_proyek_resource",
    description="Resource pasif KTP Proyek Karjimut untuk auto-attachment pada klien MCP yang mendukung.",
    mime_type="text/plain",
)
@mcp.resource(
    "mcp://sleep-mcp/ktp/{kode_proyek}",
    name="ktp_proyek_resource",
    description="Resource pasif KTP Proyek untuk auto-attachment pada klien MCP yang mendukung.",
    mime_type="text/plain",
)
def resource_ktp_proyek(kode_proyek: str) -> str:
    """Mengembalikan teks KTP Proyek secara pasif tanpa mencatat metrik sesi aktif."""
    settings = get_settings()
    kode = normalisasi_kode_proyek(kode_proyek)

    with koneksi(settings.db_path) as conn:
        kode = resolve_proyek(conn, kode)
        row = conn.execute(
            "SELECT ringkasan_inti FROM ktp_proyek WHERE kode_proyek = ?", (kode,)
        ).fetchone()

    if row is None:
        return f"Proyek '{kode}' belum memiliki KTP terdaftar."
    return str(row["ringkasan_inti"])


# ---------------------------------------------------------------------------
# 3. MCP Tool: titip_catatan_kerja
# ---------------------------------------------------------------------------
@mcp.tool(
    name="titip_catatan_kerja",
    description=(
        "Panggil otomatis setiap selesai membuat fitur, mengedit kode, atau memperbaiki bug. "
        "Menyimpan ringkasan padat ke antrean konsolidasi idle. Format opsional: "
        "'Identitas: ... Stack: ... Struktur: ... Aturan: ... Solusi: <maks 2 kalimat> #tag1 #tag2'."
    ),
)
def titip_catatan_kerja(
    kode_proyek: str,
    ringkasan_aksi: str,
    estimasi_token_mentah: int | None = None,
    path_workspace: str | None = None,
) -> str:
    """Menerima ringkasan aksi kerja, menghitung estimasi token mentah, dan menyimpan ke antrean."""
    settings = get_settings()
    try:
        normalisasi_kode_proyek(kode_proyek)
    except ValueError as exc:
        return f"[Karjimut] Parameter kode_proyek tidak valid: {exc}"

    isi_log = (ringkasan_aksi or "").replace("\x00", "").strip()
    if not isi_log:
        return "[Karjimut] Ringkasan aksi tidak boleh kosong."
    if len(isi_log) > MAX_LOG_CHARS:
        isi_log = isi_log[:MAX_LOG_CHARS]
    isi_log = _RE_PROMPT_BREAKOUT.sub(r"(\1)", isi_log)
    baris_aman = [b for b in isi_log.splitlines() if not _RE_PROMPT_INJECTION.search(b)]
    isi_log = "\n".join(baris_aman).strip()
    if not isi_log:
        return "[Karjimut] Ringkasan aksi ditolak karena terdeteksi mengandung instruksi manipulatif (prompt injection)."

    estimasi_token = hitung_token(isi_log)
    if estimasi_token_mentah is not None:
        try:
            nilai_mentah = min(int(estimasi_token_mentah), MAX_ESTIMASI_TOKEN)
            if nilai_mentah > estimasi_token:
                estimasi_token = nilai_mentah
        except (TypeError, ValueError):
            pass

    with koneksi(settings.db_path) as conn:
        with transaksi(conn):
            kode = resolve_proyek(conn, kode_proyek, path_workspace)
            cur = conn.execute(
                """
                INSERT INTO antrean_mentah (kode_proyek, isi_log, estimasi_token_mentah, status_rangkum)
                VALUES (?, ?, ?, 0)
                """,
                (kode, isi_log, estimasi_token),
            )
            log_id = cur.lastrowid

            konfirmasi = (
                f"[Karjimut] Milestone tersimpan di antrean mentah (Log #{log_id}, ~{estimasi_token} token). "
                f"Akan dikonsolidasi otomatis pada fase idle berikutnya."
            )
            token_konfirmasi = hitung_token(konfirmasi)

            catat_metrik(
                conn,
                kode_proyek=kode,
                jenis_aktivitas=AKTIVITAS_WRITE_LOG,
                token_mentah_setara=estimasi_token,
                token_aktual_terpakai=token_konfirmasi,
            )

    return konfirmasi


# ---------------------------------------------------------------------------
# 4. MCP Tool: cari_laci_solusi
# ---------------------------------------------------------------------------
@mcp.tool(
    name="cari_laci_solusi",
    description=(
        "Panggil otomatis saat menemui error terminal, kegagalan build/test, atau exception. "
        "Mencari solusi teruji di Laci Arsip (Lapis 2, Hybrid BM25 + Vector RRF) sebelum trial-and-error."
    ),
)
def cari_laci_solusi(kode_proyek: str, kata_kunci: str, path_workspace: str | None = None) -> str:
    """Mencari solusi paten relevan di Laci Arsip menggunakan FTS5 BM25 (maks. 3 hasil)."""
    settings = get_settings()
    try:
        normalisasi_kode_proyek(kode_proyek)
    except ValueError as exc:
        return f"[Karjimut Laci Solusi] Parameter kode_proyek tidak valid: {exc}"

    query = (kata_kunci or "").replace("\x00", "").strip()[:MAX_QUERY_CHARS]
    if not query:
        return "[Karjimut Laci Solusi] Kata kunci pencarian kosong."

    with koneksi(settings.db_path) as conn:
        with transaksi(conn):
            kode = resolve_proyek(conn, kode_proyek, path_workspace)
        hasil = cari_solusi_fts_conn(conn, kode_proyek=kode, kata_kunci=query, limit=3)

        if not hasil:
            respons = (
                f"[Karjimut Laci Solusi: '{kode}'] Tidak ditemukan solusi relevan untuk kata kunci: '{query}'. "
                f"Silakan investigasi mandiri dan titipkan solusinya setelah berhasil."
            )
        else:
            baris_hasil: list[str] = [
                f"[Karjimut Laci Solusi: '{kode}' | Ditemukan {len(hasil)} solusi relevan]"
            ]
            for idx, item in enumerate(hasil, 1):
                info_parts = []
                if item.get("skor_bm25") is not None:
                    info_parts.append(f"BM25: {item['skor_bm25']}")
                if item.get("skor_jarak_vektor") is not None:
                    info_parts.append(f"VecDist: {item['skor_jarak_vektor']}")
                if item.get("skor_rrf") is not None:
                    info_parts.append(f"RRF: {item['skor_rrf']}")
                conf_val = item.get("confidence", 0.7)
                info_parts.append(f"Conf: {conf_val}")
                skor_info = f" | {', '.join(info_parts)}" if info_parts else ""
                baris_hasil.append(
                    f"{idx}. [ID #{item['id']} | {item['tag_masalah']}{skor_info}]\n"
                    f"   Solusi: {item['solusi_paten']}"
                )
            respons = "\n".join(baris_hasil)

        token_aktual = hitung_token(respons)

        with transaksi(conn):
            catat_metrik(
                conn,
                kode_proyek=kode,
                jenis_aktivitas=AKTIVITAS_SEARCH_SOLUSI,
                token_mentah_setara=0,
                token_aktual_terpakai=token_aktual,
            )

    return respons


# ---------------------------------------------------------------------------
# 5. MCP Tool: nilai_solusi (Feedback Loop Pembelajaran Mandiri)
# ---------------------------------------------------------------------------
@mcp.tool(
    name="nilai_solusi",
    description=(
        "Beri feedback (`berhasil=True/False`) pada `id_solusi` dari `cari_laci_solusi` untuk memperbarui "
        "confidence score, menyimpan `catatan` evaluasi ke Laci Arsip & riwayat feedback, dan memperbarui metrik self-assessment."
    ),
)
def nilai_solusi(
    kode_proyek: str,
    id_solusi: int,
    berhasil: bool,
    catatan: str | None = None,
    path_workspace: str | None = None,
) -> str:
    """Feedback loop untuk evaluasi solusi: memperbarui confidence, hit/miss, dan menyimpan catatan evaluasi."""
    settings = get_settings()
    try:
        normalisasi_kode_proyek(kode_proyek)
    except ValueError as exc:
        return f"[Karjimut Feedback] Parameter kode_proyek tidak valid: {exc}"

    catatan_bersih = ""
    if catatan is not None and str(catatan).strip():
        catatan_bersih = normalisasi_spasi(
            bersihkan_injeksi_memori(sanitasi_pesan_error(str(catatan)))
        )[:400]

    with koneksi(settings.db_path) as conn:
        with transaksi(conn):
            kode = resolve_proyek(conn, kode_proyek, path_workspace)
            row = conn.execute(
                "SELECT id, tag_masalah, solusi_paten, confidence, hit_count, miss_count "
                "FROM laci_arsip WHERE id = ? AND kode_proyek = ?",
                (int(id_solusi), kode),
            ).fetchone()
            if row is None:
                return f"[Karjimut Feedback] Solusi #{id_solusi} tidak ditemukan pada proyek '{kode}'."

            conf_lama = float(row["confidence"] if row["confidence"] is not None else 0.7)
            hit_lama = int(row["hit_count"] or 0)
            miss_lama = int(row["miss_count"] or 0)

            if berhasil:
                conf_baru = min(1.0, round(conf_lama + 0.10, 2))
                hit_baru = hit_lama + 1
                miss_baru = miss_lama
                status_teks = "BERHASIL (Confidence meningkat 📈)"
            else:
                conf_baru = max(0.1, round(conf_lama - 0.15, 2))
                hit_baru = hit_lama
                miss_baru = miss_lama + 1
                status_teks = "GAGAL (Confidence diturunkan 📉)"

            is_stale_baru = 1 if conf_baru < 0.35 else 0

            conn.execute(
                """
                UPDATE laci_arsip
                SET confidence = ?,
                    hit_count = ?,
                    miss_count = ?,
                    last_hit = CURRENT_TIMESTAMP,
                    is_stale = ?,
                    catatan_evaluasi = COALESCE(NULLIF(?, ''), catatan_evaluasi)
                WHERE id = ?
                """,
                (conf_baru, hit_baru, miss_baru, is_stale_baru, catatan_bersih, int(id_solusi)),
            )

            conn.execute(
                """
                INSERT INTO riwayat_feedback
                    (solusi_id, kode_proyek, berhasil, confidence_sebelum, confidence_sesudah, catatan)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (int(id_solusi), kode, 1 if berhasil else 0, conf_lama, conf_baru, catatan_bersih or None),
            )

            # Catat snapshot evaluasi terbaru ke log pembelajaran
            perbarui_log_pembelajaran(conn, kode)

    info_catatan = f" | Catatan: {catatan_bersih}" if catatan_bersih else ""
    return (
        f"[Karjimut Feedback #{id_solusi}] Status: {status_teks} | "
        f"Confidence: {conf_lama} -> {conf_baru} | Hits: {hit_baru} | Misses: {miss_baru}{info_catatan}"
    )


# ---------------------------------------------------------------------------
# 6. Fungsi Alias Python Internal (Tanpa duplikasi skema @mcp.tool agar hemat token konteks)
# ---------------------------------------------------------------------------
def baca_core_proyek(kode_proyek: str, path_workspace: str | None = None) -> str:
    """Customer-friendly alias untuk membaca Core Proyek (Lapis 1)."""
    return baca_ktp_proyek(kode_proyek=kode_proyek, path_workspace=path_workspace)


def simpan_catatan_kerja(
    kode_proyek: str,
    ringkasan_aksi: str,
    estimasi_token_mentah: int | None = None,
    path_workspace: str | None = None,
) -> str:
    """Customer-friendly alias untuk menyimpan catatan kerja ke antrean konsolidasi."""
    return titip_catatan_kerja(
        kode_proyek=kode_proyek,
        ringkasan_aksi=ringkasan_aksi,
        estimasi_token_mentah=estimasi_token_mentah,
        path_workspace=path_workspace,
    )


def cari_solusi(kode_proyek: str, kata_kunci: str, path_workspace: str | None = None) -> str:
    """Customer-friendly alias untuk mencari solusi paten di Bank Solusi."""
    return cari_laci_solusi(
        kode_proyek=kode_proyek,
        kata_kunci=kata_kunci,
        path_workspace=path_workspace,
    )


def start_server(transport: str = "stdio") -> None:
    """Menjalankan server FastMCP."""
    settings = get_settings()
    pastikan_db(settings.db_path)

    global _embedded_watcher
    if settings.embedded_watcher_mcp:
        _embedded_watcher = IdleWatcherDaemon(db_path=settings.db_path)
        _embedded_watcher.start(daemon=True)
        logger.info("Embedded IdleWatcher berjalan di background.")

    logger.info("Memulai Karjimut FastMCP server (transport=%s)...", transport)
    mcp.run(transport=transport)


def main() -> None:
    """CLI runner untuk server MCP."""
    parser = argparse.ArgumentParser(description="Karjimut MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protokol MCP (default: stdio)",
    )
    args = parser.parse_args()
    start_server(transport=args.transport)


if __name__ == "__main__":
    main()
