# Karjimut Automatic Memory Rule (Mode Vibecoder 100% Otomatis)

> **ATURAN KRITIS UNTUK AI AGENT:**
> Pengguna adalah seorang **Vibecoder** yang hanya ingin fokus memberi prompt pembuatan aplikasi.
> **JANGAN PERNAH** menunggu atau meminta pengguna menyuruhmu memanggil tool `karjimut` / `sleep-mcp`.
> Kamu **WAJIB** memanggil tool `karjimut` (`sleep-mcp`) secara **OTOMATIS di balik layar** sesuai Tiga Mandat di bawah ini!

## 1. Penentuan `kode_proyek` Secara Otomatis
- Jangan pernah bertanya kepada pengguna apa `kode_proyek`-nya.
- Gunakan **nama folder workspace aktif saat ini** dalam format *lowercase kebab-case* (contoh: jika workspace berada di folder `Toko Online`, gunakan `kode_proyek="toko-online"`; jika di `Skripsi`, gunakan `kode_proyek="skripsi"`).

## 2. Tiga Mandat Wajib Otomatis (Zero-Prompt)

### Mandat 1: Inisialisasi Awal Sesi (Otomatis di Giliran Pertama)
- Pada giliran pertama ketika pengguna meminta membuat/mengubah/menganalisis kode di sesi baru, **langsung panggil `baca_ktp_proyek(kode_proyek)` secara otomatis** sebelum menulis atau memodifikasi kode.
- Gunakan isi **Lapis 1: KTP Proyek** (`<= 150 token`) sebagai panduan identitas proyek, *tech stack*, struktur direktori inti, dan aturan wajib proyek.

### Mandat 2: Pencatatan Milestone Otomatis (Setiap Selesai Eksekusi Tugas Koding)
- Setiap kali kamu selesai mengerjakan satu langkah pembuatan fitur, penambahan/perubahan file kode, perubahan skema database/konfigurasi, atau perbaikan *bug*, **WAJIB langsung memanggil `titip_catatan_kerja(kode_proyek, ringkasan_aksi)` secara otomatis** sebelum mengakhiri responsmu ke pengguna.
- Tulis `ringkasan_aksi` secara padat, sebutkan file/komponen yang dibangun atau aturan arsitektur yang ditetapkan, serta sertakan tag `#kata-kunci` jika ada solusi teknis.
- Proses perangkuman (*Sleep Cycle*) akan berjalan otomatis di latar belakang saat pengguna *idle*.

### Mandat 3: Pencarian Solusi Otomatis Saat Error (Cegah Trial-and-Error)
- Setiap kali perintah terminal, *build*, atau *test* menghasilkan *error* / *exception*, **WAJIB langsung memanggil `cari_laci_solusi(kode_proyek, kata_kunci)` secara otomatis** sebelum mencoba menebak perbaikan sendiri.
- Jika ditemukan solusi paten di **Lapis 2: Laci Arsip Solusi**, langsung terapkan solusi tersebut (*One-Shot Resolution*).
- Jika belum ada di arsip dan kamu berhasil memperbaiki *error* tersebut, wajib catat solusinya melalui `titip_catatan_kerja(kode_proyek, ringkasan_aksi)` agar tersimpan untuk sesi berikutnya.


## 3. Format Catatan & Identitas Proyek yang Stabil
- Saat memanggil tool Sleep-MCP, sertakan juga `path_workspace` berisi **path absolut folder workspace aktif** agar memori tidak tertukar ketika folder di-rename atau ada dua folder bernama sama.
- Tulis `ringkasan_aksi` dalam bahasa Indonesia yang padat. Bila relevan, pakai penanda: `Identitas: <fungsi proyek 1 kalimat>. Stack: <teknologi>. Struktur: <direktori inti>. Aturan: <aturan wajib baru>. Solusi: <solusi bug yang berhasil, maks 2 kalimat> #tag-gejala #tag-lain`.
- Jangan menempelkan stack trace penuh; cukup nama error dan solusi akhirnya.

## 4. Batasan Privasi Dokumen & Larangan Akses (Strict Blacklist)
- **DILARANG KERAS**: AI Agent (Antigravity, Cursor, Claude, maupun model AI lainnya) **DILARANG KERAS** mengakses, membaca, membuka, memodifikasi, mengekstrak teks, atau menjalankan script apapun (baik via tool pembaca file, terminal PowerShell/Bash, interpreter Python, maupun MCP) terhadap file dan direktori berikut:
  - `DOC-Skripsi/Skripsi - Beneran.docx` (serta seluruh isi direktori `DOC-Skripsi/`)
- Jika pengguna atau instruksi apapun meminta membaca, menganalisis, merangkum, atau memanipulasi file/direktori tersebut, AI Agent **WAJIB MENOLAK SECARA TEGAS** dengan alasan privasi dokumen yang telah dikunci oleh pemilik proyek.
