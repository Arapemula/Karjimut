"""Dialog Pop-Up Onboarding Wizard ("Setup Awal Karjimut") — TeamHub Mint-Teal Edition.

Ditampilkan secara otomatis ketika aplikasi desktop pertama kali dibuka dan
pengguna belum mengatur API Key LLM. Menyediakan:
  1. Kolom input tunggal dengan Auto-Detect prefix API Key secara real-time.
  2. Tombol pintas membuka Google AI Studio (API Key Gemini Gratis).
  3. Accordion opsional ``[+ Custom Base URL & Model Name]`` untuk endpoint kustom.
  4. Tombol ``[Simpan & Mulai]`` yang langsung mengaktifkan LLM Consolidator.
"""

from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Callable

import customtkinter as ctk

from .key_detector import (
    GOOGLE_AI_STUDIO_URL,
    HasilDeteksiKey,
    aktifkan_mode_offline_lokal,
    deteksi_api_key,
    simpan_konfigurasi_llm,
)

# Palet Warna TeamHub Mint-Teal Light
BG_CANVAS = "#EAF2EE"
BG_CARD = "#FFFFFF"
BG_MINT_SOFT = "#E6F4EA"
BG_SUBTLE = "#F4F8F6"
BORDER_SOFT = "#DCE7E2"
BRAND_TEAL = "#26A689"
BRAND_TEAL_HOVER = "#1D8A70"
BRAND_DARK = "#114B3E"
TEXT_PRIMARY = "#111827"
TEXT_SECONDARY = "#4B5563"
TEXT_MUTED = "#64748B"


