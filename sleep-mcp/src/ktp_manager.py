"""Modul pengelolaan KTP Proyek (Lapis 1): penguraian, perenderan, distiller lokal, dan rollback."""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from .db import normalisasi_kode_proyek
from .fts_search import normalisasi_tag
from .log_parser import (
    _RE_AKSI_TEKNIS,
    _RE_ATURAN_KATA,
    _RE_ATURAN_MARKER,
    _RE_BASA_BASI,
    _RE_GAGAL,
    _RE_HAPUS_ATURAN,
    _RE_HAPUS_STACK,
    _RE_HASHTAG,
    _RE_IDENTITAS_KATA,
    _RE_IDENTITAS_MARKER,
    _RE_IDENTITAS_PREFIX,
    _RE_KLAUSA_ALASAN,
    _RE_MASALAH,
    _RE_MIGRASI_STACK,
    _RE_NARASI_CHANGELOG,
    _RE_PROMPT_INJECTION,
    _RE_SOLUSI_KATA,
    _RE_SOLUSI_MARKER,
    _RE_STACK_MARKER,
    _RE_STRUKTUR_MARKER,
    _TAG_NON_SOLUSI,
    _batas_aturan_aktif,
    _buang_hashtag,
    _gabung_unik,
    _hapus_aturan_usang,
    _kalimat_dari_baris,
    _rapikan_aturan,
    _split_item,
    _tutup,
    bangun_tag_gejala,
    bersihkan_injeksi_memori,
    deteksi_direktori,
    deteksi_teknologi,
    gabung_aturan,
    layak_masuk_laci_arsip,
    pisahkan_noise,
)
from .tokenizer_utils import (
    batasi_kalimat,
    enforce_hard_limit_ktp,
    hitung_token,
    normalisasi_spasi,
    pecah_kalimat,
    potong_ke_token,
)

_RE_LABEL_STACK = re.compile(r"\bStack\s*:\s*(.*?)(?=\s*\b(?:Struktur|Aturan)\s*:|$)", re.S)
_RE_LABEL_STRUKTUR = re.compile(r"\bStruktur\s*:\s*(.*?)(?=\s*\b(?:Stack|Aturan)\s*:|$)", re.S)
_RE_LABEL_ATURAN = re.compile(r"\bAturan(?:\s+wajib)?\s*:\s*(.*)$", re.S | re.I)
_RE_KTP_SECTION = re.compile(
    r"(?:^|[.!?;]\s+|\n\s*)(?P<lbl>Stack|Struktur|Aturan(?:\s+wajib)?)\s*:"
    r"|\s+\b(?P<lbl_mid>Stack|Struktur)\s*:"
    r"|\s+\b(?P<lbl_aturan_num>Aturan(?:\s+wajib)?)\s*:(?=\s*\(\d+\))",
    re.S,
)


def _pecah_daftar_aturan(badan: str) -> list[str]:
    """Memecah blok teks aturan menjadi daftar aturan utuh tanpa memotong koma/tanda kurung.

    Juga menyatukan kembali fragmen kalimat yang sempat terpecah akibat penomoran/koma
    di dalam kalimat atau tanda kurung (mis. ``(1) DILARANG mengakses; (2) Membaca; ...``).
    """
    teks = badan.strip()
    if not teks:
        return []
    if re.search(r"\(\d+\)", teks):
        mentah = re.split(r"\(\d+\)\s*", teks)
    elif ";" in teks:
        mentah = re.split(r";(?![^()]*\))\s*", teks)
    else:
        mentah = [teks]

    hasil: list[str] = []
    for item in mentah:
        bersih = _rapikan_aturan(item)
        if not bersih:
            continue
        kata = bersih.split()
        kurung_belum_tutup = bool(hasil and hasil[-1].count("(") > hasil[-1].count(")"))
        diawali_konjungsi_atau_pola = bool(
            re.match(r"^(?:atau|dan|serta|maupun|or|and)\b", bersih, re.I)
            or bersih.startswith("*.")
        )
        fragmen_pendek_tanpa_subjek = len(kata) < 3 and not _RE_ATURAN_KATA.search(bersih)
        if hasil and (kurung_belum_tutup or diawali_konjungsi_atau_pola or fragmen_pendek_tanpa_subjek):
            lanjutan = bersih[0].lower() + bersih[1:] if len(bersih) > 1 and not bersih[:2].isupper() else bersih
            hasil[-1] = f"{hasil[-1].rstrip(' ,;.')}, {lanjutan}"
        else:
            hasil.append(bersih)
    return hasil


