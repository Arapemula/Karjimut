"""Mixin Halaman 2: Bank Solusi / Laci Arsip Solusi (Lapis 2) untuk GUI Karjimut."""

from __future__ import annotations

from typing import Any

import customtkinter as ctk

from ..config import setup_logging
from ..db import koneksi
from ..services import hapus_solusi, perbarui_solusi, tambah_solusi
from .i18n import t
from .theme import (
    BG_CARD,
    BG_LIME_SOFT,
    BG_MINT_SOFT,
    BG_SUBTLE,
    BORDER_CARD,
    BRAND_DARK,
    BRAND_TEAL,
    BRAND_TEAL_HOVER,
    PILL_DANGER_BG,
    PILL_DANGER_FG,
    PILL_SUCCESS_FG,
    PILL_WARN_FG,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

logger = setup_logging("sleep_mcp.gui.solusi")


class SolusiTabMixin:
    """Mixin untuk Halaman 2 (Laci Arsip Solusi / Lapis 2): pencarian BM25+Vector, CRUD, & feedback loop."""

    def _build_tab_solusi(self) -> None:
        search_bar = ctk.CTkFrame(
            self.tab_solusi,
            fg_color=BG_CARD,
            corner_radius=14,
            border_width=1,
            border_color=BORDER_CARD,
        )
        search_bar.pack(fill="x", pady=(0, 8))

        self.lbl_search_title = ctk.CTkLabel(
            search_bar,
            text="🔍 " + t("tab2_search_title"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.lbl_search_title.pack(side="left", padx=(14, 8), pady=10)

        self.entry_search_solusi = ctk.CTkEntry(
            search_bar,
            placeholder_text=t("tab2_search_placeholder"),
            height=34,
            fg_color=BG_SUBTLE,
            border_color="#CBDAD3",
            text_color=TEXT_PRIMARY,
            corner_radius=9,
            font=ctk.CTkFont(size=12),
        )
        self.entry_search_solusi.pack(side="left", fill="x", expand=True, padx=(0, 6), pady=10)
        self.entry_search_solusi.bind("<Return>", lambda _e: self._cari_solusi_klik())
        self.entry_search_solusi.bind("<KeyRelease>", self._on_search_key_release)

        self.btn_cari_bm25 = ctk.CTkButton(
            search_bar,
            text=t("btn_cari_bm25"),
            width=92,
            height=34,
            corner_radius=9,
            fg_color=BRAND_TEAL,
            hover_color=BRAND_TEAL_HOVER,
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._cari_solusi_klik,
        )
        self.btn_cari_bm25.pack(side="left", padx=(0, 4))

        self.btn_semua_solusi = ctk.CTkButton(
            search_bar,
            text=t("btn_semua_solusi"),
            width=64,
            height=34,
            corner_radius=9,
            fg_color=BG_MINT_SOFT,
            hover_color="#CBE8D4",
            text_color=BRAND_DARK,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._reset_cari_solusi,
        )
        self.btn_semua_solusi.pack(side="left", padx=(0, 8))

        self.opt_sort_solusi = ctk.CTkOptionMenu(
            search_bar,
            values=["Terbaru (ID ↓)", "Terlama (ID ↑)", "Akurasi (Conf ↓)"],
            width=128,
            height=34,
            corner_radius=9,
            fg_color=BG_SUBTLE,
            text_color=TEXT_PRIMARY,
            button_color=BRAND_TEAL,
            button_hover_color=BRAND_TEAL_HOVER,
            dropdown_fg_color=BG_CARD,
            dropdown_text_color=TEXT_PRIMARY,
            dropdown_hover_color=BG_MINT_SOFT,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._on_change_sort_solusi,
        )
        self.opt_sort_solusi.set("Terbaru (ID ↓)")
        self.opt_sort_solusi.pack(side="left", padx=(0, 12))

        body = ctk.CTkFrame(self.tab_solusi, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=5)
        body.grid_columnconfigure(1, weight=3)
        body.grid_rowconfigure(0, weight=1)

        list_panel = ctk.CTkFrame(
            body,
            fg_color=BG_CARD,
            corner_radius=16,
            border_width=1,
            border_color=BORDER_CARD,
        )
        list_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        list_header_row = ctk.CTkFrame(list_panel, fg_color="transparent")
        list_header_row.pack(fill="x", padx=14, pady=(12, 6))

        self.lbl_solusi_count = ctk.CTkLabel(
            list_header_row,
            text=t("tab2_list_title", proyek=self.kode_proyek_aktif, count=0),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.lbl_solusi_count.pack(side="left")

        self.lbl_solusi_sort_hint = ctk.CTkLabel(
            list_header_row,
            text="• Nomor urut 1..N",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self.lbl_solusi_sort_hint.pack(side="left", padx=(8, 0))

        self.scroll_solusi = ctk.CTkScrollableFrame(
            list_panel,
            fg_color=BG_SUBTLE,
            corner_radius=12,
        )
        self.scroll_solusi.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        form_panel = ctk.CTkFrame(
            body,
            fg_color=BG_CARD,
            corner_radius=16,
            border_width=1,
            border_color=BORDER_CARD,
        )
        form_panel.grid(row=0, column=1, sticky="nsew")

        self.lbl_form_solusi_title = ctk.CTkLabel(
            form_panel,
            text=t("tab2_form_add_title"),
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=TEXT_PRIMARY,
        )
        self.lbl_form_solusi_title.pack(anchor="w", padx=18, pady=(16, 4))

        self.lbl_solusi_tags_label = ctk.CTkLabel(
            form_panel,
            text=t("tab2_tag_label"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_SECONDARY,
        )
        self.lbl_solusi_tags_label.pack(anchor="w", padx=18, pady=(8, 4))

        self.entry_solusi_tags = ctk.CTkEntry(
            form_panel,
            placeholder_text=t("tab2_tag_placeholder"),
            height=38,
            fg_color=BG_SUBTLE,
            border_color="#CBDAD3",
            text_color=TEXT_PRIMARY,
            corner_radius=10,
            font=ctk.CTkFont(family="Consolas", size=12),
        )
        self.entry_solusi_tags.pack(fill="x", padx=18, pady=(0, 10))

        self.lbl_solusi_isi_label = ctk.CTkLabel(
            form_panel,
            text=t("tab2_solusi_label"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_SECONDARY,
        )
        self.lbl_solusi_isi_label.pack(anchor="w", padx=18, pady=(2, 4))

        self.txt_solusi_isi = ctk.CTkTextbox(
            form_panel,
            height=135,
            fg_color=BG_SUBTLE,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color="#CBDAD3",
            corner_radius=10,
            font=ctk.CTkFont(size=13),
            wrap="word",
        )
        self.txt_solusi_isi.pack(fill="x", padx=18, pady=(0, 14))

        form_btn_row = ctk.CTkFrame(form_panel, fg_color="transparent")
        form_btn_row.pack(fill="x", padx=18, pady=(0, 8))

        self.btn_simpan_solusi = ctk.CTkButton(
            form_btn_row,
            text=t("btn_simpan_ke_bank"),
            fg_color=BRAND_TEAL,
            hover_color=BRAND_TEAL_HOVER,
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=10,
            height=38,
            command=self._simpan_solusi_form,
        )
        self.btn_simpan_solusi.pack(side="left", fill="x", expand=True)

        self.btn_batal_edit_solusi = ctk.CTkButton(
            form_btn_row,
            text=t("btn_batal_edit"),
            width=72,
            height=38,
            corner_radius=10,
            fg_color=BG_SUBTLE,
            hover_color="#E2ECE8",
            text_color=TEXT_SECONDARY,
            border_width=1,
            border_color=BORDER_CARD,
            command=self._reset_form_solusi,
        )

        self.lbl_solusi_notif = ctk.CTkLabel(
            form_panel,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=PILL_SUCCESS_FG,
            wraplength=320,
        )
        self.lbl_solusi_notif.pack(anchor="w", padx=18, pady=(4, 8))

    def _on_search_key_release(self, _event: object = None) -> None:
        q = self.entry_search_solusi.get().strip()
        if q != self._search_query_aktif:
            self._search_query_aktif = q
            self.refresh_semua_data(force_editor=False)

    def _cari_solusi_klik(self) -> None:
        self._search_query_aktif = self.entry_search_solusi.get().strip()
        self.refresh_semua_data(force_editor=False)

    def _reset_cari_solusi(self) -> None:
        self.entry_search_solusi.delete(0, "end")
        self._search_query_aktif = ""
        self.refresh_semua_data(force_editor=False)

    def _render_tab_solusi(self, solusi_rows: list[dict[str, Any]]) -> None:
        for child in self.scroll_solusi.winfo_children():
            child.destroy()

        if self._search_query_aktif:
            self.lbl_solusi_count.configure(
                text=f"🔍 Hasil Pencarian BM25 '{self._search_query_aktif}': {len(solusi_rows)} solusi ditemukan",
                text_color=BRAND_TEAL,
            )
        else:
            self.lbl_solusi_count.configure(
                text=f"🗄️ {t('tab2_list_title', proyek=self.kode_proyek_aktif, count=len(solusi_rows))}",
                text_color=TEXT_PRIMARY,
            )

        if not solusi_rows:
            ctk.CTkLabel(
                self.scroll_solusi,
                text=t("solusi_kosong", proyek=self.kode_proyek_aktif),
                font=ctk.CTkFont(size=13),
                text_color=TEXT_MUTED,
            ).pack(pady=30)
            return

        for idx, item in enumerate(solusi_rows):
            card = ctk.CTkFrame(
                self.scroll_solusi,
                fg_color=BG_CARD,
                corner_radius=12,
                border_width=1,
                border_color=BORDER_CARD,
            )
            card.pack(fill="x", padx=4, pady=5)

            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=12, pady=(10, 4))

            ctk.CTkLabel(
                top,
                text=f"#{idx + 1} • Solusi #{item['id']}",
                font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
                fg_color=BG_MINT_SOFT,
                text_color=BRAND_DARK,
                corner_radius=6,
                padx=8,
                pady=2,
                anchor="w",
            ).pack(side="left")

            conf_val = item.get("confidence")
            if conf_val is not None:
                c_float = float(conf_val)
                bg_c = "#D1FAE5" if c_float >= 0.85 else ("#EDE9FE" if c_float >= 0.65 else "#FEE2E2")
                fg_c = "#065F46" if c_float >= 0.85 else ("#6D28D9" if c_float >= 0.65 else "#991B1B")
                ctk.CTkLabel(
                    top,
                    text=f"Conf: {c_float:.2f}",
                    font=ctk.CTkFont(size=10, weight="bold"),
                    fg_color=bg_c,
                    text_color=fg_c,
                    corner_radius=6,
                    padx=6,
                    pady=2,
                    anchor="w",
                ).pack(side="left", padx=(6, 0))

            if item.get("skor_rrf") is not None:
                ctk.CTkLabel(
                    top,
                    text=f"RRF: {item['skor_rrf']}",
                    font=ctk.CTkFont(size=10, weight="bold"),
                    fg_color="#E0E7FF",
                    text_color="#3730A3",
                    corner_radius=6,
                    padx=6,
                    pady=2,
                    anchor="w",
                ).pack(side="left", padx=(6, 0))
            elif item.get("skor_bm25") is not None:
                ctk.CTkLabel(
                    top,
                    text=f"BM25: {item['skor_bm25']}",
                    font=ctk.CTkFont(size=10, weight="bold"),
                    fg_color=BG_LIME_SOFT,
                    text_color=PILL_SUCCESS_FG,
                    corner_radius=6,
                    padx=6,
                    pady=2,
                    anchor="w",
                ).pack(side="left", padx=(6, 0))

            btn_del = ctk.CTkButton(
                top,
                text="🗑️ Hapus",
                width=62,
                height=26,
                corner_radius=7,
                fg_color=PILL_DANGER_BG,
                hover_color="#FECACA",
                text_color=PILL_DANGER_FG,
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda sid=item["id"]: self._hapus_solusi(int(sid)),
            )
            btn_del.pack(side="right", padx=(4, 0))

            btn_edit = ctk.CTkButton(
                top,
                text="✏️ Edit",
                width=58,
                height=26,
                corner_radius=7,
                fg_color=BG_SUBTLE,
                hover_color="#E2ECE8",
                text_color=TEXT_SECONDARY,
                border_width=1,
                border_color=BORDER_CARD,
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda it=item: self._mulai_edit_solusi(it),
            )
            btn_edit.pack(side="right", padx=(4, 0))

            ctk.CTkLabel(
                card,
                text=item["tag_masalah"],
                font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
                text_color=BRAND_TEAL,
                anchor="w",
                justify="left",
                wraplength=480,
            ).pack(anchor="w", fill="x", padx=12, pady=(2, 4))

            ctk.CTkLabel(
                card,
                text=item["solusi_paten"],
                font=ctk.CTkFont(size=12),
                text_color=TEXT_PRIMARY,
                anchor="w",
                justify="left",
                wraplength=480,
            ).pack(anchor="w", fill="x", padx=12, pady=(0, 8))

            bottom = ctk.CTkFrame(card, fg_color="transparent")
            bottom.pack(fill="x", padx=12, pady=(0, 8))

            h = item.get("hit_count", 0)
            m = item.get("miss_count", 0)
            ctk.CTkLabel(
                bottom,
                text=f"🎯 Hits: {h} | Miss: {m}",
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color=BG_MINT_SOFT,
                text_color=BRAND_DARK,
                corner_radius=6,
                padx=6,
                pady=2,
                anchor="w",
            ).pack(side="left")

            if item.get("superseded_by_id"):
                ctk.CTkLabel(
                    bottom,
                    text=f"🔄 Digantikan #{item['superseded_by_id']}",
                    font=ctk.CTkFont(size=10, weight="bold"),
                    fg_color="#FEF3C7",
                    text_color="#92400E",
                    corner_radius=6,
                    padx=6,
                    pady=2,
                    anchor="w",
                ).pack(side="left", padx=(6, 0))

            if item.get("supersedes_id"):
                ctk.CTkLabel(
                    bottom,
                    text=f"⭐ Menggantikan #{item['supersedes_id']}",
                    font=ctk.CTkFont(size=10, weight="bold"),
                    fg_color="#E0E7FF",
                    text_color="#3730A3",
                    corner_radius=6,
                    padx=6,
                    pady=2,
                    anchor="w",
                ).pack(side="left", padx=(6, 0))

            if item.get("is_stale"):
                ctk.CTkLabel(
                    bottom,
                    text="⚠️ Stale",
                    font=ctk.CTkFont(size=10, weight="bold"),
                    fg_color="#FEF3C7",
                    text_color="#92400E",
                    corner_radius=6,
                    padx=6,
                    pady=2,
                    anchor="w",
                ).pack(side="left", padx=(6, 0))

            btn_punish = ctk.CTkButton(
                bottom,
                text="👎 -0.15",
                width=56,
                height=24,
                corner_radius=6,
                fg_color="#FEE2E2",
                hover_color="#FECACA",
                text_color="#991B1B",
                font=ctk.CTkFont(size=10, weight="bold"),
                command=lambda sid=item["id"]: self._beri_nilai_solusi(int(sid), False),
            )
            btn_punish.pack(side="right", padx=(2, 0))

            btn_reward = ctk.CTkButton(
                bottom,
                text="👍 +0.10",
                width=56,
                height=24,
                corner_radius=6,
                fg_color=BG_MINT_SOFT,
                hover_color="#A7F3D0",
                text_color="#065F46",
                font=ctk.CTkFont(size=10, weight="bold"),
                command=lambda sid=item["id"]: self._beri_nilai_solusi(int(sid), True),
            )
            btn_reward.pack(side="right", padx=(2, 0))

    def _on_change_sort_solusi(self, pilihan: str) -> None:
        if "Terlama" in pilihan:
            self._solusi_sort_mode = "id_asc"
            self.lbl_solusi_sort_hint.configure(text="• Nomor urut 1..N (Terlama di atas)")
        elif "Akurasi" in pilihan:
            self._solusi_sort_mode = "conf_desc"
            self.lbl_solusi_sort_hint.configure(text="• Nomor urut 1..N (Akurasi tertinggi)")
        else:
            self._solusi_sort_mode = "id_desc"
            self.lbl_solusi_sort_hint.configure(text="• Nomor urut 1..N (Terbaru di atas)")
        self.refresh_semua_data(force_editor=False)

    def _mulai_edit_solusi(self, item: dict[str, Any]) -> None:
        self._solusi_edit_id = int(item["id"])
        self.lbl_form_solusi_title.configure(
            text=t("tab2_form_edit_title", id=self._solusi_edit_id),
            text_color=BRAND_TEAL,
        )
        self.entry_solusi_tags.delete(0, "end")
        self.entry_solusi_tags.insert(0, item.get("tag_masalah", ""))
        self.txt_solusi_isi.delete("1.0", "end")
        self.txt_solusi_isi.insert("1.0", item.get("solusi_paten", ""))
        self.btn_simpan_solusi.configure(text=t("btn_update_ke_bank"))
        self.btn_batal_edit_solusi.pack(side="left", padx=(8, 0))

    def _reset_form_solusi(self) -> None:
        self._solusi_edit_id = None
        self.lbl_form_solusi_title.configure(
            text=t("tab2_form_add_title"),
            text_color=TEXT_PRIMARY,
        )
        self.entry_solusi_tags.delete(0, "end")
        self.txt_solusi_isi.delete("1.0", "end")
        self.btn_simpan_solusi.configure(text=t("btn_simpan_ke_bank"))
        self.btn_batal_edit_solusi.pack_forget()

    def _simpan_solusi_form(self) -> None:
        raw_tags = self.entry_solusi_tags.get().strip()
        raw_solusi = self.txt_solusi_isi.get("1.0", "end-1c").strip()
        try:
            with koneksi(self.settings.db_path) as conn:
                if self._solusi_edit_id is not None:
                    perbarui_solusi(conn, self.kode_proyek_aktif, self._solusi_edit_id, raw_tags, raw_solusi)
                    pesan = f"✅ Solusi #{self._solusi_edit_id} berhasil diperbarui."
                else:
                    tambah_solusi(conn, self.kode_proyek_aktif, raw_tags, raw_solusi)
                    pesan = "✅ Solusi baru berhasil ditambahkan ke Laci Arsip."
        except (ValueError, LookupError) as exc:
            self.lbl_solusi_notif.configure(text=f"⚠️ {exc}", text_color=PILL_WARN_FG)
            return

        self._reset_form_solusi()
        self.lbl_solusi_notif.configure(text=pesan, text_color=PILL_SUCCESS_FG)
        self.after(4000, lambda: self.lbl_solusi_notif.configure(text=""))
        self.refresh_semua_data(force_editor=False)

    def _hapus_solusi(self, solusi_id: int) -> None:
        try:
            with koneksi(self.settings.db_path) as conn:
                hapus_solusi(conn, self.kode_proyek_aktif, solusi_id)
        except LookupError:
            pass
        if self._solusi_edit_id == solusi_id:
            self._reset_form_solusi()
        self.refresh_semua_data(force_editor=False)

    def _beri_nilai_solusi(self, solusi_id: int, berhasil: bool) -> None:
        """Feedback loop handler dari antarmuka GUI untuk memberi reward/punishment."""
        from ..mcp_server import nilai_solusi
        try:
            nilai_solusi(
                self.kode_proyek_aktif,
                solusi_id,
                berhasil=berhasil,
                catatan="Evaluasi mandiri via antarmuka GUI",
            )
            self.lbl_solusi_notif.configure(
                text="👍 Reward (+0.10) berhasil dicatat!" if berhasil else "👎 Punishment (-0.15) berhasil dicatat!",
                text_color=PILL_SUCCESS_FG if berhasil else PILL_DANGER_FG,
            )
            self.after(3500, lambda: self.lbl_solusi_notif.configure(text=""))
        except Exception as exc:
            logger.warning("Gagal memberikan nilai solusi: %s", exc)
        self.refresh_semua_data(force_editor=False)
