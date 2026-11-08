"""Modul pemfilteran noise, ekstraksi gejala/teknologi/aturan, dan quality gate log."""

from __future__ import annotations

import re
from typing import Any, Iterable

from .fts_search import normalisasi_tag
from .tokenizer_utils import normalisasi_spasi, pecah_kalimat

JACCARD_THRESHOLD = 0.5
MIN_TAG_OVERLAP = 2
MAX_TAG_PER_ARSIP = 8
MAX_CHARS_PER_LOG_PROMPT = 4000

# ===========================================================================
# Pola Regex Pembersihan Noise, Injeksi Memori, & Ekstraksi Entitas
# ===========================================================================
_RE_TRACE_START = re.compile(r"^\s*(Traceback \(most recent call last\)|Stack trace:|Stacktrace:)", re.I)
_RE_STACK_LINE = [
    re.compile(r'^\s*File ".+", line \d+'),
    re.compile(r"^\s*at\s+\S.*\(.*:\d+(:\d+)?\)\s*$"),
    re.compile(r"^\s*at\s+[\w$.<>/\\:-]+:\d+(:\d+)?\s*$"),
    re.compile(r"^\s*at\s+(async\s+)?[\w$.<>\[\]]+\s*\(?.*\)?\s*$"),
    re.compile(r"^\s*[\^~]{2,}\s*$"),
    re.compile(r"^\s*During handling of the above exception", re.I),
    re.compile(r"^\s*The above exception was the direct cause", re.I),
    re.compile(r"^\s*npm (ERR!|error)", re.I),
    re.compile(r"^\s*E\s{2,}\S"),
    re.compile(r"^\s*[\w./\\-]+\.(py|js|ts|tsx|jsx|go|java|php|rb):\d+(:\d+)?:?\s"),
    re.compile(r"^\s*Caused by:", re.I),
    re.compile(r"^\s*\.\.\.\s*\d+\s+more", re.I),
    re.compile(r"^\s*\(Background on this error at:", re.I),
    re.compile(r"^\s*\[SQL:", re.I),
]
_RE_ERROR_CLASS_LINE = re.compile(
    r"^\s*(?:[\w.]+\.)?([A-Z]\w*(?:Error|Exception|Exit|Warning|Interrupt))\b\s*[:(]"
)
_RE_ERROR_GENERIC_LINE = re.compile(
    r"^\s*(ERROR|FATAL|FAILED|CRITICAL|Error|Failed|fatal)\b\s*[:!\]\-]|blocked by CORS policy|"
    r"^\s*(INFO|WARNING|DEBUG):\s+\d+\.\d+\.\d+\.\d+",
)
_RE_ERROR_CLASS_ANY = re.compile(r"\b([A-Z][a-zA-Z]*(?:Error|Exception))\b")
_RE_HASHTAG = re.compile(r"(?<![\w#&])#([a-z][a-z0-9_]*(?:-[a-z0-9_]+)*)")