def urai_ktp(ktp: str, kode_proyek: str = "") -> dict[str, Any]:
    """Mengurai KTP lama menjadi identitas, stack, struktur, dan daftar aturan.

    Mendukung format terstruktur hasil distiller lokal
    (``... Stack: ... Struktur: ... Aturan: (1) ...; (2) ...``) maupun
    paragraf bebas hasil LLM / suntingan manual di dashboard.
    """
    hasil: dict[str, Any] = {"identitas": "", "stack": [], "struktur": [], "aturan": []}
    teks = normalisasi_spasi(ktp)
    if not teks:
        return hasil
    matches = list(_RE_KTP_SECTION.finditer(teks))
    if matches:
        pertama = matches[0]
        start_pertama = next(
            pertama.start(g) for g in ("lbl", "lbl_mid", "lbl_aturan_num") if pertama.group(g)
        )
        identitas = teks[:start_pertama].strip()
        identitas = (
            re.sub(rf"^Proyek\s+{re.escape(kode_proyek)}\s*:\s*", "", identitas, flags=re.I)
            if kode_proyek
            else identitas
        )
        identitas = re.sub(r"^Proyek\s+[\w.-]+\s*:\s*", "", identitas, flags=re.I)
        hasil["identitas"] = identitas.strip().rstrip(".").strip()

        spans: list[tuple[int, int, str]] = []
        for idx, m in enumerate(matches):
            lbl_val = ""
            for grp in ("lbl", "lbl_mid", "lbl_aturan_num"):
                if m.group(grp):
                    lbl_val = m.group(grp)
                    break
            next_start = len(teks)
            if idx + 1 < len(matches):
                nxt = matches[idx + 1]
                next_start = next(
                    nxt.start(g) for g in ("lbl", "lbl_mid", "lbl_aturan_num") if nxt.group(g)
                )
            nama_seksi = "aturan" if lbl_val.lower().startswith("aturan") else lbl_val.lower()
            spans.append((m.end(), next_start, nama_seksi))

        for awal, akhir, nama_seksi in spans:
            isi_seksi = teks[awal:akhir].strip()
            if not isi_seksi:
                continue
            if nama_seksi == "stack":
                hasil["stack"] = _gabung_unik(hasil["stack"], _split_item(isi_seksi.rstrip(" .;")))
            elif nama_seksi == "struktur":
                hasil["struktur"] = _gabung_unik(hasil["struktur"], _split_item(isi_seksi.rstrip(" .;")))
            elif nama_seksi == "aturan":
                for rule in _pecah_daftar_aturan(isi_seksi):
                    if rule and rule not in hasil["aturan"]:
                        hasil["aturan"].append(rule)
        return hasil

    # Paragraf bebas: klasifikasi per kalimat
    identitas_bagian: list[str] = []
    for kalimat in pecah_kalimat(teks):
        m_daftar = re.match(r"^(.*?\baturan\b[^:]*):\s*(.+)$", kalimat, re.I)
        if m_daftar:
            hasil["aturan"].extend(_pecah_daftar_aturan(m_daftar.group(2)))
            continue
        if _RE_ATURAN_KATA.search(kalimat):
            hasil["aturan"].append(_rapikan_aturan(kalimat))
        else:
            identitas_bagian.append(kalimat.rstrip("."))
    hasil["stack"] = deteksi_teknologi(teks)
    hasil["struktur"] = deteksi_direktori(teks)
    if identitas_bagian:
        identitas = re.sub(r"^Proyek\s+[\w.-]+\s*:\s*", "", identitas_bagian[0], flags=re.I)
        hasil["identitas"] = identitas
    return hasil


def identitas_bermakna(identitas: str, kode: str) -> str:
    """Mengembalikan identitas apa adanya, atau '' jika hanya mengulang nama proyek (tautologi)."""
    teks = normalisasi_spasi(identitas or "").strip(" .:;-")
    while True:
        baru = re.sub(r"^Proyek\s+[\w.-]+\s*:\s*", "", teks, flags=re.I).strip(" .:;-")
        if baru == teks:
            break
        teks = baru
    if not teks:
        return ""
    kandidat = {kode.lower(), f"proyek {kode}".lower(), f"project {kode}".lower()}
    return "" if teks.lower() in kandidat else teks


