"""Aplikasi Desktop Native Karjimut berbasis CustomTkinter (TeamHub Mint-Teal SaaS Edition).

Arsitektur Modular GUI (`src/gui/`):
  - `app_gui.py`         : Controller utama jendela, navigasi halaman, i18n, auto-poll DB, & Sleep Cycle Worker.
  - `shell_layout.py`    : Pembangun Sidebar, Top Header, Baris 4 Kartu KPI, & Status Footer.
  - `theme.py`           : Palet warna TeamHub Soft Mint-Teal & Sage Green.
  - `project_dialogs.py` : Dialog tambah, ganti nama/gabung, & hapus proyek.
  - `tab_ktp.py`         : Halaman 1 — Editor KTP Proyek (Lapis 1), Live Token Counter, Snapshot, & 1-Click Rollback.
  - `tab_solusi.py`      : Halaman 2 — Laci Arsip Solusi (Lapis 2), Pencarian BM25/RRF, CRUD, & Feedback Loop.
  - `tab_antrean.py`     : Halaman 3 — Dual/Tri Sustainability Card (Metrik A/B/C), Antrean Log, & Audit Token.
  - `tab_settings.py`    : Halaman 4 — Auto-Detect API Key 1 Kolom, Custom Endpoint, & Generator Config MCP IDE.
"""

from __future__ import annotations

import sys
import threading
from typing import Any

import customtkinter as ctk

from ..config import get_settings, setup_logging
from ..consolidator import jalankan_sleep_cycle_tuntas
from ..db import daftar_proyek, koneksi, pastikan_db
from ..fts_search import cari_solusi_fts_conn
from ..idle_watcher import IdleWatcherDaemon, hitung_status_siklus_proyek
from ..services import hitung_metrik_proyek
from .i18n import (
    BAHASA_TERSEDIA,
    LANG_EN,
    LANG_ID,
    muat_preferensi_bahasa_tersimpan,
    set_current_language,
    t,
)
from .key_detector import perlu_onboarding
from .onboarding_dialog import OnboardingDialog
from .project_dialogs import ProjectDialogsMixin
from .shell_layout import ShellLayoutMixin
from .tab_antrean import AntreanTabMixin
from .tab_ktp import KtpTabMixin
from .tab_settings import SettingsTabMixin
from .tab_solusi import SolusiTabMixin
from .theme import (
    BG_CANVAS,
    BG_CARD,
    BG_LIME_SOFT,
    BG_MINT_SOFT,
    BG_SUBTLE,
    BG_WORKSPACE,
    BORDER_CARD,
    BORDER_MINT,
    BRAND_DARK,
    BRAND_DARK_HOVER,
    BRAND_TEAL,
    BRAND_TEAL_HOVER,
    PILL_DANGER_BG,
    PILL_DANGER_FG,
    PILL_INFO_BG,
    PILL_INFO_FG,
    PILL_PURPLE_BG,
    PILL_PURPLE_FG,
    PILL_SUCCESS_BG,
    PILL_SUCCESS_FG,
    PILL_WARN_BG,
    PILL_WARN_FG,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

logger = setup_logging("sleep_mcp.gui")


class _SidebarNavController:
    """Adapter kompatibilitas untuk navigasi halaman berbasis Sidebar (kompatibel dengan API Tabview)."""

    def __init__(self, app: SleepMCPDesktopApp) -> None:
        self._app = app
        self._pages: dict[str, ctk.CTkFrame] = {}
        self._current: str = ""

    def add(self, name: str) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self._app.page_container, fg_color="transparent")
        self._pages[name] = frame
        if not self._current:
            self._current = name
        return frame

    def set(self, name: str) -> None:
        self._app.pilih_halaman(name)

    def get(self) -> str:
        return self._current


