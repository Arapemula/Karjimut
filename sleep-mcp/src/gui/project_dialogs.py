"""Mixin dialog manajemen proyek (tambah, ganti nama/gabung, hapus) untuk GUI Karjimut."""

from __future__ import annotations

import customtkinter as ctk

from ..db import daftar_proyek, koneksi, normalisasi_kode_proyek
from ..services import gabung_atau_ganti_nama_proyek, hapus_proyek, ringkasan_proyek
from .theme import (
    BG_CANVAS,
    BG_CARD,
    BG_SUBTLE,
    BORDER_CARD,
    PILL_DANGER_FG,
    PILL_SUCCESS_FG,
    PILL_WARN_FG,
    TEXT_SECONDARY,
)


class ProjectDialogsMixin:
    """Mixin yang menyediakan dialog pergantian, penggabungan, dan penghapusan proyek."""

    def _on_ganti_proyek(self, proyek_baru: str) -> None:
        try:
            self.kode_proyek_aktif = normalisasi_kode_proyek(proyek_baru)
        except ValueError:
            return
        self._ktp_dirty = False
        self._reset_form_solusi()
        self.pilih_halaman(self._halaman_aktif)
        self.refresh_semua_data(force_editor=True)

    def _dialog_proyek_baru(self) -> None:
        dialog = ctk.CTkInputDialog(
            text="Masukkan kode/nama proyek baru (contoh: toko-online):",
            title="Tambah / Pilih Proyek Baru",
        )
        input_nama = dialog.get_input()
        if not input_nama:
            return
        try:
            kode = normalisasi_kode_proyek(input_nama)
        except ValueError:
            return
        if kode not in self.daftar_proyek_tersedia:
            self.daftar_proyek_tersedia.insert(0, kode)
            self.opt_proyek.configure(values=self.daftar_proyek_tersedia)
        self.opt_proyek.set(kode)
        self._on_ganti_proyek(kode)

    def _dialog_ganti_nama_proyek(self) -> None:
        asal = self.kode_proyek_aktif
        dialog = ctk.CTkInputDialog(
            text=(
                f"Ganti nama atau gabungkan proyek '{asal}' ke kode proyek tujuan:\n"
                "(Alias otomatis didaftarkan agar nama folder lama tetap terhubung)"
            ),
            title=f"Ganti Nama / Gabung Proyek: {asal}",
        )
        input_tujuan = dialog.get_input()
        if not input_tujuan:
            return
        try:
            with koneksi(self.settings.db_path) as conn:
                hasil = gabung_atau_ganti_nama_proyek(conn, asal, input_tujuan)
        except (ValueError, RuntimeError) as exc:
            self.lbl_footer.configure(text=f"⚠️ Gagal ganti nama proyek: {exc}", text_color=PILL_DANGER_FG)
            return

        tujuan = hasil["kode_tujuan"]
        self.daftar_proyek_tersedia = [p for p in self.daftar_proyek_tersedia if p != asal]
        if tujuan not in self.daftar_proyek_tersedia:
            self.daftar_proyek_tersedia.insert(0, tujuan)
        self.opt_proyek.configure(values=self.daftar_proyek_tersedia)
        self.opt_proyek.set(tujuan)
        self.kode_proyek_aktif = tujuan
        self._ktp_dirty = False
        self._last_data_signature = None
        self.pilih_halaman(self._halaman_aktif)
        self.lbl_footer.configure(
            text=f"✅ Proyek '{asal}' berhasil dialihkan/digabung ke '{tujuan}' (alias aktif).",
            text_color=PILL_SUCCESS_FG,
        )
        self.refresh_semua_data(force_editor=True)

    def _dialog_hapus_proyek(self) -> None:
        kode = self.kode_proyek_aktif
        with koneksi(self.settings.db_path) as conn:
            info = ringkasan_proyek(conn, kode)

        win = ctk.CTkToplevel(self)
        win.title(f"Konfirmasi Hapus Proyek: {kode}")
        win.geometry("480x270")
        win.resizable(False, False)
        win.configure(fg_color=BG_CANVAS)
        win.transient(self)
        win.grab_set()

        box = ctk.CTkFrame(
            win,
            fg_color=BG_CARD,
            corner_radius=14,
            border_width=1,
            border_color="#FCA5A5",
        )
        box.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            box,
            text=f"🗑️ Hapus Proyek '{kode}'?",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=PILL_DANGER_FG,
        ).pack(anchor="w", padx=18, pady=(16, 6))

        ctk.CTkLabel(
            box,
            text=(
                f"Seluruh memori proyek '{kode}' akan dihapus permanen:\n"
                f"• Core Proyek: {'Ada' if info['ada_ktp'] else 'Kosong'}   |   "
                f"• Bank Solusi: {info['jumlah_solusi']} entri\n"
                f"• Catatan Kerja: {info['jumlah_log']} catatan   |   "
                f"• Riwayat Metrik: {info['jumlah_metrik']} baris"
            ),
            font=ctk.CTkFont(size=12),
            text_color=TEXT_SECONDARY,
            justify="left",
        ).pack(anchor="w", padx=18, pady=(0, 16))

        btn_row = ctk.CTkFrame(box, fg_color="transparent")
        btn_row.pack(fill="x", side="bottom", padx=18, pady=(0, 16))

        ctk.CTkButton(
            btn_row,
            text="Batal",
            fg_color=BG_SUBTLE,
            hover_color="#E2ECE8",
            text_color=TEXT_SECONDARY,
            border_width=1,
            border_color=BORDER_CARD,
            width=100,
            height=36,
            corner_radius=9,
            command=win.destroy,
        ).pack(side="left")

        def _eksekusi_hapus() -> None:
            try:
                with koneksi(self.settings.db_path) as conn:
                    hapus_proyek(conn, kode)
                    proyek_sisa = daftar_proyek(conn)
            except (ValueError, RuntimeError) as exc:
                win.destroy()
                self.lbl_footer.configure(text=f"⚠️ Gagal hapus proyek: {exc}", text_color=PILL_DANGER_FG)
                return
            win.destroy()
            if not proyek_sisa:
                proyek_sisa = ["default"]
            self.daftar_proyek_tersedia = proyek_sisa
            self.kode_proyek_aktif = proyek_sisa[0]
            self.opt_proyek.configure(values=self.daftar_proyek_tersedia)
            self.opt_proyek.set(self.kode_proyek_aktif)
            self._ktp_dirty = False
            self._last_data_signature = None
            self.pilih_halaman(self._halaman_aktif)
            self.lbl_footer.configure(
                text=f"🗑️ Proyek '{kode}' telah dihapus.",
                text_color=PILL_WARN_FG,
            )
            self.refresh_semua_data(force_editor=True)

        ctk.CTkButton(
            btn_row,
            text="🗑️ Ya, Hapus Permanen",
            fg_color="#DC2626",
            hover_color="#B91C1C",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=190,
            height=36,
            corner_radius=9,
            command=_eksekusi_hapus,
        ).pack(side="right")