def _render_ktp(kode: str, identitas: str, stack: list[str], struktur: list[str], aturan: list[str]) -> str:
    bagian: list[str] = []
    identitas = identitas_bermakna(identitas, kode)
    kepala = f"Proyek {kode}: {identitas}" if identitas else f"Proyek {kode}"
    bagian.append(_tutup(kepala))
    if stack:
        bagian.append(f"Stack: {', '.join(stack)}.")
    if struktur:
        bagian.append(f"Struktur: {', '.join(struktur)}.")
    if aturan:
        bagian.append("Aturan: " + "; ".join(f"({i}) {a}" for i, a in enumerate(aturan, 1)) + ".")
    return " ".join(bagian)


def _ringkas_identitas(identitas: str, max_tokens: int) -> str:
    teks = re.split(r",\s+|\s+dengan\s+|\s+yang\s+", identitas, maxsplit=1)[0]
    if hitung_token(teks) > max_tokens:
        teks = potong_ke_token(teks, max_tokens).rsplit(" ", 1)[0]
    return teks.strip(" ,;.")


def susun_ktp_terbatas(
    kode: str,
    identitas: str,
    stack: list[str],
    struktur: list[str],
    aturan: list[str],
    max_tokens: int | None = 0,
) -> str:
    """Menyusun KTP terstruktur dalam mode Elastic (tanpa batas) atau Bounded (``<= max_tokens``)."""
    if max_tokens is None or max_tokens <= 0:
        return _render_ktp(kode, identitas, stack, struktur, aturan)

    aturan_ringkas = [_RE_KLAUSA_ALASAN.sub("", a).strip() or a for a in aturan]
    tahapan = [
        (identitas, stack[:8], struktur[:6], aturan),
        (identitas, stack[:6], struktur[:4], aturan),
        (_ringkas_identitas(identitas, 30), stack[:6], struktur[:3], aturan),
        (_ringkas_identitas(identitas, 20), stack[:5], struktur[:2], aturan),
        (_ringkas_identitas(identitas, 20), stack[:5], struktur[:2], aturan_ringkas),
        (_ringkas_identitas(identitas, 15), stack[:4], [], aturan_ringkas),
        (_ringkas_identitas(identitas, 10), stack[:3], [], aturan_ringkas),
        ("", stack[:2], [], aturan_ringkas),
        ("", [], [], aturan_ringkas),
    ]
    for ident, st, sr, at in tahapan:
        teks = _render_ktp(kode, ident, st, sr, at)
        if hitung_token(teks) <= max_tokens:
            return teks
    teks, _ = enforce_hard_limit_ktp(_render_ktp(kode, "", [], [], aturan_ringkas), max_tokens)
    return teks


