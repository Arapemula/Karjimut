"""Pencarian Lapis 2 (Laci Arsip Solusi) dengan SQLite FTS5 + ranking BM25.

Alur :func:`cari_solusi_fts`:
  1. Normalisasi kata kunci ke lowercase.
  2. Ekstraksi token dengan mempertahankan simbol ``#`` dan ``-``
     (mis. ``#koneksi-db``), karakter lain yang dapat memicu syntax error
     FTS5 (kutip, kurung, titik dua, asterisk, dll.) dibersihkan.
  3. Ekspresi MATCH disusun dengan operator ``OR`` antar token yang
     masing-masing dikutip ganda (``"#koneksi-db" OR "#cors" OR "timeout"``).
  4. Query BM25 dijalankan; bila 0 baris atau terjadi exception, sistem
     menjalankan fallback ``LIKE`` pada ``tag_masalah`` dan ``solusi_paten``.
"""

from __future__ import annotations

import math
import re
import sqlite3
from typing import Any, Iterable

from .config import setup_logging
from .db import koneksi, normalisasi_kode_proyek

logger = setup_logging("sleep_mcp.fts")


def normalisasi_tag(tag_masalah: str | Iterable[str] | None) -> list[str]:
    """Normalisasi tag: lowercase, awalan ``#``, spasi -> ``-``, unik & berurutan.

    >>> normalisasi_tag("Koneksi DB, #CORS ,timeout")
    ['#koneksi-db', '#cors', '#timeout']
    """
    if tag_masalah is None:
        return []
    if isinstance(tag_masalah, str):
        mentah = re.split(r"[,;\n]+", tag_masalah)
        pecahan: list[str] = []
        for item in mentah:
            item = item.strip()
            if item.count("#") > 1:
                pecahan.extend(x for x in re.split(r"\s+(?=#)", item) if x.strip())
            else:
                pecahan.append(item)
    else:
        pecahan = [str(x) for x in tag_masalah]
    hasil: list[str] = []
    for item in pecahan:
        t = item.strip().lower().lstrip("#").strip()
        t = re.sub(r"\s+", "-", t)
        t = re.sub(r"[^0-9a-z_\-\u00c0-\u024f]", "", t).strip("-")
        if not t:
            continue
        tag = f"#{t}"
        if tag not in hasil:
            hasil.append(tag)
    return hasil


# Token yang dipertahankan: huruf/angka/underscore dengan '#' dan '-' internal.
_TOKEN_PATTERN = re.compile(r"#?[0-9a-z_\u00c0-\u024f]+(?:-[0-9a-z_\u00c0-\u024f]+)*")

# Kata umum (ID/EN) yang tidak informatif sebagai kata kunci gejala error.
STOPWORDS: frozenset[str] = frozenset(
    {
        "yang", "dan", "di", "ke", "dari", "untuk", "saat", "ketika", "pada", "dengan",
        "ini", "itu", "ada", "tidak", "apa", "kenapa", "mengapa", "bagaimana", "cara",
        "lagi", "muncul", "terjadi", "jadi", "atau", "juga", "sudah", "belum", "akan",
        "bisa", "dapat", "karena", "oleh", "sebuah", "seperti", "masih", "selalu", "aku",
        "saya", "kami", "kita", "nya", "lalu", "kemudian", "setelah", "sebelum", "tolong",
        "the", "a", "an", "is", "are", "was", "were", "of", "to", "in", "on", "at", "for",
        "and", "or", "not", "no", "named", "cannot", "can", "could", "would", "should",
        "does", "did", "has", "have", "had", "into", "out", "up", "down", "over", "under",
        "again", "most", "recent", "call", "last", "when", "with", "from", "by", "be",
        "it", "this", "that", "while", "near", "match",
    }
)

# Kategori token struktural/exception standar bahasa pemrograman (Python built-in exceptions,
# log levels, dan header stack trace standar) yang memiliki Document Frequency (DF) sangat tinggi
# pada korpus error log sehingga memiliki nilai Inverse Document Frequency (IDF) mendekati nol.
# Token ini dipertahankan sebagai fallback hanya bila query tidak memiliki identifier teknis spesifik.
GENERIC_NOISE_TOKENS: frozenset[str] = frozenset(
    {
        "error", "errors", "bug", "bugs", "bug-fix", "exception", "exceptions",
        "failed", "failure", "fatal", "gagal", "masalah", "issue", "issues",
        "problem", "warning", "info", "debug", "fix", "fixed", "solusi",
        "status", "code", "kode", "line", "lines", "file", "files", "app", "aplikasi", "sistem",
        "module", "modulenotfounderror", "importerror", "traceback", "runtimeerror",
        "valueerror", "typeerror", "keyerror", "attributeerror", "indexerror",
        "nameerror", "syntaxerror", "char", "character", "function", "method",
        "class", "object", "return", "found",
    }
)