class OnboardingDialog(ctk.CTkToplevel):
    """Jendela modal Setup Awal Karjimut bergaya TeamHub Mint-Teal."""

    def __init__(
        self,
        parent: ctk.CTk,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_complete = on_complete
        self._accordion_open = False
        self._show_key = False

        self.title("Setup Awal Karjimut — Auto-Detect API Key")
        self.geometry("620x500")
        self.minsize(580, 460)
        self.configure(fg_color=BG_CANVAS)
        self.resizable(False, False)

        # Jadikan modal terhadap main window
        self.transient(parent)
        self.grab_set()
        self.lift()
        self.focus_force()

        self._build_ui()
        self._center_window(parent)

    def _center_window(self, parent: ctk.CTk) -> None:
        self.update_idletasks()
        w, h = 620, 500
        px = parent.winfo_rootx() + max(0, (parent.winfo_width() - w) // 2)
        py = parent.winfo_rooty() + max(0, (parent.winfo_height() - h) // 2)
        self.geometry(f"{w}x{h}+{max(40, px)}+{max(40, py)}")

    def _build_ui(self) -> None:
        container = ctk.CTkFrame(
            self,
            fg_color=BG_CARD,
            corner_radius=18,
            border_width=1,
            border_color=BORDER_SOFT,
        )
        container.pack(fill="both", expand=True, padx=20, pady=20)

        # Header Banner Mint-Sage
        header_box = ctk.CTkFrame(
            container,
            fg_color=BG_MINT_SOFT,
            corner_radius=12,
            border_width=1,
            border_color="#C6E6D0",
        )
        header_box.pack(fill="x", padx=22, pady=(20, 14))

        header_top = ctk.CTkFrame(header_box, fg_color="transparent")
        header_top.pack(fill="x", padx=16, pady=(12, 2))

        self._logo_img = None
        try:
            from PIL import Image
            from ..config import PROJECT_ROOT
            candidates = [
                PROJECT_ROOT / "assets" / "karjimut_logo.png",
                Path(__file__).resolve().parent.parent / "assets" / "karjimut_logo.png",
                Path(__file__).resolve().parent / "assets" / "karjimut_logo.png",
            ]
            for logo_path in candidates:
                if logo_path.exists():
                    pil_img = Image.open(logo_path)
                    self._logo_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(34, 34))
                    break
        except Exception:
            pass

        if self._logo_img is not None:
            ctk.CTkLabel(
                header_top,
                text="",
                image=self._logo_img,
                width=34,
                height=34,
                fg_color="transparent",
            ).pack(side="left", padx=(0, 10))
            title_text = "Setup Awal Karjimut"
        else:
            title_text = "🌱 Setup Awal Karjimut"

        lbl_title = ctk.CTkLabel(
            header_top,
            text=title_text,
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=BRAND_DARK,
        )
        lbl_title.pack(side="left", anchor="w")

        lbl_sub = ctk.CTkLabel(
            header_box,
            text=(
                "Tempelkan API Key LLM Anda pada satu kolom di bawah ini.\n"
                "Sistem otomatis mengenali Google Gemini, Groq, OpenRouter, Claude, atau OpenAI."
            ),
            font=ctk.CTkFont(size=12),
            text_color=TEXT_SECONDARY,
            justify="left",
        )
        lbl_sub.pack(anchor="w", padx=16, pady=(0, 12))

        # Tombol ambil API Key Gemini gratis
        btn_gemini = ctk.CTkButton(
            container,
            text="🔗 Ambil API Key Gemini Gratis di Google AI Studio",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#E0F2FE",
            hover_color="#BAE6FD",
            text_color="#0369A1",
            height=36,
            corner_radius=10,
            command=lambda: webbrowser.open(GOOGLE_AI_STUDIO_URL),
        )
        btn_gemini.pack(fill="x", padx=22, pady=(0, 14))

        # Baris Input Tunggal API Key
        lbl_input = ctk.CTkLabel(
            container,
            text="API Key LLM (1-Column Auto-Detect):",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_PRIMARY,
        )
        lbl_input.pack(anchor="w", padx=22, pady=(0, 6))

        input_row = ctk.CTkFrame(container, fg_color="transparent")
        input_row.pack(fill="x", padx=22)

        self.entry_key = ctk.CTkEntry(
            input_row,
            placeholder_text="Tempel API Key di sini (AIzaSy... / gsk_... / sk-or-... / sk-ant-... / sk-...)",
            height=40,
            font=ctk.CTkFont(family="Consolas", size=13),
            fg_color=BG_SUBTLE,
            border_color="#CBDAD3",
            text_color=TEXT_PRIMARY,
            show="•",
        )
        self.entry_key.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry_key.bind("<KeyRelease>", self._on_input_change)

        self.btn_toggle_show = ctk.CTkButton(
            input_row,
            text="Lihat",
            width=64,
            height=40,
            fg_color=BG_SUBTLE,
            hover_color="#E2ECE8",
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color="#CBDAD3",
            command=self._toggle_show_key,
        )
        self.btn_toggle_show.pack(side="left", padx=(0, 6))

        btn_paste = ctk.CTkButton(
            input_row,
            text="📋 Tempel",
            width=86,
            height=40,
            fg_color=BG_MINT_SOFT,
            hover_color="#D0EBD8",
            text_color=BRAND_DARK,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._paste_from_clipboard,
        )
        btn_paste.pack(side="left")

        # Indikator Deteksi Real-Time
        self.badge_frame = ctk.CTkFrame(
            container,
            fg_color=BG_SUBTLE,
            corner_radius=10,
            border_width=1,
            border_color=BORDER_SOFT,
        )
        self.badge_frame.pack(fill="x", padx=22, pady=(12, 6))

        self.lbl_deteksi = ctk.CTkLabel(
            self.badge_frame,
            text="💡 Menunggu input API Key...",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_MUTED,
        )
        self.lbl_deteksi.pack(anchor="w", padx=14, pady=10)

        # Accordion [+ Custom Base URL & Model Name]
        self.btn_accordion = ctk.CTkButton(
            container,
            text="[+ Custom Base URL & Model Name] (Opsional: DeepSeek, Ollama, vLLM, LM Studio)",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="transparent",
            hover_color=BG_SUBTLE,
            text_color=BRAND_TEAL,
            anchor="w",
            height=28,
            command=self._toggle_accordion,
        )
        self.btn_accordion.pack(fill="x", padx=18, pady=(2, 4))

        self.frame_custom = ctk.CTkFrame(
            container,
            fg_color=BG_SUBTLE,
            corner_radius=10,
            border_width=1,
            border_color=BORDER_SOFT,
        )
        # Disembunyikan secara default

        custom_grid = ctk.CTkFrame(self.frame_custom, fg_color="transparent")
        custom_grid.pack(fill="x", padx=12, pady=10)
        custom_grid.grid_columnconfigure(0, weight=3)
        custom_grid.grid_columnconfigure(1, weight=2)

        ctk.CTkLabel(
            custom_grid,
            text="Custom Base URL:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 4))

        ctk.CTkLabel(
            custom_grid,
            text="Custom Model Name:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=1, sticky="w", pady=(0, 4))

        self.entry_base_url = ctk.CTkEntry(
            custom_grid,
            placeholder_text="Contoh: https://api.deepseek.com/v1 atau http://localhost:11434",
            height=32,
            font=ctk.CTkFont(size=12),
            fg_color=BG_CARD,
            border_color="#CBDAD3",
            text_color=TEXT_PRIMARY,
        )
        self.entry_base_url.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self.entry_base_url.bind("<KeyRelease>", self._on_input_change)

        self.entry_model = ctk.CTkEntry(
            custom_grid,
            placeholder_text="Contoh: deepseek-chat / llama3.2 / gemini-3.8-flash",
            height=32,
            font=ctk.CTkFont(size=12),
            fg_color=BG_CARD,
            border_color="#CBDAD3",
            text_color=TEXT_PRIMARY,
        )
        self.entry_model.grid(row=1, column=1, sticky="ew")
        self.entry_model.bind("<KeyRelease>", self._on_input_change)

        # Tombol Aksi Bawah
        action_row = ctk.CTkFrame(container, fg_color="transparent")
        action_row.pack(fill="x", side="bottom", padx=22, pady=(10, 18))

        btn_offline = ctk.CTkButton(
            action_row,
            text="Gunakan Mode Offline (Local Fallback)",
            fg_color=BG_SUBTLE,
            hover_color="#E2ECE8",
            border_width=1,
            border_color="#CBDAD3",
            text_color=TEXT_SECONDARY,
            height=40,
            corner_radius=10,
            command=self._gunakan_mode_offline,
        )
        btn_offline.pack(side="left")

        self.btn_simpan = ctk.CTkButton(
            action_row,
            text="✅ Simpan & Mulai",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=BRAND_TEAL,
            hover_color=BRAND_TEAL_HOVER,
            text_color="#FFFFFF",
            height=40,
            width=190,
            corner_radius=10,
            state="disabled",
            command=self._simpan_dan_mulai,
        )
        self.btn_simpan.pack(side="right")

    def _toggle_show_key(self) -> None:
        self._show_key = not self._show_key
        self.entry_key.configure(show="" if self._show_key else "•")
        self.btn_toggle_show.configure(text="Tutup" if self._show_key else "Lihat")

    def _paste_from_clipboard(self) -> None:
        try:
            teks = self.clipboard_get().strip()
            if teks:
                self.entry_key.delete(0, "end")
                self.entry_key.insert(0, teks)
                self._on_input_change()
        except Exception:
            pass

    def _toggle_accordion(self) -> None:
        self._accordion_open = not self._accordion_open
        if self._accordion_open:
            self.geometry("620x580")
            self.btn_accordion.configure(
                text="[- Sembunyikan Custom Base URL & Model Name]"
            )
            self.frame_custom.pack(fill="x", padx=22, pady=(0, 8), after=self.btn_accordion)
        else:
            self.frame_custom.pack_forget()
            self.geometry("620x500")
            self.btn_accordion.configure(
                text="[+ Custom Base URL & Model Name] (Opsional: DeepSeek, Ollama, vLLM, LM Studio)"
            )

    def _evaluasi_input(self) -> HasilDeteksiKey:
        raw_key = self.entry_key.get()
        c_url = self.entry_base_url.get() if self._accordion_open else ""
        c_model = self.entry_model.get() if self._accordion_open else ""
        return deteksi_api_key(raw_key, custom_base_url=c_url, custom_model_name=c_model)

    def _on_input_change(self, _event: object = None) -> None:
        hasil = self._evaluasi_input()
        if hasil.valid:
            self.lbl_deteksi.configure(
                text=f"🟢 Terdeteksi Otomatis: {hasil.badge_text}",
                text_color="#0F7652",
            )
            self.badge_frame.configure(fg_color=BG_MINT_SOFT, border_color=BRAND_TEAL)
            self.btn_simpan.configure(state="normal", fg_color=BRAND_TEAL)
        else:
            ikon = "⚠️" if hasil.provider == "invalid" else "💡"
            warna = "#B45309" if hasil.provider == "invalid" else TEXT_MUTED
            self.lbl_deteksi.configure(
                text=f"{ikon} {hasil.badge_text}",
                text_color=warna,
            )
            self.badge_frame.configure(fg_color=BG_SUBTLE, border_color=BORDER_SOFT)
            self.btn_simpan.configure(state="disabled", fg_color="#94A3B8")

    def _simpan_dan_mulai(self) -> None:
        raw_key = self.entry_key.get()
        c_url = self.entry_base_url.get() if self._accordion_open else ""
        c_model = self.entry_model.get() if self._accordion_open else ""
        try:
            simpan_konfigurasi_llm(
                raw_key,
                custom_base_url=c_url,
                custom_model_name=c_model,
                fallback_on_error=True,
            )
        except ValueError as exc:
            self.lbl_deteksi.configure(text=f"❌ {exc}", text_color="#B91C1C")
            return
        self._selesai()

    def _gunakan_mode_offline(self) -> None:
        aktifkan_mode_offline_lokal()
        self._selesai()

    def _selesai(self) -> None:
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
        if self._on_complete is not None:
            self._on_complete()
