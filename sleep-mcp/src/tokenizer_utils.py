"""Utilitas tokenizer & Elastic/Bounded Enforcement Lapis 1 (KTP Proyek).

Tokenizer utama: ``tiktoken`` encoding ``cl100k_base``. Jika encoding tidak
dapat dimuat (mis. lingkungan offline saat cache BPE belum terunduh), modul
otomatis beralih ke estimator subword deterministik sehingga seluruh sistem
dan pengujian tetap berjalan.

Mendukung dua mode untuk KTP Proyek:
- **Elastic Core Mode** (``max_tokens <= 0`` atau ``None``, default): tidak memotong
  identitas, stack, struktur, maupun aturan proyek besar.
- **Bounded Mode** (``max_tokens > 0``): memangkas secara terstruktur per kalimat/klausa
  hingga ``<= max_tokens`` token.
"""

from __future__ import annotations

import math
import re
import threading
from typing import Any

from .config import get_settings, setup_logging

logger = setup_logging("sleep_mcp.tokenizer")

_ENCODING_NAME = "cl100k_base"
_encoding_lock = threading.Lock()
_encoding: Any = None
_encoding_loaded = False
_encoding_error: str | None = None

# Pola estimator fallback: kata alfanumerik, atau satu karakter non-spasi.
_FALLBACK_PATTERN = re.compile(r"[A-Za-z]+|\d+|[^\sA-Za-z\d]")
_WHITESPACE = re.compile(r"\s+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?;])\s+")
_CLAUSE_SPLIT = re.compile(r"(?<=[,;:])\s+")
_INLINE_CODE_RE = re.compile(r"`[^`]+`")
_TECH_DOT_RE = re.compile(r"(?<=[A-Za-z0-9_/-])\.(?=[A-Za-z0-9_])")
_DOT_PLACEHOLDER = "\x00DOT\x00"
_SEMI_PLACEHOLDER = "\x00SEMI\x00"


def _muat_encoding() -> Any:
    """Memuat encoding tiktoken sekali (thread-safe). None jika gagal/dipaksa fallback."""
    global _encoding, _encoding_loaded, _encoding_error
    if get_settings().force_fallback_tokenizer:
        return None
    if _encoding_loaded:
        return _encoding
    with _encoding_lock:
        if _encoding_loaded:
            return _encoding
        try:
            import tiktoken  # noqa: WPS433 (import lokal agar fallback bekerja)

            _encoding = tiktoken.get_encoding(_ENCODING_NAME)
            _encoding_error = None
        except Exception as exc:  # jaringan/cache tidak tersedia
            _encoding = None
            _encoding_error = f"{type(exc).__name__}: {exc}"
            logger.warning("tiktoken tidak tersedia, memakai estimator fallback (%s)", _encoding_error)
        _encoding_loaded = True
        return _encoding


def nama_tokenizer_aktif() -> str:
    """Nama tokenizer yang sedang dipakai (untuk laporan benchmark)."""
    return f"tiktoken/{_ENCODING_NAME}" if _muat_encoding() is not None else "fallback-subword-estimator"


def estimasi_token_fallback(teks: str) -> int:
    """Estimator subword deterministik (tanpa jaringan).

    Aturan: setiap potongan huruf dihitung ``ceil(panjang / 4)`` token
    (mendekati rata-rata BPE cl100k), potongan angka ``ceil(panjang / 3)``,
    dan setiap simbol/tanda baca/karakter non-ASCII dihitung 1 token.
    """
    if not teks:
        return 0
    total = 0
    for potongan in _FALLBACK_PATTERN.findall(teks):
        if potongan.isalpha() and potongan.isascii():
            total += max(1, math.ceil(len(potongan) / 4))
        elif potongan.isdigit():
            total += max(1, math.ceil(len(potongan) / 3))
        else:
            total += 1
    return total


def hitung_token(teks: str) -> int:
    """Menghitung jumlah token ``teks`` memakai tiktoken cl100k_base (atau fallback)."""
    if not teks:
        return 0
    encoding = _muat_encoding()
    if encoding is None:
        return estimasi_token_fallback(teks)
    return len(encoding.encode(teks, disallowed_special=()))


def potong_ke_token(teks: str, max_tokens: int) -> str:
    """Memotong teks tepat pada batas ``max_tokens`` token."""
    if max_tokens <= 0 or not teks:
        return ""
    encoding = _muat_encoding()
    if encoding is not None:
        ids = encoding.encode(teks, disallowed_special=())
        if len(ids) <= max_tokens:
            return teks
        return encoding.decode(ids[:max_tokens])
    # Fallback: akumulasi kata demi kata
    hasil: list[str] = []
    for kata in teks.split():
        kandidat = " ".join(hasil + [kata])
        if estimasi_token_fallback(kandidat) > max_tokens:
            break
        hasil.append(kata)
    return " ".join(hasil)


def normalisasi_spasi(teks: str) -> str:
    return _WHITESPACE.sub(" ", teks or "").strip()


def _lindungi_token_teknis(teks: str) -> str:
    """Melindungi titik dan titik-koma di dalam backtick, nama file, atau versi."""
    def _mask_inline(match: re.Match[str]) -> str:
        isi = match.group(0)
        return isi.replace(".", _DOT_PLACEHOLDER).replace(";", _SEMI_PLACEHOLDER)

    terlindungi = _INLINE_CODE_RE.sub(_mask_inline, teks)
    terlindungi = _TECH_DOT_RE.sub(_DOT_PLACEHOLDER, terlindungi)
    return terlindungi