_RE_BASA_BASI = re.compile(
    r"^(oke+|ok|okay|baik|siap|sip|mantap|terima kasih|makasih|thanks|thank you|halo|hai|hi|"
    r"good|nice|noted|sama-sama|wah|hmm+|yes|ya)\b[\s,.!]*([\w\s,!.]{0,40})$",
    re.I,
)
_RE_GAGAL = re.compile(
    r"\b(gagal|masih error|masih gagal|tidak berhasil|belum berhasil|percobaan|mencoba|dicoba|coba lagi|"
    r"retry|error lagi|crash lagi|tidak jalan|sia-sia|tetap error|tetap gagal|still failing|failed again)\b",
    re.I,
)
_RE_SOLUSI_MARKER = re.compile(r"^\s*(solusi|fix|perbaikan|resolusi|resolved|penyelesaian|solved)\s*[:\-]\s*", re.I)
_RE_SOLUSI_KATA = re.compile(
    r"\b(berhasil diperbaiki|berhasil diatasi|berhasil diselesaikan|teratasi|terselesaikan|solusinya|"
    r"diperbaiki dengan|diatasi dengan|diselesaikan dengan|fix dengan|akhirnya berhasil|resolved by|"
    r"fixed by|beres dengan|berhasil setelah|kini berhasil|sekarang berhasil|"
    r"memperbaiki|mengatasi|menyelesaikan|menangani|"
    r"mencegah\s+(?:error|bug|race\s+condition|deadlock|leak|crash|serangan|konflik|duplikasi)|"
    r"fixed|resolved|solved|patched)\b",
    re.I,
)
_RE_AKSI_TEKNIS = re.compile(
    r"\b(menambahkan|menggunakan|mengatur|mengubah|menerapkan|mengaktifkan|memasang|mengonfigurasi|"
    r"mengganti|memperbarui|meningkatkan|membatasi|menyimpan|menjalankan)\b",
    re.I,
)
_RE_ATURAN_MARKER = re.compile(
    r"^\s*(aturan(\s+baru)?|rule|kesepakatan|konvensi|mandat|standar|ketentuan)\s*(\d+)?\s*[:\-]\s*", re.I
)
_RE_ATURAN_KATA = re.compile(r"\b(wajib|harus|dilarang|jangan|tidak boleh|selalu|must|never|always)\b", re.I)
_RE_NARASI_CHANGELOG = re.compile(
    r"\b(?:commit\s+[0-9a-f]{6,}|log\s*#\d+|\d+\s+unit\s+test|lulus\s+100%|passed\s+100%|"
    r"berhasil\s+di-?(?:push|commit|rilis|deploy|hapus|bersihkan|sinkronkan)|"
    r"rilis\s+v\d+\.\d+|versi\s+saat\s+ini\s+v?\d+\.\d+|bump\s+version|"
    r"audit\s+menyeluruh|workspace\s+dibersihkan|file\s+sampah)\b",
    re.I,
)
MAX_ATURAN_KTP = 12
_RE_PROMPT_INJECTION = re.compile(
    r"\b(abaikan\s+(?:semua\s+)?instruksi|ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions|"
    r"disregard\s+(?:all\s+)?(?:previous|prior)\s+instructions|"
    r"lupakan\s+(?:semua\s+)?aturan|hapus\s+semua\s+aturan|forget\s+all\s+rules|"
    r"system\s+prompt|system\s+override|developer\s+mode|jailbreak|"
    r"matikan\s+autentikasi|disable\s+auth|bypass\s+security|jangan\s+validasi|"
    r"izinkan\s+sql\s+injection|boleh\s+menggunakan\s+raw\s+sql)\b",
    re.I,
)
_RE_PROMPT_BREAKOUT = re.compile(
    r"(\[(?:KTP Proyek|Daftar ID|Log Aktivitas)|</?log_entry\b|</?system\b|\[/?INST\])",
    re.I,
)
_RE_STATUS_NON_SOLUSI = re.compile(
    r"^\s*(?:"
    r"menjalankan\s+\d+\s+unit\s+test|"
    r"melakukan\s+audit\s+menyeluruh|"
    r"memperbarui\s+(?:readme\.md|dokumen|dokumentasi|changelog)|"
    r"pembersihan\s+temp\s+file\b"
    r")",
    re.I,
)
_RE_INDIKATOR_MEKANISME = re.compile(
    r"\b(?:dengan|via|melalui|gunakan|menggunakan|memakai|pada|ke|untuk\s+mencegah|agar|"
    r"tambahkan|menambahkan|tingkatkan|meningkatkan|atur|mengatur|ubah|mengubah|"
    r"aktifkan|mengaktifkan|ganti|mengganti|jalankan|menjalankan|terapkan|menerapkan|"
    r"perbarui|memperbarui|konfigurasi|parameter|header|middleware|pragma|lock|locking|"
    r"pool|timeout|token|cookie|alembic|port|script|indeks|index|cache|query|schema)\b|"
    r"[=()_/\\]",
    re.I,
)
_TAG_NON_SOLUSI: frozenset[str] = frozenset(
    {
        "#pengujian", "#unit-test", "#benchmark", "#audit-kualitas",
        "#zero-error", "#verifikasi-lengkap",
        "#system-maintenance", "#cleanup-temp",
    }
)
_TAG_GENERIK_DEDUP: frozenset[str] = frozenset(
    {"#bug-fix", "#error", "#errors", "#bug", "#bugs", "#fix", "#issue", "#masalah"}
)
_RE_CREDENTIAL_REDACT = re.compile(
    r"((?:key|api_key|token|secret)=)[^&\s\"']+|"
    r"(Bearer\s+)[A-Za-z0-9._\-]+|"
    r"\b(AIza[0-9A-Za-z_\-]{20,}|sk-[A-Za-z0-9_\-]{16,}|gsk_[A-Za-z0-9_\-]{16,})",
    re.I,
)

