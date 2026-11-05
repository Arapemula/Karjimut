"""Auto-Detector API Key 1-Kolom & Sinkronisasi Konfigurasi (.env + os.environ).

Mendeteksi secara otomatis provider LLM, Base URL, dan Model Default hanya dari
awalan (prefix) API Key yang ditempelkan pengguna:
  - ``AIzaSy...`` / ``AIza...`` -> Google Gemini (``gemini-3.8-flash``)
  - ``gsk_...``                 -> Groq (``openai/gpt-oss-20b``)
  - ``sk-or-...``               -> OpenRouter (``openrouter/auto``)
  - ``sk-ant-...``              -> Anthropic Claude (``claude-haiku-5-5``)
  - ``sk-proj-...`` / ``sk-...``-> OpenAI (``gpt-6-luna``)

Mendukung pula override opsional ``Custom Base URL & Model Name`` untuk endpoint
mandiri (DeepSeek, Ollama lokal, vLLM, LM Studio).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import ENV_FILE, PROJECT_ROOT, SRC_DIR, get_settings

GOOGLE_AI_STUDIO_URL = "https://aistudio.google.com/app/apikey"

# Model default per provider. ID model cepat usang, jadi nilai ini diverifikasi ke endpoint
# list-models provider (lihat tes_koneksi_llm) dan otomatis diganti bila sudah tidak tersedia.
MODEL_DEFAULT: dict[str, str] = {
    "gemini": "gemini-3.5-flash",
    "groq": "openai/gpt-oss-20b",
    "openrouter": "openrouter/auto",
    "anthropic": "claude-haiku-5-5",
    "openai": "gpt-6-luna",
}


@dataclass(frozen=True)
class HasilDeteksiKey:
    """Hasil deteksi otomatis dari string API Key dan opsional custom endpoint."""

    valid: bool
    provider: str  # gemini | openai | anthropic | ollama | local_fallback
    provider_label: str
    base_url: str
    model_name: str
    api_key: str
    badge_text: str
    status_warna: str  # hex warna indikator UI


def mask_api_key(api_key: str) -> str:
    """Menyamarkan API key untuk ditampilkan di antarmuka (contoh: ``AIzaSy•••••••9aB2``)."""
    kunci = (api_key or "").strip()
    if not kunci:
        return "(kosong)"
    if len(kunci) <= 10:
        return kunci[:3] + "•" * max(3, len(kunci) - 3)
    return f"{kunci[:6]}{'•' * 8}{kunci[-4:]}"


def deteksi_api_key(
    raw_key: str,
    custom_base_url: str = "",
    custom_model_name: str = "",
) -> HasilDeteksiKey:
    """Mendeteksi provider, endpoint, dan model secara otomatis dari awalan API Key.

    Urutan pengecekan prefix dirancang spesifik ke umum (``sk-or-`` dan ``sk-ant-``
    diperiksa lebih dulu sebelum ``sk-proj-`` / ``sk-``).
    """
    kunci = (raw_key or "").strip()
    c_url = (custom_base_url or "").strip().rstrip("/")
    c_model = (custom_model_name or "").strip()

    # 1. Kasus endpoint lokal tanpa API Key (Ollama / LM Studio / vLLM di localhost)
    if not kunci and c_url:
        url_lower = c_url.lower()
        if "11434" in url_lower and not url_lower.endswith("/v1"):
            model = c_model or "llama3.2"
            return HasilDeteksiKey(
                valid=True,
                provider="ollama",
                provider_label="Ollama Lokal",
                base_url=c_url,
                model_name=model,
                api_key="",
                badge_text=f"Ollama Lokal ({model})",
                status_warna="#10B981",
            )
        if "localhost" in url_lower or "127.0.0.1" in url_lower:
            model = c_model or "local-model"
            return HasilDeteksiKey(
                valid=True,
                provider="openai",
                provider_label="Local OpenAI-Compatible",
                base_url=c_url,
                model_name=model,
                api_key="",
                badge_text=f"Local Endpoint ({model})",
                status_warna="#10B981",
            )

    if not kunci:
        return HasilDeteksiKey(
            valid=False,
            provider="local_fallback",
            provider_label="Belum Ada API Key",
            base_url="",
            model_name="",
            api_key="",
            badge_text="Tempelkan API Key untuk mendeteksi provider otomatis",
            status_warna="#94A3B8",
        )

    # Tolak kunci yang terlalu pendek / mengandung spasi di tengah
    if len(kunci) < 8 or any(ch.isspace() for ch in kunci):
        return HasilDeteksiKey(
            valid=False,
            provider="invalid",
            provider_label="Format Key Tidak Valid",
            base_url="",
            model_name="",
            api_key=kunci,
            badge_text="Format API Key belum lengkap atau mengandung spasi",
            status_warna="#F59E0B",
        )

    # 2. Deteksi berdasarkan prefix API Key
    if kunci.startswith("AIza") or kunci.startswith("AQ.") or kunci.startswith("AQ"):
        provider = "gemini"
        provider_label = "Google Gemini"
        base_url = c_url or "https://generativelanguage.googleapis.com/v1beta"
        if c_url and "/openai" in c_url.lower():
            provider = "openai"
        model = c_model or MODEL_DEFAULT["gemini"]
        ket = "Gratis & Cepat" if model == MODEL_DEFAULT["gemini"] else "Custom Model"
        badge = f"Google Gemini ({model} — {ket})"
    elif kunci.startswith("gsk_"):
        provider = "openai"
        provider_label = "Groq"
        base_url = c_url or "https://api.groq.com/openai/v1"
        model = c_model or MODEL_DEFAULT["groq"]
        label_model = model
        badge = f"Groq ({label_model})"
    elif kunci.startswith("sk-or-"):
        provider = "openai"
        provider_label = "OpenRouter"
        base_url = c_url or "https://openrouter.ai/api/v1"
        model = c_model or MODEL_DEFAULT["openrouter"]
        badge = f"OpenRouter ({model})"
    elif kunci.startswith("sk-ant-"):
        provider = "anthropic"
        provider_label = "Anthropic Claude"
        base_url = c_url or "https://api.anthropic.com/v1"
        model = c_model or MODEL_DEFAULT["anthropic"]
        label_model = model
        badge = f"Anthropic Claude ({label_model})"
    elif kunci.startswith("sk-proj-") or kunci.startswith("sk-"):
        provider = "openai"
        if c_url and "deepseek" in c_url.lower():
            provider_label = "DeepSeek"
            base_url = c_url
            model = c_model or "deepseek-chat"
            badge = f"DeepSeek ({model})"
        elif c_url:
            provider_label = "Custom OpenAI-Compatible"
            base_url = c_url
            model = c_model or MODEL_DEFAULT["openai"]
            badge = f"Custom Endpoint ({model})"
        else:
            provider_label = "OpenAI"
            base_url = "https://api.openai.com/v1"
            model = c_model or MODEL_DEFAULT["openai"]
            badge = f"OpenAI ({model})"
    else:
        # Prefix kustom (mis. DeepSeek tanpa sk-, TogetherAI, Mistral, vLLM, dsb.)
        provider = "openai"
        provider_label = "Custom / OpenAI-Compatible"
        base_url = c_url or "https://api.openai.com/v1"
        model = c_model or MODEL_DEFAULT["openai"]
        badge = f"{provider_label} ({model})"

    return HasilDeteksiKey(
        valid=True,
        provider=provider,
        provider_label=provider_label,
        base_url=base_url,
        model_name=model,
        api_key=kunci,
        badge_text=badge,
        status_warna="#10B981",
    )


def _update_env_file(env_path: Path, pasangan: dict[str, str]) -> None:
    """Memperbarui key-value di file ``.env`` dengan mempertahankan komentar & urutan."""
    env_example = PROJECT_ROOT / ".env.example"
    if not env_example.exists():
        env_example = SRC_DIR / ".env.example"
    if not env_path.exists():
        env_path.parent.mkdir(parents=True, exist_ok=True)
        if env_example.exists():
            env_path.write_text(env_example.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            env_path.write_text("", encoding="utf-8")

    baris_lama = env_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    sudah_diupdate: set[str] = set()
    baris_baru: list[str] = []

    for baris in baris_lama:
        m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", baris)
        if m and m.group(1) in pasangan:
            kunci = m.group(1)
            baris_baru.append(f"{kunci}={pasangan[kunci]}")
            sudah_diupdate.add(kunci)
        else:
            baris_baru.append(baris)

    for kunci, nilai in pasangan.items():
        if kunci not in sudah_diupdate:
            baris_baru.append(f"{kunci}={nilai}")

    env_path.write_text("\n".join(baris_baru) + "\n", encoding="utf-8")


def simpan_konfigurasi_llm(
    raw_key: str,
    custom_base_url: str = "",
    custom_model_name: str = "",
    fallback_on_error: bool = True,
    env_path: Path | None = None,
) -> HasilDeteksiKey:
    """Mendeteksi, menyimpan ke ``.env``, dan menyinkronkan ke ``os.environ`` aktif."""
    deteksi = deteksi_api_key(raw_key, custom_base_url=custom_base_url, custom_model_name=custom_model_name)
    if not deteksi.valid:
        raise ValueError(deteksi.badge_text)

    target_env = env_path or ENV_FILE
    pasangan = {
        "LLM_PROVIDER": deteksi.provider,
        "LLM_API_BASE_URL": deteksi.base_url,
        "LLM_API_KEY": deteksi.api_key,
        "LLM_MODEL_NAME": deteksi.model_name,
        "USE_LOCAL_FALLBACK": "false",
        "FALLBACK_LOCAL_ON_LLM_ERROR": "true" if fallback_on_error else "false",
    }
    _update_env_file(target_env, pasangan)
    for k, v in pasangan.items():
        os.environ[k] = v

    return deteksi


def aktifkan_mode_offline_lokal(env_path: Path | None = None) -> None:
    """Mengaktifkan mode Local Rule-Based Distiller (100% offline tanpa API Key)."""
    target_env = env_path or ENV_FILE
    pasangan = {
        "USE_LOCAL_FALLBACK": "true",
        "FALLBACK_LOCAL_ON_LLM_ERROR": "true",
    }
    _update_env_file(target_env, pasangan)
    for k, v in pasangan.items():
        os.environ[k] = v


def perlu_onboarding() -> bool:
    """True jika aplikasi baru dijalankan dan belum memiliki API Key maupun mode lokal eksplisit."""
    s = get_settings()
    if s.llm_aktif:
        return False
    if s.use_local_fallback:
        return False
    return True


def info_provider_aktif() -> dict[str, Any]:
    """Mengembalikan ringkasan status konfigurasi LLM saat ini untuk ditampilkan di GUI."""
    s = get_settings()
    if s.llm_aktif:
        det = deteksi_api_key(s.llm_api_key, custom_base_url=s.llm_api_base_url, custom_model_name=s.llm_model_name)
        return {
            "aktif": True,
            "mode": "LLM Aktif",
            "provider": det.provider_label if det.valid else s.llm_provider.upper(),
            "model": s.llm_model_name,
            "base_url": s.llm_api_base_url,
            "key_masked": mask_api_key(s.llm_api_key),
            "badge": det.badge_text if det.valid else f"{s.llm_provider.upper()} ({s.llm_model_name})",
            "fallback_on_error": s.fallback_local_on_llm_error,
        }
    return {
        "aktif": False,
        "mode": "Local Rule-Based Distiller (Offline Fallback)",
        "provider": "Distiller Lokal (Offline)",
        "model": "Rule-Based Deterministik",
        "base_url": "-",
        "key_masked": mask_api_key(s.llm_api_key),
        "badge": "Local Fallback (Offline)",
        "fallback_on_error": s.fallback_local_on_llm_error,
    }


# ---------------------------------------------------------------------------
# Verifikasi koneksi & pemilihan model otomatis (self-healing terhadap model usang)
# ---------------------------------------------------------------------------
_MODEL_DIHINDARI = re.compile(
    r"embed|tts|whisper|image|audio|realtime|transcribe|moderation|vision|live|guard|safeguard|"
    r"preview|exp|lite|thinking|search|computer|codex|dall|sora|video",
    re.I,
)


def _kunci_versi(nama: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", nama))


def pilih_model_terbaik(
    provider_label: str,
    provider_atau_model: str,
    model_atau_tersedia: str | list[str],
    tersedia: list[str] | None = None,
) -> str:
    """Memilih model yang tersedia: tetap memakai ``model_diinginkan`` bila ada, jika tidak
    pilih model 'kecil & cepat' terbaru milik provider (urut versi tertinggi).

    Mendukung pemanggilan 3 argumen ``(provider, model_diinginkan, tersedia)``
    maupun 4 argumen ``(provider_label, provider, model_diinginkan, tersedia)``.
    """
    if tersedia is None and isinstance(model_atau_tersedia, list):
        provider = provider_label.lower()
        model_diinginkan = provider_atau_model
        daftar_tersedia = model_atau_tersedia
    else:
        provider = provider_atau_model.lower()
        model_diinginkan = str(model_atau_tersedia)
        daftar_tersedia = list(tersedia or [])

    if not daftar_tersedia or model_diinginkan in daftar_tersedia:
        return model_diinginkan
    stabil = [m for m in daftar_tersedia if not _MODEL_DIHINDARI.search(m)]
    kandidat: list[str] = []
    if provider == "gemini":
        kandidat = [m for m in stabil if re.fullmatch(r"gemini-[\d.]+-flash", m)]
    elif provider == "anthropic":
        kandidat = [m for m in stabil if "haiku" in m] or [m for m in stabil if "sonnet" in m]
    elif provider == "ollama":
        return daftar_tersedia[0]
    elif "groq" in provider_label.lower() or provider == "groq":
        for pref in ("openai/gpt-oss-20b", "openai/gpt-oss-120b"):
            if pref in daftar_tersedia:
                return pref
        kandidat = [m for m in stabil if "instant" in m or "8b" in m]
    elif "openrouter" in provider_label.lower() or provider == "openrouter":
        return model_diinginkan
    else:  # OpenAI & endpoint OpenAI-compatible
        kandidat = [m for m in stabil if re.search(r"mini|luna|nano|small|flash|haiku", m)]
    if not kandidat:
        return model_diinginkan
    return max(kandidat, key=lambda m: (_kunci_versi(m), -len(m)))


def daftar_model_tersedia(det: HasilDeteksiKey, timeout: float = 15.0) -> list[str]:
    """Mengambil daftar ID model dari endpoint list-models provider. Raise httpx.HTTPError bila gagal."""
    import httpx

    base = det.base_url.rstrip("/")
    with httpx.Client(timeout=httpx.Timeout(timeout, connect=8.0)) as client:
        if det.provider == "gemini":
            resp = client.get(f"{base}/models", params={"pageSize": 200}, headers={"x-goog-api-key": det.api_key})
            resp.raise_for_status()
            return [
                m["name"].split("/", 1)[-1]
                for m in resp.json().get("models", [])
                if "generateContent" in (m.get("supportedGenerationMethods") or ["generateContent"])
            ]
        if det.provider == "anthropic":
            resp = client.get(
                f"{base}/models",
                params={"limit": 100},
                headers={"x-api-key": det.api_key, "anthropic-version": "2023-06-01"},
            )
            resp.raise_for_status()
            return [m["id"] for m in resp.json().get("data", [])]
        if det.provider == "ollama":
            resp = client.get(f"{base}/api/tags")
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        headers = {"Authorization": f"Bearer {det.api_key}"} if det.api_key else {}
        resp = client.get(f"{base}/models", headers=headers)
        resp.raise_for_status()
        return [m["id"] for m in resp.json().get("data", [])]


def tes_koneksi_llm(
    det: HasilDeteksiKey | None = None,
    *,
    provider: str = "",
    base_url: str = "",
    api_key: str = "",
    model_name: str = "",
    timeout: float = 15.0,
) -> dict[str, Any]:
    """Menguji API key & endpoint, memverifikasi model, dan (bila perlu) memilih model pengganti.

    Returns:
        ``{"ok": bool, "sukses": bool, "pesan": str, "model": str, "model_terpilih": str, "model_diganti": bool}``
    """
    import httpx

    if det is None:
        det = deteksi_api_key(api_key, custom_base_url=base_url, custom_model_name=model_name)
        if not det.valid and provider:
            det = HasilDeteksiKey(
                valid=True,
                provider=provider,
                provider_label=provider.upper(),
                base_url=base_url,
                model_name=model_name,
                api_key=api_key,
                badge_text=f"{provider.upper()} ({model_name})",
                status_warna="#34D399",
            )

    hasil: dict[str, Any] = {
        "ok": False,
        "sukses": False,
        "pesan": "",
        "model": det.model_name,
        "model_terpilih": det.model_name,
        "model_diganti": False,
    }
    try:
        tersedia = daftar_model_tersedia(det, timeout=timeout)
    except httpx.HTTPStatusError as exc:
        kode = exc.response.status_code
        if kode in (401, 403):
            hasil["pesan"] = f"API Key ditolak oleh provider (HTTP {kode}). Periksa kembali key Anda."
        elif kode == 404:
            hasil["pesan"] = "Endpoint tidak ditemukan (HTTP 404). Periksa Base URL."
        else:
            hasil["pesan"] = f"Provider menjawab HTTP {kode}."
        return hasil
    except httpx.HTTPError as exc:
        hasil["pesan"] = f"Tidak dapat terhubung ke provider ({type(exc).__name__}). Periksa koneksi internet."
        return hasil
    except (KeyError, ValueError):
        # Endpoint tidak punya list-models standar -> anggap tersambung, model tidak dapat diverifikasi
        hasil.update(ok=True, sukses=True, pesan="Tersambung (daftar model tidak dapat diverifikasi).")
        return hasil

    terpilih = pilih_model_terbaik(det.provider_label, det.provider, det.model_name, tersedia)
    hasil["ok"] = True
    hasil["sukses"] = True
    hasil["model"] = terpilih
    hasil["model_terpilih"] = terpilih
    if terpilih != det.model_name:
        hasil["model_diganti"] = True
        hasil["pesan"] = f"Model '{det.model_name}' tidak tersedia; otomatis memakai '{terpilih}'."
    else:
        hasil["pesan"] = f"Tersambung. Model '{terpilih}' tersedia."
    return hasil


def terapkan_model(model_name: str, env_path: Path | None = None) -> None:
    """Menyimpan nama model terpilih ke ``.env`` dan ``os.environ`` aktif."""
    _update_env_file(env_path or ENV_FILE, {"LLM_MODEL_NAME": model_name})
    os.environ["LLM_MODEL_NAME"] = model_name