# Kamus sinonim teknis dua arah (ID <-> EN) untuk pencarian lintas bahasa.
KAMUS_SINONIM_ID_EN: dict[str, tuple[str, ...]] = {
    "koneksi": ("connection", "connect"),
    "connection": ("koneksi",),
    "connect": ("koneksi",),
    "terkunci": ("locked", "lock", "busy"),
    "locked": ("terkunci", "lock"),
    "lock": ("terkunci", "locked"),
    "lambat": ("slow", "latency", "timeout"),
    "slow": ("lambat", "latency"),
    "habis-waktu": ("timeout",),
    "waktu-habis": ("timeout",),
    "timeout": ("habis-waktu", "waktu-habis"),
    "kedaluwarsa": ("expired", "kadaluarsa"),
    "kadaluarsa": ("expired", "kedaluwarsa"),
    "expired": ("kedaluwarsa", "kadaluarsa"),
    "izin": ("permission", "forbidden", "unauthorized"),
    "permission": ("izin", "akses"),
    "akses": ("access", "permission", "izin"),
    "autentikasi": ("auth", "authentication", "login"),
    "auth": ("autentikasi", "authentication"),
    "authentication": ("autentikasi", "auth"),
    "migrasi": ("migration",),
    "migration": ("migrasi",),
    "memori": ("memory", "oom"),
    "memory": ("memori", "oom"),
    "antrean": ("queue", "buffer"),
    "queue": ("antrean",),
    "sertifikat": ("ssl", "tls", "certificate"),
    "certificate": ("sertifikat", "ssl", "tls"),
}

QUERY_SQL_BM25 = """
    SELECT a.id, a.kode_proyek, a.tag_masalah, a.solusi_paten, a.waktu_dibuat,
           COALESCE(a.confidence, 0.7) AS confidence,
           COALESCE(a.hit_count, 0) AS hit_count,
           COALESCE(a.miss_count, 0) AS miss_count,
           COALESCE(a.is_stale, 0) AS is_stale,
           COALESCE(a.catatan_evaluasi, '') AS catatan_evaluasi,
           bm25(laci_arsip_fts) AS skor_bm25
    FROM laci_arsip_fts f
    JOIN laci_arsip a ON f.rowid = a.id
    WHERE laci_arsip_fts MATCH ? AND a.kode_proyek = ?
    ORDER BY bm25(laci_arsip_fts)
    LIMIT ?
"""


def ekstrak_token_kata_kunci(kata_kunci: str) -> list[str]:
    """Lowercase + ekstraksi token aman FTS5 dengan mempertahankan ``#`` dan ``-``.

    >>> ekstrak_token_kata_kunci('Error #Koneksi-DB, "CORS" (timeout)!')
    ['error', '#koneksi-db', 'cors', 'timeout']
    """
    teks = (kata_kunci or "").lower()
    # Karakter selain huruf/angka/_/#/- diganti spasi (membersihkan " ' ( ) : * ^ + dsb.)
    teks = re.sub(r"[^0-9a-z_\u00c0-\u024f#\-\s]", " ", teks)
    token_unik: list[str] = []
    for token in _TOKEN_PATTERN.findall(teks):
        token = token.strip("-")
        inti = token.lstrip("#")
        if len(inti) < 2 or inti in STOPWORDS:
            continue
        if token not in token_unik:
            token_unik.append(token)
    return token_unik


def saring_token_spesifik(token_list: list[str]) -> list[str]:
    """Memisahkan token teknis spesifik dari kata generik ('error', 'bug', 'gagal', dll.).

    Jika query memiliki minimal satu token spesifik, token generik diabaikan agar
    pencarian beroperator ``OR`` tidak mengembalikan false-positive dari entri lain.
    """
    spesifik = [t for t in token_list if t.lstrip("#") not in GENERIC_NOISE_TOKENS]
    return spesifik if spesifik else token_list