def _pulihkan_token_teknis(teks: str) -> str:
    return teks.replace(_DOT_PLACEHOLDER, ".").replace(_SEMI_PLACEHOLDER, ";")


def pecah_kalimat(teks: str) -> list[str]:
    """Memecah paragraf menjadi kalimat (aman terhadap backtick, nama file, & versi)."""
    teks = normalisasi_spasi(teks)
    if not teks:
        return []
    terlindungi = _lindungi_token_teknis(teks)
    potongan = _SENTENCE_SPLIT.split(terlindungi)
    return [_pulihkan_token_teknis(k.strip()) for k in potongan if k.strip()]


def batasi_kalimat(teks: str, maks_kalimat: int = 3) -> str:
    """Mengambil maksimal ``maks_kalimat`` kalimat pertama (dipakai solusi_paten).

    Aman terhadap titik pada nama file (``run.py``), versi (``v2.0``), maupun
    potongan kode inline di dalam backtick (`` `...` ``).
    """
    teks_rapi = normalisasi_spasi(teks)
    if not teks_rapi:
        return ""
    terlindungi = _lindungi_token_teknis(teks_rapi)
    kalimat = [
        _pulihkan_token_teknis(k.strip())
        for k in re.split(r"(?<=[.!?])\s+", terlindungi)
        if k.strip()
    ]
    hasil = " ".join(kalimat[:maks_kalimat]).strip()
    return _tutup_kalimat(hasil) if hasil else ""


def _tutup_kalimat(teks: str) -> str:
    """Merapikan akhir teks: buang koma/titik-dua menggantung, pastikan diakhiri titik."""
    teks = teks.strip().rstrip(",;:-–— ").strip()
    if not teks:
        return ""
    if teks[-1] not in ".!?`)":
        teks += "."
    return teks


def _rapikan_ke_tanda_baca(teks: str) -> str:
    """Memotong mundur ke tanda titik/koma/titik-koma terdekat agar klausa utuh."""
    teks = teks.strip()
    posisi = max(teks.rfind(". "), teks.rfind("; "), teks.rfind(", "))
    if teks.endswith((".", ";", ",")):
        posisi = max(posisi, len(teks) - 1)
    if posisi > len(teks) * 0.3:  # hanya jika tidak membuang terlalu banyak
        teks = teks[: posisi + 1]
    else:
        # potong di batas kata terakhir agar tidak ada kata terpenggal
        if " " in teks:
            teks = teks.rsplit(" ", 1)[0]
    return _tutup_kalimat(teks)


def enforce_hard_limit_ktp(teks: str, max_tokens: int | None = 0) -> tuple[str, int]:
    """Menjaga format KTP Proyek dalam mode Elastic (tanpa batas) atau Bounded (``<= max_tokens``).

    - Jika ``max_tokens is None`` atau ``max_tokens <= 0`` (**Elastic Core Mode**):
      tidak memotong kalimat maupun aturan proyek, hanya menormalisasi spasi dan
      menghitung jumlah token aktual.
    - Jika ``max_tokens > 0`` (**Bounded Mode**):
      memangkas secara terstruktur per kalimat dan klausa hingga ``<= max_tokens`` token.

    Returns:
        tuple ``(teks_hasil, jumlah_token)``.
    """
    teks_bersih = normalisasi_spasi(teks)
    if not teks_bersih:
        return "", 0
    jumlah = hitung_token(teks_bersih)
    if max_tokens is None or max_tokens <= 0 or jumlah <= max_tokens:
        return teks_bersih, jumlah

    hasil: list[str] = []
    for kalimat in pecah_kalimat(teks_bersih):
        kandidat = " ".join(hasil + [kalimat])
        if hitung_token(kandidat) <= max_tokens:
            hasil.append(kalimat)
            continue
        # Kalimat tidak muat utuh -> coba pangkas per klausa
        klausa_muat: list[str] = []
        for klausa in _CLAUSE_SPLIT.split(kalimat):
            percobaan = _tutup_kalimat(" ".join(klausa_muat + [klausa]))
            if hitung_token(" ".join(hasil + [percobaan])) <= max_tokens:
                klausa_muat.append(klausa)
            else:
                break
        if klausa_muat:
            hasil.append(_tutup_kalimat(" ".join(klausa_muat)))
        break

    if not hasil:
        hasil = [_rapikan_ke_tanda_baca(potong_ke_token(teks_bersih, max_tokens))]

    keluaran = normalisasi_spasi(" ".join(hasil))
    if keluaran and keluaran[-1] not in ".!?)":
        keluaran = _tutup_kalimat(keluaran)

    # Loop penjamin: hasil akhir DIJAMIN <= max_tokens
    while keluaran and hitung_token(keluaran) > max_tokens:
        kata = keluaran.split()
        if len(kata) <= 1:
            keluaran = potong_ke_token(keluaran, max_tokens - 1)
            break
        keluaran = _tutup_kalimat(" ".join(kata[:-1]))
    return keluaran, hitung_token(keluaran)
