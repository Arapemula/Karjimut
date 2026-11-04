"""Mixin Shell Utama (Sidebar Kiri, Header Atas, Baris 4 Kartu KPI, & Footer) untuk GUI Karjimut."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import customtkinter as ctk

from ..config import PROJECT_ROOT
from .i18n import t
from .key_detector import info_provider_aktif
from .theme import (
    BG_CARD,
    BG_LIME_SOFT,
    BG_MINT_SOFT,
    BG_SUBTLE,
    BG_WORKSPACE,
    BORDER_CARD,
    BORDER_MINT,
    BRAND_DARK,
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


class ShellLayoutMixin:
    """Mixin pembangun kerangka utama jendela (Sidebar, Top Bar, 4 Kartu KPI, & Status Footer)."""

    def _build_shell_layout(self) -> None:
        self.shell_frame = ctk.CTkFrame(
            self,
            fg_color=BG_WORKSPACE,
            corner_radius=20,
            border_width=1,
            border_color="#D0E0D9",
        )
        self.shell_frame.pack(fill="both", expand=True, padx=14, pady=(12, 6))
        self.shell_frame.grid_columnconfigure(0, weight=0, minsize=238)
        self.shell_frame.grid_columnconfigure(1, weight=1)
        self.shell_frame.grid_rowconfigure(0, weight=1)

        self.sidebar_frame = ctk.CTkFrame(
            self.shell_frame,
            width=238,
            fg_color=BG_CARD,
            corner_radius=18,
            border_width=1,
            border_color=BORDER_CARD,
        )
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew", padx=(10, 6), pady=10)
        self.sidebar_frame.grid_propagate(False)

        self.main_area = ctk.CTkFrame(self.shell_frame, fg_color="transparent")
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=(6, 10), pady=10)

    def _pasang_ikon_aplikasi(self) -> None:
        """Memasang ikon jendela aplikasi (.ico / .png) jika tersedia di folder assets."""
        try:
            candidates = [
                PROJECT_ROOT / "assets" / "karjimut.ico",
                Path(__file__).resolve().parent.parent / "assets" / "karjimut.ico",
                Path(__file__).resolve().parent / "assets" / "karjimut.ico",
            ]
            for ico_path in candidates:
                if ico_path.exists():
                    self.iconbitmap(str(ico_path))
                    break
        except Exception:
            pass

    def _muat_logo_brand(self, size: tuple[int, int] = (40, 40)) -> ctk.CTkImage | None:
        """Memuat gambar logo Karjimut sebagai CTkImage dengan fallback aman."""
        try:
            from PIL import Image
            candidates = [
                PROJECT_ROOT / "assets" / "karjimut_logo.png",
                Path(__file__).resolve().parent.parent / "assets" / "karjimut_logo.png",
                Path(__file__).resolve().parent / "assets" / "karjimut_logo.png",
            ]
            for logo_path in candidates:
                if logo_path.exists():
                    pil_img = Image.open(logo_path)
                    return ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
        except Exception:
            pass
        return None

    def _build_sidebar(self) -> None:
        brand_row = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        brand_row.pack(fill="x", padx=18, pady=(20, 18))

        self._brand_logo_img = self._muat_logo_brand(size=(40, 40))
        if self._brand_logo_img is not None:
            logo_badge = ctk.CTkLabel(
                brand_row,
                text="",
                image=self._brand_logo_img,
                width=40,
                height=40,
                fg_color="transparent",
            )
        else:
            logo_badge = ctk.CTkLabel(
                brand_row,
                text="🌱",
                font=ctk.CTkFont(size=18),
                width=38,
                height=38,
                fg_color=BG_MINT_SOFT,
                text_color=BRAND_TEAL,
                corner_radius=10,
            )
        logo_badge.pack(side="left", padx=(0, 10))

        brand_txt = ctk.CTkFrame(brand_row, fg_color="transparent")
        brand_txt.pack(side="left")

        ctk.CTkLabel(
            brand_txt,
            text="Karjimut",
            font=ctk.CTkFont(size=19, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w")

        ctk.CTkLabel(
            brand_txt,
            text="Two-Tier Memory Hub",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED,
        ).pack(anchor="w")

        self.lbl_nav_group = ctk.CTkLabel(
            self.sidebar_frame,
            text=t("nav_menu_title"),
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#94A3B8",
        )
        self.lbl_nav_group.pack(anchor="w", padx=20, pady=(2, 6))

        nav_items = [
            (self.PAGE_CORE, "🪪   " + t("nav_core")),
            (self.PAGE_SOLUSI, "🗄   " + t("nav_solusi")),
            (self.PAGE_CATATAN, "📊   " + t("nav_catatan")),
            (self.PAGE_SETTINGS, "🔑   " + t("nav_pengaturan")),
        ]
        for page_key, label in nav_items:
            btn = ctk.CTkButton(
                self.sidebar_frame,
                text=label,
                anchor="w",
                height=42,
                corner_radius=10,
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color="transparent",
                text_color=TEXT_SECONDARY,
                hover_color=BG_MINT_SOFT,
                command=lambda k=page_key: self.pilih_halaman(k),
            )
            btn.pack(fill="x", padx=14, pady=3)
            self._nav_buttons[page_key] = btn

        arch_box = ctk.CTkFrame(
            self.sidebar_frame,
            fg_color=BG_SUBTLE,
            corner_radius=12,
            border_width=1,
            border_color=BORDER_CARD,
        )
        arch_box.pack(fill="x", padx=14, pady=(16, 6))

        self.lbl_arch_title = ctk.CTkLabel(
            arch_box,
            text="📌 " + t("status_arsitektur_title"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_PRIMARY,
        )
        self.lbl_arch_title.pack(anchor="w", padx=12, pady=(10, 4))

        self.lbl_sidebar_info = ctk.CTkLabel(
            arch_box,
            text=t("status_arsitektur_body"),
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED,
            justify="left",
        )
        self.lbl_sidebar_info.pack(anchor="w", padx=12, pady=(0, 10))

        promo_card = ctk.CTkFrame(
            self.sidebar_frame,
            fg_color=BG_MINT_SOFT,
            corner_radius=14,
            border_width=1,
            border_color=BORDER_MINT,
        )
        promo_card.pack(fill="x", side="bottom", padx=14, pady=14)

        self.lbl_sidebar_promo_title = ctk.CTkLabel(
            promo_card,
            text=t("quick_action_title"),
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=BRAND_DARK,
        )
        self.lbl_sidebar_promo_title.pack(anchor="w", padx=14, pady=(12, 2))

        self.lbl_sidebar_promo_desc = ctk.CTkLabel(
            promo_card,
            text=t("quick_action_desc"),
            font=ctk.CTkFont(size=11),
            text_color=TEXT_SECONDARY,
            justify="left",
            wraplength=190,
        )
        self.lbl_sidebar_promo_desc.pack(anchor="w", padx=14, pady=(0, 10))

        self.btn_trigger_sleep = ctk.CTkButton(
            promo_card,
            text=t("btn_trigger_sleep"),
            height=36,
            corner_radius=9,
            fg_color=BRAND_TEAL,
            hover_color=BRAND_TEAL_HOVER,
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._trigger_sleep_sekarang,
        )
        self.btn_trigger_sleep.pack(fill="x", padx=14, pady=(0, 12))

    def _build_header(self) -> None:
        header = ctk.CTkFrame(
            self.main_area,
            fg_color=BG_CARD,
            corner_radius=14,
            border_width=1,
            border_color=BORDER_CARD,
        )
        header.pack(fill="x", pady=(0, 8))

        left_title = ctk.CTkFrame(header, fg_color="transparent")
        left_title.pack(side="left", padx=18, pady=10)

        self.lbl_page_title = ctk.CTkLabel(
            left_title,
            text="KTP Proyek (Lapis 1)",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=TEXT_PRIMARY,
        )
        self.lbl_page_title.pack(anchor="w")

        self.lbl_breadcrumb = ctk.CTkLabel(
            left_title,
            text=f"Karjimut  /  {self.kode_proyek_aktif}  /  Core Proyek",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=BRAND_TEAL,
        )
        self.lbl_breadcrumb.pack(anchor="w")

        right_bar = ctk.CTkFrame(header, fg_color="transparent")
        right_bar.pack(side="right", padx=(6, 16), pady=10)

        self.badge_provider = ctk.CTkLabel(
            right_bar,
            text="🤖 Provider",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=BG_SUBTLE,
            text_color=BRAND_DARK,
            corner_radius=10,
            padx=12,
            pady=6,
        )
        self.badge_provider.pack(side="right", padx=(6, 2))

        self.badge_siklus = ctk.CTkLabel(
            right_bar,
            text="● STANDBY",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=PILL_INFO_BG,
            text_color=PILL_INFO_FG,
            corner_radius=10,
            padx=10,
            pady=6,
        )
        self.badge_siklus.pack(side="right", padx=(0, 4))

        center_bar = ctk.CTkFrame(
            header,
            fg_color=BG_SUBTLE,
            corner_radius=10,
            border_width=1,
            border_color=BORDER_CARD,
        )
        center_bar.pack(side="left", padx=8, pady=10)

        self.lbl_proyek_prefix = ctk.CTkLabel(
            center_bar,
            text="📁 " + t("proyek_label"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_SECONDARY,
        )
        self.lbl_proyek_prefix.pack(side="left", padx=(10, 6), pady=6)

        self.opt_proyek = ctk.CTkOptionMenu(
            center_bar,
            values=self.daftar_proyek_tersedia,
            command=self._on_ganti_proyek,
            width=120,
            height=30,
            fg_color=BG_CARD,
            text_color=TEXT_PRIMARY,
            button_color=BRAND_TEAL,
            button_hover_color=BRAND_TEAL_HOVER,
            dropdown_fg_color=BG_CARD,
            dropdown_text_color=TEXT_PRIMARY,
            dropdown_hover_color=BG_MINT_SOFT,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.opt_proyek.set(self.kode_proyek_aktif)
        self.opt_proyek.pack(side="left", padx=(0, 4), pady=6)

        self.btn_tambah_proyek = ctk.CTkButton(
            center_bar,
            text=t("btn_tambah_proyek"),
            width=70,
            height=30,
            corner_radius=8,
            fg_color=BG_MINT_SOFT,
            hover_color="#CBE8D4",
            text_color=PILL_SUCCESS_FG,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._dialog_proyek_baru,
        )
        self.btn_tambah_proyek.pack(side="left", padx=(0, 4), pady=6)

        self.btn_gabung_proyek = ctk.CTkButton(
            center_bar,
            text=t("btn_gabung_proyek"),
            width=68,
            height=30,
            corner_radius=8,
            fg_color=BG_CARD,
            hover_color="#E2ECE8",
            text_color=TEXT_SECONDARY,
            border_width=1,
            border_color=BORDER_CARD,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._dialog_ganti_nama_proyek,
        )
        self.btn_gabung_proyek.pack(side="left", padx=(0, 4), pady=6)

        ctk.CTkButton(
            center_bar,
            text="🗑️",
            width=30,
            height=30,
            corner_radius=8,
            fg_color=PILL_DANGER_BG,
            hover_color="#FECACA",
            text_color=PILL_DANGER_FG,
            font=ctk.CTkFont(size=12),
            command=self._dialog_hapus_proyek,
        ).pack(side="left", padx=(0, 4), pady=6)

        ctk.CTkButton(
            center_bar,
            text="🔄",
            width=30,
            height=30,
            corner_radius=8,
            fg_color=BG_MINT_SOFT,
            hover_color="#CBE8D4",
            text_color=PILL_SUCCESS_FG,
            font=ctk.CTkFont(size=13),
            command=lambda: self.refresh_semua_data(force_editor=True),
        ).pack(side="left", padx=(0, 6), pady=6)

    def _build_kpi_summary_row(self) -> None:
        kpi_row = ctk.CTkFrame(self.main_area, fg_color="transparent")
        kpi_row.pack(fill="x", pady=(0, 8))
        for col in range(4):
            kpi_row.grid_columnconfigure(col, weight=1, uniform="kpi")

        k1 = ctk.CTkFrame(
            kpi_row,
            fg_color=BG_LIME_SOFT,
            corner_radius=14,
            border_width=1,
            border_color="#BFE0B4",
        )
        k1.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        self.lbl_kpi_1_title = ctk.CTkLabel(
            k1,
            text="🪪 " + t("kpi_core_title"),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=BRAND_DARK,
            anchor="w",
        )
        self.lbl_kpi_1_title.pack(anchor="w", padx=10, pady=(8, 1))

        self.lbl_kpi_ktp_val = ctk.CTkLabel(
            k1,
            text="0 Token",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.lbl_kpi_ktp_val.pack(anchor="w", padx=10)

        self.lbl_kpi_ktp_sub = ctk.CTkLabel(
            k1,
            text="Versi: - • Elastic Core Aktif",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=PILL_SUCCESS_FG,
            anchor="w",
        )
        self.lbl_kpi_ktp_sub.pack(anchor="w", padx=10, pady=(1, 8))

        k2 = ctk.CTkFrame(
            kpi_row,
            fg_color=BG_CARD,
            corner_radius=14,
            border_width=1,
            border_color=BORDER_CARD,
        )
        k2.grid(row=0, column=1, sticky="nsew", padx=6)

        self.lbl_kpi_2_title = ctk.CTkLabel(
            k2,
            text="🗄️ " + t("kpi_solusi_title"),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self.lbl_kpi_2_title.pack(anchor="w", padx=10, pady=(8, 1))

        self.lbl_kpi_solusi_val = ctk.CTkLabel(
            k2,
            text="0 Solusi Paten",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.lbl_kpi_solusi_val.pack(anchor="w", padx=10)

        self.lbl_kpi_solusi_sub = ctk.CTkLabel(
            k2,
            text="Hybrid BM25 + Vector 384d",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=BRAND_TEAL,
            anchor="w",
        )
        self.lbl_kpi_solusi_sub.pack(anchor="w", padx=10, pady=(1, 8))

        k3 = ctk.CTkFrame(
            kpi_row,
            fg_color=BG_CARD,
            corner_radius=14,
            border_width=1,
            border_color=BORDER_CARD,
        )
        k3.grid(row=0, column=2, sticky="nsew", padx=6)

        self.lbl_kpi_3_title = ctk.CTkLabel(
            k3,
            text="📉 " + t("kpi_metrik_a_title"),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self.lbl_kpi_3_title.pack(anchor="w", padx=10, pady=(8, 1))

        self.lbl_kpi_metrik_a_val = ctk.CTkLabel(
            k3,
            text="0.00%",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.lbl_kpi_metrik_a_val.pack(anchor="w", padx=10)

        self.lbl_kpi_metrik_a_sub = ctk.CTkLabel(
            k3,
            text="Target Efisiensi > 60%",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=PILL_SUCCESS_FG,
            anchor="w",
        )
        self.lbl_kpi_metrik_a_sub.pack(anchor="w", padx=10, pady=(1, 8))

        k4 = ctk.CTkFrame(
            kpi_row,
            fg_color=BG_CARD,
            corner_radius=14,
            border_width=1,
            border_color=BORDER_CARD,
        )
        k4.grid(row=0, column=3, sticky="nsew", padx=(6, 0))

        self.lbl_kpi_4_title = ctk.CTkLabel(
            k4,
            text="📥 " + t("kpi_catatan_title"),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self.lbl_kpi_4_title.pack(anchor="w", padx=10, pady=(8, 1))

        self.lbl_kpi_antrean_val = ctk.CTkLabel(
            k4,
            text="0 Pending",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.lbl_kpi_antrean_val.pack(anchor="w", padx=10)

        self.lbl_kpi_antrean_sub = ctk.CTkLabel(
            k4,
            text="0 Terangkum • Net: +0 tok",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self.lbl_kpi_antrean_sub.pack(anchor="w", padx=10, pady=(1, 8))

    def _build_status_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color="transparent", height=24)
        footer.pack(fill="x", side="bottom", padx=20, pady=(0, 6))

        self.lbl_footer = ctk.CTkLabel(
            footer,
            text="Siap. Idle Watcher Daemon berjalan otomatis di background.",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=TEXT_SECONDARY,
        )
        self.lbl_footer.pack(side="left")

        self.lbl_footer_db = ctk.CTkLabel(
            footer,
            text=f"SQLite WAL: {Path(self.settings.db_path).name}  •  Copyright © Karjimut",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=TEXT_MUTED,
        )
        self.lbl_footer_db.pack(side="right")

    def _render_kpi_summary_row(
        self,
        ktp_row: Any,
        total_solusi: int,
        metrik: dict[str, Any],
        status_siklus: dict[str, Any],
    ) -> None:
        batas = self.settings.ktp_max_tokens
        if batas <= 0:
            if ktp_row is not None:
                tok = int(ktp_row["jumlah_token"] or 0)
                versi = int(ktp_row["versi_ktp"] or 1)
                self.lbl_kpi_ktp_val.configure(text=f"{tok} Token")
                self.lbl_kpi_ktp_sub.configure(text=t("kpi_core_sub_elastic", versi=versi))
            else:
                self.lbl_kpi_ktp_val.configure(text="0 Token")
                self.lbl_kpi_ktp_sub.configure(text=t("kpi_core_sub_elastic", versi="-"))
        else:
            if ktp_row is not None:
                tok = int(ktp_row["jumlah_token"] or 0)
                versi = int(ktp_row["versi_ktp"] or 1)
                persen = int((tok / max(1, batas)) * 100)
                self.lbl_kpi_ktp_val.configure(text=f"{tok} / {batas} Token")
                self.lbl_kpi_ktp_sub.configure(text=t("kpi_core_sub", versi=versi, pct=persen))
            else:
                self.lbl_kpi_ktp_val.configure(text=f"0 / {batas} Token")
                self.lbl_kpi_ktp_sub.configure(text=t("kpi_core_sub", versi="-", pct=0))

        self.lbl_kpi_solusi_val.configure(text=t("kpi_solusi_unit", count=total_solusi))
        self.lbl_kpi_solusi_sub.configure(
            text=t("kpi_solusi_sub", proyek=self.kode_proyek_aktif)
        )

        ef_a = metrik["efisiensi_aktif_persen"]
        self.lbl_kpi_metrik_a_val.configure(text=f"{ef_a:.2f}%")
        self.lbl_kpi_metrik_a_sub.configure(
            text=t("kpi_metrik_a_sub") if metrik["metrik_a_tercapai"] else "Pra-Target (<60%)",
            text_color=PILL_SUCCESS_FG if metrik["metrik_a_tercapai"] else PILL_WARN_FG,
        )

        antrean = status_siklus["antrean"]
        net_tok = metrik["net_savings_tokens"]
        tanda = "+" if net_tok >= 0 else ""
        self.lbl_kpi_antrean_val.configure(text=t("kpi_catatan_unit", count=antrean["pending"]))
        self.lbl_kpi_antrean_sub.configure(
            text=t("kpi_catatan_sub", terangkum=antrean["processed"], net=f"{tanda}{net_tok:,}")
        )

    def _render_header_badges(self, status_siklus: dict[str, Any]) -> None:
        st = status_siklus["status"]
        antrean = status_siklus["antrean"]
        if st == "WORKING":
            warna_bg, warna_txt = PILL_SUCCESS_BG, PILL_SUCCESS_FG
            teks = f"🟢 WORKING ({antrean['pending']} pending)"
        elif st == "IDLE_COUNTDOWN":
            warna_bg, warna_txt = PILL_WARN_BG, PILL_WARN_FG
            teks = f"⏳ IDLE ({status_siklus['sisa_countdown_detik']}s)"
        elif st == "SLEEPING" or self._sedang_sleep:
            warna_bg, warna_txt = PILL_PURPLE_BG, PILL_PURPLE_FG
            teks = "🟣 SLEEPING"
        else:
            warna_bg, warna_txt = PILL_INFO_BG, PILL_INFO_FG
            teks = "🔵 STANDBY"

        self.badge_siklus.configure(text=teks, fg_color=warna_bg, text_color=warna_txt)

        info_prov = info_provider_aktif()
        if info_prov["aktif"]:
            prov_raw = info_prov["provider"]
            if "OpenAI-Compatible" in prov_raw or "Custom" in prov_raw:
                prov_label = "OpenAI-Compat"
            elif "Google Gemini" in prov_raw:
                prov_label = "Gemini"
            elif "Anthropic Claude" in prov_raw:
                prov_label = "Claude"
            elif "Groq" in prov_raw:
                prov_label = "Groq"
            else:
                prov_label = prov_raw.split()[0]

            model_short = info_prov["model"]
            if len(model_short) > 13:
                model_short = model_short[:11] + "…"

            self.badge_provider.configure(
                text=f"🤖 {prov_label} ({model_short})",
                fg_color=BG_MINT_SOFT,
                text_color=PILL_SUCCESS_FG,
            )
        else:
            self.badge_provider.configure(
                text="⚙️ Local Distiller (Offline)",
                fg_color=PILL_WARN_BG,
                text_color=PILL_WARN_FG,
            )
