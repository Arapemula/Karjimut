"""Modul deduplikasi Laci Arsip Solusi, auto-supersede, memory decay, dan sinkronisasi tim/workspace."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config import STATUS_PROCESSED, get_settings, setup_logging
from .db import normalisasi_kode_proyek, resolve_proyek, transaksi
from .embedding import simpan_vektor_solusi
from .fts_search import normalisasi_tag
from .ktp_manager import (
    identitas_bermakna,
    susun_ktp_terbatas,
    terapkan_ktp_baru,
    urai_ktp,
)
from .log_parser import (
    JACCARD_THRESHOLD,
    MAX_TAG_PER_ARSIP,
    MIN_TAG_OVERLAP,
    _RE_CREDENTIAL_REDACT,
    _RE_PROMPT_BREAKOUT,
    _RE_PROMPT_INJECTION,
    _TAG_GENERIK_DEDUP,
    _batas_aturan_aktif,
    _gabung_unik,
    _kata_kunci_aturan,
    _tutup,
    bersihkan_injeksi_memori,
    deteksi_teknologi,
    gabung_aturan,
    jaccard_similarity,
    layak_masuk_laci_arsip,
)
from .tokenizer_utils import batasi_kalimat, normalisasi_spasi, pecah_kalimat

logger = setup_logging("sleep_mcp.archive_manager")

_BLACKLIST_WORKSPACE_SEGMENTS = (".git", "node_modules", ".venv", "venv", "__pycache__", "private", "secrets")
_MANIFEST_FILES = (
    "pyproject.toml",
    "package.json",
    "requirements.txt",
    "pubspec.yaml",
    "go.mod",
    "Cargo.toml",
)
_CORE_DIRS_CANDIDATES = (
    "src", "app", "lib", "api", "services", "components", "models",
    "controllers", "routes", "migrations", "tests", "cmd", "pkg", "scripts",
)
_ABAIKAN_SUBDIR: frozenset[str] = frozenset(
    {
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        "dist",
        "build",
        "data",
        "target",
        "docs-private",
        "private",
        "secrets",
    }
)

_TEAM_SECRET_ENV_KEY = "KARJIMUT_TEAM_SECRET"
_TEAM_SIGNATURE_PREFIX = "hmac-sha256:"
_RE_TEAM_SIGNATURE_HEX = re.compile(r"^hmac-sha256:[0-9a-f]{64}$")
_TEAM_MEMORY_ALLOWED_KEYS: frozenset[str] = frozenset(
    {"schema_version", "kode_proyek", "versi_ktp", "ringkasan_inti", "arsip_solusi", "signature"}
)
_TEAM_SOLUTION_ALLOWED_KEYS: frozenset[str] = frozenset(
    {"tag_masalah", "solusi_paten", "confidence"}
)
_MAX_TEAM_FILE_BYTES = 512 * 1024
_MAX_TEAM_KTP_CHARS = 8000
_MAX_TEAM_SOLUSI_COUNT = 200
_MAX_TEAM_SOLUSI_CHARS = 1500


def gabung_solusi_paten(solusi_lama: str, solusi_baru: str) -> str:
    """Menggabungkan solusi lama dan solusi baru secara non-destruktif (maks. 2-3 kalimat)."""
    lama = normalisasi_spasi(str(solusi_lama or "")).strip()
    baru = normalisasi_spasi(str(solusi_baru or "")).strip()
    batas = 3 if ("`" in lama or "`" in baru) else 2
    if not lama:
        return batasi_kalimat(baru, batas)
    if not baru:
        return batasi_kalimat(lama, batas)
    if lama.lower() in baru.lower():
        return batasi_kalimat(baru, batas)
    if baru.lower() in lama.lower():
        return batasi_kalimat(lama, batas)
    kata_lama = _kata_kunci_aturan(lama)
    kata_baru = _kata_kunci_aturan(baru)
    if kata_lama and kata_baru and jaccard_similarity(kata_lama, kata_baru) >= 0.55:
        return batasi_kalimat(baru, batas)
    kal_lama = pecah_kalimat(lama)
    kal_baru = pecah_kalimat(baru)
    inti_lama = _tutup(kal_lama[-1]) if kal_lama else _tutup(lama)
    inti_baru = _tutup(kal_baru[0]) if kal_baru else _tutup(baru)
    return batasi_kalimat(f"{inti_lama} {inti_baru}", batas)


def terapkan_memory_decay(
    conn: sqlite3.Connection,
    kode_proyek: str,
    hari_threshold: int = 14,
    faktor_decay: float = 0.98,
    interval_decay_hari: int = 7,
) -> int:
    """Meluruhkan confidence solusi yang tidak pernah diakses/digunakan berbasis waktu kalender.

    Peluruhan hanya terjadi apabila solusi sudah tidak diakses selama >= ``hari_threshold`` hari
    (dihitung dari ``COALESCE(last_hit, waktu_dibuat)``) DAN belum pernah mengalami decay dalam
    ``interval_decay_hari`` terakhir, sehingga frekuensi pemicuan Sleep Cycle harian tidak
    mempercepat peluruhan secara artifisial.
    """
    try:
        cur = conn.execute(
            """
            UPDATE laci_arsip
            SET confidence = MAX(0.2, ROUND(confidence * ?, 2)),
                is_stale = CASE WHEN ROUND(confidence * ?, 2) < 0.35 THEN 1 ELSE 0 END,
                last_decay = CURRENT_TIMESTAMP
            WHERE kode_proyek = ?
              AND COALESCE(last_hit, waktu_dibuat) <= datetime('now', ?)
              AND (last_decay IS NULL OR last_decay <= datetime('now', ?))
              AND confidence > 0.25
            """,
            (
                faktor_decay,
                faktor_decay,
                kode_proyek,
                f"-{int(hari_threshold)} days",
                f"-{int(interval_decay_hari)} days",
            ),
        )
        return cur.rowcount or 0
    except sqlite3.Error as exc:
        logger.debug("Memory decay dilewati: %s", exc)
        return 0


def kompaksi_antrean_lama(
    conn: sqlite3.Connection,
    kode_proyek: str,
    max_processed_rows: int = 500,
) -> int:
    """Memadatkan isi_log lama yang sudah selesai dirangkum (status=2) agar ukuran DB tetap ramping."""
    try:
        cur = conn.execute(
            """
            UPDATE antrean_mentah
            SET isi_log = '[compacted]'
            WHERE kode_proyek = ?
              AND status_rangkum = ?
              AND isi_log != '[compacted]'
              AND id NOT IN (
                  SELECT id FROM antrean_mentah
                  WHERE kode_proyek = ? AND status_rangkum = ?
                  ORDER BY id DESC
                  LIMIT ?
              )
            """,
            (kode_proyek, STATUS_PROCESSED, kode_proyek, STATUS_PROCESSED, int(max_processed_rows)),
        )
        return cur.rowcount or 0
    except sqlite3.Error as exc:
        logger.debug("Kompaksi antrean lama dilewati: %s", exc)
        return 0


def perbarui_log_pembelajaran(conn: sqlite3.Connection, kode_proyek: str) -> dict[str, Any]:
    """Menghitung ringkasan metrik evolusi pembelajaran mandiri proyek."""
    try:
        ada_tabel = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='log_pembelajaran'"
        ).fetchone()
        if not ada_tabel:
            return {}

        row = conn.execute(
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
            (kode_proyek,),
        ).fetchone()

        avg_conf = round(float(row["avg_conf"]), 3)
        total_hit = int(row["total_hit"])
        total_miss = int(row["total_miss"])
        total_pencarian = total_hit + total_miss

        conn.execute(
            """
            INSERT INTO log_pembelajaran (kode_proyek, total_pencarian, total_hit, total_sukses, total_gagal, confidence_rata2)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (kode_proyek, total_pencarian, total_hit, total_hit, total_miss, avg_conf),
        )

        return {
            "total_solusi": int(row["total_solusi"]),
            "avg_confidence": avg_conf,
            "total_hit": total_hit,
            "total_miss": total_miss,
            "total_proven": int(row["total_proven"]),
            "total_stale": int(row["total_stale"]),
        }
    except sqlite3.Error as exc:
        logger.debug("Perbarui log pembelajaran dilewati: %s", exc)
        return {}


