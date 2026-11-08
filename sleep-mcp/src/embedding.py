"""Modul embedding vektor lokal untuk Sleep-MCP v2 (Hybrid Search).

Fitur:
* Model lokal hemat daya dan cepat (384 dimensi, berbasis ONNX via fastembed).
* Fallback deterministik n-gram feature hashing jika fastembed tidak tersedia
  sehingga 100% luring (offline) tanpa dependensi jaringan.
* Serialisasi biner struct pack float32 untuk integrasi native dengan virtual table `sqlite-vec`.
"""

from __future__ import annotations

import hashlib
import re
import struct
from typing import Any, Iterable, Sequence

from .config import setup_logging

logger = setup_logging("sleep_mcp.embedding")

DIMENSI_VEKTOR: int = 384
NAMA_MODEL_DEFAULT: str = "BAAI/bge-small-en-v1.5"

_model_cache: Any = None
_model_failed: bool = False


_SINONIM_EMBEDDING: dict[str, str] = {
    "koneksi": "connection",
    "terkunci": "locked lock",
    "lambat": "slow timeout",
    "kedaluwarsa": "expired",
    "kadaluarsa": "expired",
    "izin": "permission unauthorized",
    "autentikasi": "auth authentication",
    "migrasi": "migration",
    "memori": "memory oom",
    "antrean": "queue buffer",
    "sertifikat": "ssl tls certificate",
}


def _bersihkan_teks_embedding(teks: str) -> str:
    """Membersihkan spasi ganda dan memperkaya sinonim teknis lintas bahasa (ID <-> EN)."""
    bersih = re.sub(r"\s+", " ", str(teks or "")).strip()
    if not bersih:
        return ""
    rendah = bersih.lower()
    tambahan: list[str] = []
    for kata_id, padanan_en in _SINONIM_EMBEDDING.items():
        if kata_id in rendah and padanan_en not in rendah:
            tambahan.append(padanan_en)
    if tambahan:
        return f"{bersih} {' '.join(tambahan)}"
    return bersih


def _get_fastembed_model() -> Any:
    """Lazy loader untuk model fastembed."""
    global _model_cache, _model_failed
    if _model_cache is not None:
        return _model_cache
    if _model_failed:
        return None

    try:
        from fastembed import TextEmbedding

        _model_cache = TextEmbedding(model_name=NAMA_MODEL_DEFAULT)
        logger.info("FastEmbed loaded model '%s' (dimensi=%d)", NAMA_MODEL_DEFAULT, DIMENSI_VEKTOR)
        return _model_cache
    except Exception as exc:
        _model_failed = True
        logger.warning(
            "FastEmbed gagal diinisialisasi (%s). Mengaktifkan fallback feature hashing.", exc
        )
        return None


def _fallback_hash_embedding(teks: str, dim: int = DIMENSI_VEKTOR) -> list[float]:
    """Fallback deterministik 100% offline menggunakan n-gram feature hashing + normalisasi L2."""
    clean = _bersihkan_teks_embedding(teks).lower()
    vec = [0.0] * dim
    if not clean:
        return vec

    # Ekstraksi unigram kata & trigram karakter
    tokens = re.findall(r"[\w#-]+", clean)
    for tok in tokens:
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest()[:8], 16) % dim
        vec[h] += 2.0  # Bobot kata utuh

    # Karakter trigram
    for i in range(len(clean) - 2):
        tri = clean[i : i + 3]
        h = int(hashlib.sha1(tri.encode("utf-8")).hexdigest()[:8], 16) % dim
        vec[h] += 1.0

    # Normalisasi L2 (unit norm)
    sq_sum = sum(x * x for x in vec)
    if sq_sum > 0:
        norm = sq_sum**0.5
        vec = [x / norm for x in vec]
    return vec


def get_active_embedding_backend() -> str:
    """Mengembalikan pengenal backend embedding aktif ('fastembed:...' atau 'hash:v1')."""
    if _get_fastembed_model() is not None:
        return f"fastembed:{NAMA_MODEL_DEFAULT}"
    return "hash:v1"


def generate_embedding(teks: str) -> list[float]:
    """Menghasilkan vektor float embedding 384 dimensi untuk sebuah string."""
    clean = _bersihkan_teks_embedding(teks)
    if not clean:
        return [0.0] * DIMENSI_VEKTOR

    model = _get_fastembed_model()
    if model is not None:
        try:
            generator = model.embed([clean])
            vec = next(iter(generator))
            return [float(x) for x in vec]
        except Exception as exc:
            logger.warning("Gagal embed via fastembed (%s), fallback ke hash embedding.", exc)

    return _fallback_hash_embedding(clean)


