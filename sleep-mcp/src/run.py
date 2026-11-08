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
elif hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
elif hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if sys.platform == "win32":
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("karjimut.desktop.v2")
    except Exception:
        pass

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
RULES_TEMPLATE_DIR = PACKAGE_DIR / "rules_template"
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


def _bersihkan_blok_karjimut_dari_teks(teks: str) -> str:
    """Menghapus blok aturan Karjimut dari teks markdown sambil mempertahankan isi milik pengguna."""
    import re

    hasil = re.sub(
        r"<!--\s*KARJIMUT:START\s*-->.*?<!--\s*KARJIMUT:END\s*-->\s*",
        "",
        teks,
        flags=re.S,
    )
    hasil = re.sub(
        r"#\s*Karjimut Automatic Memory Rule.*?(?=\n#\s+(?!Karjimut\b)|\Z)",
        "",
        hasil,
        flags=re.S,
    )
    return hasil.strip()


def pasang_aturan_otomatis_global(verbose: bool = False, pasang_global: bool = False) -> None:
    """Memasang aturan Tiga Mandat Otomatis (Zero-Prompt Vibecoder) tanpa duplikasi lintas file."""
    rule_md_src = RULES_TEMPLATE_DIR / "antigravity_rules.md"
    cursor_src = RULES_TEMPLATE_DIR / ".cursorrules"
    if not rule_md_src.exists():
        return

    isi_rule = rule_md_src.read_text(encoding="utf-8")

    # 1. Pasang Global Rule di ~/.gemini/config/rules/sleep-mcp-auto.md saat setup-ide
    #    (dan bersihkan duplikat di ~/.gemini/GEMINI.md tanpa menghapus instruksi custom milik user)
    if pasang_global:
        try:
            gemini_home = Path.home() / ".gemini"
            if gemini_home.exists():
                global_rule_file = gemini_home / "config" / "rules" / "sleep-mcp-auto.md"
                _tulis_jika_berubah(global_rule_file, isi_rule)

                global_gemini_md = gemini_home / "GEMINI.md"
                if global_gemini_md.exists():
                    existing_raw = global_gemini_md.read_text(encoding="utf-8", errors="ignore")
                    if "karjimut" in existing_raw.lower():
                        shutil.copyfile(global_gemini_md, global_gemini_md.with_suffix(".md.bak"))
                        sisa_user = _bersihkan_blok_karjimut_dari_teks(existing_raw)
                        _tulis_jika_berubah(global_gemini_md, (sisa_user + "\n") if sisa_user else "")

                if verbose:
                    print(f"[Auto-Rule] Global Rule Antigravity terpasang di: {global_rule_file}")
        except Exception as exc:
            if verbose:
                print(f"[Auto-Rule] Peringatan saat memasang global rule: {exc}")

    # 2. Pasang di root workspace proyek saat ini jika berjalan dari local checkout (bukan ~/.karjimut)
    if not IS_INSTALLED_PACKAGE:
        try:
            workspace_root = ROOT_DIR.parent
            if cursor_src.exists():
                isi_cursor = cursor_src.read_text(encoding="utf-8")
                _tulis_jika_berubah(workspace_root / ".cursorrules", isi_cursor)
            _tulis_jika_berubah(workspace_root / ".agents" / "rules" / "sleep-mcp-auto.md", isi_rule)
            ws_gemini_md = workspace_root / "GEMINI.md"
            if ws_gemini_md.exists():
                raw_ws_gemini = ws_gemini_md.read_text(encoding="utf-8", errors="ignore")
                if "karjimut" in raw_ws_gemini.lower():
                    sisa_ws = _bersihkan_blok_karjimut_dari_teks(raw_ws_gemini)
                    if sisa_ws:
                        _tulis_jika_berubah(ws_gemini_md, sisa_ws + "\n")
                    else:
                        ws_gemini_md.unlink(missing_ok=True)
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