def simpan_arsip_deduplikasi(
    conn: sqlite3.Connection,
    kode_proyek: str,
    item: dict[str, Any],
    sync_vektor: bool = True,
) -> dict[str, Any]:
    """INSERT/UPDATE satu solusi dengan aturan deduplikasi deterministik, vector embedding, & auto-supersede."""
    tags_baru = normalisasi_tag(item.get("tag_masalah"))
    teks_mentah = bersihkan_injeksi_memori(str(item.get("solusi_paten") or ""))
    batas_kal = 3 if "`" in teks_mentah else 2
    solusi = batasi_kalimat(teks_mentah, batas_kal)
    if not tags_baru or not solusi:
        return {"aksi": "SKIP", "id": None, "alasan": "tag/solusi kosong"}
    if not layak_masuk_laci_arsip(solusi, tags_baru):
        return {"aksi": "SKIP", "id": None, "alasan": "bukan solusi teknis konkret"}

    def _apakah_usang(row: sqlite3.Row) -> bool:
        conf = float(row["confidence"] if row["confidence"] is not None else 0.7)
        stale = int(row["is_stale"] or 0)
        return stale == 1 or conf < 0.45

    def _supersede_usang(row_usang: sqlite3.Row, alasan: str) -> dict[str, Any]:
        old_id = int(row_usang["id"])
        tags_lama = normalisasi_tag(row_usang["tag_masalah"])
        gabungan = (tags_baru + [t for t in tags_lama if t not in tags_baru])[:MAX_TAG_PER_ARSIP]
        tag_final = ", ".join(gabungan)
        conn.execute("UPDATE laci_arsip SET is_stale = 1 WHERE id = ?", (old_id,))
        cur = conn.execute(
            """
            INSERT INTO laci_arsip (kode_proyek, tag_masalah, solusi_paten, confidence, is_stale)
            VALUES (?, ?, ?, 0.75, 0)
            """,
            (kode_proyek, tag_final, solusi),
        )
        new_id = int(cur.lastrowid)
        if sync_vektor:
            simpan_vektor_solusi(conn, new_id, tag_final, solusi)
        try:
            conn.execute(
                "INSERT OR IGNORE INTO relasi_solusi (source_id, target_id, relasi) VALUES (?, ?, 'SUPERSEDED')",
                (new_id, old_id),
            )
        except sqlite3.Error as exc:
            logger.debug("Catat relasi auto-SUPERSEDED dilewati: %s", exc)
        return {
            "aksi": "INSERT",
            "id": new_id,
            "alasan": alasan,
            "supersedes_id": old_id,
            "tag_masalah": tag_final,
            "solusi_paten": solusi,
        }

    def _update(row: sqlite3.Row, alasan: str, skor: float | None = None, irisan: int | None = None) -> dict[str, Any]:
        if _apakah_usang(row):
            return _supersede_usang(row, f"auto_supersede_{alasan}")
        tags_lama = normalisasi_tag(row["tag_masalah"])
        gabungan = (tags_lama + [t for t in tags_baru if t not in tags_lama])[:MAX_TAG_PER_ARSIP]
        solusi_gabungan = gabung_solusi_paten(row["solusi_paten"], solusi)
        row_id = int(row["id"])
        conn.execute(
            """
            UPDATE laci_arsip
            SET tag_masalah = ?, solusi_paten = ?, embedding_backend = NULL, waktu_dibuat = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (", ".join(gabungan), solusi_gabungan, row_id),
        )
        if sync_vektor:
            simpan_vektor_solusi(conn, row_id, ", ".join(gabungan), solusi_gabungan)

        supersedes_id = item.get("supersedes_id")
        if supersedes_id and int(supersedes_id) != row_id:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO relasi_solusi (source_id, target_id, relasi) VALUES (?, ?, 'SUPERSEDED')",
                    (row_id, int(supersedes_id)),
                )
            except sqlite3.Error as exc:
                logger.debug("Catat relasi SUPERSEDED dilewati: %s", exc)

        return {
            "aksi": "UPDATE",
            "id": row_id,
            "alasan": alasan,
            "jaccard": skor,
            "irisan": irisan,
            "tag_masalah": ", ".join(gabungan),
            "solusi_paten": solusi_gabungan,
        }

    target = item.get("id_arsip_target")
    if target is not None:
        row = conn.execute(
            """
            SELECT id, tag_masalah, solusi_paten,
                   COALESCE(confidence, 0.7) AS confidence,
                   COALESCE(is_stale, 0) AS is_stale
            FROM laci_arsip WHERE id = ? AND kode_proyek = ?
            """,
            (int(target), kode_proyek),
        ).fetchone()
        if row is not None:
            return _update(row, "id_arsip_target")

    set_baru_all = set(tags_baru)
    set_baru = set_baru_all - _TAG_GENERIK_DEDUP
    if not set_baru:
        set_baru = set_baru_all
    terbaik_aktif: tuple[float, int, sqlite3.Row] | None = None
    terbaik_usang: tuple[float, int, sqlite3.Row] | None = None
    for row in conn.execute(
        """
        SELECT id, tag_masalah, solusi_paten,
               COALESCE(confidence, 0.7) AS confidence,
               COALESCE(is_stale, 0) AS is_stale
        FROM laci_arsip WHERE kode_proyek = ?
        """,
        (kode_proyek,),
    ):
        set_lama_all = set(normalisasi_tag(row["tag_masalah"]))
        set_lama = (set_lama_all - _TAG_GENERIK_DEDUP) or set_lama_all
        irisan = len(set_baru & set_lama)
        skor = jaccard_similarity(set_baru, set_lama)
        if skor >= JACCARD_THRESHOLD or irisan >= MIN_TAG_OVERLAP:
            if _apakah_usang(row):
                if terbaik_usang is None or (skor, irisan) > (terbaik_usang[0], terbaik_usang[1]):
                    terbaik_usang = (skor, irisan, row)
            else:
                if terbaik_aktif is None or (skor, irisan) > (terbaik_aktif[0], terbaik_aktif[1]):
                    terbaik_aktif = (skor, irisan, row)
    if terbaik_aktif is not None:
        return _update(terbaik_aktif[2], "jaccard_tag_overlap", round(terbaik_aktif[0], 4), terbaik_aktif[1])
    if terbaik_usang is not None:
        return _supersede_usang(terbaik_usang[2], "auto_supersede_jaccard")

    try:
        conf_awal = max(0.1, min(1.0, round(float(item.get("confidence") or 0.7), 2)))
    except (TypeError, ValueError):
        conf_awal = 0.7
    cur = conn.execute(
        "INSERT INTO laci_arsip (kode_proyek, tag_masalah, solusi_paten, confidence) VALUES (?, ?, ?, ?)",
        (kode_proyek, ", ".join(tags_baru), solusi, conf_awal),
    )
    new_id = int(cur.lastrowid)
    if sync_vektor:
        simpan_vektor_solusi(conn, new_id, ", ".join(tags_baru), solusi)

    supersedes_id = item.get("supersedes_id")
    if supersedes_id:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO relasi_solusi (source_id, target_id, relasi) VALUES (?, ?, 'SUPERSEDED')",
                (new_id, int(supersedes_id)),
            )
        except sqlite3.Error as exc:
            logger.debug("Catat relasi SUPERSEDED dilewati: %s", exc)

    caused_by_id = item.get("caused_by_id")
    if caused_by_id:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO relasi_solusi (source_id, target_id, relasi) VALUES (?, ?, 'CAUSED_BY')",
                (new_id, int(caused_by_id)),
            )
        except sqlite3.Error as exc:
            logger.debug("Catat relasi CAUSED_BY dilewati: %s", exc)

    return {"aksi": "INSERT", "id": new_id, "alasan": "solusi baru", "tag_masalah": ", ".join(tags_baru)}


def _path_workspace_diizinkan(path_ws: Path) -> bool:
    """Memastikan path workspace valid dan tidak melanggar daftar hitam privasi."""
    try:
        norm_parts = set(str(path_ws.resolve()).lower().replace("\\", "/").split("/"))
        if any(seg in norm_parts for seg in _BLACKLIST_WORKSPACE_SEGMENTS):
            return False
        return path_ws.is_dir()
    except OSError:
        return False


@contextmanager
def _transaksi_jika_perlu(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Membuka transaksi BEGIN IMMEDIATE hanya jika koneksi belum berada di dalam transaksi."""
    if conn.in_transaction:
        yield conn
    else:
        with transaksi(conn):
            yield conn


def _baca_var_env_workspace(env_path: Path, nama_var: str) -> str:
    """Membaca satu variabel env secara terisolasi tanpa menyentuh kredensial lain."""
    if not env_path.is_file() or env_path.is_symlink():
        return ""
    try:
        for baris in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            bersih = baris.strip()
            if not bersih or bersih.startswith("#"):
                continue
            if bersih.startswith("export "):
                bersih = bersih[7:].strip()
            m = re.match(rf"^{re.escape(nama_var)}\s*=\s*(.*)$", bersih)
            if not m:
                continue
            val = m.group(1).strip()
            m_q = re.match(r'^([\'"])(.*)\1(?:\s+#.*)?$', val)
            if m_q:
                val = m_q.group(2).strip()
            else:
                if " #" in val:
                    val = val.split(" #", 1)[0].strip()
            if val:
                return val
    except OSError as exc:
        logger.debug("Pembacaan %s dari %s dilewati: %s", nama_var, env_path, exc)
    return ""


def ambil_team_secret(path_workspace: str | None = None) -> str:
    """Meresolusi kunci rahasia tim per-workspace terlebih dahulu, lalu fallback ke konfigurasi global."""
    if path_workspace:
        ws = Path(str(path_workspace).strip())
        if _path_workspace_diizinkan(ws):
            for kandidat in (ws / ".karjimut" / ".team_secret", ws / ".sleep-mcp" / ".team_secret"):
                if kandidat.is_file() and not kandidat.is_symlink():
                    try:
                        if kandidat.stat().st_size <= 4096:
                            isi = kandidat.read_text(encoding="utf-8", errors="ignore").strip()
                            if isi:
                                return isi
                    except OSError:
                        pass
            val_ws_env = _baca_var_env_workspace(ws / ".env", _TEAM_SECRET_ENV_KEY)
            if val_ws_env:
                return val_ws_env
    return get_settings().team_secret


def _strict_signature_diwajibkan(ws: Path | None) -> bool:
    """True jika mode wajib tanda tangan HMAC aktif di environment global atau ``.env`` workspace."""
    if get_settings().require_team_signature:
        return True
    if ws is not None:
        ws_val = _baca_var_env_workspace(ws / ".env", "KARJIMUT_REQUIRE_TEAM_SIGNATURE").lower()
        if ws_val in ("1", "true", "yes", "on"):
            return True
    return False


def _kanonisasi_payload_tim(payload: dict[str, Any]) -> bytes:
    """Menyusun byte JSON deterministik untuk penandatanganan HMAC team_memory.json."""
    arsip_kanonik = []
    for item in payload.get("arsip_solusi") or []:
        if not isinstance(item, dict):
            continue
        arsip_kanonik.append(
            {
                "confidence": round(float(item.get("confidence", 0.7)), 2),
                "solusi_paten": str(item.get("solusi_paten") or ""),
                "tag_masalah": str(item.get("tag_masalah") or ""),
            }
        )
    objek = {
        "arsip_solusi": arsip_kanonik,
        "kode_proyek": str(payload.get("kode_proyek") or ""),
        "ringkasan_inti": str(payload.get("ringkasan_inti") or ""),
        "schema_version": int(payload.get("schema_version", 1)),
        "versi_ktp": int(payload.get("versi_ktp", 1)),
    }
    return json.dumps(
        objek,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def hitung_signature_tim(payload: dict[str, Any], secret: str) -> str:
    """Menghitung tanda tangan HMAC-SHA256 kanonik untuk payload ``team_memory.json``."""
    kunci = str(secret or "").strip()
    if not kunci:
        raise ValueError("Kunci rahasia tim (KARJIMUT_TEAM_SECRET) tidak boleh kosong.")
    pesan = _kanonisasi_payload_tim(payload)
    digest = hmac.new(kunci.encode("utf-8"), pesan, hashlib.sha256).hexdigest()
    return f"{_TEAM_SIGNATURE_PREFIX}{digest}"


def verifikasi_signature_tim(payload: dict[str, Any], secret: str) -> bool:
    """Memverifikasi signature HMAC-SHA256 secara constant-time terhadap payload tim."""
    sig = payload.get("signature")
    if not isinstance(sig, str) or not _RE_TEAM_SIGNATURE_HEX.match(sig.strip()):
        return False
    try:
        expected = hitung_signature_tim(payload, secret)
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(expected, sig.strip())


def _cek_teks_berbahaya_tim(label: str, teks: str) -> list[str]:
    """Mendaur ulang detektor injeksi, tag breakout, dan kebocoran kredensial untuk audit team_memory."""
    temuan: list[str] = []
    if _RE_PROMPT_INJECTION.search(teks):
        temuan.append(f"{label} mengandung pola instruksi manipulatif / pelemahan keamanan.")
    if _RE_PROMPT_BREAKOUT.search(teks):
        temuan.append(f"{label} mengandung token pembatas prompt ilegal (breakout marker).")
    if _RE_CREDENTIAL_REDACT.search(teks):
        temuan.append(f"{label} terindikasi mengandung kredensial atau API key sensitif.")
    return temuan


def validasi_skema_team_memory(data: Any, periksa_konten: bool = True) -> list[str]:
    """Memvalidasi skema JSON ketat ``team_memory.json`` (allowlist, tipe, batas ukuran, dan konten)."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Root payload team_memory.json wajib berupa objek JSON (dict)."]

    unknown_top = sorted(set(data.keys()) - _TEAM_MEMORY_ALLOWED_KEYS)
    if unknown_top:
        errors.append(f"Field asing tidak diizinkan pada root JSON: {', '.join(unknown_top)}")

    sv = data.get("schema_version")
    if isinstance(sv, bool) or not isinstance(sv, int) or sv != 1:
        errors.append("Field 'schema_version' wajib integer bernilai 1.")

    kode_raw = data.get("kode_proyek")
    if not isinstance(kode_raw, str) or not kode_raw.strip() or len(kode_raw) > 100:
        errors.append("Field 'kode_proyek' wajib string non-kosong (maks. 100 karakter).")

    versi = data.get("versi_ktp")
    if isinstance(versi, bool) or not isinstance(versi, int) or versi < 1:
        errors.append("Field 'versi_ktp' wajib integer positif (>= 1).")

    ktp = data.get("ringkasan_inti")
    if not isinstance(ktp, str):
        errors.append("Field 'ringkasan_inti' wajib berupa string.")
    elif len(ktp) > _MAX_TEAM_KTP_CHARS:
        errors.append(f"Field 'ringkasan_inti' melebihi batas aman {_MAX_TEAM_KTP_CHARS} karakter.")
    elif periksa_konten and ktp:
        errors.extend(_cek_teks_berbahaya_tim("ringkasan_inti", ktp))

    sig = data.get("signature")
    if sig is not None and (not isinstance(sig, str) or not _RE_TEAM_SIGNATURE_HEX.match(sig.strip())):
        errors.append("Format field 'signature' tidak valid (wajib 'hmac-sha256:<64 hex>').")

    arsip = data.get("arsip_solusi", [])
    if not isinstance(arsip, list):
        errors.append("Field 'arsip_solusi' wajib berupa array JSON.")
    elif len(arsip) > _MAX_TEAM_SOLUSI_COUNT:
        errors.append(f"Jumlah entri 'arsip_solusi' melebihi batas {_MAX_TEAM_SOLUSI_COUNT} item.")
    else:
        for idx, item in enumerate(arsip, 1):
            if not isinstance(item, dict):
                errors.append(f"arsip_solusi[{idx}] wajib berupa objek JSON.")
                continue
            unknown_item = sorted(set(item.keys()) - _TEAM_SOLUTION_ALLOWED_KEYS)
            if unknown_item:
                errors.append(f"Field asing pada arsip_solusi[{idx}]: {', '.join(unknown_item)}")
            tag = item.get("tag_masalah")
            sol = item.get("solusi_paten")
            if not isinstance(tag, str) or not tag.strip() or len(tag) > 300:
                errors.append(f"arsip_solusi[{idx}].tag_masalah wajib string non-kosong (maks. 300 karakter).")
            if not isinstance(sol, str) or not sol.strip() or len(sol) > _MAX_TEAM_SOLUSI_CHARS:
                errors.append(f"arsip_solusi[{idx}].solusi_paten wajib string non-kosong (maks. {_MAX_TEAM_SOLUSI_CHARS} karakter).")
            conf = item.get("confidence", 0.7)
            if isinstance(conf, bool) or not isinstance(conf, (int, float)) or not math.isfinite(float(conf)) or not (0.0 <= float(conf) <= 1.0):
                errors.append(f"arsip_solusi[{idx}].confidence wajib angka antara 0.0 hingga 1.0.")
            if periksa_konten:
                if isinstance(tag, str) and tag:
                    errors.extend(_cek_teks_berbahaya_tim(f"arsip_solusi[{idx}].tag_masalah", tag))
                if isinstance(sol, str) and sol:
                    errors.extend(_cek_teks_berbahaya_tim(f"arsip_solusi[{idx}].solusi_paten", sol))
    return errors


def audit_berkas_team_memory(
    file_tim: Path,
    path_workspace: str | None = None,
    strict_signature: bool = False,
) -> dict[str, Any]:
    """Mengaudit berkas ``team_memory.json`` secara menyeluruh untuk CLI ``verify-team`` dan CI."""
    errors: list[str] = []
    warnings: list[str] = []
    data: dict[str, Any] | None = None
    signed = False
    signature_valid: bool | None = None

    if not file_tim.is_file():
        return {
            "valid": False,
            "signed": False,
            "signature_valid": None,
            "errors": [f"Berkas tidak ditemukan: {file_tim}"],
            "warnings": [],
            "data": None,
        }

    try:
        if file_tim.stat().st_size > _MAX_TEAM_FILE_BYTES:
            errors.append(f"Ukuran berkas melebihi batas {_MAX_TEAM_FILE_BYTES // 1024} KB.")
        else:
            raw = file_tim.read_text(encoding="utf-8")
            parsed = json.loads(raw)
            errors.extend(validasi_skema_team_memory(parsed, periksa_konten=True))
            if isinstance(parsed, dict):
                data = parsed
                signed = bool(parsed.get("signature"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"Gagal membaca/mem-parse JSON: {exc}")

    ws_path = Path(path_workspace) if path_workspace else file_tim.parent.parent
    gitignore_fp = ws_path / ".gitignore"
    if gitignore_fp.is_file():
        gi_lines = {
            b.strip()
            for b in gitignore_fp.read_text(encoding="utf-8", errors="ignore").splitlines()
            if b.strip() and not b.strip().startswith("#")
        }
        for secret_file in (ws_path / ".karjimut" / ".team_secret", ws_path / ".sleep-mcp" / ".team_secret"):
            if secret_file.is_file():
                parent_name = secret_file.parent.name
                terlindung = any(
                    pola in gi_lines
                    for pola in (
                        ".team_secret",
                        f"{parent_name}/.team_secret",
                        f"/{parent_name}/.team_secret",
                        f"{parent_name}/",
                        f"/{parent_name}/",
                        parent_name,
                    )
                )
                if not terlindung:
                    warnings.append(f"{secret_file.name} ditemukan namun belum tercatat di .gitignore!")

    secret = ambil_team_secret(str(ws_path))
    strict = bool(strict_signature or _strict_signature_diwajibkan(ws_path))
    if data is not None:
        if secret:
            signature_valid = verifikasi_signature_tim(data, secret)
            if not signature_valid:
                errors.append(
                    "Verifikasi signature HMAC-SHA256 gagal (tanda tangan hilang atau isi team_memory.json telah dimodifikasi)."
                )
        else:
            if strict:
                errors.append(
                    "Mode wajib signature aktif (KARJIMUT_REQUIRE_TEAM_SIGNATURE=true / --strict), "
                    "namun KARJIMUT_TEAM_SECRET belum ditemukan untuk memverifikasi signature."
                )
            elif signed:
                warnings.append("File memiliki signature HMAC, namun secret lokal tidak tersedia (verifikasi kriptografi dilewati).")
            else:
                warnings.append("File belum bertanda tangan HMAC (saat impor default, bagian Aturan: akan ditahan).")

    return {
        "valid": len(errors) == 0,
        "signed": signed,
        "signature_valid": signature_valid,
        "errors": errors,
        "warnings": warnings,
        "data": data,
    }


def _pindai_direktori_kandidat(
    dir_path: Path,
    rel_prefix: str,
    gabungan_manifest: list[str],
    struktur: list[str],
    identitas_awal: str,
) -> tuple[str, bool]:
    """Memindai manifest, README, dan subfolder inti pada satu direktori workspace."""
    identitas = identitas_awal
    ada_manifest_atau_dir = False

    for nama_file in _MANIFEST_FILES:
        fp = dir_path / nama_file
        if fp.is_file():
            ada_manifest_atau_dir = True
            try:
                isi = fp.read_text(encoding="utf-8", errors="ignore")[:8192]
                gabungan_manifest.append(isi)
                if not identitas and nama_file == "pyproject.toml":
                    m_desc = re.search(r'^\s*description\s*=\s*["\']([^"\']+)["\']', isi, re.M)
                    if m_desc:
                        identitas = m_desc.group(1).strip()
                elif not identitas and nama_file == "package.json":
                    m_desc = re.search(r'"description"\s*:\s*"([^"]+)"', isi)
                    if m_desc:
                        identitas = m_desc.group(1).strip()
            except OSError:
                continue

    readme_fp = dir_path / "README.md"
    if readme_fp.is_file():
        try:
            isi_rm = readme_fp.read_text(encoding="utf-8", errors="ignore")[:4096]
            gabungan_manifest.append(isi_rm)
            if not identitas:
                for baris in isi_rm.splitlines():
                    b = baris.strip()
                    if not b or b.startswith(("#", "!", "[", ">", "`", "-", "*", "|", "<")):
                        continue
                    if len(b) >= 15:
                        identitas = pecah_kalimat(b)[0].rstrip(".")
                        break
        except OSError:
            pass

    for nama_dir in _CORE_DIRS_CANDIDATES:
        if (dir_path / nama_dir).is_dir():
            ada_manifest_atau_dir = True
            entry = f"{rel_prefix}{nama_dir}/"
            if entry not in struktur:
                struktur.append(entry)

    return identitas, ada_manifest_atau_dir


def auto_bootstrap_workspace(
    conn: sqlite3.Connection,
    kode_proyek: str,
    path_workspace: str,
) -> dict[str, Any] | None:
    """Memindai manifest proyek secara instan (< 30 ms, offline) saat cold-start untuk menyusun KTP v1.

    Mendukung struktur root tunggal maupun monorepo / workspace bertingkat kedalaman 1
    (mis. ``sleep-mcp/src/``, ``official-site/``). Seluruh pembacaan berkas dilakukan di luar
    transaksi database agar tidak menahan write-lock SQLite.
    """
    if not path_workspace or not str(path_workspace).strip():
        return None
    ws = Path(str(path_workspace).strip())
    if not _path_workspace_diizinkan(ws):
        return None

    kode = normalisasi_kode_proyek(kode_proyek)
    identitas = ""
    gabungan_manifest: list[str] = []
    struktur: list[str] = []

    identitas, _ = _pindai_direktori_kandidat(ws, "", gabungan_manifest, struktur, identitas)

    try:
        subdir_kandidat = [
            p
            for p in sorted(ws.iterdir(), key=lambda x: x.name.lower())
            if p.is_dir()
            and not p.name.startswith(".")
            and p.name.lower() not in _ABAIKAN_SUBDIR
            and not p.name.lower().startswith(("doc-", "docs-"))
            and _path_workspace_diizinkan(p)
        ][:15]
    except OSError:
        subdir_kandidat = []

    for sub in subdir_kandidat:
        jml_sebelum = len(struktur)
        identitas, ada_sinyal = _pindai_direktori_kandidat(
            sub, f"{sub.name}/", gabungan_manifest, struktur, identitas
        )
        ada_web_statis = (sub / "index.html").is_file()
        if (ada_sinyal or ada_web_statis) and len(struktur) == jml_sebelum:
            folder_entry = f"{sub.name}/"
            if folder_entry not in struktur:
                struktur.append(folder_entry)

    stack = deteksi_teknologi("\n".join(gabungan_manifest))
    struktur = struktur[:12]

    if not identitas and not stack and not struktur:
        return None

    if not identitas:
        identitas = f"Workspace aplikasi pada direktori {ws.name}"

    s = get_settings()
    teks_ktp = susun_ktp_terbatas(kode, identitas, stack, struktur, [], s.ktp_max_tokens)
    try:
        ws_resolved = str(ws.resolve())
    except OSError:
        ws_resolved = str(ws)

    with _transaksi_jika_perlu(conn):
        info = terapkan_ktp_baru(conn, kode, teks_ktp, s.ktp_max_tokens, simpan_snapshot=False)
        try:
            resolve_proyek(conn, kode, ws_resolved)
        except (sqlite3.Error, ValueError, OSError) as exc:
            logger.debug("Pencatatan peta_workspace saat auto-bootstrap dilewati: %s", exc)
    return info


def ekspor_memori_tim(
    conn: sqlite3.Connection,
    kode_proyek: str,
    path_workspace: str | None = None,
) -> str | None:
    """Mengekspor KTP Proyek dan solusi teruji ke ``<workspace>/.sleep-mcp/team_memory.json``."""
    kode = normalisasi_kode_proyek(kode_proyek)
    row_ktp = conn.execute(
        "SELECT kode_proyek, ringkasan_inti, versi_ktp, waktu_update FROM ktp_proyek WHERE kode_proyek = ?",
        (kode,),
    ).fetchone()
    if row_ktp is None:
        return None

    ws_raw = path_workspace
    if not ws_raw:
        try:
            row_ws = conn.execute(
                "SELECT path_workspace FROM peta_workspace WHERE kode_proyek = ? ORDER BY waktu_dibuat DESC LIMIT 1",
                (kode,),
            ).fetchone()
            if row_ws:
                ws_raw = row_ws["path_workspace"]
        except sqlite3.Error as exc:
            logger.debug("Gagal membaca peta_workspace untuk ekspor memori tim: %s", exc)
            ws_raw = None
    if not ws_raw:
        return None
    ws = Path(str(ws_raw).strip())
    if not _path_workspace_diizinkan(ws):
        return None

    dir_karjimut = ws / ".karjimut"
    dir_legacy = ws / ".sleep-mcp"
    if path_workspace is None and not dir_karjimut.is_dir() and not dir_legacy.is_dir():
        return None

    try:
        rows_arsip = conn.execute(
            """
            SELECT tag_masalah, solusi_paten, COALESCE(confidence, 0.7) AS confidence
            FROM laci_arsip
            WHERE kode_proyek = ?
              AND COALESCE(is_stale, 0) = 0
              AND COALESCE(confidence, 0.7) >= 0.70
            ORDER BY tag_masalah ASC, id ASC
            """,
            (kode,),
        ).fetchall()

        payload: dict[str, Any] = {
            "schema_version": 1,
            "kode_proyek": kode,
            "versi_ktp": int(row_ktp["versi_ktp"]),
            "ringkasan_inti": row_ktp["ringkasan_inti"],
            "arsip_solusi": [
                {
                    "tag_masalah": r["tag_masalah"],
                    "solusi_paten": r["solusi_paten"],
                    "confidence": round(float(r["confidence"]), 2),
                }
                for r in rows_arsip
            ],
        }
        secret = ambil_team_secret(str(ws))
        require_sig = _strict_signature_diwajibkan(ws)
        if require_sig and not secret:
            logger.warning(
                "[Keamanan Tim] Ekspor memori tim dilewati: mode wajib signature aktif namun KARJIMUT_TEAM_SECRET belum disetel (%s).",
                ws,
            )
            return None
        if secret:
            payload["signature"] = hitung_signature_tim(payload, secret)
        else:
            # Jangan menimpa atau membuat cermin tak bertanda tangan bila workspace sudah memakai HMAC signature
            for existing_fp in (dir_karjimut / "team_memory.json", dir_legacy / "team_memory.json"):
                if existing_fp.is_file():
                    try:
                        existing = json.loads(existing_fp.read_text(encoding="utf-8", errors="ignore"))
                        if isinstance(existing, dict) and existing.get("signature"):
                            logger.warning(
                                "[Keamanan Tim] Melewati ekspor memori tim karena %s bertanda tangan HMAC dan KARJIMUT_TEAM_SECRET belum tersedia.",
                                existing_fp,
                            )
                            return None
                    except (OSError, json.JSONDecodeError):
                        pass

        konten_json = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        target_dirs: list[Path] = []
        if path_workspace is not None:
            target_dirs.extend([dir_karjimut, dir_legacy])
        else:
            if dir_karjimut.is_dir():
                target_dirs.append(dir_karjimut)
            if dir_legacy.is_dir():
                target_dirs.append(dir_legacy)

        hasil_path: str | None = None
        for d in target_dirs:
            d.mkdir(parents=True, exist_ok=True)
            tf = d / "team_memory.json"
            if not (tf.is_file() and tf.read_text(encoding="utf-8", errors="ignore") == konten_json):
                tf.write_text(konten_json, encoding="utf-8")
            if hasil_path is None:
                hasil_path = str(tf)
        return hasil_path
    except OSError as exc:
        logger.debug("Ekspor memori tim dilewati: %s", exc)
        return None


def impor_memori_tim(
    conn: sqlite3.Connection,
    kode_proyek: str,
    path_workspace: str | None = None,
) -> dict[str, Any]:
    """Menggabungkan ``<workspace>/.karjimut/team_memory.json`` secara non-destruktif ke SQLite lokal.

    Menerapkan validasi skema ketat, verifikasi HMAC-SHA256 bila ``KARJIMUT_TEAM_SECRET`` aktif,
    serta *Trust Boundary* yang menahan bagian ``Aturan:`` tak bertanda tangan secara default.
    Pembacaan dan penulisan file JSON dilakukan di luar transaksi BEGIN IMMEDIATE agar tidak menahan lock DB.
    """
    hasil: dict[str, Any] = {
        "ktp_merged": False,
        "solusi_baru": 0,
        "solusi_update": 0,
        "security_status": "SKIPPED",
        "aturan_ditahan": 0,
        "peringatan_keamanan": "",
    }
    if not path_workspace:
        return hasil
    ws = Path(str(path_workspace).strip())
    if not _path_workspace_diizinkan(ws):
        return hasil
    file_tim = ws / ".karjimut" / "team_memory.json"
    if not file_tim.is_file():
        file_tim = ws / ".sleep-mcp" / "team_memory.json"
    if not file_tim.is_file():
        return hasil

    try:
        # 1. Baca, validasi skema, & verifikasi tanda tangan di luar transaksi DB
        if file_tim.stat().st_size > _MAX_TEAM_FILE_BYTES:
            hasil["security_status"] = "REJECTED_SCHEMA"
            hasil["peringatan_keamanan"] = "[Keamanan Tim] Impor team_memory.json ditolak: ukuran file melebihi batas aman."
            logger.warning("%s (%s)", hasil["peringatan_keamanan"], file_tim)
            return hasil

        raw_text = file_tim.read_text(encoding="utf-8")
        data = json.loads(raw_text)
        err_skema = validasi_skema_team_memory(data, periksa_konten=False)
        if err_skema:
            hasil["security_status"] = "REJECTED_SCHEMA"
            hasil["peringatan_keamanan"] = f"[Keamanan Tim] Impor team_memory.json ditolak karena skema tidak valid: {err_skema[0]}"
            logger.warning("%s (%s)", hasil["peringatan_keamanan"], file_tim)
            return hasil

        s = get_settings()
        secret = ambil_team_secret(str(ws))
        require_sig = _strict_signature_diwajibkan(ws)
        ada_sig = bool(data.get("signature"))
        izinkan_aturan_tim = False

        if secret:
            if not verifikasi_signature_tim(data, secret):
                hasil["security_status"] = "REJECTED_INVALID_SIGNATURE"
                hasil["peringatan_keamanan"] = (
                    "[Keamanan Tim] Impor team_memory.json DITOLAK: tanda tangan HMAC-SHA256 tidak valid atau file telah dimodifikasi."
                )
                logger.warning("%s (%s)", hasil["peringatan_keamanan"], file_tim)
                return hasil
            hasil["security_status"] = "VERIFIED"
            izinkan_aturan_tim = True
        elif require_sig:
            hasil["security_status"] = "REJECTED_SIGNATURE_REQUIRED"
            hasil["peringatan_keamanan"] = (
                "[Keamanan Tim] Impor team_memory.json DITOLAK: mode wajib signature aktif namun KARJIMUT_TEAM_SECRET belum disetel."
            )
            logger.warning("%s (%s)", hasil["peringatan_keamanan"], file_tim)
            return hasil
        elif s.trust_unsigned_team_rules:
            hasil["security_status"] = "PERMISSIVE_UNSIGNED"
            izinkan_aturan_tim = True
        else:
            hasil["security_status"] = "PARTIAL_UNSIGNED"
            izinkan_aturan_tim = False

        kode = normalisasi_kode_proyek(kode_proyek)
        ktp_tim_raw = normalisasi_spasi(bersihkan_injeksi_memori(str(data.get("ringkasan_inti") or "")))

        # Sanitasi per-komponen KTP tim & penegakan Trust Boundary pada Aturan:
        ktp_tim = ""
        u_tim: dict[str, Any] = {"identitas": "", "stack": [], "struktur": [], "aturan": []}
        if ktp_tim_raw:
            u_tim = urai_ktp(ktp_tim_raw, kode)
            aturan_aman = [
                bersihkan_injeksi_memori(a)
                for a in u_tim["aturan"]
                if a
                and not _RE_PROMPT_INJECTION.search(a)
                and not _RE_CREDENTIAL_REDACT.search(a)
                and bersihkan_injeksi_memori(a)
            ]
            if not izinkan_aturan_tim and aturan_aman:
                hasil["aturan_ditahan"] = len(aturan_aman)
                hasil["peringatan_keamanan"] = (
                    f"[Info Keamanan Tim] {hasil['aturan_ditahan']} Aturan: di team_memory.json ditahan karena belum terverifikasi HMAC "
                    "(atur KARJIMUT_TEAM_SECRET di .env workspace/global untuk menyinkronkan aturan tim)."
                )
                logger.info("%s (%s)", hasil["peringatan_keamanan"], file_tim)
                u_tim["aturan"] = []
            else:
                u_tim["aturan"] = aturan_aman

            ident_tim_awal = identitas_bermakna(u_tim["identitas"], kode)
            if ident_tim_awal or u_tim["stack"] or u_tim["struktur"] or u_tim["aturan"]:
                ktp_tim = susun_ktp_terbatas(
                    kode, ident_tim_awal, u_tim["stack"], u_tim["struktur"], u_tim["aturan"], s.ktp_max_tokens
                )

        arsip_tim = data.get("arsip_solusi") or []
        kandidat_arsip: list[dict[str, Any]] = []
        if isinstance(arsip_tim, list):
            for item in arsip_tim[:_MAX_TEAM_SOLUSI_COUNT]:
                if not isinstance(item, dict):
                    continue
                tag_str = ", ".join(normalisasi_tag(item.get("tag_masalah")))
                sol_str = normalisasi_spasi(bersihkan_injeksi_memori(str(item.get("solusi_paten") or "")))
                if not tag_str or not sol_str or _RE_PROMPT_INJECTION.search(sol_str) or _RE_CREDENTIAL_REDACT.search(sol_str):
                    continue
                if not layak_masuk_laci_arsip(sol_str, tag_str):
                    continue
                kandidat_arsip.append(
                    {
                        "id_arsip_target": None,
                        "tag_masalah": tag_str,
                        "solusi_paten": sol_str,
                        "confidence": item.get("confidence", 0.7),
                    }
                )

        # 2. Operasi database murni di dalam transaksi atomik singkat
        if ktp_tim or kandidat_arsip:
            with _transaksi_jika_perlu(conn):
                if ktp_tim:
                    row_lokal = conn.execute(
                        "SELECT ringkasan_inti FROM ktp_proyek WHERE kode_proyek = ?", (kode,)
                    ).fetchone()
                    if row_lokal is None:
                        terapkan_ktp_baru(conn, kode, ktp_tim, s.ktp_max_tokens, simpan_snapshot=False)
                        hasil["ktp_merged"] = True
                    elif normalisasi_spasi(row_lokal["ringkasan_inti"]) != ktp_tim:
                        u_lokal = urai_ktp(row_lokal["ringkasan_inti"], kode)
                        ident_lokal = identitas_bermakna(u_lokal["identitas"], kode)
                        ident_tim = identitas_bermakna(u_tim["identitas"], kode)
                        ident = ident_lokal or ident_tim
                        stack_gab = _gabung_unik(u_lokal["stack"], u_tim["stack"])
                        struk_gab = _gabung_unik(u_lokal["struktur"], u_tim["struktur"])
                        aturan_gab = gabung_aturan(
                            u_lokal["aturan"],
                            u_tim["aturan"],
                            max_aturan=_batas_aturan_aktif(s.ktp_max_tokens),
                        )
                        ada_tambahan = (
                            len(stack_gab) > len(u_lokal["stack"])
                            or len(struk_gab) > len(u_lokal["struktur"])
                            or aturan_gab != u_lokal["aturan"]
                            or (not ident_lokal and bool(ident_tim))
                        )
                        if ada_tambahan:
                            ktp_gabungan = susun_ktp_terbatas(
                                kode, ident, stack_gab, struk_gab, aturan_gab, s.ktp_max_tokens
                            )
                            if normalisasi_spasi(ktp_gabungan) != normalisasi_spasi(row_lokal["ringkasan_inti"]):
                                terapkan_ktp_baru(conn, kode, ktp_gabungan, s.ktp_max_tokens, simpan_snapshot=True)
                                hasil["ktp_merged"] = True

                for item_bersih in kandidat_arsip:
                    sudah_ada = conn.execute(
                        "SELECT 1 FROM laci_arsip WHERE kode_proyek = ? AND tag_masalah = ? AND solusi_paten = ? LIMIT 1",
                        (kode, item_bersih["tag_masalah"], item_bersih["solusi_paten"]),
                    ).fetchone()
                    if sudah_ada:
                        continue
                    res = simpan_arsip_deduplikasi(conn, kode, item_bersih, sync_vektor=False)
                    if res["aksi"] == "INSERT":
                        hasil["solusi_baru"] += 1
                    elif res["aksi"] == "UPDATE":
                        hasil["solusi_update"] += 1

        # 3. Ekspor kembali dilakukan di luar transaksi DB, hanya jika aman (tidak menghapus signature/aturan tim)
        boleh_ekspor_ulang = (
            (hasil["ktp_merged"] or hasil["solusi_baru"] > 0 or hasil["solusi_update"] > 0)
            and not conn.in_transaction
            and hasil["aturan_ditahan"] == 0
            and not (ada_sig and not secret)
        )
        if boleh_ekspor_ulang:
            ekspor_memori_tim(conn, kode, path_workspace)
        return hasil
    except (OSError, json.JSONDecodeError, sqlite3.Error, ValueError) as exc:
        logger.debug("Impor memori tim dilewati: %s", exc)
        return hasil
