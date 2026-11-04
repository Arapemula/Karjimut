# Karjimut Automatic Memory Rule (Mode Vibecoder 100% Otomatis)

> **ATURAN KRITIS UNTUK AI AGENT:**
> Pengguna adalah seorang **Vibecoder** yang fokus memberi prompt pembuatan aplikasi tanpa mengurus manajemen memori.
> **JANGAN PERNAH** menunggu atau meminta pengguna menyuruhmu memanggil tool `karjimut` / `sleep-mcp`.
> Kamu **WAJIB** memanggil tool `karjimut` secara **OTOMATIS di balik layar** sesuai Tiga Mandat di bawah ini!

## 1. Penentuan `kode_proyek` Secara Otomatis
- Jangan pernah bertanya kepada pengguna apa `kode_proyek`-nya.
- Gunakan **nama folder workspace aktif saat ini** dalam format *lowercase kebab-case* (contoh: jika workspace berada di folder `Toko Online`, gunakan `kode_proyek="toko-online"`; jika di `Backend API`, gunakan `kode_proyek="backend-api"`).

## 2. Tiga Mandat Wajib Otomatis (Zero-Prompt)

### Mandat 1: Inisialisasi Awal Sesi (Otomatis di Giliran Pertama)
- Pada giliran pertama ketika pengguna meminta membuat/mengubah/menganalisis kode di sesi baru, **langsung panggil `baca_ktp_proyek(kode_proyek, path_workspace)` secara otomatis** sebelum menulis atau memodifikasi kode.
- Gunakan isi **Lapis 1: KTP Proyek** (*Elastic Core*) sebagai panduan identitas proyek, *tech stack*, struktur direktori inti, dan aturan wajib arsitektur proyek.

### Mandat 2: Pencatatan Milestone Otomatis (Setiap Selesai Eksekusi Tugas Koding)
- Setiap kali kamu selesai mengerjakan satu langkah pembuatan fitur, penambahan/perubahan file kode, perubahan skema database/konfigurasi, atau perbaikan *bug*, **WAJIB langsung memanggil `titip_catatan_kerja(kode_proyek, ringkasan_aksi, path_workspace)` secara otomatis** sebelum mengakhiri responsmu ke pengguna.
- Tulis `ringkasan_aksi` secara padat, sebutkan file/komponen yang dibangun atau aturan arsitektur yang ditetapkan, serta sertakan tag `#kata-kunci` jika ada solusi teknis.
- Proses perangkuman (*Sleep Cycle*) akan berjalan otomatis di latar belakang saat pengguna *idle* ($\ge 5$ menit).

### Mandat 3: Pencarian Solusi Otomatis Saat Error (Cegah Trial-and-Error)
- Setiap kali perintah terminal, *build*, atau *test* menghasilkan *error* / *exception*, **WAJIB langsung memanggil `cari_laci_solusi(kode_proyek, kata_kunci, path_workspace)` secara otomatis** sebelum mencoba menebak perbaikan sendiri.
- Jika ditemukan solusi paten di **Lapis 2: Laci Arsip Solusi**, langsung terapkan solusi tersebut (*One-Shot Resolution*).
- Jika belum ada di arsip dan kamu berhasil memperbaiki *error* tersebut, wajib catat solusinya melalui `titip_catatan_kerja(kode_proyek, ringkasan_aksi, path_workspace)` agar tersimpan untuk sesi berikutnya.

## 3. Format Catatan & Identitas Proyek yang Stabil
- Saat memanggil tool Karjimut, sertakan parameter `path_workspace` berisi **path absolut folder workspace aktif** agar memori terikat akurat ke direktori proyek dan mendukung sinkronisasi tim via `.karjimut/team_memory.json`.
- Tulis `ringkasan_aksi` secara padat. Bila relevan, gunakan penanda terstruktur:
  `Identitas: <fungsi proyek 1 kalimat>. Stack: <teknologi>. Struktur: <direktori inti>. Aturan: <aturan arsitektur baru>. Solusi: <solusi bug yang berhasil, maks 2 kalimat> #tag-gejala #tag-kunci`.
- Jangan menempelkan *stack trace* penuh; cukup nama *error* dan langkah solusinya.

## 4. Keamanan & Privasi Kredensial (Strict Security)
- **DILARANG KERAS**: AI Agent dilarang mengekspos, mencatat, atau menempelkan isi file rahasia/kredensial lokal (seperti `.env`, `.env.local`, file private key `*.pem`/`*.key`, token API rahasia) ke dalam catatan kerja maupun log memori publik.