_RE_IDENTITAS_MARKER = re.compile(r"^\s*(identitas|deskripsi proyek|nama proyek|proyek|project)\s*[:\-]\s*", re.I)
_RE_IDENTITAS_KATA = re.compile(
    r"^(proyek|project|aplikasi|sistem|platform|layanan)\b[\w\s-]{0,40}?\b(adalah|merupakan|bernama|yaitu)\b",
    re.I,
)
_RE_IDENTITAS_PREFIX = re.compile(
    r"^(proyek|project|aplikasi|sistem|platform|layanan)(\s+(ini|kita|[\w.-]+))?\s+(adalah|merupakan|bernama|yaitu)\s+",
    re.I,
)
_RE_STACK_MARKER = re.compile(r"^\s*(stack|tech stack|stack teknologi|teknologi)\s*[:\-]\s*", re.I)
_RE_STRUKTUR_MARKER = re.compile(r"^\s*(struktur( direktori)?|direktori|folder inti)\s*[:\-]\s*", re.I)
_RE_MASALAH = re.compile(
    r"\b(error|exception|bug|traceback|failed|crash|timeout|blocked|tidak bisa|refused|kadaluarsa|expired|"
    r"401|403|404|500|conflict|bentrok)\b",
    re.I,
)
_RE_KLAUSA_ALASAN = re.compile(
    r"\s*,?\s+(agar|supaya|karena|sehingga|demi|untuk menghindari|untuk mencegah|biar)\s+.*$", re.I
)
_RE_DIR = re.compile(r"(?<![\w/.:\\-])((?:[A-Za-z_.][\w.-]*/)+)([\w.-]+)?")
_DIR_DIABAIKAN = {
    "node_modules/", ".venv/", "venv/", "site-packages/", "__pycache__/", "usr/", "home/", "lib/",
    "dist-packages/", ".git/", "http/", "https/", "localhost/",
}
_RE_HAPUS_ATURAN = re.compile(
    r"^\s*(?:hapus|cabut|batalkan|abaikan|jangan\s+lagi\s+pakai|tidak\s+lagi\s+berlaku)\s+aturan\s*:?\s*(.+)$",
    re.I,
)
_RE_MIGRASI_STACK = re.compile(
    r"\b(?:migrasi|ganti|beralih)\s+dari\s+([A-Za-z0-9_./-]+)\s+ke\s+([A-Za-z0-9_./-]+)",
    re.I,
)
_RE_HAPUS_STACK = re.compile(
    r"\b(?:hapus|tidak\s+lagi\s+menggunakan|berhenti\s+menggunakan|copot)\s+(?:teknologi\s+|stack\s+|library\s+)?([A-Za-z0-9_./-]+)",
    re.I,
)

