"""Modul Internasionalisasi (i18n) untuk Karjimut Desktop Application.

Menyediakan lokalisasi teks dua bahasa:
  - 'id': Bahasa Indonesia (Default, customer-friendly SaaS terminology)
  - 'en': English (International SaaS standard)

Mendukung penggantian bahasa dinamis secara real-time dari menu Pengaturan.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..config import PROJECT_ROOT

LANG_ID = "id"
LANG_EN = "en"

BAHASA_TERSEDIA: dict[str, str] = {
    LANG_ID: "🇮🇩 Bahasa Indonesia",
    LANG_EN: "🇬🇧 English",
}

# Direktori penyimpanan preferensi bahasa pengguna
_CONFIG_DIR = PROJECT_ROOT / "data"
_LANG_PREF_FILE = _CONFIG_DIR / "gui_language.json"

_CURRENT_LANG: str = LANG_ID


def get_current_language() -> str:
    """Mengembalikan kode bahasa aktif saat ini ('id' atau 'en')."""
    global _CURRENT_LANG
    return _CURRENT_LANG


def set_current_language(lang_code: str) -> str:
    """Menyetel bahasa aktif dan menyimpannya secara persisten ke disk."""
    global _CURRENT_LANG
    if lang_code in BAHASA_TERSEDIA:
        _CURRENT_LANG = lang_code
        try:
            _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            _LANG_PREF_FILE.write_text(
                json.dumps({"language": _CURRENT_LANG}, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass
    return _CURRENT_LANG


def muat_preferensi_bahasa_tersimpan() -> str:
    """Memuat preferensi bahasa dari file konfigurasi atau environment variable."""
    global _CURRENT_LANG
    env_lang = (os.environ.get("KARJIMUT_LANGUAGE") or os.environ.get("SLEEP_MCP_LANGUAGE") or "").strip().lower()
    if env_lang in BAHASA_TERSEDIA:
        _CURRENT_LANG = env_lang
        return _CURRENT_LANG

    if _LANG_PREF_FILE.exists():
        try:
            data = json.loads(_LANG_PREF_FILE.read_text(encoding="utf-8"))
            saved = data.get("language", "").strip().lower()
            if saved in BAHASA_TERSEDIA:
                _CURRENT_LANG = saved
                return _CURRENT_LANG
        except Exception:
            pass

    _CURRENT_LANG = LANG_ID
    return _CURRENT_LANG


# Kamus Terjemahan Lengkap (ID & EN)
TRANSLATIONS: dict[str, dict[str, str]] = {
    LANG_ID: {
        # Navigasi & Sidebar
        "nav_core": "Core Proyek (Lapis 1)",
        "nav_solusi": "Bank Solusi (Lapis 2)",
        "nav_catatan": "Catatan & Laporan",
        "nav_pengaturan": "Pengaturan & Koneksi",
        "nav_menu_title": "MENU NAVIGASI",
        "app_title": "Karjimut",
        "app_subtitle": "Two-Tier Memory Hub",
        "quick_action_title": "Rapikan Memori",
        "quick_action_desc": "Rangkum catatan kerja menjadi Core Proyek & sinkronkan embedding vektor solusi.",
        "btn_trigger_sleep": "⚡ Rapikan Memori Sekarang",
        "btn_sleeping": "⏳ Merapikan Memori...",
        "status_arsitektur_title": "Status Sistem",
        "status_arsitektur_body": "• Lapis 1: Core Proyek (Elastic Core)\n• Lapis 2: Hybrid Search (BM25 + sqlite-vec 384-dim)\n• Self-Learning: Feedback Loop + Causal Graph\n• Mode: SQLite WAL + Team Sync",
        
        # Top Bar
        "breadcrumb_dashboard": "Dashboard",
        "proyek_label": "Proyek:",
        "btn_tambah_proyek": "+ Proyek",
        "btn_gabung_proyek": "Rename",
        "btn_hapus_proyek": "Hapus Proyek",
        "status_standby": "Siaga (Standby)",
        "status_working": "Sedang Bekerja",
        "status_idle_prefix": "Idle",
        "status_sleeping": "Merapikan Memori (Sleeping)...",
        
        # 4 Bento KPI Cards
        "kpi_core_title": "Kapasitas Core Proyek",
        "kpi_core_sub": "Versi v{versi} ({pct}% Kapasitas)",
        "kpi_core_sub_elastic": "Versi v{versi} (Elastic Core • Auto-Scale)",
        "kpi_solusi_title": "Bank Solusi Hibrida",
        "kpi_solusi_sub": "Hybrid BM25 + Vector 384d",
        "kpi_solusi_unit": "{count} Solusi Paten",
        "kpi_metrik_a_title": "Efisiensi Context (Metrik A)",
        "kpi_metrik_a_sub": "Tercapai (>60%)",
        "kpi_catatan_title": "Catatan & Penghematan",
        "kpi_catatan_unit": "{count} Catatan Pending",
        "kpi_catatan_sub": "{terangkum} Terangkum • Net: {net} tok",
        
        # Tab 1: Core Proyek
        "tab1_title": "Core Proyek: {proyek}",
        "tab1_desc": "Inti Core Proyek (Identitas, Tech Stack, Struktur Direktori, & Aturan Wajib). Mode Elastic Core menyimpan seluruh aturan proyek besar tanpa terpotong.",
        "tab1_capacity": "Kapasitas Core Proyek: {used}/{max} Token ({pct}%)",
        "tab1_safe": "Aman",
        "tab1_elastic": "Elastic Core (Tanpa Batas Potong)",
        "tab1_warning": "Mendekati Batas",
        "tab1_critical": "Kritis / Melebihi",
        "btn_simpan_core": "💾 Simpan Core Proyek",
        "btn_rollback": "⏪ 1-Click Rollback",
        "snapshot_title": "Snapshot Versi Sebelumnya",
        "snapshot_desc": "Cadangan otomatis 1-Step Rollback sebelum konsolidasi terakhir.",
        "snapshot_kosong": "Belum ada snapshot cadangan untuk proyek '{proyek}'. Snapshot otomatis dibuat setiap kali fase Sleep Cycle berjalan.",
        "mandat_title": "Empat Mandat & Feedback Loop",
        "mandat_1_name": "1. baca_ktp_proyek",
        "mandat_1_desc": "Injeksi identitas & aturan di awal sesi (Elastic Core)",
        "mandat_2_name": "2. titip_catatan_kerja",
        "mandat_2_desc": "Mencatat milestone secara non-blocking ke antrean",
        "mandat_3_name": "3. cari_laci_solusi",
        "mandat_3_desc": "Pencarian hibrida BM25 + Vector RRF k=60 saat error",
        "mandat_4_name": "4. nilai_solusi",
        "mandat_4_desc": "Closed-loop feedback: reward (+0.10) / punishment (-0.15)",
        
        # Tab 2: Bank Solusi
        "tab2_search_title": "Pencarian Hibrida:",
        "tab2_search_placeholder": "Ketik kata kunci gejala error atau sinonim bahasa alami (misal: db connection timeout, cors, null pointer)...",
        "btn_cari_bm25": "Cari Hibrida",
        "btn_semua_solusi": "Semua",
        "tab2_list_title": "Daftar Solusi Paten '{proyek}' ({count} entri)",
        "tab2_form_add_title": "+ Tambah Solusi Paten Baru",
        "tab2_form_edit_title": "✏️ Edit Solusi Paten #{id}",
        "tab2_tag_label": "Tag Gejala / Error (dipisahkan koma, otomatis berawalan #):",
        "tab2_tag_placeholder": "Contoh: #koneksi-db, #timeout, #sqlalchemy",
        "tab2_solusi_label": "Solusi Paten (Maksimal 2 kalimat konkret):",
        "tab2_solusi_placeholder": "Tuliskan solusi pasti yang berhasil mengatasi error di atas...",
        "btn_simpan_ke_bank": "💾 Simpan ke Bank Solusi",
        "btn_update_ke_bank": "💾 Update Solusi Paten",
        "btn_batal_edit": "Batal Edit",
        "solusi_kosong": "Belum ada solusi paten untuk proyek '{proyek}'. Solusi otomatis disaring dan disimpan saat Sleep Cycle atau dapat Anda tambahkan manual.",
        
        # Tab 3: Catatan & Laporan
        "tab3_page_title": "Catatan Kerja & Audit Metrik",
        "tab3_breadcrumb": "Audit & Catatan",
        "tab3_metrik_a_box_title": "Metrik A: Efisiensi Context Window Aktif",
        "tab3_metrik_b_box_title": "Metrik B: Efisiensi Total Sistem (Net Token Savings & BEP)",
        "tab3_quick_note_title": "Catat Aktivitas Cepat:",
        "tab3_quick_note_placeholder": "Masukkan ringkasan aksi / milestone baru (contoh: Menambahkan fitur auth JWT #jwt #auth)...",
        "btn_masuk_antrean": "+ Masuk Catatan",
        "tab3_queue_title": "Daftar Catatan Kerja (Pending: {pending} | Processing: {proc} | Processed: {done})",
        "tab3_audit_title": "Breakdown & Riwayat Audit Token",
        "queue_kosong": "Antrean catatan kosong. Tidak ada aktivitas pending.",
        
        # Tab 4: Pengaturan & Koneksi
        "tab4_page_title": "Pengaturan & Koneksi",
        "tab4_breadcrumb": "Pengaturan",
        "tab4_lang_title": "🌐 Bahasa Antarmuka (Interface Language)",
        "tab4_provider_title": "Provider LLM",  # User explicitly requested to keep exact
        "tab4_mcp_config_title": "Konfigurasi MCP Siap Pakai",  # User explicitly requested to keep exact
        "lbl_deteksi_key": "Deteksi Otomatis API Key:",
        "lbl_custom_endpoint": "Pengaturan Custom Endpoint (DeepSeek / Ollama / vLLM / LM Studio):",
        "lbl_endpoint_url": "Base URL Endpoint:",
        "lbl_endpoint_model": "Model Name:",
        "btn_simpan_key": "💾 Simpan & Aktifkan API Key",
        "btn_offline_mode": "🛡️ Jalankan Mode 100% Offline (Local Distiller)",
        "btn_tes_koneksi": "⚡ Tes Koneksi Endpoint",
        "btn_salin_mcp": "📋 Salin Konfigurasi JSON",
        "mcp_guide_text": "Tempelkan konfigurasi JSON di bawah ini ke file pengaturan klien MCP Anda (Claude Desktop, Antigravity, Cursor, atau VS Code):",
    },
    LANG_EN: {
        # Navigasi & Sidebar
        "nav_core": "Project Core (Tier 1)",
        "nav_solusi": "Solution Bank (Tier 2)",
        "nav_catatan": "Notes & Reports",
        "nav_pengaturan": "Settings & Connections",
        "nav_menu_title": "NAVIGATION MENU",
        "app_title": "Karjimut",
        "app_subtitle": "Two-Tier Memory Hub",
        "quick_action_title": "Consolidate Memory",
        "quick_action_desc": "Summarize work notes into Project Core & sync solution vector embeddings.",
        "btn_trigger_sleep": "⚡ Consolidate Memory Now",
        "btn_sleeping": "⏳ Consolidating Memory...",
        "status_arsitektur_title": "System Status",
        "status_arsitektur_body": "• Tier 1: Project Core (Elastic Core)\n• Tier 2: Hybrid Search (BM25 + sqlite-vec 384-dim)\n• Self-Learning: Feedback Loop + Causal Graph\n• Mode: SQLite WAL + Team Sync",
        
        # Top Bar
        "breadcrumb_dashboard": "Dashboard",
        "proyek_label": "Project:",
        "btn_tambah_proyek": "+ Project",
        "btn_gabung_proyek": "Rename",
        "btn_hapus_proyek": "Delete Project",
        "status_standby": "Standby",
        "status_working": "Working",
        "status_idle_prefix": "Idle",
        "status_sleeping": "Consolidating Memory (Sleeping)...",
        
        # 4 Bento KPI Cards
        "kpi_core_title": "Project Core Capacity",
        "kpi_core_sub": "Version v{versi} ({pct}% Capacity)",
        "kpi_core_sub_elastic": "Version v{versi} (Elastic Core • Auto-Scale)",
        "kpi_solusi_title": "Hybrid Solution Bank",
        "kpi_solusi_sub": "Hybrid BM25 + Vector 384d",
        "kpi_solusi_unit": "{count} Proven Solutions",
        "kpi_metrik_a_title": "Context Efficiency (Metric A)",
        "kpi_metrik_a_sub": "Achieved (>60%)",
        "kpi_catatan_title": "Notes & Savings",
        "kpi_catatan_unit": "{count} Pending Notes",
        "kpi_catatan_sub": "{terangkum} Processed • Net: {net} tok",
        
        # Tab 1: Core Proyek
        "tab1_title": "Project Core: {proyek}",
        "tab1_desc": "Permanent project identity (Tech Stack, Core Architecture, & Mandatory Rules). Elastic Core preserves all rules without truncation.",
        "tab1_capacity": "Project Core Capacity: {used}/{max} Tokens ({pct}%)",
        "tab1_safe": "Safe",
        "tab1_elastic": "Elastic Core (Unbounded)",
        "tab1_warning": "Near Limit",
        "tab1_critical": "Critical / Overflow",
        "btn_simpan_core": "💾 Save Project Core",
        "btn_rollback": "⏪ 1-Click Rollback",
        "snapshot_title": "Previous Version Snapshot",
        "snapshot_desc": "Automated 1-step rollback backup captured before the last consolidation cycle.",
        "snapshot_kosong": "No rollback snapshot available yet for project '{proyek}'. Snapshots are automatically saved during each Sleep Cycle.",
        "mandat_title": "Four Mandates & Feedback Loop",
        "mandat_1_name": "1. baca_ktp_proyek",
        "mandat_1_desc": "Injects identity & rules at session start (Elastic Core)",
        "mandat_2_name": "2. titip_catatan_kerja",
        "mandat_2_desc": "Non-blocking milestone ingestion into queue",
        "mandat_3_name": "3. cari_laci_solusi",
        "mandat_3_desc": "Hybrid BM25 + Vector RRF k=60 search upon errors",
        "mandat_4_name": "4. nilai_solusi",
        "mandat_4_desc": "Closed-loop feedback: reward (+0.10) / punishment (-0.15)",
        
        # Tab 2: Bank Solusi
        "tab2_search_title": "Hybrid Search:",
        "tab2_search_placeholder": "Type error keywords or natural language synonyms (e.g. db connection timeout, cors, null pointer)...",
        "btn_cari_bm25": "Hybrid Search",
        "btn_semua_solusi": "All",
        "tab2_list_title": "Proven Solutions for '{proyek}' ({count} entries)",
        "tab2_form_add_title": "+ Add New Proven Solution",
        "tab2_form_edit_title": "✏️ Edit Proven Solution #{id}",
        "tab2_tag_label": "Symptom / Error Tags (comma-separated, auto-prefixed with #):",
        "tab2_tag_placeholder": "Example: #db-connection, #timeout, #sqlalchemy",
        "tab2_solusi_label": "Proven Solution (Maximum 2 concrete sentences):",
        "tab2_solusi_placeholder": "Write the exact solution that resolved the issue above...",
        "btn_simpan_ke_bank": "💾 Save to Solution Bank",
        "btn_update_ke_bank": "💾 Update Proven Solution",
        "btn_batal_edit": "Cancel Edit",
        "solusi_kosong": "No proven solutions found for project '{proyek}'. Solutions are distilled automatically during Sleep Cycle or can be created manually.",
        
        # Tab 3: Catatan & Laporan
        "tab3_page_title": "Work Notes & Audit Metrics",
        "tab3_breadcrumb": "Audit & Notes",
        "tab3_metrik_a_box_title": "Metric A: Active Context Window Efficiency",
        "tab3_metrik_b_box_title": "Metric B: System Total Efficiency (Net Token Savings & BEP)",
        "tab3_quick_note_title": "Quick Activity Note:",
        "tab3_quick_note_placeholder": "Enter new action / milestone summary (e.g. Added JWT auth feature #jwt #auth)...",
        "btn_masuk_antrean": "+ Add Note",
        "tab3_queue_title": "Work Notes Queue (Pending: {pending} | Processing: {proc} | Processed: {done})",
        "tab3_audit_title": "Token Audit Breakdown & History",
        "queue_kosong": "Work notes queue is empty. No pending activities.",
        
        # Tab 4: Pengaturan & Koneksi
        "tab4_page_title": "Settings & Connections",
        "tab4_breadcrumb": "Settings",
        "tab4_lang_title": "🌐 Interface Language",
        "tab4_provider_title": "Provider LLM",  # User explicitly requested to keep exact
        "tab4_mcp_config_title": "Konfigurasi MCP Siap Pakai",  # User explicitly requested to keep exact
        "lbl_deteksi_key": "Auto-Detect API Key:",
        "lbl_custom_endpoint": "Custom Endpoint Settings (DeepSeek / Ollama / vLLM / LM Studio):",
        "lbl_endpoint_url": "Endpoint Base URL:",
        "lbl_endpoint_model": "Model Name:",
        "btn_simpan_key": "💾 Save & Activate API Key",
        "btn_offline_mode": "🛡️ Run 100% Offline Mode (Local Distiller)",
        "btn_tes_koneksi": "⚡ Test Endpoint Connection",
        "btn_salin_mcp": "📋 Copy JSON Configuration",
        "mcp_guide_text": "Paste this JSON configuration into your MCP client settings (Claude Desktop, Antigravity, Cursor, or VS Code):",
    },
}


def t(key: str, default: str = "", **kwargs: Any) -> str:
    """Mengambil string terjemahan berdasarkan kunci dan bahasa aktif saat ini."""
    lang = get_current_language()
    teks = TRANSLATIONS.get(lang, {}).get(key)
    if teks is None:
        teks = TRANSLATIONS.get(LANG_ID, {}).get(key, default or key)
    if kwargs:
        try:
            return teks.format(**kwargs)
        except Exception:
            return teks
    return teks
