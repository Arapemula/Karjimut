"""Mixin Halaman 3: Catatan & Laporan (Antrean Log Mentah & Audit Metrik A/B/C) untuk GUI Karjimut."""

from __future__ import annotations

from typing import Any

import customtkinter as ctk

from ..config import (
    AKTIVITAS_READ_KTP,
    AKTIVITAS_SEARCH_SOLUSI,
    AKTIVITAS_SLEEP,
    AKTIVITAS_WRITE_LOG,
    setup_logging,
)
from ..db import koneksi
from ..mcp_server import titip_catatan_kerja
from ..services import hitung_self_assessment_proyek
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

logger = setup_logging("sleep_mcp.gui.antrean")


class AntreanTabMixin:
    """Mixin untuk Halaman 3 (Antrean Log & Audit Metrik Keberlanjutan A, B, & C)."""

    def _build_tab_antrean(self) -> None:
        cards_row = ctk.CTkFrame(self.tab_antrean, fg_color="transparent")
        cards_row.pack(fill="x", pady=(0, 8))
        cards_row.grid_columnconfigure(0, weight=1)
        cards_row.grid_columnconfigure(1, weight=1)
        cards_row.grid_columnconfigure(2, weight=1)

        # Card Metrik A
        card_a = ctk.CTkFrame(
            cards_row,
            fg_color=BG_MINT_SOFT,
            corner_radius=14,
            border_width=1,
            border_color=BORDER_MINT,
        )
        card_a.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        ctk.CTkLabel(
            card_a,
            text="📉 Metrik A: Efisiensi Context",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=BRAND_DARK,
        ).pack(anchor="w", padx=12, pady=(12, 2))

        self.lbl_metrik_a_val = ctk.CTkLabel(
            card_a,
            text="0.0%",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=PILL_SUCCESS_FG,
        )
        self.lbl_metrik_a_val.pack(anchor="w", padx=12)

        self.lbl_metrik_a_sub = ctk.CTkLabel(
            card_a,
            text="Baseline: 0 tok | Aktif: 0 tok | Target > 60%",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_SECONDARY,
        )
        self.lbl_metrik_a_sub.pack(anchor="w", padx=12, pady=(2, 12))

        # Card Metrik B
        card_b = ctk.CTkFrame(
            cards_row,
            fg_color=BG_CARD,
            corner_radius=14,
            border_width=1,
            border_color=BORDER_CARD,
        )
        card_b.grid(row=0, column=1, sticky="nsew", padx=4)

        ctk.CTkLabel(
            card_b,
            text="⚖️ Metrik B: Net Token & BEP",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_MUTED,
        ).pack(anchor="w", padx=12, pady=(12, 2))

        self.lbl_metrik_b_val = ctk.CTkLabel(
            card_b,
            text="+0 Token (0.0%)",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=BRAND_TEAL,
        )
        self.lbl_metrik_b_val.pack(anchor="w", padx=12)

        self.lbl_metrik_b_sub = ctk.CTkLabel(
            card_b,
            text="Sleep: 0 tok | Total: 0 tok | Status: -",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_SECONDARY,
        )
        self.lbl_metrik_b_sub.pack(anchor="w", padx=12, pady=(2, 12))

        # Card Metrik C
        card_c = ctk.CTkFrame(
            cards_row,
            fg_color="#F5F3FF",
            corner_radius=14,
            border_width=1,
            border_color="#DDD6FE",
        )
        card_c.grid(row=0, column=2, sticky="nsew", padx=(4, 0))

        ctk.CTkLabel(
            card_c,
            text="🧠 Metrik C: Pembelajaran Mandiri",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#6D28D9",
        ).pack(anchor="w", padx=12, pady=(12, 2))

        self.lbl_metrik_c_val = ctk.CTkLabel(
            card_c,
            text="0.0% Hit Rate",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#6D28D9",
        )
        self.lbl_metrik_c_val.pack(anchor="w", padx=12)

        self.lbl_metrik_c_sub = ctk.CTkLabel(
            card_c,
            text="Avg Conf: 0.70 | Proven: 0 | Hits: 0, Miss: 0",
            font=ctk.CTkFont(size=11),
            text_color="#5B21B6",
        )
        self.lbl_metrik_c_sub.pack(anchor="w", padx=12, pady=(2, 12))

        # Bar Input Cepat Catatan Kerja
        quick_log_bar = ctk.CTkFrame(
            self.tab_antrean,
            fg_color=BG_CARD,
            corner_radius=14,
            border_width=1,
            border_color=BORDER_CARD,
        )
        quick_log_bar.pack(fill="x", pady=(0, 8))

        self.lbl_quick_log_title = ctk.CTkLabel(
            quick_log_bar,
            text="📝 " + t("tab3_quick_note_title"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_PRIMARY,
        )
        self.lbl_quick_log_title.pack(side="left", padx=(16, 8), pady=10)

        self.entry_quick_log = ctk.CTkEntry(
            quick_log_bar,
            placeholder_text=t("tab3_quick_note_placeholder"),
            height=34,
            fg_color=BG_SUBTLE,
            border_color="#CBDAD3",
            text_color=TEXT_PRIMARY,
            corner_radius=9,
        )
        self.entry_quick_log.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=10)
        self.entry_quick_log.bind("<Return>", lambda _e: self._tambah_log_cepat())

        self.btn_masuk_antrean = ctk.CTkButton(
            quick_log_bar,
            text=t("btn_masuk_antrean"),
            width=135,
            height=34,
            corner_radius=9,
            fg_color=BRAND_TEAL,
            hover_color=BRAND_TEAL_HOVER,
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._tambah_log_cepat,
        )
        self.btn_masuk_antrean.pack(side="left", padx=(0, 14))

        split_bottom = ctk.CTkFrame(self.tab_antrean, fg_color="transparent")
        split_bottom.pack(fill="both", expand=True)
        split_bottom.grid_columnconfigure(0, weight=3)
        split_bottom.grid_columnconfigure(1, weight=2)
        split_bottom.grid_rowconfigure(0, weight=1)

        left_log = ctk.CTkFrame(
            split_bottom,
            fg_color=BG_CARD,
            corner_radius=16,
            border_width=1,
            border_color=BORDER_CARD,
        )
        left_log.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        self.lbl_antrean_header = ctk.CTkLabel(
            left_log,
            text=t("tab3_queue_title", pending=0, proc=0, done=0),
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_PRIMARY,
        )
        self.lbl_antrean_header.pack(anchor="w", padx=16, pady=(12, 6))

        self.scroll_antrean = ctk.CTkScrollableFrame(
            left_log,
            fg_color=BG_SUBTLE,
            corner_radius=12,
        )
        self.scroll_antrean.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        right_audit = ctk.CTkFrame(
            split_bottom,
            fg_color=BG_CARD,
            corner_radius=16,
            border_width=1,
            border_color=BORDER_CARD,
        )
        right_audit.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        self.lbl_audit_header = ctk.CTkLabel(
            right_audit,
            text="📊 " + t("tab3_audit_title"),
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_PRIMARY,
        )
        self.lbl_audit_header.pack(anchor="w", padx=16, pady=(12, 6))

        self.scroll_audit = ctk.CTkScrollableFrame(
            right_audit,
            fg_color=BG_SUBTLE,
            corner_radius=12,
        )
        self.scroll_audit.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _tambah_log_cepat(self) -> None:
        isi = self.entry_quick_log.get().strip()
        if not isi:
            return
        titip_catatan_kerja(self.kode_proyek_aktif, isi)
        self.entry_quick_log.delete(0, "end")
        self.refresh_semua_data(force_editor=False)

    def _render_tab_antrean(
        self,
        antrean_rows: list[dict[str, Any]],
        metrik: dict[str, Any],
        status_siklus: dict[str, Any],
        self_assessment: dict[str, Any] | None = None,
    ) -> None:
        ef_a = metrik["efisiensi_aktif_persen"]
        warna_a = PILL_SUCCESS_FG if metrik["metrik_a_tercapai"] else PILL_WARN_FG
        status_a = "TERCAPAI (>60%)" if metrik["metrik_a_tercapai"] else "PRA-TARGET"
        self.lbl_metrik_a_val.configure(text=f"{ef_a:.2f}%  [{status_a}]", text_color=warna_a)
        self.lbl_metrik_a_sub.configure(
            text=(
                f"Baseline: {metrik['t_baseline']:,} tok  |  "
                f"Aktif: {metrik['t_aktif_mcp']:,} tok"
            )
        )

        net_tok = metrik["net_savings_tokens"]
        net_pct = metrik["net_savings_persen"]
        tanda = "+" if net_tok >= 0 else ""
        warna_b = BRAND_TEAL if metrik["bep_tercapai"] else PILL_WARN_FG
        self.lbl_metrik_b_val.configure(
            text=f"{tanda}{net_tok:,} Token ({net_pct:.2f}%)",
            text_color=warna_b,
        )
        self.lbl_metrik_b_sub.configure(
            text=(
                f"Sleep: {metrik['t_sleep_llm']:,} tok  |  "
                f"Total: {metrik['t_total_mcp']:,} tok  |  {metrik['status_bep']}"
            )
        )

        if hasattr(self, "lbl_metrik_c_val"):
            try:
                sa = self_assessment
                if sa is None:
                    with koneksi(self.settings.db_path) as conn:
                        sa = hitung_self_assessment_proyek(conn, self.kode_proyek_aktif)
                hr = float(sa.get("hit_rate_persen", sa.get("hit_rate", 0.0)))
                avg_c = float(sa.get("avg_confidence", sa.get("avg_conf", 0.7)))
                warna_c = "#059669" if hr >= 70.0 else ("#6D28D9" if hr >= 40.0 else "#D97706")
                self.lbl_metrik_c_val.configure(
                    text=f"{hr:.1f}% Hit Rate",
                    text_color=warna_c,
                )
                self.lbl_metrik_c_sub.configure(
                    text=(
                        f"Avg Conf: {avg_c:.2f} | Proven: {sa.get('total_proven', 0)} | "
                        f"Hits: {sa.get('total_hit', 0)}, Miss: {sa.get('total_miss', 0)}"
                    )
                )
            except Exception as exc:
                logger.debug("Gagal memuat self-assessment metrik c: %s", exc)

        counts = status_siklus["antrean"]
        self.lbl_antrean_header.configure(
            text=t(
                "tab3_queue_title",
                pending=counts["pending"],
                proc=counts["processing"],
                done=counts["processed"],
            )
        )
        for child in self.scroll_antrean.winfo_children():
            child.destroy()

        if not antrean_rows:
            ctk.CTkLabel(
                self.scroll_antrean,
                text=t("queue_kosong"),
                text_color=TEXT_MUTED,
            ).pack(pady=24)
        else:
            for r in antrean_rows:
                st = int(r["status_rangkum"])
                if st == 0:
                    badge_st, bg_st, col_st = "⏳ PENDING", PILL_WARN_BG, PILL_WARN_FG
                elif st == 1:
                    badge_st, bg_st, col_st = "⚙️ PROCESSING", PILL_PURPLE_BG, PILL_PURPLE_FG
                else:
                    badge_st, bg_st, col_st = "✅ PROCESSED", PILL_SUCCESS_BG, PILL_SUCCESS_FG

                row_card = ctk.CTkFrame(
                    self.scroll_antrean,
                    fg_color=BG_CARD,
                    corner_radius=10,
                    border_width=1,
                    border_color=BORDER_CARD,
                )
                row_card.pack(fill="x", padx=4, pady=4)

                head = ctk.CTkFrame(row_card, fg_color="transparent")
                head.pack(fill="x", padx=10, pady=(6, 2))

                ctk.CTkLabel(
                    head,
                    text=f"Log #{r['id']}  •  ~{r['estimasi_token_mentah']} token  •  {r['waktu_masuk']}",
                    font=ctk.CTkFont(family="Consolas", size=11),
                    text_color=TEXT_MUTED,
                ).pack(side="left")

                ctk.CTkLabel(
                    head,
                    text=badge_st,
                    font=ctk.CTkFont(size=10, weight="bold"),
                    fg_color=bg_st,
                    text_color=col_st,
                    corner_radius=6,
                    padx=8,
                    pady=2,
                ).pack(side="right")

                ctk.CTkLabel(
                    row_card,
                    text=str(r["isi_log"]),
                    font=ctk.CTkFont(size=12),
                    text_color=TEXT_PRIMARY,
                    anchor="w",
                    wraplength=430,
                    justify="left",
                ).pack(anchor="w", fill="x", padx=10, pady=(2, 8))

        for child in self.scroll_audit.winfo_children():
            child.destroy()

        bd = metrik["breakdown"]
        label_map = {
            AKTIVITAS_READ_KTP: "1. " + t("mandat_1_name") + " (Mandat 1)",
            AKTIVITAS_WRITE_LOG: "2. " + t("mandat_2_name") + " (Mandat 2)",
            AKTIVITAS_SEARCH_SOLUSI: "3. " + t("mandat_3_name") + " (Mandat 3)",
            AKTIVITAS_SLEEP: "4. " + t("quick_action_title") + " (Sleep Cycle)",
        }
        for akt_key in (
            AKTIVITAS_READ_KTP,
            AKTIVITAS_WRITE_LOG,
            AKTIVITAS_SEARCH_SOLUSI,
            AKTIVITAS_SLEEP,
        ):
            label_akt = label_map[akt_key]
            info_b = bd.get(akt_key, {"count": 0, "mentah": 0, "aktual": 0})
            b_card = ctk.CTkFrame(
                self.scroll_audit,
                fg_color=BG_CARD,
                corner_radius=10,
                border_width=1,
                border_color=BORDER_CARD,
            )
            b_card.pack(fill="x", padx=4, pady=3)

            top_b = ctk.CTkFrame(b_card, fg_color="transparent")
            top_b.pack(fill="x", padx=10, pady=(5, 1))

            ctk.CTkLabel(
                top_b,
                text=label_akt,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=TEXT_PRIMARY,
                wraplength=260,
                justify="left",
            ).pack(side="left")

            ctk.CTkLabel(
                top_b,
                text=f"{info_b['count']}x",
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color=BG_MINT_SOFT,
                text_color=BRAND_DARK,
                corner_radius=6,
                padx=6,
                pady=1,
            ).pack(side="right")

            ctk.CTkLabel(
                b_card,
                text=f"Baseline: {info_b['mentah']:,} tok  |  Aktual: {info_b['aktual']:,} tok",
                font=ctk.CTkFont(family="Consolas", size=10),
                text_color=TEXT_SECONDARY,
            ).pack(anchor="w", padx=10, pady=(0, 6))