STOPWORDS_ATURAN = {
    "yang", "dan", "di", "ke", "dari", "untuk", "pada", "dengan", "ini", "itu", "setiap", "semua",
    "wajib", "harus", "selalu", "the", "a", "an", "of", "to", "in",
}

KAMUS_TEKNOLOGI: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pola, re.I), nama)
    for pola, nama in (
        (r"\bpython\b", "Python"), (r"\bfastapi\b", "FastAPI"), (r"\bflask\b", "Flask"),
        (r"\bdjango\b", "Django"), (r"\bsqlalchemy\b", "SQLAlchemy"), (r"\balembic\b", "Alembic"),
        (r"\bpydantic\b", "Pydantic"), (r"\bpostgre(s|sql)\b", "PostgreSQL"), (r"\bmysql\b", "MySQL"),
        (r"\bmariadb\b", "MariaDB"), (r"\bsqlite\b", "SQLite"), (r"\bredis\b", "Redis"),
        (r"\bmongo(db)?\b", "MongoDB"), (r"\bdocker([- ]compose)?\b", "Docker"),
        (r"\b(kubernetes|k8s)\b", "Kubernetes"), (r"\bnginx\b", "Nginx"), (r"\breact(\.js|js)?\b", "React"),
        (r"\bvue(\.js)?\b", "Vue"), (r"\bnext\.?js\b", "Next.js"), (r"\bvite\b", "Vite"),
        (r"\btypescript\b", "TypeScript"), (r"\bjavascript\b", "JavaScript"), (r"\bnode\.?js\b", "Node.js"),
        (r"\bexpress(\.js)?\b", "Express"), (r"\btailwind(css)?\b", "TailwindCSS"), (r"\bjwt\b", "JWT"),
        (r"\bcelery\b", "Celery"), (r"\brabbitmq\b", "RabbitMQ"), (r"\bpytest\b", "Pytest"),
        (r"\bjest\b", "Jest"), (r"\bgithub actions\b", "GitHub Actions"), (r"\blaravel\b", "Laravel"),
        (r"\bphp\b", "PHP"), (r"\bgolang\b", "Go"), (r"\brust\b", "Rust"), (r"\bspring boot\b", "Spring Boot"),
        (r"\bkotlin\b", "Kotlin"), (r"\bflutter\b", "Flutter"), (r"\bgraphql\b", "GraphQL"),
        (r"\bprisma\b", "Prisma"), (r"\bsupabase\b", "Supabase"), (r"\bfirebase\b", "Firebase"),
        (r"\buvicorn\b", "Uvicorn"), (r"\bgunicorn\b", "Gunicorn"), (r"\baxios\b", "Axios"),
        (r"\bminio\b", "MinIO"), (r"\belasticsearch\b", "Elasticsearch"), (r"\bmcp\b", "MCP"),
    )
)

KAMUS_GEJALA: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pola, re.I), tag)
    for pola, tag in (
        (r"\bcors\b|access-control-allow-origin", "#cors"),
        (r"\btime(d)?[ -]?out\b|timeout expired", "#timeout"),
        (r"connection refused", "#connection-refused"),
        (r"(koneksi|connection)\s+(ke\s+)?(database|db|postgres\w*|mysql)|database connection", "#koneksi-db"),
        (r"\bjwt\b", "#jwt"),
        (r"(token|signature)\s+(has\s+)?(expired|kadaluarsa|kedaluwarsa)|expiredsignature", "#token-expired"),
        (r"\b401\b|unauthorized", "#unauthorized"),
        (r"\balembic\b", "#alembic"),
        (r"\bmigrasi\b|\bmigration\b", "#migrasi"),
        (r"multiple head", "#multiple-heads"),
        (r"modulenotfound|no module named|importerror", "#import-error"),
        (r"circular import", "#circular-import"),
        (r"address already in use|port\s+\d+\s+(is\s+)?(already\s+)?in use", "#port-in-use"),
        (r"permission denied", "#permission-denied"),
        (r"database is locked|deadlock", "#database-locked"),
        (r"unicode(en|de)codeerror|\butf-?8\b", "#encoding"),
        (r"nonetype|undefined is not|null pointer", "#null-reference"),
        (r"\b404\b|not found", "#not-found"),
        (r"\b500\b|internal server error", "#internal-server-error"),
        (r"\bn\+1\b|query lambat|slow query", "#query-lambat"),
        (r"\bredis\b", "#redis"),
        (r"\bdocker\b", "#docker"),
    )
)