def _unit_pencocokan_spesifik(token_spesifik: list[str]) -> list[str]:
    """Menurunkan unit kata/tag spesifik (panjang >= 3) untuk verifikasi relevansi hasil."""
    unit: list[str] = []
    for tok in token_spesifik:
        inti = tok.lstrip("#")
        if not inti or inti in GENERIC_NOISE_TOKENS or inti in STOPWORDS:
            continue
        if len(inti) >= 2 and inti not in unit:
            unit.append(inti)
        if "-" in inti:
            for bagian in inti.split("-"):
                if (
                    len(bagian) >= 3
                    and bagian not in GENERIC_NOISE_TOKENS
                    and bagian not in STOPWORDS
                    and bagian not in unit
                ):
                    unit.append(bagian)
    return unit


def _cocok_kata_batas(kandidat: str, teks_target: str) -> bool:
    """Pencocokan berbasis batas kata (word boundary) agar token pendek tidak cocok di tengah kata lain."""
    if not kandidat:
        return False
    if len(kandidat) >= 5:
        pola = rf"(?<![0-9a-z_]){re.escape(kandidat)}"
    else:
        pola = rf"(?<![0-9a-z_]){re.escape(kandidat)}(?![0-9a-z_])"
    return bool(re.search(pola, teks_target))


def _cocok_unit_atau_sinonim(unit: str, teks_target: str) -> bool:
    """Memeriksa apakah unit atau sinonim teknis dwibahasanya ada pada teks_target."""
    if _cocok_kata_batas(unit, teks_target):
        return True
    for sin in KAMUS_SINONIM_ID_EN.get(unit, ()):
        if _cocok_kata_batas(sin, teks_target):
            return True
    return False


AMBIGUOUS_SINGLE_TOKENS: frozenset[str] = frozenset(
    {
        "token",
        "port",
        "service",
        "header",
        "key",
        "pool",
        "status",
        "code",
        "client",
        "server",
        "data",
        "type",
        "value",
        "object",
        "invalid",
        "unexpected",
        "position",
        "src",
        "lib",
        "app",
        "main",
        "test",
        "tests",
        "file",
        "line",
        "name",
    }
)


def _hasil_memenuhi_relevansi(item: dict[str, Any], unit_spesifik: list[str]) -> bool:
    """Memastikan hasil pencarian benar-benar relevan (mencegah false-positive kata tunggal di luar domain)."""
    if not unit_spesifik:
        return True
    tag_teks = str(item.get("tag_masalah", "")).lower()
    solusi_teks = str(item.get("solusi_paten", "")).lower()
    gabungan = f"{tag_teks} {solusi_teks}"
    unit_cocok_tag = [u for u in unit_spesifik if _cocok_unit_atau_sinonim(u, tag_teks)]
    unit_cocok_total = [u for u in unit_spesifik if _cocok_unit_atau_sinonim(u, gabungan)]

    if len(unit_cocok_total) >= 2:
        return True
    if len(unit_cocok_tag) == 1:
        # Jika query panjang (>= 3 unit spesifik) dan satu-satunya kata yang cocok adalah kata ambigu
        # seperti 'token' pada 'SyntaxError: Unexpected token < in JSON', wajib ada kata pendukung lain
        if len(unit_spesifik) >= 3 and unit_cocok_tag[0] in AMBIGUOUS_SINGLE_TOKENS:
            return False
        return True
    if len(unit_spesifik) >= 3:
        return False
    return len(unit_cocok_total) >= 1


def ekspansi_token(token: str) -> list[str]:
    """Varian token agar kata kunci bebas (tanpa ``#``) & dwibahasa (ID <-> EN) tetap cocok dengan tag.

    Contoh ``cors`` -> ``"cors"``, ``"#cors"``, ``"#cors"*`` (prefix: cocok ``#cors-policy``).
    Contoh ``#koneksi-db`` -> ``"#koneksi-db"``, ``"koneksi-db"``, ``"koneksi"``, ``"connection"``, ``"db"``.
    """
    varian: list[str] = [f'"{token}"']
    inti = token.lstrip("#")
    if token.startswith("#"):
        varian.append(f'"{inti}"')
    else:
        varian.append(f'"#{inti}"')
        if len(inti) >= 3:
            varian.append(f'"#{inti}"*')
    for sin in KAMUS_SINONIM_ID_EN.get(inti, ()):
        varian.append(f'"{sin}"')
        varian.append(f'"#{sin}"')
    if "-" in inti:
        for bagian in inti.split("-"):
            if len(bagian) >= 2 and bagian not in STOPWORDS and bagian not in GENERIC_NOISE_TOKENS:
                varian.append(f'"{bagian}"')
                varian.append(f'"#{bagian}"')
                for sin in KAMUS_SINONIM_ID_EN.get(bagian, ()):
                    varian.append(f'"{sin}"')
                    varian.append(f'"#{sin}"')
    hasil: list[str] = []
    for v in varian:
        if v not in hasil:
            hasil.append(v)
    return hasil


