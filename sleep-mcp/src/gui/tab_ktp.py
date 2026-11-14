"""Mixin Halaman 1: Core Proyek / KTP Proyek (Lapis 1) untuk GUI Karjimut."""

from __future__ import annotations

from typing import Any

import customtkinter as ctk

from ..consolidator import ekspor_memori_tim, rollback_ktp
from ..db import koneksi, transaksi
from ..services import simpan_ktp_manual
from ..tokenizer_utils import hitung_token
from .i18n import t
from .theme import (
    BG_CARD,
    BG_MINT_SOFT,
    BG_SUBTLE,
    BORDER_CARD,
    BORDER_MINT,
    BRAND_DARK,
    BRAND_TEAL,
    BRAND_TEAL_HOVER,
    PILL_DANGER_FG,
    PILL_INFO_FG,
    PILL_SUCCESS_FG,
    PILL_WARN_BG,
    PILL_WARN_FG,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class KtpTabMixin:
    """Mixin untuk Halaman 1 (KTP Proyek / Lapis 1): editor, live token counter, snapshot, & rollback."""

    def _build_tab_ktp(self) -> None:
        grid = ctk.CTkFrame(self.tab_ktp, fg_color="transparent")
        grid.pack(fill="both", expand=True)
        grid.grid_columnconfigure(0, weight=7)
        grid.grid_columnconfigure(1, weight=4)
        grid.grid_rowconfigure(0, weight=1)

        # Kolom Kiri: Kartu Editor Utama KTP Proyek
        left_card = ctk.CTkFrame(
            grid,
            fg_color=BG_CARD,
            corner_radius=16,
            border_width=1,
            border_color=BORDER_CARD,
        )
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        top_bar = ctk.CTkFrame(
            left_card,
            fg_color=BG_SUBTLE,
            corner_radius=12,
            border_width=1,
            border_color=BORDER_CARD,
        )
        top_bar.pack(fill="x", padx=16, pady=(14, 10))
        top_bar.grid_columnconfigure(0, weight=1)
        top_bar.grid_columnconfigure(1, weight=0)

        self.lbl_ktp_judul = ctk.CTkLabel(
            top_bar,
            text="🪪 " + t("tab1_title", proyek=self.kode_proyek_aktif),
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=TEXT_PRIMARY,
        )
        self.lbl_ktp_judul.grid(row=0, column=0, sticky="w", padx=14, pady=(8, 1))

        self.lbl_token_counter = ctk.CTkLabel(
            top_bar,
            text=(
                f"{t('kpi_core_title')}: 0 Token ({t('tab1_elastic')})"
                if self.settings.ktp_max_tokens <= 0
                else t("tab1_capacity", used=0, max=self.settings.ktp_max_tokens, pct=0)
            ),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=PILL_SUCCESS_FG,
        )
        self.lbl_token_counter.grid(row=0, column=1, sticky="e", padx=14, pady=(8, 1))

        self.lbl_ktp_meta = ctk.CTkLabel(
            top_bar,
            text="Versi: - | Terakhir diperbarui: -",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED,
        )
        self.lbl_ktp_meta.grid(row=1, column=0, sticky="w", padx=14, pady=(1, 8))

        self.progress_token = ctk.CTkProgressBar(
            top_bar,
            width=180,
            height=9,
            progress_color=BRAND_TEAL,
            fg_color=BG_MINT_SOFT,
            corner_radius=6,
        )
        self.progress_token.set(0.0)
        self.progress_token.grid(row=1, column=1, sticky="e", padx=14, pady=(1, 8))

        self.lbl_ktp_desc = ctk.CTkLabel(
            left_card,
            text=t("tab1_desc"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_SECONDARY,
            anchor="w",
            wraplength=520,
            justify="left",
        )
        self.lbl_ktp_desc.pack(anchor="w", fill="x", padx=18, pady=(0, 6))

        self.txt_ktp = ctk.CTkTextbox(
            left_card,
            height=210,
            font=ctk.CTkFont(family="Consolas", size=13),
            fg_color=BG_SUBTLE,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color="#CBDAD3",
            corner_radius=12,
            wrap="word",
        )
        self.txt_ktp.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        self.txt_ktp.bind("<KeyRelease>", self._on_ktp_text_changed)

        btn_row = ctk.CTkFrame(left_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0, 16))

        self.btn_simpan_ktp = ctk.CTkButton(
            btn_row,
            text=t("btn_simpan_core"),
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=BRAND_TEAL,
            hover_color=BRAND_TEAL_HOVER,
            text_color="#FFFFFF",
            corner_radius=10,
            height=36,
            command=self._simpan_ktp_manual,
        )
        self.btn_simpan_ktp.pack(side="left", padx=(0, 8))

        self.btn_rollback_ktp = ctk.CTkButton(
            btn_row,
            text=t("btn_rollback"),
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=PILL_WARN_BG,
            hover_color="#FDE68A",
            text_color=PILL_WARN_FG,
            corner_radius=10,
            height=36,
            command=self._rollback_ktp_klik,
        )
        self.btn_rollback_ktp.pack(side="left")

        self.lbl_ktp_notif = ctk.CTkLabel(
            btn_row,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=PILL_SUCCESS_FG,
        )
        self.lbl_ktp_notif.pack(side="right")

        # Kolom Kanan: Snapshot Versi Sebelumnya & Panduan Mandat
        right_col = ctk.CTkFrame(grid, fg_color="transparent")
        right_col.grid(row=0, column=1, sticky="nsew")
        right_col.grid_rowconfigure(0, weight=1)
        right_col.grid_rowconfigure(1, weight=1)
        right_col.grid_columnconfigure(0, weight=1)

        snap_card = ctk.CTkFrame(
            right_col,
            fg_color=BG_CARD,
            corner_radius=16,
            border_width=1,
            border_color=BORDER_CARD,
        )
        snap_card.grid(row=0, column=0, sticky="nsew", pady=(0, 6))

        self.lbl_snap_title = ctk.CTkLabel(
            snap_card,
            text="🕒 " + t("snapshot_title"),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.lbl_snap_title.pack(anchor="w", padx=14, pady=(10, 1))

        self.lbl_snap_desc = ctk.CTkLabel(
            snap_card,
            text=t("snapshot_desc"),
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED,
            anchor="w",
            wraplength=280,
            justify="left",
        )
        self.lbl_snap_desc.pack(anchor="w", fill="x", padx=14, pady=(0, 4))

        self.txt_ktp_snapshot = ctk.CTkTextbox(
            snap_card,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=BG_MINT_SOFT,
            text_color=BRAND_DARK,
            border_width=1,
            border_color=BORDER_MINT,
            corner_radius=10,
            wrap="word",
        )
        self.txt_ktp_snapshot.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self.txt_ktp_snapshot.configure(state="disabled")
        self.lbl_ktp_snapshot = self.txt_ktp_snapshot

        guide_card = ctk.CTkFrame(
            right_col,
            fg_color=BG_CARD,
            corner_radius=16,
            border_width=1,
            border_color=BORDER_CARD,
        )
        guide_card.grid(row=1, column=0, sticky="nsew")

        self.lbl_guide_title = ctk.CTkLabel(
            guide_card,
            text="📋 " + t("mandat_title"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.lbl_guide_title.pack(anchor="w", padx=14, pady=(8, 2))

        for judul_m, ket_m in (
            (t("mandat_1_name"), t("mandat_1_desc")),
            (t("mandat_2_name"), t("mandat_2_desc")),
            (t("mandat_3_name"), t("mandat_3_desc")),
            (t("mandat_4_name"), t("mandat_4_desc")),
        ):
            m_row = ctk.CTkFrame(guide_card, fg_color=BG_SUBTLE, corner_radius=8)
            m_row.pack(fill="x", padx=10, pady=1)
            ctk.CTkLabel(
                m_row,
                text=judul_m,
                font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
                text_color=BRAND_TEAL,
                anchor="w",
            ).pack(anchor="w", padx=8, pady=(2, 0))
            ctk.CTkLabel(
                m_row,
                text=ket_m,
                font=ctk.CTkFont(size=10),
                text_color=TEXT_SECONDARY,
                anchor="w",
                wraplength=280,
                justify="left",
            ).pack(anchor="w", fill="x", padx=8, pady=(0, 2))

    def _render_tab_ktp(self, ktp_row: Any, force_editor: bool = False) -> None:
        self.lbl_ktp_judul.configure(text=f"🪪 {t('tab1_title', proyek=self.kode_proyek_aktif)}")
        if ktp_row is None:
            self.lbl_ktp_meta.configure(
                text="Belum ada Core Proyek terdaftar untuk proyek ini. Ketik di bawah atau jalankan Sleep Cycle."
            )
            if force_editor or not self._ktp_dirty:
                self.txt_ktp.delete("1.0", "end")
                self._update_live_token_counter("")
            self.txt_ktp_snapshot.configure(state="normal")
            self.txt_ktp_snapshot.delete("1.0", "end")
            self.txt_ktp_snapshot.insert("1.0", f"({t('snapshot_kosong', proyek=self.kode_proyek_aktif)})")
            self.txt_ktp_snapshot.configure(state="disabled")
            self.btn_rollback_ktp.configure(state="disabled")
            return

        versi = ktp_row["versi_ktp"]
        waktu = ktp_row["waktu_update"]
        ringkasan = ktp_row["ringkasan_inti"] or ""
        sebelumnya = ktp_row["ringkasan_sebelumnya"]

        self.lbl_ktp_meta.configure(
            text=f"Versi: v{versi}   |   Update Terakhir (UTC): {waktu}"
        )
        if force_editor or not self._ktp_dirty:
            self.txt_ktp.delete("1.0", "end")
            self.txt_ktp.insert("1.0", ringkasan)
            self._ktp_dirty = False
            self._update_live_token_counter(ringkasan)

        self.txt_ktp_snapshot.configure(state="normal")
        self.txt_ktp_snapshot.delete("1.0", "end")
        if sebelumnya:
            tok_prev = hitung_token(sebelumnya)
            self.txt_ktp_snapshot.insert("1.0", f"[{tok_prev} token]\n\n{sebelumnya}")
            self.btn_rollback_ktp.configure(state="normal")
        else:
            self.txt_ktp_snapshot.insert("1.0", f"({t('snapshot_kosong', proyek=self.kode_proyek_aktif)})")
            self.btn_rollback_ktp.configure(state="disabled")
        self.txt_ktp_snapshot.configure(state="disabled")

    def _on_ktp_text_changed(self, _event: object = None) -> None:
        self._ktp_dirty = True
        teks = self.txt_ktp.get("1.0", "end-1c")
        self._update_live_token_counter(teks)

    def _update_live_token_counter(self, teks: str) -> None:
        jml = hitung_token(teks)
        batas = self.settings.ktp_max_tokens
        if batas <= 0:
            rasio_visual = min(1.0, jml / 300.0) if jml > 0 else 0.0
            self.progress_token.set(rasio_visual)
            self.progress_token.configure(progress_color=BRAND_TEAL)
            self.lbl_token_counter.configure(
                text=f"{t('kpi_core_title')}: {jml} Token ({t('tab1_elastic')})",
                text_color=PILL_SUCCESS_FG,
            )
            return

        rasio = min(1.0, jml / max(1, batas))
        persen = int((jml / max(1, batas)) * 100)
        self.progress_token.set(rasio)

        if jml <= int(batas * 0.8):
            warna_bar = BRAND_TEAL
            warna_txt = PILL_SUCCESS_FG
            ket = t("tab1_safe")
        elif jml <= batas:
            warna_bar = "#D97706"
            warna_txt = PILL_WARN_FG
            ket = t("tab1_warning")
        else:
            warna_bar = "#DC2626"
            warna_txt = PILL_DANGER_FG
            ket = t("tab1_critical")

        self.progress_token.configure(progress_color=warna_bar)
        self.lbl_token_counter.configure(
            text=f"{t('kpi_core_title')}: {jml} / {batas} Token ({persen}% — {ket})",
            text_color=warna_txt,
        )

    def _simpan_ktp_manual(self) -> None:
        teks = self.txt_ktp.get("1.0", "end-1c").strip()
        if not teks:
            self._tampilkan_notif_ktp("⚠️ Isi KTP Proyek tidak boleh kosong.", PILL_WARN_FG)
            return
        try:
            with koneksi(self.settings.db_path) as conn:
                info = simpan_ktp_manual(conn, self.kode_proyek_aktif, teks, self.settings.ktp_max_tokens)
            self._ktp_dirty = False
            self._tampilkan_notif_ktp(
                f"✅ Tersimpan ke v{info['versi_ktp']} ({info['jumlah_token']} token)",
                PILL_SUCCESS_FG,
            )
            self.refresh_semua_data(force_editor=True)
        except Exception as exc:
            self._tampilkan_notif_ktp(f"❌ Gagal: {exc}", PILL_DANGER_FG)

    def _rollback_ktp_klik(self) -> None:
        try:
            with koneksi(self.settings.db_path) as conn:
                with transaksi(conn):
                    info = rollback_ktp(conn, self.kode_proyek_aktif)
                ekspor_memori_tim(conn, self.kode_proyek_aktif)
            self._ktp_dirty = False
            self._tampilkan_notif_ktp(
                f"⏪ Rollback berhasil ke v{info['versi_ktp']} ({info['jumlah_token']} token)",
                PILL_INFO_FG,
            )
            self.refresh_semua_data(force_editor=True)
        except Exception as exc:
            self._tampilkan_notif_ktp(f"⚠️ {exc}", PILL_WARN_FG)

    def _tampilkan_notif_ktp(self, pesan: str, warna: str) -> None:
        self.lbl_ktp_notif.configure(text=pesan, text_color=warna)
        self.after(4500, lambda: self.lbl_ktp_notif.configure(text=""))