# ===========================================================================
# Fungsi Sanitasi, Pemfilteran Noise, & Quality Gate
# ===========================================================================
def sanitasi_pesan_error(pesan: Any) -> str:
    """Menyensor API key/token dari pesan exception sebelum dicatat ke log atau dikembalikan."""
    teks = str(pesan or "")
    return _RE_CREDENTIAL_REDACT.sub(
        lambda m: f"{m.group(1) or m.group(2) or ''}[REDACTED_SECRET]",
        teks,
    )


def bersihkan_injeksi_memori(teks: str) -> str:
    """Membuang kalimat yang mengandung pola prompt injection / memory poisoning."""
    if not teks:
        return ""
    kalimat_aman: list[str] = []
    for kal in pecah_kalimat(str(teks)):
        if _RE_PROMPT_INJECTION.search(kal):
            continue
        kal_bersih = _RE_PROMPT_BREAKOUT.sub("", kal).strip()
        if kal_bersih:
            kalimat_aman.append(kal_bersih)
    return normalisasi_spasi(" ".join(kalimat_aman))


def _buang_hashtag(teks: str) -> str:
    teks = re.sub(r"\(?\s*(?:#[a-z][\w-]*[\s,]*)+\)?", " ", teks, flags=re.I)
    teks = re.sub(r"\b(tag|tags)\s*:\s*$", "", teks.strip(), flags=re.I)
    return normalisasi_spasi(teks).strip(" ,;")


def _tutup(teks: str) -> str:
    teks = teks.strip().rstrip(",;: ").strip()
    if teks and teks[-1] not in ".!?":
        teks += "."
    return teks


def _split_item(teks: str) -> list[str]:
    return [x.strip().rstrip(". ").strip() for x in re.split(r",", teks) if x.strip().rstrip(". ").strip()]


def layak_masuk_laci_arsip(solusi: str, tag_masalah: str | Iterable[str] = "") -> bool:
    """Quality gate Laci Arsip: menolak log status/maintenance rutin dan kalimat tanpa mekanisme teknis."""
    teks = normalisasi_spasi(_buang_hashtag(str(solusi or "")))
    if not teks or len(teks) < 18 or len(teks.split()) < 4:
        return False
    if _RE_PROMPT_INJECTION.search(teks) or _RE_STATUS_NON_SOLUSI.search(teks):
        return False
    tags = set(normalisasi_tag(tag_masalah))
    tags_spesifik = tags - _TAG_GENERIK_DEDUP
    if tags_spesifik and tags_spesifik <= _TAG_NON_SOLUSI:
        return False
    if not _RE_INDIKATOR_MEKANISME.search(teks):
        return False
    return True