def hentikan_proses_wrapper_terkunci(verbose: bool = False) -> int:
    """Menghentikan proses ``Scripts/karjimut.exe`` atau ``sleep-mcp.exe`` lama di Windows.

    Mencegah ``PermissionError: [WinError 32]`` ketika pengguna menjalankan
    ``pip uninstall karjimut`` atau ``pip install -U karjimut``.
    """
    if sys.platform != "win32":
        return 0
    my_pid = os.getpid()
    parent_pid = os.getppid()
    dihentikan = 0
    for exe_name in ("karjimut.exe", "sleep-mcp.exe"):
        try:
            proc = subprocess.run(
                [
                    "taskkill",
                    "/F",
                    "/IM",
                    exe_name,
                    "/FI",
                    f"PID ne {my_pid}",
                    "/FI",
                    f"PID ne {parent_pid}",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if "SUCCESS" in (proc.stdout or "").upper():
                dihentikan += 1
                if verbose:
                    print(f"[Info] Proses terkunci '{exe_name}' di latar belakang berhasil dibebaskan.")
        except Exception:
            pass
    # Bersihkan folder residu '~arjimut*' akibat pip uninstall yang sempat gagal sebelumnya
    try:
        import site

        for sp in site.getsitepackages() + [site.getusersitepackages()]:
            sp_path = Path(sp)
            if sp_path.is_dir():
                for sisa in sp_path.glob("~arjimut*"):
                    shutil.rmtree(sisa, ignore_errors=True)
    except Exception:
        pass
    return dihentikan


def jalankan_desktop_gui() -> None:
    """Meluncurkan Aplikasi Desktop Native Karjimut berbasis CustomTkinter.

    Pada Windows, bila dipanggil dari wrapper ``Scripts/karjimut.exe``, fungsi ini
    meluncurkan proses ``pythonw.exe -m karjimut gui`` secara terpisah (*detached*)
    lalu langsung keluar dari ``karjimut.exe`` dalam <0.1 detik agar file
    ``Scripts/karjimut.exe`` tidak terkunci oleh OS (mencegah ``WinError 32`` saat
    ``pip install -U karjimut`` atau ``pip uninstall karjimut``).
    """
    if (
        sys.platform == "win32"
        and not IS_FROZEN
        and os.environ.get("KARJIMUT_GUI_WORKER") != "1"
        and os.environ.get("KARJIMUT_FOREGROUND") != "1"
        and (IS_INSTALLED_PACKAGE or Path(sys.argv[0]).stem.lower() in ("karjimut", "sleep-mcp"))
    ):
        try:
            py_console = Path(_get_console_python())
            pyw_kandidat = py_console.with_name("pythonw.exe")
            runner_exe = str(pyw_kandidat) if pyw_kandidat.exists() else str(py_console)
            env_child = os.environ.copy()
            env_child["KARJIMUT_GUI_WORKER"] = "1"
            flags = (
                getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
                | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            )
            subprocess.Popen(
                [runner_exe, "-m", "karjimut", "gui"],
                env=env_child,
                creationflags=flags,
                close_fds=True,
            )
            return
        except Exception:
            pass

    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("karjimut.desktop.v2")
        except Exception:
            pass

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
        str((PACKAGE_DIR / "run.py").resolve()),
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


def _get_mcp_server_config() -> dict[str, object]:
    """Mengembalikan konfigurasi JSON server Karjimut yang paling andal untuk platform saat ini.

    Penting (Windows): Menggunakan ``python.exe -m karjimut mcp`` alih-alih ``karjimut.exe``
    agar proses MCP server di IDE tidak mengunci ``Scripts/karjimut.exe`` (mencegah
    ``PermissionError: [WinError 32]`` saat ``pip uninstall karjimut`` atau ``pip install -U karjimut``).
    """
    py_exe = _get_console_python()
    if IS_INSTALLED_PACKAGE or importlib.util.find_spec("karjimut") is not None:
        return {
            "command": py_exe,
            "args": ["-m", "karjimut", "mcp"],
        }
    kandidat_run = ROOT_DIR / "run.py"
    if not kandidat_run.exists():
        kandidat_run = PACKAGE_DIR / "run.py"
    run_script = kandidat_run.resolve().as_posix()
    return {
        "command": py_exe,
        "args": [run_script, "mcp"],
    }


def _parse_json_toleran(raw: str) -> dict[str, object] | None:
    """Mem-parsing JSON konfigurasi IDE secara aman (mendukung trailing comma sederhana).

    Mengembalikan ``None`` bila JSON rusak agar file pengguna TIDAK PERNAH ditimpa dengan ``{}``.
    """
    import re

    bersih = (raw or "").strip()
    if not bersih:
        return {}
    try:
        parsed = json.loads(bersih)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass
    try:
        tanpa_komentar = re.sub(r"^\s*//.*$", "", bersih, flags=re.M)
        tanpa_koma_akhir = re.sub(r",\s*([}\]])", r"\1", tanpa_komentar)
        parsed = json.loads(tanpa_koma_akhir)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _inject_mcp_into_json(config_path: Path, server_config: dict[str, object], server_name: str = "karjimut") -> bool:
    """Menyuntikkan konfigurasi server MCP ke file JSON target tanpa merusak konfigurasi lain.

    Jika file target sudah ada tetapi tidak dapat di-parse sebagai JSON objek yang sah,
    fungsi ini membatalkan penulisan (return False) agar tidak menghapus konfigurasi pengguna,
    serta membuat salinan cadangan ``.bak`` sebelum memodifikasi file yang ada.
    """
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, object] = {}
        file_lama_ada = config_path.exists()
        if file_lama_ada:
            raw_existing = config_path.read_text(encoding="utf-8", errors="replace")
            parsed = _parse_json_toleran(raw_existing)
            if parsed is None:
                return False
            data = parsed

        mcp_servers = data.get("mcpServers")
        if mcp_servers is not None and not isinstance(mcp_servers, dict):
            return False
        if mcp_servers is None:
            mcp_servers = {}
            data["mcpServers"] = mcp_servers

        mcp_servers[server_name] = server_config
        konten_baru = json.dumps(data, indent=2) + "\n"
        if file_lama_ada:
            try:
                shutil.copyfile(config_path, config_path.with_suffix(config_path.suffix + ".bak"))
            except Exception:
                pass
        config_path.write_text(konten_baru, encoding="utf-8")
        return True
    except Exception:
        return False


def auto_inject_mcp_ke_semua_ide(verbose: bool = True) -> list[str]:
    """Mendeteksi otomatis seluruh IDE yang terpasang dan menyuntikkan konfigurasi MCP + Global Rules.
    
    Target yang didukung:
      1. Claude Desktop (Windows, macOS, Linux)
      2. Cursor (Global MCP ~/.cursor/mcp.json & Global Rules ~/.cursor/rules/karjimut.mdc)
      3. Windsurf (~/.codeium/windsurf/mcp_config.json)
      4. Antigravity / Gemini CLI (~/.gemini/config/rules/ & ~/.gemini/GEMINI.md)
      5. VS Code Cline & Roo Code (globalStorage mcp settings)
    """
    server_cfg = _get_mcp_server_config()
    terinjeksi: list[str] = []
    home = Path.home()
    appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))

    # 1. Claude Desktop
    claude_candidates = [
        appdata / "Claude" / "claude_desktop_config.json",  # Windows
        home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",  # macOS
        home / ".config" / "Claude" / "claude_desktop_config.json",  # Linux
    ]
    for cp in claude_candidates:
        if cp.parent.exists() or cp.exists():
            if _inject_mcp_into_json(cp, server_cfg):
                terinjeksi.append(f"Claude Desktop ({cp})")
                if verbose:
                    print(f"  [Auto-Inject] [OK] Claude Desktop: {cp}")
            break

    # 2. Cursor (Global MCP & Global Rules)
    cursor_mcp = home / ".cursor" / "mcp.json"
    if _inject_mcp_into_json(cursor_mcp, server_cfg):
        rule_md_src = RULES_TEMPLATE_DIR / "antigravity_rules.md"
        if rule_md_src.exists():
            isi_rule = rule_md_src.read_text(encoding="utf-8")
            cursor_rule_dir = home / ".cursor" / "rules"
            _tulis_jika_berubah(cursor_rule_dir / "karjimut.mdc", isi_rule)
        terinjeksi.append(f"Cursor ({cursor_mcp})")
        if verbose:
            print(f"  [Auto-Inject] [OK] Cursor (Global MCP & Rules): {cursor_mcp}")

    # 3. Windsurf
    windsurf_cfg = home / ".codeium" / "windsurf" / "mcp_config.json"
    if windsurf_cfg.parent.exists() or windsurf_cfg.exists():
        if _inject_mcp_into_json(windsurf_cfg, server_cfg):
            terinjeksi.append(f"Windsurf ({windsurf_cfg})")
            if verbose:
                print(f"  [Auto-Inject] [OK] Windsurf: {windsurf_cfg}")

    # 4. Antigravity / Gemini CLI
    gemini_home = home / ".gemini"
    rule_md_src = RULES_TEMPLATE_DIR / "antigravity_rules.md"
    if gemini_home.exists():
        try:
            agy_mcp_cfg = gemini_home / "config" / "mcp_config.json"
            _inject_mcp_into_json(agy_mcp_cfg, server_cfg)

            legacy_agy_mcp = gemini_home / "antigravity" / "mcp_config.json"
            if legacy_agy_mcp.parent.exists() and not legacy_agy_mcp.is_symlink():
                try:
                    if not legacy_agy_mcp.exists() or legacy_agy_mcp.resolve() != agy_mcp_cfg.resolve():
                        _inject_mcp_into_json(legacy_agy_mcp, server_cfg)
                except Exception:
                    pass

            gemini_cli_settings = gemini_home / "settings.json"
            if gemini_cli_settings.exists():
                _inject_mcp_into_json(gemini_cli_settings, server_cfg)

            if rule_md_src.exists():
                isi_rule = rule_md_src.read_text(encoding="utf-8")
                _tulis_jika_berubah(gemini_home / "config" / "rules" / "sleep-mcp-auto.md", isi_rule)
                global_gemini_md = gemini_home / "GEMINI.md"
                if global_gemini_md.exists():
                    existing_raw = global_gemini_md.read_text(encoding="utf-8", errors="ignore")
                    if "karjimut" in existing_raw.lower():
                        shutil.copyfile(global_gemini_md, global_gemini_md.with_suffix(".md.bak"))
                        sisa_user = _bersihkan_blok_karjimut_dari_teks(existing_raw)
                        _tulis_jika_berubah(global_gemini_md, (sisa_user + "\n") if sisa_user else "")
            terinjeksi.append(f"Antigravity/Gemini ({agy_mcp_cfg})")
            if verbose:
                print(f"  [Auto-Inject] [OK] Antigravity / Gemini CLI: {agy_mcp_cfg}")
        except Exception:
            pass

    # 5. VS Code Extensions (Cline & Roo Code)
    vscode_exts = [
        ("VS Code Cline", appdata / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json"),
        ("VS Code Cline (macOS)", home / "Library" / "Application Support" / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json"),
        ("VS Code Roo Code", appdata / "Code" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline" / "settings" / "cline_mcp_settings.json"),
        ("VS Code Roo Code (macOS)", home / "Library" / "Application Support" / "Code" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline" / "settings" / "cline_mcp_settings.json"),
    ]
    for label, vpath in vscode_exts:
        if vpath.parent.exists() or vpath.exists():
            if _inject_mcp_into_json(vpath, server_cfg):
                terinjeksi.append(f"{label} ({vpath})")
                if verbose:
                    print(f"  [Auto-Inject] [OK] {label}: {vpath}")

    return terinjeksi


def tampilkan_setup_ide(target_dir: str | None = None) -> None:
    """Menyiapkan konfigurasi JSON MCP siap tempel, auto-inject ke seluruh IDE, & menyalin Rules."""
    pastikan_lingkungan_siap(auto_install=False)
    pasang_aturan_otomatis_global(verbose=False, pasang_global=True)
    mcp_json = {"mcpServers": {"karjimut": _get_mcp_server_config()}}

    config_out = ROOT_DIR / "mcp_config_siap_pakai.json"
    config_out.write_text(json.dumps(mcp_json, indent=2), encoding="utf-8")

    print("\n" + "=" * 72)
    print("  KARJIMUT ZERO-SETUP AUTO-INJECTOR (IDE & AGENTS)")
    print("=" * 72)
    print("Mendeteksi lingkungan IDE dan menyuntikkan MCP & Aturan Otomatis...\n")
    terinjeksi = auto_inject_mcp_ke_semua_ide(verbose=True)
    print("-" * 72)
    if terinjeksi:
        print(f"[Sukses] Karjimut otomatis terkonfigurasi di {len(terinjeksi)} lingkungan:")
        for nama in terinjeksi:
            print(f"   * {nama}")
    else:
        print("[Info] Tidak ada IDE desktop yang terdeteksi otomatis. File mcp_config_siap_pakai.json dibuat.")
    print(f"\nSalinan mcp_config_siap_pakai.json tersimpan di:\n  {config_out}")
    print("=" * 72)

    if target_dir:
        tujuan = Path(target_dir).resolve()
        tujuan.mkdir(parents=True, exist_ok=True)
        src_cursor = RULES_TEMPLATE_DIR / ".cursorrules"
        src_antigravity = RULES_TEMPLATE_DIR / "antigravity_rules.md"
        if src_cursor.exists():
            shutil.copyfile(src_cursor, tujuan / ".cursorrules")
        if src_antigravity.exists():
            isi_raw = src_antigravity.read_text(encoding="utf-8")
            isi_bersih = isi_raw.split("---", 2)[-1].strip() + "\n" if isi_raw.startswith("---") else isi_raw
            (tujuan / "GEMINI.md").write_text(isi_bersih, encoding="utf-8")
            agents_dir = tujuan / ".agents" / "rules"
            agents_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src_antigravity, agents_dir / "sleep-mcp-auto.md")
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
        print("  [4] Auto-Setup Semua IDE & Generator Config MCP (Cursor, Claude, dll)")
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
    try:
        from . import __app_name__, __version__
    except Exception:
        try:
            from src import __app_name__, __version__
        except Exception:
            try:
                from karjimut import __app_name__, __version__
            except Exception:
                __app_name__ = "Karjimut"
                __version__ = "2.0.12"

    parser = argparse.ArgumentParser(description="Karjimut One-Step Runner")
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"{__app_name__} v{__version__}",
        help="Tampilkan versi Karjimut saat ini",
    )
    parser.add_argument(
        "aksi",
        nargs="?",
        choices=["gui", "menu", "test", "benchmark", "mcp", "setup", "setup-ide", "stop", "build-exe", "version"],
        default="gui",
        help="Aksi yang ingin dijalankan (default: gui / Aplikasi Desktop CustomTkinter)",
    )
    parser.add_argument("--target-dir", type=str, default=None, help="Folder proyek tujuan untuk menyalin Bootstrap Rules")
    args = parser.parse_args()

    if args.aksi == "version":
        print(f"{__app_name__} v{__version__}")
        sys.exit(0)
    elif args.aksi == "stop":
        jml = hentikan_proses_wrapper_terkunci(verbose=True)
        if jml == 0:
            print("[Info] Tidak ada proses wrapper karjimut.exe / sleep-mcp.exe yang sedang terkunci.")
        sys.exit(0)
    elif args.aksi == "gui":
        jalankan_desktop_gui()
    elif args.aksi == "test":
        sys.exit(jalankan_unit_test())
    elif args.aksi == "benchmark":
        sys.exit(jalankan_simulasi_skenario())
    elif args.aksi == "mcp":
        jalankan_mcp_server()
    elif args.aksi in ("setup", "setup-ide"):
        tampilkan_setup_ide(target_dir=args.target_dir)
    elif args.aksi == "build-exe":
        sys.exit(build_standalone_exe())
    else:
        menu_interaktif()


if __name__ == "__main__":
    main()