def bangun_query_fts(kata_kunci: str, ekspansi: bool = True) -> str:
    """Menyusun ekspresi MATCH FTS5 beroperator OR, dibatasi ke kolom tag & solusi."""
    token_list = saring_token_spesifik(ekstrak_token_kata_kunci(kata_kunci))
    if not token_list:
        return ""
    istilah: list[str] = []
    for token in token_list:
        for varian in (ekspansi_token(token) if ekspansi else [f'"{token}"']):
            if varian not in istilah:
                istilah.append(varian)
    ekspresi_or = " OR ".join(istilah)
    # Filter kolom FTS5 agar token kode_proyek tidak ikut mendongkrak skor.
    return "{tag_masalah solusi_paten} : (" + ekspresi_or + ")"


MAX_COSINE_DISTANCE = 0.38  # Ambang batas kemiripan kosinus (~0.62 similarity)


def _baris_ke_dict(row: sqlite3.Row, metode: str) -> dict[str, Any]:
    data = dict(row)
    skor = data.get("skor_bm25")
    data["skor_bm25"] = round(float(skor), 6) if skor is not None else None
    data["confidence"] = round(float(data.get("confidence") if data.get("confidence") is not None else 0.7), 2)
    data["hit_count"] = int(data.get("hit_count") or 0)
    data["miss_count"] = int(data.get("miss_count") or 0)
    data["is_stale"] = int(data.get("is_stale") or 0)
    data["metode"] = metode
    return data


def cari_fallback_like(
    conn: sqlite3.Connection, kode_proyek: str, kata_kunci: str, limit: int = 10
) -> list[dict[str, Any]]:
    """Fallback ``LIKE`` pada ``tag_masalah`` & ``solusi_paten`` (diurutkan jumlah kecocokan)."""
    token_mentah = ekstrak_token_kata_kunci(kata_kunci)
    token_dasar = [t for t in saring_token_spesifik(token_mentah) if len(t.lstrip("#")) >= 3]
    if not token_dasar and not token_mentah:
        bersih = re.sub(r"[%_]", " ", (kata_kunci or "").lower()).strip()
        if len(bersih) >= 3 and bersih not in GENERIC_NOISE_TOKENS:
            token_dasar = [bersih]
    token_list: list[str] = []
    for t in token_dasar:
        inti = t.lstrip("#")
        if inti not in token_list:
            token_list.append(inti)
        for sin in KAMUS_SINONIM_ID_EN.get(inti, ()):
            if sin not in token_list:
                token_list.append(sin)
    if not token_list:
        return []
    skor_parts: list[str] = []
    where_parts: list[str] = []
    params_skor: list[str] = []
    params_where: list[str] = []
    for token in token_list:
        pola = f"%{token.lstrip('#')}%"
        skor_parts.append(
            "(CASE WHEN lower(tag_masalah) LIKE ? THEN 2 ELSE 0 END"
            " + CASE WHEN lower(solusi_paten) LIKE ? THEN 1 ELSE 0 END)"
        )
        params_skor.extend([pola, pola])
        where_parts.append("(lower(tag_masalah) LIKE ? OR lower(solusi_paten) LIKE ?)")
        params_where.extend([pola, pola])
    sql = f"""
        SELECT id, kode_proyek, tag_masalah, solusi_paten, waktu_dibuat,
               COALESCE(confidence, 0.7) AS confidence,
               COALESCE(hit_count, 0) AS hit_count,
               COALESCE(miss_count, 0) AS miss_count,
               COALESCE(is_stale, 0) AS is_stale,
               COALESCE(catatan_evaluasi, '') AS catatan_evaluasi,
               NULL AS skor_bm25, ({' + '.join(skor_parts)}) AS skor_like
        FROM laci_arsip
        WHERE kode_proyek = ? AND ({' OR '.join(where_parts)})
        ORDER BY skor_like DESC, waktu_dibuat DESC, id DESC
        LIMIT ?
    """
    rows = conn.execute(sql, [*params_skor, kode_proyek, *params_where, int(limit)]).fetchall()
    hasil = []
    for row in rows:
        data = _baris_ke_dict(row, "LIKE_FALLBACK")
        data.pop("skor_like", None)
        hasil.append(data)
    return hasil


