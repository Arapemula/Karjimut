"""Background daemon pemantau waktu idle untuk arsitektur Sleep-MCP.

Daemon ini secara periodik memantau tabel `antrean_mentah`.
Jika terdeteksi suatu proyek memiliki antrean berstatus pending (`status_rangkum = 0`)
dan selisih waktu antara saat ini dengan `MAX(waktu_masuk)` pada proyek tersebut
telah mencapai atau melampaui `IDLE_TIMEOUT_SECONDS` (default 300 detik / 5 menit),
maka konsolidasi fase idle (Sleep Cycle) akan otomatis dipicu untuk proyek tersebut.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any

from .config import (
    STATUS_PENDING,
    STATUS_PROCESSING,
    get_settings,
    setup_logging,
)
from .consolidator import jalankan_sleep_cycle_tuntas
from .db import koneksi, normalisasi_kode_proyek

logger = setup_logging("sleep_mcp.idle_watcher")

# Pelacak exponential backoff per proyek: kode_proyek -> (jumlah_gagal_beruntun, monotonic_next_retry)
_backoff_lock = threading.Lock()
_backoff_state: dict[str, tuple[int, float]] = {}


def reset_idle_backoff(kode_proyek: str | None = None) -> None:
    """Mereset state exponential backoff (seluruh proyek atau satu proyek)."""
    with _backoff_lock:
        if kode_proyek is None:
            _backoff_state.clear()
        else:
            _backoff_state.pop(normalisasi_kode_proyek(kode_proyek), None)

_SQL_COUNTS_ANTREAN = """
    SELECT
        SUM(CASE WHEN status_rangkum = 0 THEN 1 ELSE 0 END) AS pending,
        SUM(CASE WHEN status_rangkum = 1 THEN 1 ELSE 0 END) AS processing,
        SUM(CASE WHEN status_rangkum = 2 THEN 1 ELSE 0 END) AS processed,
        MAX(CASE WHEN status_rangkum = 0 THEN waktu_masuk ELSE NULL END) AS max_waktu_pending,
        MAX(waktu_masuk) AS max_waktu_terakhir
    FROM antrean_mentah
    WHERE kode_proyek = ?
"""


def hitung_status_siklus_proyek(
    kode_proyek: str,
    db_path: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Menghitung status siklus real-time untuk sebuah proyek.

    Nilai status:
    - 'SLEEPING': jika ada batch yang sedang diproses (status_rangkum = 1).
    - 'WORKING': jika log terakhir masuk dalam jendela WORKING_WINDOW_SECONDS.
    - 'IDLE_COUNTDOWN': jika ada log pending dan sedang menghitung mundur ke 5 menit.
    - 'STANDBY': jika antrean pending kosong (semua log sudah diproses).

    Returns:
        dict berisi info status, sisa_detik_countdown, dan statistik antrean.
    """
    kode = normalisasi_kode_proyek(kode_proyek)
    settings = get_settings()

    if conn is not None:
        counts = conn.execute(_SQL_COUNTS_ANTREAN, (kode,)).fetchone()
    else:
        with koneksi(db_path) as active_conn:
            counts = active_conn.execute(_SQL_COUNTS_ANTREAN, (kode,)).fetchone()

    pending_count = int(counts["pending"] or 0)
    processing_count = int(counts["processing"] or 0)
    processed_count = int(counts["processed"] or 0)
    max_waktu_str = counts["max_waktu_pending"] or counts["max_waktu_terakhir"]

    detik_sejak_log = 0.0
    if max_waktu_str:
        try:
            # Format SQLite CURRENT_TIMESTAMP: 'YYYY-MM-DD HH:MM:SS'
            waktu_log = datetime.fromisoformat(max_waktu_str)
            # SQLite CURRENT_TIMESTAMP disimpan dalam UTC
            sekarang_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            detik_sejak_log = max(0.0, (sekarang_utc - waktu_log).total_seconds())
        except Exception:
            detik_sejak_log = 0.0

    sisa_countdown = max(0, int(settings.idle_timeout_seconds - detik_sejak_log))

    if processing_count > 0:
        status = "SLEEPING"
        label = "Sleeping (Batch Processing)"
    elif pending_count > 0:
        if detik_sejak_log < settings.working_window_seconds:
            status = "WORKING"
            label = "Working (Aktivitas Baru Terdeteksi)"
        else:
            status = "IDLE_COUNTDOWN"
            label = f"Idle Countdown ({sisa_countdown}s menuju Sleep)"
    else:
        status = "STANDBY"
        label = "Standby (Semua Log Terkonsolidasi)"

    return {
        "kode_proyek": kode,
        "status": status,
        "label": label,
        "detik_sejak_log_terakhir": round(detik_sejak_log, 1),
        "sisa_countdown_detik": sisa_countdown,
        "idle_timeout_detik": settings.idle_timeout_seconds,
        "antrean": {
            "pending": pending_count,
            "processing": processing_count,
            "processed": processed_count,
            "total": pending_count + processing_count + processed_count,
        },
    }


