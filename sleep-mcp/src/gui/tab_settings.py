"""Mixin Halaman 4: Pengaturan API Key & Integrasi MCP IDE untuk GUI Karjimut."""

from __future__ import annotations

import json
import shutil
import sys
import threading
import webbrowser
from pathlib import Path

import customtkinter as ctk

from ..config import IS_FROZEN, IS_INSTALLED_PACKAGE, PROJECT_ROOT, SRC_DIR, get_settings
from .i18n import get_current_language, t
from .key_detector import (
    GOOGLE_AI_STUDIO_URL,
    aktifkan_mode_offline_lokal,
    deteksi_api_key,
    info_provider_aktif,
    simpan_konfigurasi_llm,
    terapkan_model,
    tes_koneksi_llm,
)
from .theme import (
    BG_CARD,
    BG_MINT_SOFT,
    BG_SUBTLE,
    BORDER_CARD,
    BORDER_MINT,
    BRAND_DARK,
    BRAND_DARK_HOVER,
    BRAND_TEAL,
    BRAND_TEAL_HOVER,
    PILL_DANGER_FG,
    PILL_INFO_BG,
    PILL_INFO_FG,
    PILL_SUCCESS_FG,
    PILL_WARN_FG,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class SettingsTabMixin:
    """Mixin untuk Halaman 4 (Pengaturan API Key, Bahasa, Custom Endpoint, & Generator Config MCP IDE)."""

    def _build_tab_settings(self) -> None:
        wrapper = ctk.CTkScrollableFrame(
            self.tab_settings,
            fg_color="transparent",
        )
        wrapper.pack(fill="both", expand=True)

        # 0. Kartu Preferensi Bahasa Antarmuka
        lang_card = ctk.CTkFrame(
            wrapper,
            fg_color=BG_CARD,
            corner_radius=14,
            border_width=1,
            border_color=BORDER_CARD,
        )
        lang_card.pack(fill="x", padx=2, pady=(0, 10))

        lang_row = ctk.CTkFrame(lang_card, fg_color="transparent")
        lang_row.pack(fill="x", padx=18, pady=12)

        self.lbl_settings_lang_title = ctk.CTkLabel(
            lang_row,
            text=t("tab4_lang_title"),
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_PRIMARY,
        )
        self.lbl_settings_lang_title.pack(side="left")

        self.opt_bahasa = ctk.CTkOptionMenu(
            lang_row,
            values=["🇮🇩 Bahasa Indonesia", "🇬🇧 English"],
            command=self._on_ganti_bahasa,
            width=190,
            height=32,
            fg_color=BRAND_TEAL,
            button_color=BRAND_TEAL_HOVER,
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=9,
        )
        cur_l = get_current_language()
        self.opt_bahasa.set("🇮🇩 Bahasa Indonesia" if cur_l == "id" else "🇬🇧 English")
        self.opt_bahasa.pack(side="right")

        # 1. Kartu Status Provider LLM
        status_card = ctk.CTkFrame(
            wrapper,
            fg_color=BG_MINT_SOFT,
            corner_radius=14,
            border_width=1,
            border_color=BORDER_MINT,
        )
        status_card.pack(fill="x", padx=2, pady=(0, 10))

        self.lbl_settings_provider_title = ctk.CTkLabel(
            status_card,
            text="🤖 " + t("tab4_provider_title"),
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=BRAND_DARK,
        )
        self.lbl_settings_provider_title.pack(anchor="w", padx=18, pady=(12, 4))

        self.lbl_settings_status = ctk.CTkLabel(
            status_card,
            text="Memuat status konfigurasi...",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color=TEXT_PRIMARY,
            justify="left",
        )
        self.lbl_settings_status.pack(anchor="w", padx=18, pady=(0, 12))

        # 2. Kartu Input 1 Kolom Auto-Detect API Key
        key_card = ctk.CTkFrame(
            wrapper,
            fg_color=BG_CARD,
            corner_radius=14,
            border_width=1,
            border_color=BORDER_CARD,
        )
        key_card.pack(fill="x", padx=2, pady=(0, 10))

        top_key_row = ctk.CTkFrame(key_card, fg_color="transparent")
        top_key_row.pack(fill="x", padx=18, pady=(14, 6))

        ctk.CTkLabel(
            top_key_row,
            text="🔑 Ganti / Perbarui API Key (1 Kolom Auto-Detect Otomatis)",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkButton(
            top_key_row,
            text="🔗 Ambil API Key Gemini Gratis di Google AI Studio",
            fg_color=PILL_INFO_BG,
            hover_color="#BAE6FD",
            text_color=PILL_INFO_FG,
            corner_radius=9,
            height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: webbrowser.open(GOOGLE_AI_STUDIO_URL),
        ).pack(side="right")

        ctk.CTkLabel(
            key_card,
            text="Tempelkan API Key LLM Anda di bawah. Provider (Gemini, Groq, OpenRouter, Claude, OpenAI) dan model terbaik akan dideteksi secara otomatis.",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
            justify="left",
            wraplength=700,
        ).pack(anchor="w", padx=18, pady=(0, 10))

        input_row = ctk.CTkFrame(key_card, fg_color="transparent")
        input_row.pack(fill="x", padx=18)

        self.entry_settings_key = ctk.CTkEntry(
            input_row,
            placeholder_text="Tempel API Key baru di sini (AIzaSy... / gsk_... / sk-or-... / sk-ant-... / sk-...)",
            height=40,
            font=ctk.CTkFont(family="Consolas", size=13),
            fg_color=BG_SUBTLE,
            border_color="#CBDAD3",
            text_color=TEXT_PRIMARY,
            corner_radius=10,
            show="•",
        )
        self.entry_settings_key.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry_settings_key.bind("<KeyRelease>", self._on_settings_key_change)

        self.btn_settings_show = ctk.CTkButton(
            input_row,
            text="Lihat",
            width=64,
            height=40,
            corner_radius=10,
            fg_color=BG_SUBTLE,
            hover_color="#E2ECE8",
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=BORDER_CARD,
            command=self._toggle_settings_show_key,
        )
        self.btn_settings_show.pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            input_row,
            text="📋 Tempel",
            width=86,
            height=40,
            corner_radius=10,
            fg_color=BG_MINT_SOFT,
            hover_color="#CBE8D4",
            text_color=BRAND_DARK,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._paste_settings_key,
        ).pack(side="left")

        self.lbl_settings_deteksi = ctk.CTkLabel(
            key_card,
            text="💡 Ketik atau tempel API Key untuk melihat hasil deteksi otomatis.",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_MUTED,
        )
        self.lbl_settings_deteksi.pack(anchor="w", padx=18, pady=(10, 6))

        # Accordion Custom Base URL & Model Name
        self.btn_settings_accordion = ctk.CTkButton(
            key_card,
            text="[+ Custom Base URL & Model Name] (Opsional: DeepSeek, Ollama, vLLM, LM Studio)",
            fg_color="transparent",
            hover_color=BG_SUBTLE,
            text_color=BRAND_TEAL,
            anchor="w",
            height=28,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._toggle_settings_accordion,
        )
        self.btn_settings_accordion.pack(fill="x", padx=14, pady=(0, 6))

        self.frame_settings_custom = ctk.CTkFrame(
            key_card,
            fg_color=BG_SUBTLE,
            corner_radius=10,
            border_width=1,
            border_color=BORDER_CARD,
        )

        c_grid = ctk.CTkFrame(self.frame_settings_custom, fg_color="transparent")
        c_grid.pack(fill="x", padx=14, pady=10)
        c_grid.grid_columnconfigure(0, weight=3)
        c_grid.grid_columnconfigure(1, weight=2)

        ctk.CTkLabel(
            c_grid,
            text="Custom Base URL:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=(0, 4))

        ctk.CTkLabel(
            c_grid,
            text="Custom Model Name:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=1, sticky="w", pady=(0, 4))

        self.entry_settings_url = ctk.CTkEntry(
            c_grid,
            placeholder_text="https://api.deepseek.com/v1 atau http://localhost:11434",
            height=34,
            fg_color=BG_CARD,
            border_color="#CBDAD3",
            text_color=TEXT_PRIMARY,
        )
        self.entry_settings_url.grid(row=1, column=0, sticky="ew", padx=(0, 10))
        self.entry_settings_url.bind("<KeyRelease>", self._on_settings_key_change)

        self.entry_settings_model = ctk.CTkEntry(
            c_grid,
            placeholder_text="deepseek-chat / llama3.2 / gemini-3.8-flash",
            height=34,
            fg_color=BG_CARD,
            border_color="#CBDAD3",
            text_color=TEXT_PRIMARY,
        )
        self.entry_settings_model.grid(row=1, column=1, sticky="ew")
        self.entry_settings_model.bind("<KeyRelease>", self._on_settings_key_change)

        self.chk_fallback_error = ctk.CTkCheckBox(
            key_card,
            text="Jaring Pengaman: Otomatis gunakan Local Rule-Based Distiller jika internet putus / LLM error",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_SECONDARY,
            fg_color=BRAND_TEAL,
            hover_color=BRAND_TEAL_HOVER,
        )
        self.chk_fallback_error.select()
        self.chk_fallback_error.pack(anchor="w", padx=18, pady=(6, 12))

        btn_save_row = ctk.CTkFrame(key_card, fg_color="transparent")
        btn_save_row.pack(fill="x", padx=18, pady=(0, 16))

        ctk.CTkButton(
            btn_save_row,
            text="💾 Simpan & Aktifkan API Key",
            fg_color=BRAND_TEAL,
            hover_color=BRAND_TEAL_HOVER,
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=10,
            height=38,
            width=210,
            command=self._simpan_settings_key,
        ).pack(side="left", padx=(0, 8))

        self.btn_tes_koneksi = ctk.CTkButton(
            btn_save_row,
            text="🧪 Tes Koneksi & Verifikasi Model",
            fg_color=BRAND_DARK,
            hover_color=BRAND_DARK_HOVER,
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=10,
            height=38,
            width=235,
            command=self._tes_koneksi_dari_settings,
        )
        self.btn_tes_koneksi.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_save_row,
            text="📴 Mode Offline (Local Distiller)",
            fg_color=BG_SUBTLE,
            hover_color="#E2ECE8",
            text_color=TEXT_SECONDARY,
            border_width=1,
            border_color=BORDER_CARD,
            corner_radius=10,
            height=38,
            command=self._aktifkan_offline_dari_settings,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_save_row,
            text="✨ Wizard Setup Awal",
            fg_color=BG_MINT_SOFT,
            hover_color="#CBE8D4",
            text_color=BRAND_DARK,
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=10,
            height=38,
            command=self.buka_onboarding_wizard,
        ).pack(side="left")

        # 3. Kartu Integrasi MCP IDE
        ide_card = ctk.CTkFrame(
            wrapper,
            fg_color=BG_CARD,
            corner_radius=14,
            border_width=1,
            border_color=BORDER_CARD,
        )
        ide_card.pack(fill="x", padx=2, pady=(0, 8))

        ide_top = ctk.CTkFrame(ide_card, fg_color="transparent")
        ide_top.pack(fill="x", padx=18, pady=(14, 6))

        self.lbl_settings_mcp_title = ctk.CTkLabel(
            ide_top,
            text="🔌 " + t("tab4_mcp_config_title") + " (Antigravity / Cursor / Claude Desktop / Windsurf)",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_PRIMARY,
        )
        self.lbl_settings_mcp_title.pack(side="left")

        ide_actions = ctk.CTkFrame(ide_top, fg_color="transparent")
        ide_actions.pack(side="right")

        self.seg_mcp_mode = ctk.CTkSegmentedButton(
            ide_actions,
            values=["Portabel (python)", "Path Absolut PC"],
            command=self._on_ganti_mcp_mode,
            height=30,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=BG_SUBTLE,
            selected_color=BRAND_TEAL,
            selected_hover_color=BRAND_TEAL_HOVER,
            unselected_color=BG_CARD,
            unselected_hover_color=BG_MINT_SOFT,
            text_color=TEXT_PRIMARY,
        )
        self.seg_mcp_mode.set("Portabel (python)")
        self.seg_mcp_mode.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            ide_actions,
            text="📋 Salin JSON MCP",
            fg_color=BRAND_TEAL,
            hover_color=BRAND_TEAL_HOVER,
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=9,
            height=30,
            command=self._salin_json_mcp,
        ).pack(side="left")

        ctk.CTkButton(
            ide_actions,
            text="🚀 Pasang Otomatis ke Semua IDE",
            fg_color=BRAND_DARK,
            hover_color=BRAND_DARK_HOVER,
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=9,
            height=30,
            command=self._auto_inject_ide_dari_gui,
        ).pack(side="left", padx=(8, 0))

        self.lbl_mcp_info_mode = ctk.CTkLabel(
            ide_card,
            text="💡 Mode Portabel: menggunakan perintah 'python' dari PATH sistem (konfigurasi standar & portabel tanpa path username laptop pribadi).",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED,
            justify="left",
        )
        self.lbl_mcp_info_mode.pack(anchor="w", padx=18, pady=(0, 6))

        self.txt_mcp_json = ctk.CTkTextbox(
            ide_card,
            height=135,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=BG_SUBTLE,
            text_color=BRAND_DARK,
            border_width=1,
            border_color=BORDER_CARD,
            corner_radius=10,
        )
        self.txt_mcp_json.pack(fill="x", padx=18, pady=(0, 14))
        self._muat_json_mcp_preview()

    def _render_tab_settings_status(self) -> None:
        info = info_provider_aktif()
        fallback_txt = "Aktif (Aman saat offline)" if info["fallback_on_error"] else "Nonaktif"
        teks = (
            f"Mode Konsolidasi : {info['mode']}\n"
            f"Provider Aktif   : {info['provider']}\n"
            f"Model LLM        : {info['model']}\n"
            f"Endpoint URL     : {info['base_url']}\n"
            f"API Key Tersimpan: {info['key_masked']}\n"
            f"Fallback Offline : {fallback_txt}\n"
            f"Mesin Vektor     : FastEmbed ONNX (384-dim, BAAI/bge-small-en-v1.5) [AKTIF]\n"
            f"Mesin Leksikal   : SQLite FTS5 Okapi BM25 [AKTIF]\n"
            f"Fusi Pemeringkat : Reciprocal Rank Fusion (RRF k=60) [AKTIF]\n"
            f"Graf Kausalitas  : Tabel relasi_solusi (SUPERSEDED/CAUSED_BY) [AKTIF]"
        )
        self.lbl_settings_status.configure(
            text=teks,
            text_color=BRAND_DARK if info["aktif"] else PILL_WARN_FG,
        )

    def _toggle_settings_show_key(self) -> None:
        self._show_settings_key = not self._show_settings_key
        self.entry_settings_key.configure(show="" if self._show_settings_key else "•")
        self.btn_settings_show.configure(text="Tutup" if self._show_settings_key else "Lihat")

    def _paste_settings_key(self) -> None:
        try:
            teks = self.clipboard_get().strip()
            if teks:
                self.entry_settings_key.delete(0, "end")
                self.entry_settings_key.insert(0, teks)
                self._on_settings_key_change()
        except Exception:
            pass

    def _toggle_settings_accordion(self) -> None:
        self._custom_endpoint_open = not self._custom_endpoint_open
        if self._custom_endpoint_open:
            self.btn_settings_accordion.configure(text="[- Sembunyikan Custom Base URL & Model Name]")
            self.frame_settings_custom.pack(
                fill="x", padx=18, pady=(0, 8), after=self.btn_settings_accordion
            )
        else:
            self.frame_settings_custom.pack_forget()
            self.btn_settings_accordion.configure(
                text="[+ Custom Base URL & Model Name] (Opsional: DeepSeek, Ollama, vLLM, LM Studio)"
            )

    def _on_settings_key_change(self, _event: object = None) -> None:
        raw_key = self.entry_settings_key.get()
        c_url = self.entry_settings_url.get() if self._custom_endpoint_open else ""
        c_model = self.entry_settings_model.get() if self._custom_endpoint_open else ""
        hasil = deteksi_api_key(raw_key, custom_base_url=c_url, custom_model_name=c_model)
        if hasil.valid:
            self.lbl_settings_deteksi.configure(
                text=f"🟢 Terdeteksi Otomatis: {hasil.badge_text}",
                text_color=PILL_SUCCESS_FG,
            )
        else:
            warna = PILL_WARN_FG if hasil.provider == "invalid" else TEXT_MUTED
            self.lbl_settings_deteksi.configure(
                text=f"💡 {hasil.badge_text}",
                text_color=warna,
            )

    def _simpan_settings_key(self) -> None:
        raw_key = self.entry_settings_key.get()
        c_url = self.entry_settings_url.get() if self._custom_endpoint_open else ""
        c_model = self.entry_settings_model.get() if self._custom_endpoint_open else ""
        fallback = bool(self.chk_fallback_error.get())
        try:
            det = simpan_konfigurasi_llm(
                raw_key,
                custom_base_url=c_url,
                custom_model_name=c_model,
                fallback_on_error=fallback,
            )
            self.entry_settings_key.delete(0, "end")
            self.lbl_settings_deteksi.configure(
                text=f"✅ Berhasil disimpan & diaktifkan: {det.badge_text}",
                text_color=PILL_SUCCESS_FG,
            )
            self.refresh_semua_data(force_editor=False)
        except ValueError as exc:
            self.lbl_settings_deteksi.configure(
                text=f"❌ {exc}",
                text_color=PILL_DANGER_FG,
            )

    def _aktifkan_offline_dari_settings(self) -> None:
        aktifkan_mode_offline_lokal()
        self.lbl_settings_deteksi.configure(
            text="✅ Mode 100% Offline (Local Rule-Based Distiller) diaktifkan.",
            text_color=PILL_WARN_FG,
        )
        self.refresh_semua_data(force_editor=False)

    def _tes_koneksi_dari_settings(self) -> None:
        raw_key = self.entry_settings_key.get().strip()
        c_url = self.entry_settings_url.get().strip() if self._custom_endpoint_open else ""
        c_model = self.entry_settings_model.get().strip() if self._custom_endpoint_open else ""

        s = get_settings()
        pakai_key_tersimpan = False
        if not raw_key:
            if not s.llm_api_key:
                self.lbl_settings_deteksi.configure(
                    text="⚠️ Masukkan API Key terlebih dahulu atau simpan API Key sebelum tes koneksi.",
                    text_color=PILL_WARN_FG,
                )
                return
            pakai_key_tersimpan = True
            key_uji = s.llm_api_key
            prov_uji = s.llm_provider
            url_uji = c_url or s.llm_api_base_url
            model_uji = c_model or s.llm_model_name
        else:
            det = deteksi_api_key(raw_key, custom_base_url=c_url, custom_model_name=c_model)
            if not det.valid:
                self.lbl_settings_deteksi.configure(
                    text=f"⚠️ {det.badge_text}",
                    text_color=PILL_WARN_FG,
                )
                return
            key_uji = det.api_key
            prov_uji = det.provider
            url_uji = det.base_url
            model_uji = det.model_name

        self.btn_tes_koneksi.configure(state="disabled", text="⏳ Menguji Endpoint...")
        self.lbl_settings_deteksi.configure(
            text=f"⏳ Menghubungi {url_uji} ({model_uji})...",
            text_color=PILL_INFO_FG,
        )

        def _worker() -> None:
            hasil = tes_koneksi_llm(
                provider=prov_uji,
                base_url=url_uji,
                api_key=key_uji,
                model_name=model_uji,
            )

            def _selesai() -> None:
                self.btn_tes_koneksi.configure(state="normal", text="🧪 Tes Koneksi & Verifikasi Model")
                if hasil["sukses"]:
                    model_terpilih = hasil["model_terpilih"]
                    if pakai_key_tersimpan and model_terpilih != s.llm_model_name:
                        terapkan_model(model_terpilih)
                    elif not pakai_key_tersimpan and self._custom_endpoint_open:
                        self.entry_settings_model.delete(0, "end")
                        self.entry_settings_model.insert(0, model_terpilih)
                    self.lbl_settings_deteksi.configure(
                        text=f"🟢 {hasil['pesan']}",
                        text_color=PILL_SUCCESS_FG,
                    )
                    self.refresh_semua_data(force_editor=False)
                else:
                    self.lbl_settings_deteksi.configure(
                        text=f"❌ {hasil['pesan']}",
                        text_color=PILL_DANGER_FG,
                    )

            self.after(0, _selesai)

        threading.Thread(target=_worker, daemon=True, name="SleepMCP-TestLLM").start()

    def _on_ganti_mcp_mode(self, mode: str) -> None:
        if mode == "Portabel (python)":
            self.lbl_mcp_info_mode.configure(
                text="💡 Mode Portabel: menggunakan perintah 'python' dari PATH sistem (konfigurasi standar & portabel tanpa path username laptop pribadi)."
            )
        else:
            self.lbl_mcp_info_mode.configure(
                text="💡 Mode Path Absolut: membaca lokasi instalasi Python laptop ini secara otomatis via sys.executable (berguna jika Claude Desktop/IDE tidak mengenali PATH)."
            )
        self._muat_json_mcp_preview()

    def _muat_json_mcp_preview(self) -> None:
        mode = getattr(self, "seg_mcp_mode", None)
        mode_val = mode.get() if mode is not None else "Portabel (python)"
        cwd_path = PROJECT_ROOT.resolve().as_posix()
        exe_kandidat_0 = PROJECT_ROOT / "Karjimut.exe"
        exe_kandidat_1 = PROJECT_ROOT / "Sleep-MCP.exe"
        exe_kandidat_2 = PROJECT_ROOT / "dist" / "Karjimut.exe"
        exe_kandidat_3 = PROJECT_ROOT / "dist" / "Sleep-MCP.exe"
        cli_karjimut = shutil.which("karjimut")

        if mode_val == "Portabel (python)":
            if IS_INSTALLED_PACKAGE or cli_karjimut:
                mcp_json = {
                    "mcpServers": {
                        "karjimut": {
                            "command": "karjimut",
                            "args": ["mcp"],
                        }
                    }
                }
                teks_json = json.dumps(mcp_json, indent=2)
                self.txt_mcp_json.delete("1.0", "end")
                self.txt_mcp_json.insert("1.0", teks_json)
                return
            cmd_path = "python"
            args_list = ["run.py", "mcp"]
        elif IS_FROZEN:
            cmd_path = Path(sys.executable).resolve().as_posix()
            args_list = ["mcp"]
        elif exe_kandidat_0.exists():
            cmd_path = exe_kandidat_0.resolve().as_posix()
            args_list = ["mcp"]
        elif exe_kandidat_1.exists():
            cmd_path = exe_kandidat_1.resolve().as_posix()
            args_list = ["mcp"]
        elif exe_kandidat_2.exists():
            cmd_path = exe_kandidat_2.resolve().as_posix()
            args_list = ["mcp"]
        elif exe_kandidat_3.exists():
            cmd_path = exe_kandidat_3.resolve().as_posix()
            args_list = ["mcp"]
        elif cli_karjimut and not (PROJECT_ROOT / "run.py").exists():
            cmd_path = Path(cli_karjimut).resolve().as_posix()
            args_list = ["mcp"]
        else:
            cmd_path = Path(sys.executable).resolve().as_posix()
            if cmd_path.lower().endswith("pythonw.exe"):
                kandidat = Path(sys.executable).with_name("python.exe")
                if kandidat.exists():
                    cmd_path = kandidat.resolve().as_posix()
            run_script = (
                f"{cwd_path}/run.py"
                if (PROJECT_ROOT / "run.py").exists()
                else f"{SRC_DIR.resolve().as_posix()}/run.py"
            )
            args_list = [run_script, "mcp"]

        mcp_json = {
            "mcpServers": {
                "karjimut": {
                    "command": cmd_path,
                    "args": args_list,
                    "cwd": cwd_path,
                }
            }
        }
        teks_json = json.dumps(mcp_json, indent=2)
        self.txt_mcp_json.delete("1.0", "end")
        self.txt_mcp_json.insert("1.0", teks_json)

    def _salin_json_mcp(self) -> None:
        teks = self.txt_mcp_json.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(teks)
        self.lbl_footer.configure(
            text="📋 Konfigurasi JSON MCP berhasil disalin ke Clipboard!",
            text_color=PILL_SUCCESS_FG,
        )

    def _auto_inject_ide_dari_gui(self) -> None:
        try:
            try:
                from ..run import auto_inject_mcp_ke_semua_ide
            except ImportError:
                from src.run import auto_inject_mcp_ke_semua_ide

            hasil = auto_inject_mcp_ke_semua_ide(verbose=False)
            if hasil:
                pesan = f"🚀 Berhasil disuntikkan ke {len(hasil)} IDE (Cursor, Claude, Windsurf, dll)!"
                self.lbl_footer.configure(text=pesan, text_color=PILL_SUCCESS_FG)
            else:
                self.lbl_footer.configure(
                    text="⚠️ Tidak ada IDE desktop yang terdeteksi otomatis. Silakan salin JSON manual.",
                    text_color=PILL_WARN_FG,
                )
        except Exception as exc:
            self.lbl_footer.configure(
                text=f"❌ Gagal menyuntikkan ke IDE: {exc}",
                text_color=PILL_DANGER_FG,
            )
