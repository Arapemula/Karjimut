"""Konfigurasi terpusat Karjimut.

Seluruh nilai dibaca dari environment variable (dan file ``.env`` di root
folder proyek). Nilai dibaca ulang setiap kali :func:`get_settings`
dipanggil sehingga unit test maupun benchmark dapat mengganti konfigurasi
(misalnya path database) cukup dengan mengubah ``os.environ``.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

try:  # python-dotenv bersifat opsional saat runtime
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependensi wajib di requirements.txt
    load_dotenv = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Path dasar proyek
# ---------------------------------------------------------------------------
SRC_DIR: Path = Path(__file__).resolve().parent
IS_INSTALLED_PACKAGE: bool = any(
    p.lower() in ("site-packages", "dist-packages") for p in SRC_DIR.parts
)


def _migrasi_data_legacy_site_packages(user_dir: Path) -> None:
    """Migrasi aman satu kali bila terdapat data lama di site-packages menuju ~/.karjimut."""
    try:
        user_dir.mkdir(parents=True, exist_ok=True)
        target_env = user_dir / ".env"
        if not target_env.exists():
            for kandidat_env in (SRC_DIR.parent / ".env", SRC_DIR / ".env", SRC_DIR.parent / "src" / ".env"):
                if kandidat_env.is_file():
                    shutil.copyfile(kandidat_env, target_env)
                    break

        target_db = user_dir / "data" / "sleep_mcp.db"
        if not target_db.exists():
            for kandidat_db in (
                SRC_DIR.parent / "data" / "sleep_mcp.db",
                SRC_DIR / "data" / "sleep_mcp.db",
                SRC_DIR.parent / "src" / "data" / "sleep_mcp.db",
            ):
                if kandidat_db.is_file():
                    target_db.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(kandidat_db, target_db)
                    break
    except Exception:
        pass


# Mode aplikasi ter-bundle (PyInstaller .exe) atau paket PyPI (site-packages):
# data (.env, database) disimpan di direktori user (~/.karjimut) atau di samping .exe.
def _tentukan_project_root() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if (exe_dir / ".env").exists() or (exe_dir / "data").exists():
            return exe_dir
        if (exe_dir.parent / ".env").exists() or (exe_dir.parent / "data").exists():
            return exe_dir.parent
        return exe_dir
    if IS_INSTALLED_PACKAGE:
        user_dir = Path.home() / ".karjimut"
        _migrasi_data_legacy_site_packages(user_dir)
        return user_dir
    return SRC_DIR.parent



IS_FROZEN: bool = bool(getattr(sys, "frozen", False))
PROJECT_ROOT: Path = _tentukan_project_root()
ENV_FILE: Path = PROJECT_ROOT / ".env"

if load_dotenv is not None and ENV_FILE.exists():
    # override=False -> environment variable eksplisit (mis. dari pytest) menang.
    load_dotenv(ENV_FILE, override=False)

# Nilai jenis_aktivitas yang sah pada tabel log_metrik_token.
AKTIVITAS_READ_KTP = "TOOL_READ_KTP"
AKTIVITAS_WRITE_LOG = "TOOL_WRITE_LOG"
AKTIVITAS_SEARCH_SOLUSI = "TOOL_SEARCH_SOLUSI"
AKTIVITAS_SLEEP = "SLEEP_CONSOLIDATION"
JENIS_AKTIVITAS_VALID = (
    AKTIVITAS_READ_KTP,
    AKTIVITAS_WRITE_LOG,
    AKTIVITAS_SEARCH_SOLUSI,
    AKTIVITAS_SLEEP,
)

# Status state machine antrean_mentah.status_rangkum
STATUS_PENDING = 0
STATUS_PROCESSING = 1
STATUS_PROCESSED = 2


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip()


def _env_int(name: str, default: int, minimum: int | None = None) -> int:
    raw = os.environ.get(name)
    try:
        value = int(raw) if raw not in (None, "") else default
    except ValueError:
        value = default
    if minimum is not None and value < minimum:
        value = minimum
    return value


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    try:
        return float(raw) if raw not in (None, "") else default
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


_VALID_DB_SUFFIXES: frozenset[str] = frozenset({".db", ".sqlite", ".sqlite3"})


def _resolve_db_path(raw: str) -> str:
    if raw == ":memory:":
        return raw
    if "\x00" in raw:
        raise ValueError("Path database mengandung karakter null ilegal.")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    else:
        path = path.resolve()
    if path.suffix.lower() not in _VALID_DB_SUFFIXES:
        raise ValueError(
            f"Ekstensi file database tidak diizinkan: '{path.suffix}' (gunakan .db, .sqlite, atau .sqlite3)."
        )
    return str(path)


@dataclass(frozen=True)
class Settings:
    """Snapshot konfigurasi aktif."""

    db_path: str
    ktp_max_tokens: int
    idle_timeout_seconds: int
    idle_poll_interval_seconds: int
    stale_lock_minutes: int
    sleep_batch_limit: int
    working_window_seconds: int
    embedded_watcher_mcp: bool
    llm_provider: str
    llm_api_base_url: str
    llm_api_key: str
    llm_model_name: str
    llm_timeout_seconds: float
    llm_temperature: float
    use_local_fallback: bool
    fallback_local_on_llm_error: bool
    force_fallback_tokenizer: bool
    log_level: str

    @property
    def llm_aktif(self) -> bool:
        """True jika konsolidasi harus memakai LLM eksternal (bukan distiller lokal)."""
        if self.use_local_fallback:
            return False
        if not self.llm_api_base_url or not self.llm_model_name:
            return False
        if self.llm_provider == "ollama":
            return True  # Ollama lokal tidak memerlukan API key
        if "localhost" in self.llm_api_base_url or "127.0.0.1" in self.llm_api_base_url:
            return True  # server OpenAI-compatible lokal (Ollama /v1, LM Studio)
        return bool(self.llm_api_key)


def get_settings() -> Settings:
    """Membaca konfigurasi terkini dari environment."""
    raw_db = _env_str("KARJIMUT_DB_PATH", "") or _env_str("SLEEP_MCP_DB_PATH", "data/sleep_mcp.db")
    return Settings(
        db_path=_resolve_db_path(raw_db),
        ktp_max_tokens=_env_int("KTP_MAX_TOKENS", 0, minimum=0),
        idle_timeout_seconds=_env_int("IDLE_TIMEOUT_SECONDS", 300, minimum=1),
        idle_poll_interval_seconds=_env_int("IDLE_POLL_INTERVAL_SECONDS", 10, minimum=1),
        stale_lock_minutes=_env_int("STALE_LOCK_MINUTES", 3, minimum=1),
        sleep_batch_limit=_env_int("SLEEP_BATCH_LIMIT", 200, minimum=1),
        working_window_seconds=_env_int("WORKING_WINDOW_SECONDS", 60, minimum=1),
        embedded_watcher_mcp=_env_bool("KARJIMUT_EMBEDDED_WATCHER", _env_bool("SLEEP_MCP_EMBEDDED_WATCHER", True)),
        llm_provider=_env_str("LLM_PROVIDER", "openai").lower(),
        llm_api_base_url=_env_str("LLM_API_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        llm_api_key=_env_str("LLM_API_KEY", ""),
        llm_model_name=_env_str("LLM_MODEL_NAME", "gpt-6-luna"),
        llm_timeout_seconds=_env_float("LLM_TIMEOUT_SECONDS", 60.0),
        llm_temperature=_env_float("LLM_TEMPERATURE", 0.1),
        use_local_fallback=_env_bool("USE_LOCAL_FALLBACK", False),
        fallback_local_on_llm_error=_env_bool("FALLBACK_LOCAL_ON_LLM_ERROR", False),
        force_fallback_tokenizer=_env_bool("FORCE_FALLBACK_TOKENIZER", False),
        log_level=_env_str("LOG_LEVEL", "INFO").upper(),
    )


def setup_logging(name: str = "sleep_mcp") -> logging.Logger:
    """Logger ke STDERR (STDOUT dipakai oleh transport stdio MCP)."""
    settings = get_settings()
    root = logging.getLogger("sleep_mcp")
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
        )
        root.addHandler(handler)
        root.propagate = False
    root.setLevel(getattr(logging, settings.log_level, logging.INFO))
    return logging.getLogger(name if name.startswith("sleep_mcp") else f"sleep_mcp.{name}")