def _cari_vektor_terfilter_proyek(
    conn: sqlite3.Connection,
    kode_proyek: str,
    aktif_backend: str,
    query_vec: list[float],
    limit: int,
) -> list[dict[str, Any]]:
    """Fallback jarak kosinus terlingkup ``kode_proyek`` saat pool KNN global ``sqlite-vec`` jenuh proyek lain."""
    from .embedding import bytes_ke_vector

    norm_q = math.sqrt(sum(x * x for x in query_vec))
    if norm_q <= 0.0:
        return []

    rows = conn.execute(
        """
        SELECT a.id, a.kode_proyek, a.tag_masalah, a.solusi_paten, a.waktu_dibuat,
               COALESCE(a.confidence, 0.7) AS confidence,
               COALESCE(a.hit_count, 0) AS hit_count,
               COALESCE(a.miss_count, 0) AS miss_count,
               COALESCE(a.is_stale, 0) AS is_stale,
               COALESCE(a.catatan_evaluasi, '') AS catatan_evaluasi,
               v.embedding AS vec_blob
        FROM laci_arsip a
        JOIN laci_arsip_vec v ON v.id = a.id
        WHERE a.kode_proyek = ?
          AND (a.embedding_backend IS NULL OR a.embedding_backend = ?)
        """,
        (kode_proyek, aktif_backend),
    ).fetchall()

    dim = len(query_vec)
    kandidat: list[tuple[float, sqlite3.Row]] = []
    for r in rows:
        blob = r["vec_blob"]
        if not blob:
            continue
        vec_row = bytes_ke_vector(blob)
        if len(vec_row) != dim:
            continue
        norm_v = math.sqrt(sum(y * y for y in vec_row))
        if norm_v <= 0.0:
            continue
        dot = sum(x * y for x, y in zip(query_vec, vec_row))
        cosine = max(-1.0, min(1.0, dot / (norm_q * norm_v)))
        dist = 1.0 - cosine
        if dist <= MAX_COSINE_DISTANCE:
            kandidat.append((dist, r))

    kandidat.sort(key=lambda pair: (pair[0], -int(pair[1]["id"])))
    hasil: list[dict[str, Any]] = []
    for dist, r in kandidat[: int(limit)]:
        d = _baris_ke_dict(r, "VECTOR_COSINE")
        d.pop("vec_blob", None)
        d["skor_jarak_vektor"] = round(dist, 4)
        hasil.append(d)
    return hasil