def _camel_ke_kebab(nama: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", nama).lower()


def pisahkan_noise(isi_log: str) -> tuple[list[str], list[str], int]:
    """Memisahkan baris bermakna dari stack trace.

    Returns:
        ``(baris_bersih, baris_error, jumlah_baris_noise)``. ``baris_error``
        berisi baris pesan error akhir (mis. ``OperationalError: ...``) yang
        tidak masuk KTP tetapi dipakai sebagai sumber tag gejala.
    """
    bersih: list[str] = []
    error: list[str] = []
    noise = 0
    dalam_trace = False
    for baris in (isi_log or "").splitlines():
        teks = baris.rstrip()
        if not teks.strip():
            dalam_trace = False
            continue
        if _RE_TRACE_START.match(teks):
            dalam_trace = True
            noise += 1
            continue
        if any(p.match(teks) for p in _RE_STACK_LINE):
            dalam_trace = True
            noise += 1
            continue
        if _RE_ERROR_CLASS_LINE.match(teks) or _RE_ERROR_GENERIC_LINE.search(teks):
            error.append(teks.strip())
            noise += 1
            dalam_trace = False
            continue
        if dalam_trace and teks[:1] in (" ", "\t"):
            noise += 1
            continue
        dalam_trace = False
        bersih.append(teks.strip())
    return bersih, error, noise


def ringkas_stack_trace(isi_log: str) -> str:
    """Pra-filter prompt LLM: blok stack trace diganti penanda + baris error akhirnya."""
    keluaran: list[str] = []
    frame_dipangkas = 0
    dalam_trace = False

    def flush() -> None:
        nonlocal frame_dipangkas
        if frame_dipangkas:
            keluaran.append(f"[stack trace dipangkas: {frame_dipangkas} baris]")
            frame_dipangkas = 0

    for baris in (isi_log or "").splitlines():
        teks = baris.rstrip()
        if not teks.strip():
            flush()
            dalam_trace = False
            continue
        if _RE_TRACE_START.match(teks) or any(p.match(teks) for p in _RE_STACK_LINE):
            dalam_trace = True
            frame_dipangkas += 1
            continue
        if dalam_trace and teks[:1] in (" ", "\t") and not _RE_ERROR_CLASS_LINE.match(teks):
            frame_dipangkas += 1
            continue
        flush()
        dalam_trace = False
        keluaran.append(teks.strip())
    flush()
    return "\n".join(keluaran)


def _kalimat_dari_baris(baris: Iterable[str]) -> list[str]:
    kalimat: list[str] = []
    for b in baris:
        b = re.sub(r"^\s*([-*•]|\d+[.)])\s+", "", b)
        kalimat.extend(pecah_kalimat(b))
    return kalimat


def deteksi_teknologi(teks: str) -> list[str]:
    hasil: list[str] = []
    for pola, nama in KAMUS_TEKNOLOGI:
        if pola.search(teks) and nama not in hasil:
            hasil.append(nama)
    return hasil


def deteksi_direktori(teks: str) -> list[str]:
    """Ekstraksi direktori inti (maks. kedalaman 2) dari kalimat milestone."""
    hasil: list[str] = []
    for m in _RE_DIR.finditer(teks):
        bagian_dir, sisa = m.group(1), m.group(2)
        segmen = [s for s in bagian_dir.split("/") if s]
        if not segmen:
            continue
        punya_ekstensi = bool(sisa and "." in sisa)
        eksplisit = sisa is None
        if not (punya_ekstensi or eksplisit or len(segmen) >= 2):
            continue
        if any(s.isupper() and len(s) <= 4 for s in segmen):
            continue
        direktori = "/".join(segmen[:2]) + "/"
        if direktori.lower() in _DIR_DIABAIKAN or segmen[0].lower() + "/" in _DIR_DIABAIKAN:
            continue
        if direktori not in hasil:
            hasil.append(direktori)
    return hasil


def jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    """``|A ∩ B| / |A ∪ B|`` (0.0 jika keduanya kosong)."""
    gabungan = set_a | set_b
    if not gabungan:
        return 0.0
    return len(set_a & set_b) / len(gabungan)


def bangun_tag_gejala(
    hashtags: list[str],
    baris_error: list[str],
    teks: str,
    minimal: int = 3,
    maksimal: int = 5,
) -> list[str]:
    """Menyusun 3-5 tag gejala: hashtag eksplisit > nama exception > kamus gejala > teknologi."""
    tags: list[str] = normalisasi_tag(hashtags)
    for baris in baris_error:
        for nama in _RE_ERROR_CLASS_ANY.findall(baris):
            tag = f"#{_camel_ke_kebab(nama)}"
            if tag not in tags:
                tags.append(tag)
    for pola, tag in KAMUS_GEJALA:
        if pola.search(teks) and tag not in tags:
            tags.append(tag)
    if len(tags) < minimal:
        for nama in deteksi_teknologi(teks):
            tag = normalisasi_tag(nama.replace(".", ""))[0]
            if tag not in tags:
                tags.append(tag)
            if len(tags) >= minimal:
                break
    for cadangan in ("#bug-fix", "#error"):
        if len(tags) >= minimal:
            break
        if cadangan not in tags:
            tags.append(cadangan)
    return tags[:maksimal]


def _rapikan_aturan(kalimat: str) -> str:
    teks = _RE_ATURAN_MARKER.sub("", kalimat)
    teks = re.sub(
        r"^\s*(mulai sekarang|mulai saat ini|kita sepakat( bahwa)?|disepakati( bahwa)?|pastikan|tolong)\s*,?\s*",
        "",
        teks,
        flags=re.I,
    )
    teks = re.sub(r"^\(?\d+[.)]\s*", "", teks)
    teks = _buang_hashtag(teks)
    teks = normalisasi_spasi(teks).rstrip(" .;")
    return teks[:1].upper() + teks[1:] if teks else ""


def _kata_kunci_aturan(aturan: str) -> set[str]:
    kata = re.findall(r"[\w./-]+", aturan.lower())
    return {k for k in kata if len(k) > 2 and k not in STOPWORDS_ATURAN}


def gabung_aturan(aturan_lama: list[str], aturan_baru: list[str]) -> list[str]:
    """Incremental merge aturan: aturan lama dipertahankan, aturan baru yang mirip
    (Jaccard kata >= 0.55) menggantikan versi lamanya di posisi yang sama,
    dan narasi changelog/milestone disaring agar KTP tidak membengkak."""
    hasil = [a for a in aturan_lama if a and not _RE_NARASI_CHANGELOG.search(a)]
    for baru in aturan_baru:
        if not baru or _RE_NARASI_CHANGELOG.search(baru):
            continue
        kunci_baru = _kata_kunci_aturan(baru)
        indeks_mirip = -1
        for i, lama in enumerate(hasil):
            kunci_lama = _kata_kunci_aturan(lama)
            if kunci_baru and kunci_lama and (
                jaccard_similarity(kunci_baru, kunci_lama) >= 0.55 or kunci_baru <= kunci_lama
            ):
                indeks_mirip = i
                break
        if indeks_mirip >= 0:
            hasil[indeks_mirip] = baru
        else:
            hasil.append(baru)
    if len(hasil) > MAX_ATURAN_KTP:
        hasil = hasil[-MAX_ATURAN_KTP:]
    return hasil


def _gabung_unik(lama: list[str], baru: list[str]) -> list[str]:
    hasil = list(lama)
    lower = {x.lower() for x in hasil}
    for item in baru:
        if item and item.lower() not in lower:
            hasil.append(item)
            lower.add(item.lower())
    return hasil


def _hapus_aturan_usang(aturan_list: list[str], target_hapus: list[str]) -> list[str]:
    """Menghapus aturan lama yang cocok dengan instruksi pencabutan/deprekasi."""
    if not target_hapus or not aturan_list:
        return aturan_list
    kunci_hapus_list = [_kata_kunci_aturan(t) for t in target_hapus if _kata_kunci_aturan(t)]
    if not kunci_hapus_list:
        return aturan_list
    sisa: list[str] = []
    for a in aturan_list:
        kunci_a = _kata_kunci_aturan(a)
        terhapus = False
        for kh in kunci_hapus_list:
            if kh and kunci_a and (kh <= kunci_a or jaccard_similarity(kh, kunci_a) >= 0.5):
                terhapus = True
                break
        if not terhapus:
            sisa.append(a)
    return sisa