def batch_embed(daftar_teks: Sequence[str]) -> list[list[float]]:
    """Menghasilkan list vektor untuk sekumpulan string secara efisien."""
    if not daftar_teks:
        return []

    bersih = [_bersihkan_teks_embedding(t) for t in daftar_teks]
    model = _get_fastembed_model()
    if model is not None:
        try:
            hasil = list(model.embed(bersih))
            return [[float(x) for x in v] for v in hasil]
        except Exception as exc:
            logger.warning("Gagal batch embed via fastembed (%s), fallback per item.", exc)

    return [generate_embedding(t) for t in bersih]


def vector_ke_bytes(vec: Sequence[float]) -> bytes:
    """Mengubah sequence float32 menjadi buffer byte biner untuk sqlite-vec."""
    count = len(vec)
    return struct.pack(f"{count}f", *vec)


def bytes_ke_vector(b: bytes) -> list[float]:
    """Mengubah buffer byte biner sqlite-vec menjadi list float."""
    count = len(b) // 4
    return list(struct.unpack(f"{count}f", b))


def simpan_vektor_solusi(
    conn: Any,
    id_solusi: int,
    tag_masalah: str,
    solusi_paten: str,
    precomputed_vec: Sequence[float] | None = None,
    backend: str | None = None,
) -> bool:
    """Membuat dan menyimpan vektor embedding solusi ke tabel virtual `laci_arsip_vec`."""
    try:
        # Periksa apakah tabel virtual laci_arsip_vec tersedia
        ada_tabel = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='laci_arsip_vec'"
        ).fetchone()
        if not ada_tabel:
            return False

        teks_gabungan = f"{tag_masalah} {solusi_paten}"
        vec = list(precomputed_vec) if precomputed_vec is not None else generate_embedding(teks_gabungan)
        aktif_backend = backend or get_active_embedding_backend()
        raw_bytes = vector_ke_bytes(vec)

        # INSERT OR REPLACE pada virtual table vec0
        conn.execute("DELETE FROM laci_arsip_vec WHERE id = ?", (int(id_solusi),))
        conn.execute(
            "INSERT INTO laci_arsip_vec(id, embedding) VALUES (?, ?)",
            (int(id_solusi), raw_bytes),
        )
        try:
            conn.execute(
                "UPDATE laci_arsip SET embedding_backend = ? WHERE id = ?",
                (aktif_backend, int(id_solusi)),
            )
        except Exception:
            pass
        return True
    except Exception as exc:
        logger.warning("Gagal menyimpan vektor solusi id=%s: %s", id_solusi, exc)
        return False


def hapus_vektor_solusi(conn: Any, id_solusi: int) -> bool:
    """Menghapus vektor solusi dari virtual table `laci_arsip_vec`."""
    try:
        ada_tabel = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='laci_arsip_vec'"
        ).fetchone()
        if not ada_tabel:
            return False
        conn.execute("DELETE FROM laci_arsip_vec WHERE id = ?", (int(id_solusi),))
        return True
    except Exception as exc:
        logger.warning("Gagal menghapus vektor solusi id=%s: %s", id_solusi, exc)
        return False


def sinkron_vektor_laci_arsip(conn: Any, limit: int = 200) -> int:
    """Menyinkronkan baris laci_arsip yang belum memiliki embedding atau berbeda backend."""
    try:
        ada_tabel = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='laci_arsip_vec'"
        ).fetchone()
        if not ada_tabel:
            return 0

        aktif_backend = get_active_embedding_backend()
        try:
            rows = conn.execute(
                """
                SELECT a.id, a.tag_masalah, a.solusi_paten
                FROM laci_arsip a
                LEFT JOIN laci_arsip_vec v ON a.id = v.id
                WHERE v.id IS NULL OR a.embedding_backend IS NULL OR a.embedding_backend != ?
                LIMIT ?
                """,
                (aktif_backend, int(limit)),
            ).fetchall()
        except Exception:
            rows = conn.execute(
                """
                SELECT a.id, a.tag_masalah, a.solusi_paten
                FROM laci_arsip a
                LEFT JOIN laci_arsip_vec v ON a.id = v.id
                WHERE v.id IS NULL
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()

        if not rows:
            return 0

        teks_list = [f"{r['tag_masalah']} {r['solusi_paten']}" for r in rows]
        vecs = batch_embed(teks_list)
        aktif_backend = get_active_embedding_backend()

        terproses = 0
        for r, vec in zip(rows, vecs):
            if simpan_vektor_solusi(
                conn,
                int(r["id"]),
                r["tag_masalah"],
                r["solusi_paten"],
                precomputed_vec=vec,
                backend=aktif_backend,
            ):
                terproses += 1
        return terproses
    except Exception as exc:
        logger.debug("Sinkronisasi vektor laci arsip dilewati: %s", exc)
        return 0