def local_rule_based_distiller(
    kode_proyek: str,
    ktp_lama: str,
    arsip_eksisting: list[dict[str, Any]],
    log_batch: list[Any],
    max_tokens: int | None = 0,
) -> dict[str, Any]:
    """Distiller deterministik pengganti LLM (100% offline & bebas race condition)."""
    kode = normalisasi_kode_proyek(kode_proyek)
    lama = urai_ktp(ktp_lama or "", kode)
    identitas = identitas_bermakna(lama["identitas"], kode)
    stack: list[str] = list(lama["stack"])
    struktur: list[str] = list(lama["struktur"])
    aturan_lama_aktif: list[str] = list(lama["aturan"])
    aturan_dihapus: list[str] = []
    stack_dihapus: set[str] = set()
    aturan_baru: list[str] = []
    arsip_solusi: list[dict[str, Any]] = []

    pending_hashtag: list[str] = []
    pending_error: list[str] = []
    pending_teks: list[str] = []

    for entri in log_batch:
        isi = entri.get("isi_log", "") if isinstance(entri, dict) else str(entri)
        baris_bersih, baris_error, _ = pisahkan_noise(isi)
        hashtags = _RE_HASHTAG.findall(isi.lower())
        teks_bersih = " ".join(baris_bersih)
        entri_bug = bool(baris_error) or bool(_RE_MASALAH.search(teks_bersih))

        solusi_kalimat: list[str] = []
        kandidat_solusi_hashtag: list[str] = []
        stack_entri: list[str] = []
        struktur_entri: list[str] = []

        for kalimat in _kalimat_dari_baris(baris_bersih):
            k = kalimat.strip()
            if not k or _RE_BASA_BASI.match(k) or _RE_PROMPT_INJECTION.search(k):
                continue

            m_hapus_aturan = _RE_HAPUS_ATURAN.match(k)
            if m_hapus_aturan:
                aturan_dihapus.append(m_hapus_aturan.group(1))
                continue

            for m_mig in _RE_MIGRASI_STACK.finditer(k):
                asal_raw, tujuan_raw = m_mig.group(1), m_mig.group(2)
                for t_asal in deteksi_teknologi(asal_raw) or [asal_raw]:
                    stack_dihapus.add(t_asal.lower())
                stack_entri.extend(deteksi_teknologi(tujuan_raw) or [tujuan_raw])

            for m_hst in _RE_HAPUS_STACK.finditer(k):
                hapus_raw = m_hst.group(1)
                for t_hps in deteksi_teknologi(hapus_raw):
                    stack_dihapus.add(t_hps.lower())

            if _RE_SOLUSI_MARKER.match(k):
                solusi_kalimat.append(_RE_SOLUSI_MARKER.sub("", k))
                continue
            if _RE_ATURAN_MARKER.match(k):
                isi_at = _RE_ATURAN_MARKER.sub("", k).strip()
                m_sub_hapus = _RE_HAPUS_ATURAN.match(isi_at)
                if m_sub_hapus:
                    aturan_dihapus.append(m_sub_hapus.group(1))
                    continue
                aturan = _rapikan_aturan(k)
                if aturan:
                    aturan_baru.append(aturan)
                continue
            if _RE_STACK_MARKER.match(k):
                isi_stack = _RE_STACK_MARKER.sub("", k)
                terdeteksi = deteksi_teknologi(isi_stack)
                stack_entri.extend(terdeteksi or _split_item(isi_stack))
                continue
            if _RE_STRUKTUR_MARKER.match(k):
                isi_struktur = _RE_STRUKTUR_MARKER.sub("", k)
                struktur_entri.extend(deteksi_direktori(isi_struktur) or _split_item(isi_struktur))
                continue
            if _RE_IDENTITAS_MARKER.match(k) and not _RE_IDENTITAS_KATA.match(k):
                identitas = _buang_hashtag(_RE_IDENTITAS_MARKER.sub("", k)).rstrip(".")
                stack_entri.extend(deteksi_teknologi(k))
                continue
            if _RE_SOLUSI_KATA.search(k) and not _RE_GAGAL.search(k):
                solusi_kalimat.append(k)
                stack_entri.extend(deteksi_teknologi(k))
                struktur_entri.extend(deteksi_direktori(k))
                continue
            if _RE_GAGAL.search(k):
                continue
            if _RE_IDENTITAS_KATA.match(k):
                identitas = _buang_hashtag(_RE_IDENTITAS_PREFIX.sub("", k)).rstrip(".")
                identitas = identitas[:1].upper() + identitas[1:]
                stack_entri.extend(deteksi_teknologi(k))
                continue
            if (
                _RE_ATURAN_KATA.search(k)
                and not entri_bug
                and not _RE_NARASI_CHANGELOG.search(k)
                and len(k.split()) <= 25
            ):
                aturan = _rapikan_aturan(k)
                if aturan:
                    aturan_baru.append(aturan)
                continue
            if hashtags and _RE_AKSI_TEKNIS.search(k):
                kandidat_solusi_hashtag.append(k)
            if entri_bug and _RE_MASALAH.search(k):
                continue
            stack_entri.extend(deteksi_teknologi(k))
            struktur_entri.extend(deteksi_direktori(k))

        if not solusi_kalimat and kandidat_solusi_hashtag:
            tags_kandidat = normalisasi_tag(hashtags)
            if not (set(tags_kandidat) <= _TAG_NON_SOLUSI):
                solusi_kalimat.extend(kandidat_solusi_hashtag)

        stack = _gabung_unik(stack, stack_entri)
        if stack_dihapus:
            stack = [s for s in stack if s.lower() not in stack_dihapus]
        struktur = _gabung_unik(struktur, struktur_entri)

        if solusi_kalimat:
            teks_gejala = " ".join(pending_teks + [isi])
            tags = bangun_tag_gejala(pending_hashtag + hashtags, pending_error + baris_error, teks_gejala)
            gabung_sol = " ".join(_buang_hashtag(s) for s in solusi_kalimat)
            batas_kal = 3 if "`" in gabung_sol else 2
            solusi = batasi_kalimat(gabung_sol, batas_kal)
            solusi = solusi[:1].upper() + solusi[1:] if solusi else solusi
            id_target = None
            for arsip in arsip_eksisting:
                tag_lama = normalisasi_tag(arsip.get("tag_masalah", ""))
                if tag_lama and tags and tag_lama[0] == tags[0]:
                    id_target = int(arsip["id"])
                    break
            if solusi and layak_masuk_laci_arsip(solusi, tags):
                arsip_solusi.append(
                    {"id_arsip_target": id_target, "tag_masalah": ", ".join(tags), "solusi_paten": solusi}
                )
            pending_hashtag, pending_error, pending_teks = [], [], []
        elif entri_bug:
            pending_hashtag.extend(hashtags)
            pending_error.extend(baris_error)
            pending_teks.append(isi)

    aturan_lama_aktif = _hapus_aturan_usang(aturan_lama_aktif, aturan_dihapus)
    aturan = gabung_aturan(aturan_lama_aktif, aturan_baru, max_aturan=_batas_aturan_aktif(max_tokens))
    ktp_baru = susun_ktp_terbatas(kode, identitas, stack, struktur, aturan, max_tokens)
    return {"ktp_proyek_baru": ktp_baru, "arsip_solusi": arsip_solusi}