def periksa_dan_konsolidasi_idle(db_path: str | None = None) -> list[dict[str, Any]]:
    """Memeriksa seluruh proyek yang memiliki antrean pending dan telah idle >= timeout.

    Jika memenuhi syarat, langsung jalankan Sleep Cycle untuk proyek terkait.
    """
    settings = get_settings()
    timeout = settings.idle_timeout_seconds
    hasil_eksekusi: list[dict[str, Any]] = []

    # Ambil kandidat proyek dengan status_rangkum = 0 dan belum ada batch aktif (status 1 yang belum stale)
    # Menggunakan datetime('now', '-N seconds') pada SQLite UTC
    stale_menit = settings.stale_lock_minutes
    with koneksi(db_path) as conn:
        kandidat = conn.execute(
            """
            SELECT kode_proyek, MAX(waktu_masuk) as log_terakhir, COUNT(*) as jml_pending
            FROM antrean_mentah
            WHERE status_rangkum = ?
              AND kode_proyek NOT IN (
                  SELECT DISTINCT kode_proyek
                  FROM antrean_mentah
                  WHERE status_rangkum = ?
                    AND waktu_kunci > datetime('now', ?)
              )
            GROUP BY kode_proyek
            HAVING MAX(waktu_masuk) <= datetime('now', ?)
            """,
            (STATUS_PENDING, STATUS_PROCESSING, f"-{int(stale_menit)} minutes", f"-{int(timeout)} seconds"),
        ).fetchall()

    sekarang_mono = time.monotonic()
    for baris in kandidat:
        kode = baris["kode_proyek"]
        jml = baris["jml_pending"]
        with _backoff_lock:
            gagal_sebelumnya, next_retry = _backoff_state.get(kode, (0, 0.0))
        if sekarang_mono < next_retry:
            logger.debug(
                "Proyek '%s' sedang dalam masa backoff (sisa %.1fs setelah %dx gagal).",
                kode,
                next_retry - sekarang_mono,
                gagal_sebelumnya,
            )
            continue

        # Setelah >= 2 kegagalan LLM berturut-turut, otomatis paksa fallback distiller lokal
        # agar antrean tidak macet dan tidak membakar kuota API berulang-ulang.
        paksa_lokal = True if gagal_sebelumnya >= 2 else None
        logger.info(
            "Proyek '%s' idle selama >= %d detik dengan %d log pending. Memulai Sleep Cycle...",
            kode,
            timeout,
            jml,
        )
        try:
            hasil_list = jalankan_sleep_cycle_tuntas(kode, db_path=db_path, paksa_lokal=paksa_lokal)
            ada_error = False
            for h in hasil_list:
                hasil_eksekusi.append(h.to_dict())
                if h.status == "ERROR":
                    ada_error = True
            with _backoff_lock:
                if ada_error:
                    gagal_baru = gagal_sebelumnya + 1
                    jeda = min(1800.0, 30.0 * (2 ** (gagal_baru - 1)))
                    _backoff_state[kode] = (gagal_baru, time.monotonic() + jeda)
                    logger.warning(
                        "Sleep Cycle '%s' gagal (%dx). Retry berikutnya ditunda %.0f detik.",
                        kode,
                        gagal_baru,
                        jeda,
                    )
                else:
                    _backoff_state.pop(kode, None)
        except Exception as exc:
            with _backoff_lock:
                gagal_baru = gagal_sebelumnya + 1
                jeda = min(1800.0, 30.0 * (2 ** (gagal_baru - 1)))
                _backoff_state[kode] = (gagal_baru, time.monotonic() + jeda)
            logger.exception("Gagal menjalankan Sleep Cycle otomatis untuk '%s': %s", kode, exc)

    return hasil_eksekusi


class IdleWatcherDaemon:
    """Daemon thread/proses pemantau idle."""

    def __init__(self, db_path: str | None = None, interval: int | None = None) -> None:
        self.db_path = db_path
        self.interval = interval or get_settings().idle_poll_interval_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, daemon: bool = True) -> None:
        """Menjalankan loop pemantauan dalam background thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=daemon, name="SleepMCP-IdleWatcher")
        self._thread.start()
        logger.info("IdleWatcherDaemon dimulai (interval=%d detik).", self.interval)

    def stop(self, timeout: float = 5.0) -> None:
        """Menghentikan daemon pemantauan."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            logger.info("IdleWatcherDaemon dihentikan.")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                periksa_dan_konsolidasi_idle(self.db_path)
            except Exception as exc:
                logger.error("Error dalam periksa_dan_konsolidasi_idle: %s", exc)
            self._stop_event.wait(self.interval)


def main() -> None:
    """Entry point CLI untuk menjalankan idle watcher secara mandiri."""
    parser = argparse.ArgumentParser(description="Sleep-MCP Background Idle Watcher Daemon")
    parser.add_argument("--interval", type=int, default=None, help="Polling interval dalam detik")
    parser.add_argument("--db-path", type=str, default=None, help="Path ke database SQLite")
    args = parser.parse_args()

    daemon = IdleWatcherDaemon(db_path=args.db_path, interval=args.interval)
    logger.info("Menjalankan Sleep-MCP Idle Watcher standalone. Tekan Ctrl+C untuk berhenti.")
    daemon.start(daemon=True)
    try:
        while daemon.is_running():
            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.info("Sinyal interupsi (Ctrl+C) diterima, menghentikan Idle Watcher...")
    finally:
        daemon.stop()


if __name__ == "__main__":
    main()