class SleepMCPDesktopApp(
    ShellLayoutMixin,
    KtpTabMixin,
    SolusiTabMixin,
    AntreanTabMixin,
    SettingsTabMixin,
    ProjectDialogsMixin,
    ctk.CTk,
):
    """Jendela Utama Aplikasi Desktop Native Karjimut (TeamHub Mint-Teal Edition)."""

    PAGE_CORE = "🪪 1. Core Proyek (Lapis 1)"
    PAGE_SOLUSI = "🗄 2. Bank Solusi (Lapis 2)"
    PAGE_CATATAN = "📊 3. Catatan & Laporan"
    PAGE_SETTINGS = "🔑 4. Pengaturan & Koneksi"

    # Backward compatibility aliases
    PAGE_KTP = PAGE_CORE
    PAGE_ANTREAN = PAGE_CATATAN

    def __init__(self, skip_onboarding: bool = False) -> None:
        if sys.platform == "win32":
            try:
                import ctypes

                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("karjimut.desktop.v2")
            except Exception:
                pass

        super().__init__()

        muat_preferensi_bahasa_tersimpan()

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("green")

        self.title("Karjimut — Two-Tier Memory Hub")
        self.geometry("1300x850")
        self.minsize(1080, 720)
        self.configure(fg_color=BG_CANVAS)
        self._pasang_ikon_aplikasi()

        self.settings = get_settings()
        pastikan_db(self.settings.db_path)

        # State aplikasi
        self.kode_proyek_aktif: str = "default"
        self.daftar_proyek_tersedia: list[str] = []
        self._sedang_sleep: bool = False
        self._solusi_edit_id: int | None = None
        self._solusi_sort_mode: str = "id_desc"
        self._search_query_aktif: str = ""
        self._last_data_signature: tuple[Any, ...] | None = None
        self._ktp_dirty: bool = False
        self._custom_endpoint_open: bool = False
        self._show_settings_key: bool = False
        self._closing: bool = False
        self._poll_job: str | None = None
        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        self._halaman_aktif: str = self.PAGE_CORE

        # Background Idle Watcher Daemon
        self.watcher = IdleWatcherDaemon(db_path=self.settings.db_path)
        self.watcher.start(daemon=True)

        self._muat_daftar_proyek_awal()
        self._build_shell_layout()
        self._build_sidebar()
        self._build_header()
        self._build_kpi_summary_row()
        self._build_tabs()
        self._build_status_footer()

        self.pilih_halaman(self.PAGE_CORE)
        self.refresh_semua_data(force_editor=True)

        self._poll_job = self.after(2000, self._auto_poll_loop)

        if not skip_onboarding and perlu_onboarding():
            self.after(250, self.buka_onboarding_wizard)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        try:
            self.update()
        except Exception:
            pass

    def _muat_daftar_proyek_awal(self) -> None:
        with koneksi(self.settings.db_path) as conn:
            proyek = daftar_proyek(conn)
        if not proyek:
            proyek = ["default"]
        self.daftar_proyek_tersedia = proyek
        self.kode_proyek_aktif = proyek[0]

    # =========================================================================
    # KONTROLER 4 HALAMAN UTAMA
    # =========================================================================
    def _build_tabs(self) -> None:
        self.page_container = ctk.CTkFrame(self.main_area, fg_color="transparent")
        self.page_container.pack(fill="both", expand=True)

        self.tabview = _SidebarNavController(self)

        self.tab_ktp = self.tabview.add(self.PAGE_CORE)
        self.tab_solusi = self.tabview.add(self.PAGE_SOLUSI)
        self.tab_antrean = self.tabview.add(self.PAGE_CATATAN)
        self.tab_settings = self.tabview.add(self.PAGE_SETTINGS)

        self._build_tab_ktp()
        self._build_tab_solusi()
        self._build_tab_antrean()
        self._build_tab_settings()

    def pilih_halaman(self, nama_halaman: str) -> None:
        """Mengganti tampilan halaman aktif dan memperbarui tombol aktif di Sidebar & Breadcrumb."""
        if nama_halaman in (self.PAGE_CORE, "PAGE_CORE", "🪪 1. KTP Proyek (Lapis 1)", "🪪 1. Core Proyek (Lapis 1)"):
            nama_halaman = self.PAGE_CORE
        elif nama_halaman in (
            self.PAGE_SOLUSI,
            "PAGE_SOLUSI",
            "🗄️ 2. Laci Arsip Solusi (Lapis 2)",
            "🗄️ 2. Bank Solusi (Lapis 2)",
            "🗄 2. Bank Solusi (Lapis 2)",
        ):
            nama_halaman = self.PAGE_SOLUSI
        elif nama_halaman in (self.PAGE_CATATAN, "PAGE_CATATAN", "📊 3. Antrean Log & Audit Metrik", "📊 3. Catatan & Laporan"):
            nama_halaman = self.PAGE_CATATAN
        elif nama_halaman in (self.PAGE_SETTINGS, "PAGE_SETTINGS", "🔑 4. Pengaturan API Key", "🔑 4. Pengaturan & Koneksi"):
            nama_halaman = self.PAGE_SETTINGS

        if nama_halaman not in self.tabview._pages:
            return
        self._halaman_aktif = nama_halaman
        self.tabview._current = nama_halaman

        for key, frame in self.tabview._pages.items():
            if key == nama_halaman:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

        for key, btn in self._nav_buttons.items():
            if key == nama_halaman:
                btn.configure(
                    fg_color=BRAND_TEAL,
                    text_color="#FFFFFF",
                    hover_color=BRAND_TEAL_HOVER,
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=TEXT_SECONDARY,
                    hover_color=BG_MINT_SOFT,
                )

        judul_map = {
            self.PAGE_CORE: (t("nav_core"), t("nav_core")),
            self.PAGE_SOLUSI: (t("nav_solusi"), "Hybrid (BM25 + Vector)"),
            self.PAGE_CATATAN: (t("tab3_page_title"), t("tab3_breadcrumb")),
            self.PAGE_SETTINGS: (t("tab4_page_title"), t("tab4_breadcrumb")),
        }
        judul, pendek = judul_map.get(nama_halaman, (t("breadcrumb_dashboard"), "Overview"))
        self.lbl_page_title.configure(text=judul)
        self.lbl_breadcrumb.configure(
            text=f"{t('breadcrumb_dashboard')}  /  {self.kode_proyek_aktif}  /  {pendek}"
        )

    # =========================================================================
    # LOGIKA SINKRONISASI DATA, I18N, & EVENT HANDLER
    # =========================================================================
    def _on_ganti_bahasa(self, pilihan: str) -> None:
        """Mengubah bahasa antarmuka (ID / EN) dan memperbarui teks secara dinamis."""
        lang_code = LANG_EN if "English" in pilihan else LANG_ID
        set_current_language(lang_code)
        self._terapkan_terjemahan_ui()

    def _terapkan_terjemahan_ui(self) -> None:
        """Menerapkan terjemahan bahasa aktif ke seluruh elemen antarmuka."""
        if hasattr(self, "lbl_nav_group"):
            self.lbl_nav_group.configure(text=t("nav_menu_title"))
        if self.PAGE_CORE in self._nav_buttons:
            self._nav_buttons[self.PAGE_CORE].configure(text="🪪   " + t("nav_core"))
        if self.PAGE_SOLUSI in self._nav_buttons:
            self._nav_buttons[self.PAGE_SOLUSI].configure(text="🗄   " + t("nav_solusi"))
        if self.PAGE_CATATAN in self._nav_buttons:
            self._nav_buttons[self.PAGE_CATATAN].configure(text="📊   " + t("nav_catatan"))
        if self.PAGE_SETTINGS in self._nav_buttons:
            self._nav_buttons[self.PAGE_SETTINGS].configure(text="🔑   " + t("nav_pengaturan"))

        if hasattr(self, "lbl_arch_title"):
            self.lbl_arch_title.configure(text="📌 " + t("status_arsitektur_title"))
        if hasattr(self, "lbl_sidebar_info"):
            self.lbl_sidebar_info.configure(text=t("status_arsitektur_body"))
        if hasattr(self, "lbl_sidebar_promo_title"):
            self.lbl_sidebar_promo_title.configure(text=t("quick_action_title"))
        if hasattr(self, "lbl_sidebar_promo_desc"):
            self.lbl_sidebar_promo_desc.configure(text=t("quick_action_desc"))
        if hasattr(self, "btn_trigger_sleep") and not self._sedang_sleep:
            self.btn_trigger_sleep.configure(text=t("btn_trigger_sleep"))

        if hasattr(self, "lbl_proyek_prefix"):
            self.lbl_proyek_prefix.configure(text="📁 " + t("proyek_label"))
        if hasattr(self, "btn_tambah_proyek"):
            self.btn_tambah_proyek.configure(text=t("btn_tambah_proyek"))
        if hasattr(self, "btn_gabung_proyek"):
            self.btn_gabung_proyek.configure(text=t("btn_gabung_proyek"))

        if hasattr(self, "lbl_kpi_1_title"):
            self.lbl_kpi_1_title.configure(text="🪪 " + t("kpi_core_title"))
        if hasattr(self, "lbl_kpi_2_title"):
            self.lbl_kpi_2_title.configure(text="🗄️ " + t("kpi_solusi_title"))
        if hasattr(self, "lbl_kpi_3_title"):
            self.lbl_kpi_3_title.configure(text="📉 " + t("kpi_metrik_a_title"))
        if hasattr(self, "lbl_kpi_4_title"):
            self.lbl_kpi_4_title.configure(text="📥 " + t("kpi_catatan_title"))

        if hasattr(self, "lbl_ktp_desc"):
            self.lbl_ktp_desc.configure(text=t("tab1_desc"))
        if hasattr(self, "btn_simpan_ktp"):
            self.btn_simpan_ktp.configure(text=t("btn_simpan_core"))
        if hasattr(self, "btn_rollback_ktp"):
            self.btn_rollback_ktp.configure(text=t("btn_rollback"))
        if hasattr(self, "lbl_snap_title"):
            self.lbl_snap_title.configure(text="🕒 " + t("snapshot_title"))
        if hasattr(self, "lbl_snap_desc"):
            self.lbl_snap_desc.configure(text=t("snapshot_desc"))
        if hasattr(self, "lbl_guide_title"):
            self.lbl_guide_title.configure(text="📋 " + t("mandat_title"))

        if hasattr(self, "lbl_search_title"):
            self.lbl_search_title.configure(text="🔍 " + t("tab2_search_title"))
        if hasattr(self, "btn_cari_bm25"):
            self.btn_cari_bm25.configure(text=t("btn_cari_bm25"))
        if hasattr(self, "btn_semua_solusi"):
            self.btn_semua_solusi.configure(text=t("btn_semua_solusi"))
        if hasattr(self, "lbl_form_solusi_title"):
            self.lbl_form_solusi_title.configure(
                text=t("tab2_form_add_title")
                if self._solusi_edit_id is None
                else t("tab2_form_edit_title", id=self._solusi_edit_id)
            )
        if hasattr(self, "lbl_solusi_tags_label"):
            self.lbl_solusi_tags_label.configure(text=t("tab2_tag_label"))
        if hasattr(self, "entry_solusi_tags"):
            self.entry_solusi_tags.configure(placeholder_text=t("tab2_tag_placeholder"))
        if hasattr(self, "lbl_solusi_isi_label"):
            self.lbl_solusi_isi_label.configure(text=t("tab2_solusi_label"))
        if hasattr(self, "btn_simpan_solusi"):
            self.btn_simpan_solusi.configure(
                text=t("btn_simpan_ke_bank")
                if self._solusi_edit_id is None
                else t("btn_update_ke_bank")
            )
        if hasattr(self, "btn_batal_edit_solusi"):
            self.btn_batal_edit_solusi.configure(text=t("btn_batal_edit"))

        if hasattr(self, "lbl_quick_log_title"):
            self.lbl_quick_log_title.configure(text="📝 " + t("tab3_quick_note_title"))
        if hasattr(self, "btn_masuk_antrean"):
            self.btn_masuk_antrean.configure(text=t("btn_masuk_antrean"))
        if hasattr(self, "lbl_audit_header"):
            self.lbl_audit_header.configure(text="📊 " + t("tab3_audit_title"))

        if hasattr(self, "lbl_settings_lang_title"):
            self.lbl_settings_lang_title.configure(text=t("tab4_lang_title"))
        if hasattr(self, "lbl_settings_provider_title"):
            self.lbl_settings_provider_title.configure(text="🤖 " + t("tab4_provider_title"))
        if hasattr(self, "lbl_settings_mcp_title"):
            self.lbl_settings_mcp_title.configure(
                text="🔌 " + t("tab4_mcp_config_title") + " (Antigravity / Cursor / Claude Desktop / Windsurf)"
            )

        self.pilih_halaman(self._halaman_aktif)
        self.refresh_semua_data(force_editor=True)

    def buka_onboarding_wizard(self) -> None:
        OnboardingDialog(self, on_complete=lambda: self.refresh_semua_data(force_editor=False))

    def _auto_poll_loop(self) -> None:
        """Polling ringan setiap 2 detik untuk memperbarui status siklus & mendeteksi perubahan DB."""
        if self._closing:
            return
        try:
            self.refresh_semua_data(force_editor=False)
        except Exception as exc:
            logger.debug("Auto-poll warning: %s", exc)
        finally:
            if not self._closing:
                self._poll_job = self.after(2000, self._auto_poll_loop)

    def refresh_semua_data(self, force_editor: bool = False) -> None:
        """Membaca state terkini dari SQLite dalam 1 koneksi dan memperbarui komponen UI."""
        self.settings = get_settings()
        kode = self.kode_proyek_aktif

        with koneksi(self.settings.db_path) as conn:
            proyek_db = daftar_proyek(conn)
            for p in proyek_db:
                if p not in self.daftar_proyek_tersedia:
                    self.daftar_proyek_tersedia.append(p)
            if kode not in self.daftar_proyek_tersedia:
                self.daftar_proyek_tersedia.insert(0, kode)
            self.opt_proyek.configure(values=self.daftar_proyek_tersedia)

            status_siklus = hitung_status_siklus_proyek(kode, self.settings.db_path, conn=conn)
            metrik = hitung_metrik_proyek(conn, kode)

            ktp_row = conn.execute(
                """
                SELECT ringkasan_inti, ringkasan_sebelumnya, jumlah_token, versi_ktp, waktu_update
                FROM ktp_proyek WHERE kode_proyek = ?
                """,
                (kode,),
            ).fetchone()

            total_solusi = conn.execute(
                "SELECT COUNT(*) FROM laci_arsip WHERE kode_proyek = ?",
                (kode,),
            ).fetchone()[0]

            if self._search_query_aktif:
                solusi_rows = cari_solusi_fts_conn(conn, kode, self._search_query_aktif, limit=10)
            else:
                raw_solusi = conn.execute(
                    """
                    SELECT id, kode_proyek, tag_masalah, solusi_paten,
                           COALESCE(confidence, 0.7) AS confidence,
                           COALESCE(hit_count, 0) AS hit_count,
                           COALESCE(miss_count, 0) AS miss_count,
                           COALESCE(is_stale, 0) AS is_stale,
                           waktu_dibuat,
                           (SELECT GROUP_CONCAT(target_id, ', ') FROM relasi_solusi WHERE source_id = laci_arsip.id AND relasi = 'SUPERSEDED') AS supersedes_id,
                           (SELECT GROUP_CONCAT(source_id, ', ') FROM relasi_solusi WHERE target_id = laci_arsip.id AND relasi = 'SUPERSEDED') AS superseded_by_id
                    FROM laci_arsip WHERE kode_proyek = ? ORDER BY id DESC
                    """,
                    (kode,),
                ).fetchall()
                solusi_rows = [dict(r) for r in raw_solusi]
                if self._solusi_sort_mode == "id_asc":
                    solusi_rows.sort(key=lambda s: int(s.get("id", 0)))
                elif self._solusi_sort_mode == "conf_desc":
                    solusi_rows.sort(key=lambda s: (float(s.get("confidence", 0.7)), int(s.get("id", 0))), reverse=True)
                else:
                    solusi_rows.sort(key=lambda s: int(s.get("id", 0)), reverse=True)

            antrean_rows = conn.execute(
                """
                SELECT id, kode_proyek, isi_log, estimasi_token_mentah,
                       waktu_masuk, waktu_kunci, status_rangkum
                FROM antrean_mentah
                WHERE kode_proyek = ?
                ORDER BY id DESC
                LIMIT 25
                """,
                (kode,),
            ).fetchall()

        self._render_header_badges(status_siklus)
        self._render_tab_settings_status()
        self._render_kpi_summary_row(ktp_row, int(total_solusi), metrik, status_siklus)

        sig = (
            kode,
            dict(ktp_row) if ktp_row else None,
            tuple(
                (
                    s.get("id"),
                    s.get("tag_masalah"),
                    s.get("solusi_paten"),
                    s.get("confidence"),
                    s.get("hit_count"),
                    s.get("miss_count"),
                    s.get("is_stale"),
                    s.get("skor_bm25"),
                    s.get("skor_rrf"),
                )
                for s in solusi_rows
            ),
            self._solusi_sort_mode,
            tuple((r["id"], r["status_rangkum"]) for r in antrean_rows),
            metrik["t_baseline"],
            metrik["t_total_mcp"],
            len(metrik["history"]),
        )
        if not force_editor and sig == self._last_data_signature:
            return
        self._last_data_signature = sig

        self._render_tab_ktp(ktp_row, force_editor=force_editor)
        self._render_tab_solusi(solusi_rows)
        self._render_tab_antrean([dict(r) for r in antrean_rows], metrik, status_siklus)

    # =========================================================================
    # LOGIKA TRIGGER SLEEP CYCLE (BACKGROUND THREAD) & PENUTUPAN JENDELA
    # =========================================================================
    def _trigger_sleep_sekarang(self) -> None:
        if self._sedang_sleep:
            return
        self._sedang_sleep = True
        self.btn_trigger_sleep.configure(state="disabled", text=t("btn_sleeping"))
        self.lbl_footer.configure(
            text=f"Menjalankan Sleep Cycle untuk proyek '{self.kode_proyek_aktif}'...",
            text_color=PILL_PURPLE_FG,
        )
        self._render_header_badges(hitung_status_siklus_proyek(self.kode_proyek_aktif, self.settings.db_path))

        kode = self.kode_proyek_aktif

        def _worker() -> None:
            pesan_akhir = ""
            warna_akhir = PILL_SUCCESS_FG
            try:
                hasil_list = jalankan_sleep_cycle_tuntas(kode, db_path=self.settings.db_path)
                if not hasil_list:
                    pesan_akhir = "Tidak ada log pending."
                else:
                    last = hasil_list[-1]
                    pesan_akhir = f"[{last.mode_distiller}] {last.pesan}"
                    if last.status == "ERROR":
                        warna_akhir = PILL_DANGER_FG
                    elif last.status == "NO_PENDING":
                        warna_akhir = PILL_INFO_FG
            except Exception as exc:
                pesan_akhir = f"Sleep Cycle gagal: {exc}"
                warna_akhir = PILL_DANGER_FG

            def _selesai_ui() -> None:
                self._sedang_sleep = False
                self.btn_trigger_sleep.configure(state="normal", text=t("btn_trigger_sleep"))
                self.lbl_footer.configure(text=pesan_akhir, text_color=warna_akhir)
                self._ktp_dirty = False
                self.refresh_semua_data(force_editor=True)

            self.after(0, _selesai_ui)

        threading.Thread(target=_worker, daemon=True, name="SleepMCP-GUI-ManualSleep").start()

    def _on_close(self) -> None:
        self._closing = True
        if self._poll_job is not None:
            try:
                self.after_cancel(self._poll_job)
            except Exception:
                pass
            self._poll_job = None
        try:
            self.watcher.stop(timeout=1.5)
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass


KarjimutDesktopApp = SleepMCPDesktopApp


def start_desktop_app(skip_onboarding: bool = False) -> None:
    """Meluncurkan jendela utama Karjimut Desktop Native App."""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("karjimut.desktop.v2")
        except Exception:
            pass

    app = KarjimutDesktopApp(skip_onboarding=skip_onboarding)
    app.mainloop()


if __name__ == "__main__":
    start_desktop_app()