def terapkan_ktp_baru(
    conn: sqlite3.Connection,
    kode_proyek: str,
    teks_ktp: str,
    max_tokens: int | None = 0,
    simpan_snapshot: bool = True,
) -> dict[str, Any]:
    """UPSERT KTP: ringkasan lama -> ringkasan_sebelumnya, versi_ktp + 1, mendukung Elastic Core (max_tokens=0)."""
    teks_aman = bersihkan_injeksi_memori(teks_ktp)
    teks, jumlah = enforce_hard_limit_ktp(teks_aman, max_tokens)
    if not teks:
        raise ValueError("KTP Proyek baru kosong setelah normalisasi.")
    row = conn.execute(
        "SELECT ringkasan_inti, versi_ktp FROM ktp_proyek WHERE kode_proyek = ?", (kode_proyek,)
    ).fetchone()
    if row is None:
        conn.execute(
            """
            INSERT INTO ktp_proyek (kode_proyek, ringkasan_inti, ringkasan_sebelumnya, jumlah_token, versi_ktp)
            VALUES (?, ?, NULL, ?, 1)
            """,
            (kode_proyek, teks, jumlah),
        )
        versi = 1
    else:
        if simpan_snapshot:
            conn.execute(
                """
                UPDATE ktp_proyek
                SET ringkasan_sebelumnya = ringkasan_inti,
                    ringkasan_inti = ?,
                    jumlah_token = ?,
                    versi_ktp = versi_ktp + 1,
                    waktu_update = CURRENT_TIMESTAMP
                WHERE kode_proyek = ?
                """,
                (teks, jumlah, kode_proyek),
            )
        else:
            conn.execute(
                """
                UPDATE ktp_proyek
                SET ringkasan_inti = ?,
                    jumlah_token = ?,
                    versi_ktp = versi_ktp + 1,
                    waktu_update = CURRENT_TIMESTAMP
                WHERE kode_proyek = ?
                """,
                (teks, jumlah, kode_proyek),
            )
        versi = int(row["versi_ktp"]) + 1
    return {"ringkasan_inti": teks, "jumlah_token": jumlah, "versi_ktp": versi}


def rollback_ktp(conn: sqlite3.Connection, kode_proyek: str) -> dict[str, Any]:
    """1-Click Rollback: memulihkan ``ringkasan_sebelumnya`` menjadi ``ringkasan_inti``."""
    from .archive_manager import ekspor_memori_tim

    row = conn.execute(
        "SELECT ringkasan_inti, ringkasan_sebelumnya FROM ktp_proyek WHERE kode_proyek = ?", (kode_proyek,)
    ).fetchone()
    if row is None:
        raise LookupError(f"KTP Proyek '{kode_proyek}' tidak ditemukan.")
    if not row["ringkasan_sebelumnya"]:
        raise ValueError("Tidak ada snapshot versi sebelumnya untuk di-rollback.")
    jumlah = hitung_token(row["ringkasan_sebelumnya"])
    conn.execute(
        """
        UPDATE ktp_proyek
        SET ringkasan_inti = ringkasan_sebelumnya,
            ringkasan_sebelumnya = ringkasan_inti,
            jumlah_token = ?,
            versi_ktp = versi_ktp + 1,
            waktu_update = CURRENT_TIMESTAMP
        WHERE kode_proyek = ?
        """,
        (jumlah, kode_proyek),
    )
    hasil = conn.execute(
        "SELECT ringkasan_inti, ringkasan_sebelumnya, jumlah_token, versi_ktp FROM ktp_proyek WHERE kode_proyek = ?",
        (kode_proyek,),
    ).fetchone()
    if not conn.in_transaction:
        ekspor_memori_tim(conn, kode_proyek)
    return dict(hasil)
