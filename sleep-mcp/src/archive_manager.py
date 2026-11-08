"""Modul deduplikasi Laci Arsip Solusi, auto-supersede, memory decay, dan sinkronisasi tim/workspace."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from .config import STATUS_PROCESSED, get_settings, setup_logging
from .db import normalisasi_kode_proyek, resolve_proyek
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
    _TAG_GENERIK_DEDUP,
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


def auto_bootstrap_workspace(
    conn: sqlite3.Connection,
    kode_proyek: str,
    path_workspace: str,
) -> dict[str, Any] | None:
    """Memindai manifest proyek secara instan (< 30 ms, offline) saat cold-start untuk menyusun KTP v1."""
    if not path_workspace or not str(path_workspace).strip():
        return None
    ws = Path(str(path_workspace).strip())
    if not _path_workspace_diizinkan(ws):
        return None

    kode = normalisasi_kode_proyek(kode_proyek)
    identitas = ""
    gabungan_manifest: list[str] = []

    for nama_file in _MANIFEST_FILES:
        fp = ws / nama_file
        if fp.is_file():
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

    readme_fp = ws / "README.md"
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

    stack = deteksi_teknologi("\n".join(gabungan_manifest))
    struktur: list[str] = []
    for nama_dir in _CORE_DIRS_CANDIDATES:
        if (ws / nama_dir).is_dir():
            struktur.append(f"{nama_dir}/")

    if not identitas and not stack and not struktur:
        return None

    if not identitas:
        identitas = f"Workspace aplikasi pada direktori {ws.name}"

    s = get_settings()
    teks_ktp = susun_ktp_terbatas(kode, identitas, stack, struktur, [], s.ktp_max_tokens)
    info = terapkan_ktp_baru(conn, kode, teks_ktp, s.ktp_max_tokens, simpan_snapshot=False)
    try:
        resolve_proyek(conn, kode, str(ws.resolve()))
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

        payload = {
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
    """Menggabungkan ``<workspace>/.karjimut/team_memory.json`` secara non-destruktif ke SQLite lokal."""
    hasil = {"ktp_merged": False, "solusi_baru": 0, "solusi_update": 0}
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
        data = json.loads(file_tim.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return hasil
        kode = normalisasi_kode_proyek(kode_proyek)
        ktp_tim = normalisasi_spasi(bersihkan_injeksi_memori(str(data.get("ringkasan_inti") or "")))
        s = get_settings()

        if ktp_tim:
            row_lokal = conn.execute(
                "SELECT ringkasan_inti FROM ktp_proyek WHERE kode_proyek = ?", (kode,)
            ).fetchone()
            if row_lokal is None:
                terapkan_ktp_baru(conn, kode, ktp_tim, s.ktp_max_tokens, simpan_snapshot=False)
                hasil["ktp_merged"] = True
            elif normalisasi_spasi(row_lokal["ringkasan_inti"]) != ktp_tim:
                u_lokal = urai_ktp(row_lokal["ringkasan_inti"], kode)
                u_tim = urai_ktp(ktp_tim, kode)
                ident_lokal = identitas_bermakna(u_lokal["identitas"], kode)
                ident_tim = identitas_bermakna(u_tim["identitas"], kode)
                ident = ident_lokal or ident_tim
                stack_gab = _gabung_unik(u_lokal["stack"], u_tim["stack"])
                struk_gab = _gabung_unik(u_lokal["struktur"], u_tim["struktur"])
                aturan_gab = gabung_aturan(u_lokal["aturan"], u_tim["aturan"])
                ada_tambahan = (
                    len(stack_gab) > len(u_lokal["stack"])
                    or len(struk_gab) > len(u_lokal["struktur"])
                    or aturan_gab != u_lokal["aturan"]
                    or (not ident_lokal and bool(ident_tim))
                )
                if ada_tambahan:
                    ktp_gabungan = susun_ktp_terbatas(kode, ident, stack_gab, struk_gab, aturan_gab, s.ktp_max_tokens)
                    if normalisasi_spasi(ktp_gabungan) != normalisasi_spasi(row_lokal["ringkasan_inti"]):
                        terapkan_ktp_baru(conn, kode, ktp_gabungan, s.ktp_max_tokens, simpan_snapshot=True)
                        hasil["ktp_merged"] = True

        arsip_tim = data.get("arsip_solusi") or []
        if isinstance(arsip_tim, list):
            for item in arsip_tim[:200]:
                if not isinstance(item, dict):
                    continue
                tag_str = ", ".join(normalisasi_tag(item.get("tag_masalah")))
                sol_str = normalisasi_spasi(bersihkan_injeksi_memori(str(item.get("solusi_paten") or "")))
                if not tag_str or not sol_str:
                    continue
                sudah_ada = conn.execute(
                    "SELECT 1 FROM laci_arsip WHERE kode_proyek = ? AND tag_masalah = ? AND solusi_paten = ? LIMIT 1",
                    (kode, tag_str, sol_str),
                ).fetchone()
                if sudah_ada:
                    continue
                res = simpan_arsip_deduplikasi(
                    conn,
                    kode,
                    {
                        "id_arsip_target": None,
                        "tag_masalah": tag_str,
                        "solusi_paten": sol_str,
                        "confidence": item.get("confidence", 0.7),
                    },
                    sync_vektor=False,
                )
                if res["aksi"] == "INSERT":
                    hasil["solusi_baru"] += 1
                elif res["aksi"] == "UPDATE":
                    hasil["solusi_update"] += 1

        if hasil["ktp_merged"] or hasil["solusi_baru"] > 0 or hasil["solusi_update"] > 0:
            ekspor_memori_tim(conn, kode, path_workspace)
        return hasil
    except (OSError, json.JSONDecodeError, sqlite3.Error, ValueError) as exc:
        logger.debug("Impor memori tim dilewati: %s", exc)
        return hasil