def cari_vektor_solusi_conn(
    conn: sqlite3.Connection,
    kode_proyek: str,
    kata_kunci: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Pencarian semantik jarak kosinus via virtual table `laci_arsip_vec` (sqlite-vec)."""
    try:
        ada_tabel = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='laci_arsip_vec'"
        ).fetchone()
        if not ada_tabel:
            return []

        from .embedding import generate_embedding, get_active_embedding_backend, vector_ke_bytes

        vec = generate_embedding(kata_kunci)
        aktif_backend = get_active_embedding_backend()
        raw_bytes = vector_ke_bytes(vec)
        k_pool = max(50, int(limit) * 10)

        query_sql = """
            SELECT a.id, a.kode_proyek, a.tag_masalah, a.solusi_paten, a.waktu_dibuat,
                   COALESCE(a.confidence, 0.7) AS confidence,
                   COALESCE(a.hit_count, 0) AS hit_count,
                   COALESCE(a.miss_count, 0) AS miss_count,
                   COALESCE(a.is_stale, 0) AS is_stale,
                   COALESCE(a.catatan_evaluasi, '') AS catatan_evaluasi,
                   v.distance AS skor_jarak_vektor
            FROM laci_arsip_vec v
            JOIN laci_arsip a ON v.id = a.id
            WHERE v.embedding MATCH ?
              AND v.id IN (
                  SELECT id FROM laci_arsip
                  WHERE kode_proyek = ?
                    AND (embedding_backend IS NULL OR embedding_backend = ?)
              )
              AND v.k = ?
            ORDER BY v.distance ASC
            LIMIT ?
        """
        rows = conn.execute(query_sql, (raw_bytes, kode_proyek, aktif_backend, k_pool, int(limit))).fetchall()
        if len(rows) < int(limit):
            total_row = conn.execute("SELECT COUNT(*) FROM laci_arsip_vec").fetchone()
            total_vec = int(total_row[0]) if total_row else 0
            if total_vec >= k_pool:
                return _cari_vektor_terfilter_proyek(conn, kode_proyek, aktif_backend, vec, int(limit))
        hasil: list[dict[str, Any]] = []
        for r in rows:
            dist = float(r["skor_jarak_vektor"])
            if dist > MAX_COSINE_DISTANCE:
                continue
            d = _baris_ke_dict(r, "VECTOR_COSINE")
            d["skor_jarak_vektor"] = round(dist, 4)
            hasil.append(d)
        return hasil
    except Exception as exc:
        logger.debug("Pencarian vektor dilewati: %s", exc)
        return []


def reciprocal_rank_fusion(
    daftar_hasil: list[list[dict[str, Any]]], k: int = 60
) -> list[dict[str, Any]]:
    """Menggabungkan hasil perangkingan multi-jalur menggunakan Reciprocal Rank Fusion (RRF) + Bayesian Hit-Ratio."""
    skor_rrf: dict[int, float] = {}
    item_map: dict[int, dict[str, Any]] = {}
    metode_map: dict[int, list[str]] = {}

    for daftar in daftar_hasil:
        for rank, item in enumerate(daftar, 1):
            item_id = int(item["id"])
            if item_id not in item_map:
                item_map[item_id] = dict(item)
                metode_map[item_id] = []
            m = item.get("metode", "UNKNOWN")
            if m not in metode_map[item_id]:
                metode_map[item_id].append(m)
            skor_rrf[item_id] = skor_rrf.get(item_id, 0.0) + (1.0 / (k + rank))

    hasil_akhir: list[dict[str, Any]] = []
    for item_id, base_score in skor_rrf.items():
        data = item_map[item_id]
        conf = float(data.get("confidence", 0.7))
        hit = int(data.get("hit_count", 0))
        miss = int(data.get("miss_count", 0))
        is_stale = int(data.get("is_stale", 0))
        rasio_bayesian = (hit + 1.0) / (hit + miss + 2.0)
        pengali_hit = 0.85 + 0.30 * rasio_bayesian
        # Penalti stale jika solusi usang, boost jika confidence & hit ratio tinggi
        pengali = (0.5 + 0.5 * conf) * pengali_hit * (0.35 if is_stale else 1.0)
        skor_final = base_score * pengali
        data["skor_rrf"] = round(skor_final, 6)
        # Tetapkan metode utama (prioritaskan FTS5_BM25 untuk backward compatibility test)
        if "FTS5_BM25" in metode_map[item_id]:
            data["metode"] = "FTS5_BM25"
        elif "LIKE_FALLBACK" in metode_map[item_id]:
            data["metode"] = "LIKE_FALLBACK"
        elif "HOT_BUFFER" in metode_map[item_id]:
            data["metode"] = "HOT_BUFFER"
        else:
            data["metode"] = "VECTOR_COSINE"
        data["jalur"] = metode_map[item_id]
        hasil_akhir.append(data)

    hasil_akhir.sort(key=lambda x: (x.get("skor_rrf", 0.0), x.get("waktu_dibuat", "")), reverse=True)
    return hasil_akhir


def cari_hot_buffer_antrean(
    conn: sqlite3.Connection,
    kode_proyek: str,
    kata_kunci: str,
    unit_spesifik: list[str],
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Mencari solusi baru pada antrean_mentah (status_rangkum = 0) yang belum sempat dikonsolidasi."""
    if not unit_spesifik:
        return []
    try:
        rows = conn.execute(
            """
            SELECT id, kode_proyek, isi_log, waktu_masuk
            FROM antrean_mentah
            WHERE kode_proyek = ? AND status_rangkum = 0
            ORDER BY id DESC
            LIMIT 50
            """,
            (kode_proyek,),
        ).fetchall()
        if not rows:
            return []

        from .consolidator import _RE_GAGAL, _RE_SOLUSI_KATA, _RE_SOLUSI_MARKER, layak_masuk_laci_arsip

        hasil: list[dict[str, Any]] = []
        for r in rows:
            isi = str(r["isi_log"] or "").strip()
            if not isi or re.match(r"^\s*error\s*:", isi, re.I) or _RE_GAGAL.search(isi):
                continue
            tags_ditemukan = normalisasi_tag(re.findall(r"#[0-9A-Za-z_\-]+", isi))
            punya_penanda_solusi = bool(_RE_SOLUSI_MARKER.search(isi)) or bool(_RE_SOLUSI_KATA.search(isi))
            if not punya_penanda_solusi and not (tags_ditemukan and layak_masuk_laci_arsip(isi, tags_ditemukan)):
                continue
            tag_str = ", ".join(tags_ditemukan) if tags_ditemukan else "#hot-buffer"
            kandidat = {
                "id": -int(r["id"]),  # ID negatif penanda entri hot-buffer sementara
                "kode_proyek": r["kode_proyek"],
                "tag_masalah": tag_str,
                "solusi_paten": f"[Hot-Buffer Antrean] {isi}",
                "waktu_dibuat": r["waktu_masuk"],
                "confidence": 0.72,
                "hit_count": 0,
                "miss_count": 0,
                "is_stale": 0,
                "skor_bm25": None,
                "metode": "HOT_BUFFER",
                "hot_buffer": True,
            }
            if _hasil_memenuhi_relevansi(kandidat, unit_spesifik):
                hasil.append(kandidat)
                if len(hasil) >= limit:
                    break
        return hasil
    except Exception as exc:
        logger.debug("Pencarian hot-buffer dilewati: %s", exc)
        return []


def cari_lintas_proyek(
    conn: sqlite3.Connection,
    kode_asal: str,
    kata_kunci: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Fallback: mencari solusi dari proyek lain yang memiliki kesamaan konteks/stack teknologi."""
    try:
        from .consolidator import deteksi_teknologi, jaccard_similarity

        row_ktp = conn.execute(
            "SELECT ringkasan_inti FROM ktp_proyek WHERE kode_proyek = ?", (kode_asal,)
        ).fetchone()
        stack_asal = set(deteksi_teknologi(row_ktp["ringkasan_inti"])) if row_ktp else set()

        proyek_lain_rows = conn.execute(
            "SELECT DISTINCT kode_proyek FROM laci_arsip WHERE kode_proyek != ?", (kode_asal,)
        ).fetchall()

        kandidat_proyek: list[tuple[float, str]] = []
        for r in proyek_lain_rows:
            p_kode = r["kode_proyek"]
            p_ktp = conn.execute(
                "SELECT ringkasan_inti FROM ktp_proyek WHERE kode_proyek = ?", (p_kode,)
            ).fetchone()
            stack_p = set(deteksi_teknologi(p_ktp["ringkasan_inti"])) if p_ktp else set()
            sim = jaccard_similarity(stack_asal, stack_p) if (stack_asal and stack_p) else 0.1
            kandidat_proyek.append((sim, p_kode))

        kandidat_proyek.sort(key=lambda x: x[0], reverse=True)

        token_mentah = ekstrak_token_kata_kunci(kata_kunci)
        ada_spesifik = any(t.lstrip("#") not in GENERIC_NOISE_TOKENS for t in token_mentah)
        unit_spesifik = _unit_pencocokan_spesifik(saring_token_spesifik(token_mentah)) if ada_spesifik else []
        if not unit_spesifik:
            return []

        hasil_lintas: list[dict[str, Any]] = []
        for sim_skor, p_kode in kandidat_proyek[:3]:
            hasil = cari_solusi_fts_conn(conn, p_kode, kata_kunci, limit=limit, cari_eksternal=False)
            for h in hasil:
                if not _hasil_memenuhi_relevansi(h, unit_spesifik):
                    continue
                if h.get("metode") == "VECTOR_COSINE" and float(h.get("skor_jarak_vektor") or 1.0) > 0.28:
                    continue
                item = dict(h)
                item["lintas_proyek"] = True
                item["proyek_asal"] = p_kode
                item["confidence"] = round(float(item.get("confidence", 0.7)) * 0.7, 2)
                item["solusi_paten"] = (
                    f"[Diadopsi dari Proyek '{p_kode}'] {item['solusi_paten']}"
                )
                hasil_lintas.append(item)
                if len(hasil_lintas) >= limit:
                    break
            if len(hasil_lintas) >= limit:
                break
        return hasil_lintas
    except Exception as exc:
        logger.debug("Pencarian lintas proyek dilewati: %s", exc)
        return []


def cari_solusi_fts_conn(
    conn: sqlite3.Connection,
    kode_proyek: str,
    kata_kunci: str,
    limit: int = 3,
    cari_eksternal: bool = True,
) -> list[dict[str, Any]]:
    """Versi :func:`cari_solusi_fts` hybrid (BM25 + Vector + RRF + Hot-Buffer + Cross-Project Fallback)."""
    kode = normalisasi_kode_proyek(kode_proyek)
    limit = max(1, min(int(limit), 10))  # Default Top-3 untuk MCP tool; hingga 10 untuk pencarian GUI
    token_mentah = ekstrak_token_kata_kunci(kata_kunci)
    ada_spesifik = any(t.lstrip("#") not in GENERIC_NOISE_TOKENS for t in token_mentah)
    unit_spesifik = _unit_pencocokan_spesifik(saring_token_spesifik(token_mentah)) if ada_spesifik else []

    # 1. Jalur Leksikal (FTS5 BM25)
    query = bangun_query_fts(kata_kunci)
    hasil_leksikal: list[dict[str, Any]] = []
    if query:
        try:
            rows = conn.execute(QUERY_SQL_BM25, (query, kode, 10)).fetchall()
            hasil_leksikal = [
                d
                for r in rows
                if _hasil_memenuhi_relevansi(d := _baris_ke_dict(r, "FTS5_BM25"), unit_spesifik)
            ]
        except sqlite3.Error as exc:
            logger.warning("Query FTS5 gagal (%s) -> fallback LIKE. query=%s", exc, query)
            hasil_leksikal = []
    if not hasil_leksikal:
        kandidat_like = cari_fallback_like(conn, kode, kata_kunci, limit=10)
        hasil_leksikal = [d for d in kandidat_like if _hasil_memenuhi_relevansi(d, unit_spesifik)]

    # 2. Jalur Semantik (sqlite-vec)
    hasil_vektor: list[dict[str, Any]] = []
    if not (ada_spesifik and not unit_spesifik):
        kandidat_vec = cari_vektor_solusi_conn(conn, kode, kata_kunci, limit=10)
        hasil_vektor = [
            v for v in kandidat_vec if _hasil_memenuhi_relevansi(v, unit_spesifik)
        ]

    # 3. Fusion & Ranking
    jalur_list = []
    if hasil_leksikal:
        jalur_list.append(hasil_leksikal)
    if hasil_vektor:
        jalur_list.append(hasil_vektor)

    if jalur_list:
        hasil = reciprocal_rank_fusion(jalur_list)[:limit]
    else:
        hasil = []

    # 4. Fallback Hot-Buffer (antrean_mentah yang belum dirangkum) pada proyek aktif
    if not hasil and unit_spesifik:
        hasil = cari_hot_buffer_antrean(conn, kode, kata_kunci, unit_spesifik, limit=limit)

    # 5. Fallback Lintas Proyek jika belum ada solusi pada proyek aktif
    if not hasil and cari_eksternal:
        hasil = cari_lintas_proyek(conn, kode, kata_kunci, limit=limit)

    # 6. Cek relasi kausal / supersesi
    if hasil:
        try:
            ada_relasi = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='relasi_solusi'"
            ).fetchone()
            if ada_relasi:
                for item in hasil:
                    if int(item.get("id", 0)) <= 0:
                        continue
                    rel_row = conn.execute(
                        "SELECT source_id FROM relasi_solusi WHERE target_id = ? AND relasi = 'SUPERSEDED' LIMIT 1",
                        (int(item["id"]),),
                    ).fetchone()
                    if rel_row:
                        item["superseded_by"] = int(rel_row["source_id"])
                        item["solusi_paten"] = (
                            f"⚠️ [Solusi ini telah diperbarui oleh Solusi #{rel_row['source_id']}] {item['solusi_paten']}"
                        )
        except Exception as exc:
            logger.debug("Pemeriksaan relasi solusi dilewati: %s", exc)

    return hasil


def cari_solusi_fts(
    kode_proyek: str, kata_kunci: str, limit: int = 3, db_path: str | None = None
) -> list[dict[str, Any]]:
    """Mencari Top-N solusi paling relevan (Hybrid BM25 + Vector) pada ``laci_arsip``.

    Returns:
        list dict berisi ``id, kode_proyek, tag_masalah, solusi_paten, waktu_dibuat,
        confidence, hit_count, is_stale, skor_bm25/skor_rrf, metode``.
    """
    with koneksi(db_path) as conn:
        return cari_solusi_fts_conn(conn, kode_proyek, kata_kunci, limit)
