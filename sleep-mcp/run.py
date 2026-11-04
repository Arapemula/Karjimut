"""Launcher & Auto-Setup Terpadu Karjimut (One-Step Runner).

Memungkinkan pengguna menjalankan seluruh komponen Karjimut tanpa setup manual:
  karjimut / python run.py            -> Langsung meluncurkan Aplikasi Desktop Native (CustomTkinter)
  karjimut gui                        -> Langsung meluncurkan Aplikasi Desktop Native (CustomTkinter)
  karjimut menu                       -> Menu interaktif terminal (pilih 1-5)
  karjimut test                       -> Jalankan seluruh Unit & Integration Test (pytest)
  karjimut benchmark                  -> Jalankan Simulasi Benchmark Efisiensi & Retensi Token
  karjimut mcp                        -> Jalankan FastMCP Server (stdio) + Embedded Idle Watcher
  karjimut setup-ide                  -> Tampilkan / pasang otomatis konfigurasi MCP & Bootstrap Rules
  karjimut build-exe                  -> Kemas Karjimut menjadi aplikasi mandiri Karjimut.exe (PyInstaller)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Amankan stdout/stderr jika diluncurkan melalui pythonw.exe atau .exe windowed (tanpa console)
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115

IS_FROZEN = bool(getattr(sys, "frozen", False))
_HERE = Path(__file__).resolve().parent
PACKAGE_DIR = _HERE if (_HERE / "config.py").exists() else (_HERE / "src")
IS_INSTALLED_PACKAGE = any(
    p.lower() in ("site-packages", "dist-packages") for p in PACKAGE_DIR.parts
)


def _tentukan_root_dir() -> Path:
    if IS_FROZEN:
        exe_dir = Path(sys.executable).resolve().parent
        if (exe_dir / ".env").exists() or (exe_dir / "data").exists():
            return exe_dir
        if (exe_dir.parent / ".env").exists() or (exe_dir.parent / "data").exists():
            return exe_dir.parent
        return exe_dir
    if IS_INSTALLED_PACKAGE:
        user_dir = Path.home() / ".karjimut"
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir
    return PACKAGE_DIR.parent


ROOT_DIR = _tentukan_root_dir()
if not IS_FROZEN:
    parent_pkg = str(PACKAGE_DIR.parent)
    if parent_pkg not in sys.path:
        sys.path.insert(0, parent_pkg)

ENV_FILE = ROOT_DIR / ".env"
ENV_EXAMPLE = (
    ROOT_DIR / ".env.example"
    if (ROOT_DIR / ".env.example").exists()
    else PACKAGE_DIR / ".env.example"
)
RULES_TEMPLATE_DIR = (
    ROOT_DIR / "rules_template"
    if (ROOT_DIR / "rules_template").exists()
    else PACKAGE_DIR / "rules_template"
)
DB_FILE = ROOT_DIR / "data" / "sleep_mcp.db"

REQUIRED_MODULES = ("mcp", "tiktoken", "dotenv", "httpx", "customtkinter")


def _get_console_python() -> str:
    """Mengembalikan path python.exe (bukan pythonw.exe) untuk subprocess CLI/MCP stdio."""
    exe = Path(sys.executable).resolve()
    if exe.name.lower() == "pythonw.exe":
        kandidat = exe.with_name("python.exe")
        if kandidat.exists():
            return str(kandidat)
    return str(exe)


def _tulis_jika_berubah(target: Path, konten: str) -> bool:
    """Menulis file hanya jika belum ada atau isinya berubah (mencegah disk I/O berulang)."""
    try:
        if target.exists() and target.read_text(encoding="utf-8", errors="ignore") == konten:
            return False
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(konten, encoding="utf-8")
        return True
    except Exception:
        return False


def pasang_aturan_otomatis_global(verbose: bool = False, pasang_global: bool = False) -> None:
    """Memasang aturan Tiga Mandat Otomatis (Zero-Prompt Vibecoder) di workspace (dan global hanya saat setup-ide)."""
    rule_md_src = RULES_TEMPLATE_DIR / "antigravity_rules.md"
    cursor_src = RULES_TEMPLATE_DIR / ".cursorrules"
    if not rule_md_src.exists():
        return

    isi_rule = rule_md_src.read_text(encoding="utf-8")
    isi_gemini_md = isi_rule
    if isi_gemini_md.startswith("---"):
        bagian = isi_gemini_md.split("---", 2)
        if len(bagian) == 3:
            isi_gemini_md = bagian[2].lstrip()

    # 1. Pasang Global Rule di ~/.gemini hanya saat opt-in eksplisit (setup-ide)
    if pasang_global:
        try:
            gemini_home = Path.home() / ".gemini"
            if gemini_home.exists():
                global_rule_file = gemini_home / "config" / "rules" / "sleep-mcp-auto.md"
                _tulis_jika_berubah(global_rule_file, isi_rule)

                global_gemini_md = gemini_home / "GEMINI.md"
                if not global_gemini_md.exists() or "Sleep-MCP" not in global_gemini_md.read_text(encoding="utf-8", errors="ignore"):
                    existing = global_gemini_md.read_text(encoding="utf-8", errors="ignore").strip() if global_gemini_md.exists() else ""
                    gabungan = (existing + "\n\n" + isi_gemini_md).strip() + "\n" if existing else isi_gemini_md
                    _tulis_jika_berubah(global_gemini_md, gabungan)

                if verbose:
                    print(f"[Auto-Rule] Global Rule Antigravity terpasang di: {global_rule_file}")
                    print(f"[Auto-Rule] Global GEMINI.md terpasang di: {global_gemini_md}")
        except Exception as exc:
            if verbose:
                print(f"[Auto-Rule] Peringatan saat memasang global rule: {exc}")

    # 2. Pasang di root workspace proyek saat ini jika berjalan dari local checkout (bukan ~/.karjimut)
    if not IS_INSTALLED_PACKAGE:
        try:
            workspace_root = ROOT_DIR.parent
            _tulis_jika_berubah(workspace_root / "GEMINI.md", isi_gemini_md)
            if cursor_src.exists():
                isi_cursor = cursor_src.read_text(encoding="utf-8")
                _tulis_jika_berubah(workspace_root / ".cursorrules", isi_cursor)
            _tulis_jika_berubah(workspace_root / ".agents" / "rules" / "sleep-mcp-auto.md", isi_rule)
        except Exception:
            pass


def pastikan_lingkungan_siap(auto_install: bool = True, fast_boot: bool = False) -> None:
    """Memastikan file .env, dependensi Python, database SQLite, dan aturan otomatis siap."""
    # 1. Buat .env otomatis dari .env.example jika belum ada
    if not ENV_FILE.exists() and ENV_EXAMPLE.exists():
        ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ENV_EXAMPLE, ENV_FILE)
        if not fast_boot:
            print("[Auto-Setup] File konfigurasi '.env' otomatis dibuat dari '.env.example'.")

    # 2. Periksa paket Python wajib (dilewati saat fast_boot MCP stdio, mode installed package, atau .exe frozen)
    if not fast_boot and not IS_FROZEN and not IS_INSTALLED_PACKAGE:
        paket_kurang = [m for m in REQUIRED_MODULES if importlib.util.find_spec(m) is None]
        req_file = ROOT_DIR / "requirements.txt"
        if paket_kurang and auto_install and req_file.exists():
            print(f"[Auto-Setup] Menginstal dependensi yang belum ada ({', '.join(paket_kurang)})...")
            py_cmd = _get_console_python()
            in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix) or bool(os.environ.get("VIRTUAL_ENV"))
            pip_args = [py_cmd, "-m", "pip", "install"]
            if not in_venv:
                pip_args.append("--user")
            pip_args.extend(["-r", str(req_file)])
            subprocess.check_call(pip_args)

    # 3. Pastikan database terinisialisasi bersih (tanpa mencemari DB produksi dengan data dummy benchmark)
    if not DB_FILE.exists():
        DB_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            from .db import init_db
        except ImportError:
            from src.db import init_db

        init_db(str(DB_FILE))
        if not fast_boot:
            print(f"[Auto-Setup] Database bersih '{DB_FILE.relative_to(ROOT_DIR)}' berhasil diinisialisasi.")

    # 4. Pasang aturan otomatis workspace (dilewati saat fast_boot MCP stdio)
    if not fast_boot:
        pasang_aturan_otomatis_global(verbose=False, pasang_global=False)


def jalankan_desktop_gui() -> None:
    """Meluncurkan Aplikasi Desktop Native Karjimut berbasis CustomTkinter."""
    pastikan_lingkungan_siap()
    try:
        from .gui.app_gui import start_desktop_app
    except ImportError:
        from src.gui.app_gui import start_desktop_app

    start_desktop_app()


def jalankan_unit_test() -> int:
    """Menjalankan seluruh suite pengujian pytest."""
    pastikan_lingkungan_siap()
    print("\n[Karjimut] Menjalankan Unit & Integration Test...\n")
    return subprocess.call(
        [_get_console_python(), "-m", "pytest", "tests/test_unit_core.py", "tests/test_v2_features.py", "-v"],
        cwd=str(ROOT_DIR),
    )


def jalankan_simulasi_skenario() -> int:
    """Menjalankan simulasi benchmark efisiensi token & retensi aturan di database terisolasi."""
    pastikan_lingkungan_siap()
    print("\n[Karjimut] Menjalankan Simulasi Benchmark Efisiensi & Retensi Token...\n")
    return subprocess.call([_get_console_python(), "tests/benchmark.py"], cwd=str(ROOT_DIR))


def jalankan_mcp_server() -> None:
    """Menjalankan FastMCP server (stdio) beserta Embedded Idle Watcher."""
    pastikan_lingkungan_siap(auto_install=False, fast_boot=True)
    os.environ.setdefault("SLEEP_MCP_EMBEDDED_WATCHER", "true")
    try:
        from .mcp_server import start_server
    except ImportError:
        from src.mcp_server import start_server

    start_server(transport="stdio")


def build_standalone_exe() -> int:
    """Mengemas Karjimut menjadi file mandiri Karjimut.exe menggunakan PyInstaller."""
    if IS_FROZEN:
        print("[Build-EXE] Aplikasi sudah berjalan dalam mode .exe mandiri.")
        return 0

    py = _get_console_python()
    if importlib.util.find_spec("PyInstaller") is None:
        print("[Build-EXE] Menginstal PyInstaller...")
        subprocess.check_call([py, "-m", "pip", "install", "pyinstaller>=6.0.0"])

    print("\n" + "=" * 72)
    print("  MEMBANGUN APLIKASI DESKTOP MANDIRI: Karjimut.exe (PyInstaller)")
    print("=" * 72)
    cmd = [
        py,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        "Karjimut",
        "--collect-all",
        "customtkinter",
        "--collect-all",
        "tiktoken",
        "--collect-submodules",
        "mcp",
        "run.py",
    ]
    rc = subprocess.call(cmd, cwd=str(ROOT_DIR))
    dist_exe = ROOT_DIR / "dist" / "Karjimut.exe"
    root_exe = ROOT_DIR / "Karjimut.exe"
    if rc == 0 and dist_exe.exists():
        try:
            shutil.copyfile(dist_exe, root_exe)
            print(f"\n[Berhasil] Aplikasi mandiri siap digunakan di:\n  1. {root_exe}\n  2. {dist_exe}")
        except Exception:
            print(f"\n[Berhasil] Aplikasi mandiri siap digunakan di: {dist_exe}")
    return rc


def tampilkan_setup_ide(target_dir: str | None = None) -> None:
    """Menyiapkan konfigurasi JSON MCP siap tempel & menyalin Bootstrap Rules ke proyek target."""
    pastikan_lingkungan_siap(auto_install=False)
    pasang_aturan_otomatis_global(verbose=True, pasang_global=True)
    cwd_path = ROOT_DIR.resolve().as_posix()

    if IS_INSTALLED_PACKAGE or shutil.which("karjimut"):
        mcp_json: dict[str, object] = {
            "mcpServers": {
                "karjimut": {
                    "command": "karjimut",
                    "args": ["mcp"],
                }
            }
        }
    else:
        mcp_json = {
            "mcpServers": {
                "karjimut": {
                    "command": "python",
                    "args": ["run.py", "mcp"],
                    "cwd": cwd_path,
                }
            }
        }

    config_out = ROOT_DIR / "mcp_config_siap_pakai.json"
    config_out.write_text(json.dumps(mcp_json, indent=2), encoding="utf-8")

    print("\n" + "=" * 72)
    print("  KONFIGURASI OTOMATIS MCP (ANTIGRAVITY / CURSOR / CLAUDE DESKTOP)")
    print("=" * 72)
    print(f"File konfigurasi telah disimpan ke: {config_out}\n")
    print(json.dumps(mcp_json, indent=2))
    print("=" * 72)

    if target_dir:
        tujuan = Path(target_dir).resolve()
        tujuan.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RULES_TEMPLATE_DIR / ".cursorrules", tujuan / ".cursorrules")
        shutil.copyfile(RULES_TEMPLATE_DIR / "antigravity_rules.md", tujuan / "GEMINI.md")
        agents_dir = tujuan / ".agents" / "rules"
        agents_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RULES_TEMPLATE_DIR / "antigravity_rules.md", agents_dir / "sleep-mcp-auto.md")
        print(f"\n[Berhasil] Aturan Tiga Mandat Otomatis (.cursorrules, GEMINI.md, .agents/rules/) disalin ke: {tujuan}")


def menu_interaktif() -> None:
    """Menu interaktif terminal untuk pengguna."""
    pastikan_lingkungan_siap()
    while True:
        print("\n" + "=" * 68)
        print("   KARJIMUT: ARSITEKTUR MEMORI DUA LAPIS (PANEL KENDALI CEPAT)")
        print("=" * 68)
        print("  [1] Jalankan Aplikasi Desktop Native (CustomTkinter + Idle Watcher)")
        print("  [2] Jalankan Unit & Integration Test (Pytest)")
        print("  [3] Jalankan Simulasi Benchmark Efisiensi & Retensi Token")
        print("  [4] Buat Konfigurasi Otomatis MCP IDE (mcp_config_siap_pakai.json)")
        print("  [5] Build Aplikasi Mandiri Karjimut.exe (PyInstaller)")
        print("  [0] Keluar")
        print("=" * 68)
        try:
            pilihan = input("Pilih menu [default=1, tekan Enter]: ").strip() or "1"
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar.")
            break

        if pilihan == "1":
            jalankan_desktop_gui()
            break
        elif pilihan == "2":
            jalankan_unit_test()
        elif pilihan == "3":
            jalankan_simulasi_skenario()
        elif pilihan == "4":
            tampilkan_setup_ide()
        elif pilihan == "5":
            build_standalone_exe()
        elif pilihan == "0":
            print("Terima kasih!")
            break
        else:
            print("Pilihan tidak dikenal, silakan ketik angka 1, 2, 3, 4, 5, atau 0.")
        time.sleep(0.5)


def main() -> None:
    parser = argparse.ArgumentParser(description="Karjimut One-Step Runner")
    parser.add_argument(
        "aksi",
        nargs="?",
        choices=["gui", "menu", "test", "benchmark", "mcp", "setup-ide", "build-exe"],
        default="gui",
        help="Aksi yang ingin dijalankan (default: gui / Aplikasi Desktop CustomTkinter)",
    )
    parser.add_argument("--target-dir", type=str, default=None, help="Folder proyek tujuan untuk menyalin Bootstrap Rules")
    args = parser.parse_args()

    if args.aksi == "gui":
        jalankan_desktop_gui()
    elif args.aksi == "test":
        sys.exit(jalankan_unit_test())
    elif args.aksi == "benchmark":
        sys.exit(jalankan_simulasi_skenario())
    elif args.aksi == "mcp":
        jalankan_mcp_server()
    elif args.aksi == "setup-ide":
        tampilkan_setup_ide(target_dir=args.target_dir)
    elif args.aksi == "build-exe":
        sys.exit(build_standalone_exe())
    else:
        menu_interaktif()


if __name__ == "__main__":
    main()
