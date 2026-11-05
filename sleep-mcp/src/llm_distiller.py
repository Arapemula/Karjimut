"""Modul integrasi LLM multi-provider (OpenAI-compatible, Gemini, Anthropic, Ollama) & validasi output."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from .config import Settings, get_settings, setup_logging
from .fts_search import normalisasi_tag
from .ktp_manager import local_rule_based_distiller
from .log_parser import (
    MAX_CHARS_PER_LOG_PROMPT,
    _RE_PROMPT_BREAKOUT,
    bersihkan_injeksi_memori,
    layak_masuk_laci_arsip,
    ringkas_stack_trace,
    sanitasi_pesan_error,
)
from .tokenizer_utils import hitung_token, normalisasi_spasi

logger = setup_logging("sleep_mcp.llm_distiller")

SYSTEM_PROMPT_CONSOLIDATOR = (
    "Kamu adalah mesin konsolidasi memori untuk arsitektur Karjimut (Sleep-MCP). Baca [KTP Proyek Saat Ini], "
    "[Daftar ID & Tag Arsip Solusi Eksisting], dan [Log Aktivitas Mentah Batch Terbaru] berikut. "
    "Buang semua baris stack trace error yang gagal, percobaan berulang, dan percakapan basa-basi. "
    "Tugasmu hanya dua: (1) Gabungkan informasi lama dan baru untuk memperbarui KTP Proyek dalam 1 "
    "paragraf terstruktur dan padat yang merangkum identitas, stack teknologi, struktur direktori inti, "
    "dan seluruh aturan wajib proyek saat ini secara utuh tanpa memotong aturan lama yang masih relevan, "
    "namun hapus aturan atau teknologi lama apabila log terbaru menyatakan sudah dicabut/dimigrasi. "
    "(2) Jika di dalam log terbaru terdapat masalah teknis/bug yang akhirnya berhasil "
    "diselesaikan, ekstrak hanya solusi berhasilnya dalam maksimal 2-3 kalimat beserta 3 hingga 5 tag "
    "kata kunci/gejala error berhuruf kecil (format #kata-kunci). Jika masalah tersebut merujuk pada "
    "entri yang sudah ada di [Daftar ID & Tag Arsip Solusi Eksisting], isi atribut id_arsip_target "
    "dengan ID entri tersebut dan gunakan tag utama yang sama agar sistem dapat memperbarui catatan "
    "lama tanpa duplikasi; jika masalah baru, isi id_arsip_target dengan null. Keluarkan hasil "
    "semata-mata dalam format JSON valid dengan skema: {\"ktp_proyek_baru\": \"...\", \"arsip_solusi\": "
    "[{\"id_arsip_target\": null, \"tag_masalah\": \"#tag1, #tag2, #tag3\", \"solusi_paten\": \"...\"}]}. "
    "Panduan kualitas: kalimat pertama KTP wajib menjelaskan fungsi/tujuan proyek (jangan hanya mengulang "
    "nama proyek); buang teknologi, direktori, atau aturan yang menurut log terbaru sudah dihapus/diganti; "
    "pertahankan seluruh aturan wajib yang masih berlaku beserta kode inline/nama file penting."
)

SYSTEM_PROMPT_KOMPRESI = (
    "Kamu adalah kompresor KTP Proyek Karjimut (Elastic Core). Padatkan teks KTP Proyek berikut secara ringkas "
    "dan efisien tanpa menghapus identitas, stack teknologi, direktori inti, dan seluruh aturan arsitektur wajib "
    "proyek. Keluarkan semata-mata JSON valid: {\"ktp_proyek_baru\": \"...\"}."
)


def susun_user_prompt(konteks: dict[str, Any]) -> str:
    """Menyusun prompt user: KTP saat ini, daftar ID & tag arsip, dan log batch (pra-filter & sanitasi prompt injection)."""
    ktp = konteks.get("ktp_lama") or "(belum ada - proyek baru)"
    arsip = konteks.get("arsip_eksisting") or []
    daftar_arsip = "\n".join(f"- id={a['id']} | {a['tag_masalah']}" for a in arsip) or "(kosong)"
    blok_log = []
    for log in konteks.get("log_batch") or []:
        isi_aman = ringkas_stack_trace(log["isi_log"])[:MAX_CHARS_PER_LOG_PROMPT]
        isi_aman = _RE_PROMPT_BREAKOUT.sub(r"(\1)", isi_aman)
        blok_log.append(f"--- log #{log['id']} ({log.get('waktu_masuk', '')}) ---\n{isi_aman}")
    return (
        f"[KTP Proyek Saat Ini]\n{ktp}\n\n"
        f"[Daftar ID & Tag Arsip Solusi Eksisting]\n{daftar_arsip}\n\n"
        f"[Log Aktivitas Mentah Batch Terbaru]\n" + "\n".join(blok_log)
    )


def ekstrak_json(teks: str) -> dict[str, Any]:
    """Parsing JSON tahan banting (membuang code fence / teks pengantar)."""
    bersih = (teks or "").strip()
    bersih = re.sub(r"^```(?:json)?\s*|\s*```$", "", bersih, flags=re.I | re.S).strip()
    try:
        data = json.loads(bersih)
    except json.JSONDecodeError:
        awal, akhir = bersih.find("{"), bersih.rfind("}")
        if awal < 0 or akhir <= awal:
            raise ValueError("Respons LLM tidak mengandung objek JSON.")
        data = json.loads(bersih[awal : akhir + 1])
    if not isinstance(data, dict):
        raise ValueError("Respons LLM bukan objek JSON.")
    return data


def validasi_output_distiller(data: dict[str, Any]) -> dict[str, Any]:
    """Validasi & normalisasi skema keluaran distiller."""
    ktp = bersihkan_injeksi_memori(str(data.get("ktp_proyek_baru") or ""))
    if not isinstance(ktp, str) or not ktp.strip():
        raise ValueError("Field 'ktp_proyek_baru' kosong / tidak valid.")
    arsip_mentah = data.get("arsip_solusi") or []
    if isinstance(arsip_mentah, dict):
        arsip_mentah = [arsip_mentah]
    arsip: list[dict[str, Any]] = []
    for item in arsip_mentah:
        if not isinstance(item, dict):
            continue
        solusi = bersihkan_injeksi_memori(str(item.get("solusi_paten") or "").strip())
        tag = item.get("tag_masalah") or ""
        tag_str = ", ".join(tag) if isinstance(tag, list) else str(tag)
        if not solusi or not normalisasi_tag(tag_str) or not layak_masuk_laci_arsip(solusi, tag_str):
            continue
        target = item.get("id_arsip_target")
        try:
            target = int(target) if target not in (None, "", "null") else None
        except (TypeError, ValueError):
            target = None
        arsip.append({"id_arsip_target": target, "tag_masalah": tag_str, "solusi_paten": solusi})
    return {"ktp_proyek_baru": normalisasi_spasi(ktp), "arsip_solusi": arsip}


def _post_json(client: httpx.Client, url: str, headers: dict[str, str], body: dict[str, Any]) -> httpx.Response:
    """POST JSON; bila endpoint menolak ``temperature`` (model penalaran baru) ulangi tanpa parameter itu."""
    resp = client.post(url, headers=headers, json=body)
    if resp.status_code == 400 and "temperature" in resp.text.lower() and "temperature" in body:
        body = {k: v for k, v in body.items() if k != "temperature"}
        resp = client.post(url, headers=headers, json=body)
    return resp


def panggil_llm_json(
    system_prompt: str, user_prompt: str, settings: Settings | None = None
) -> tuple[str, int, int]:
    """Memanggil endpoint LLM dalam JSON mode."""
    s = settings or get_settings()
    base = s.llm_api_base_url.rstrip("/")
    timeout = httpx.Timeout(s.llm_timeout_seconds, connect=10.0)
    token_prompt = token_completion = 0
    with httpx.Client(timeout=timeout) as client:
        if s.llm_provider == "gemini":
            model_clean = s.llm_model_name.replace("models/", "")
            url = f"{base}/models/{model_clean}:generateContent"
            headers = {"Content-Type": "application/json"}
            if s.llm_api_key:
                headers["x-goog-api-key"] = s.llm_api_key
            body = {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "generationConfig": {"temperature": s.llm_temperature, "responseMimeType": "application/json"},
            }
            resp = client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
            teks = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
            usage = data.get("usageMetadata") or {}
            token_prompt = int(usage.get("promptTokenCount") or 0)
            token_completion = int(usage.get("candidatesTokenCount") or 0)
        elif s.llm_provider == "anthropic":
            url = f"{base}/messages"
            headers = {
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            }
            if s.llm_api_key:
                headers["x-api-key"] = s.llm_api_key
            body = {
                "model": s.llm_model_name,
                "max_tokens": 1024,
                "temperature": s.llm_temperature,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            }
            resp = _post_json(client, url, headers, body)
            resp.raise_for_status()
            data = resp.json()
            teks = "".join(
                block.get("text", "")
                for block in (data.get("content") or [])
                if isinstance(block, dict)
            )
            usage = data.get("usage") or {}
            token_prompt = int(usage.get("input_tokens") or 0)
            token_completion = int(usage.get("output_tokens") or 0)
        elif s.llm_provider == "ollama":
            url = f"{base}/api/chat"
            body = {
                "model": s.llm_model_name,
                "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                "stream": False,
                "format": "json",
                "options": {"temperature": s.llm_temperature},
            }
            resp = client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()
            teks = data["message"]["content"]
            token_prompt = int(data.get("prompt_eval_count") or 0)
            token_completion = int(data.get("eval_count") or 0)
        else:
            url = f"{base}/chat/completions"
            headers = {"Content-Type": "application/json"}
            if s.llm_api_key:
                headers["Authorization"] = f"Bearer {s.llm_api_key}"
            body: dict[str, Any] = {
                "model": s.llm_model_name,
                "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                "temperature": s.llm_temperature,
                "response_format": {"type": "json_object"},
            }
            resp = _post_json(client, url, headers, body)
            if resp.status_code == 400 and "response_format" in resp.text:
                body.pop("response_format")
                resp = _post_json(client, url, headers, body)
            resp.raise_for_status()
            data = resp.json()
            teks = data["choices"][0]["message"]["content"] or ""
            usage = data.get("usage") or {}
            token_prompt = int(usage.get("prompt_tokens") or 0)
            token_completion = int(usage.get("completion_tokens") or 0)
    if token_prompt <= 0:
        token_prompt = hitung_token(system_prompt) + hitung_token(user_prompt)
    if token_completion <= 0:
        token_completion = hitung_token(teks)
    return teks, token_prompt, token_completion


def distilasi(
    konteks: dict[str, Any],
    settings: Settings | None = None,
    paksa_lokal: bool | None = None,
) -> tuple[str, dict[str, Any], int, int]:
    """Langkah 4 + retry kompresi Langkah 5."""
    s = settings or get_settings()
    gunakan_lokal = (not s.llm_aktif) if paksa_lokal is None else paksa_lokal
    user_prompt = susun_user_prompt(konteks)
    token_prompt_setara = hitung_token(SYSTEM_PROMPT_CONSOLIDATOR) + hitung_token(user_prompt)

    def _lokal() -> tuple[str, dict[str, Any], int, int]:
        hasil = local_rule_based_distiller(
            konteks["kode_proyek"],
            konteks.get("ktp_lama", ""),
            konteks.get("arsip_eksisting", []),
            konteks.get("log_batch", []),
            s.ktp_max_tokens,
        )
        hasil = validasi_output_distiller(hasil)
        completion = hitung_token(json.dumps(hasil, ensure_ascii=False))
        return "LOCAL_RULE_BASED", hasil, token_prompt_setara, completion

    if gunakan_lokal:
        return _lokal()

    try:
        teks, tp, tc = panggil_llm_json(SYSTEM_PROMPT_CONSOLIDATOR, user_prompt, s)
        hasil = validasi_output_distiller(ekstrak_json(teks))
        if s.ktp_max_tokens > 0 and hitung_token(hasil["ktp_proyek_baru"]) > s.ktp_max_tokens:
            logger.info("KTP hasil LLM > %d token, menjalankan 1x retry kompresi.", s.ktp_max_tokens)
            try:
                teks2, tp2, tc2 = panggil_llm_json(
                    SYSTEM_PROMPT_KOMPRESI, f"[KTP Proyek]\n{hasil['ktp_proyek_baru']}", s
                )
                tp += tp2
                tc += tc2
                kompres = ekstrak_json(teks2).get("ktp_proyek_baru")
                if isinstance(kompres, str) and kompres.strip():
                    hasil["ktp_proyek_baru"] = normalisasi_spasi(kompres)
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                logger.warning("Retry kompresi gagal (%s); memakai pemangkasan terstruktur.", sanitasi_pesan_error(exc))
        return "LLM", hasil, tp, tc
    except (httpx.HTTPError, ValueError, KeyError, IndexError, json.JSONDecodeError) as exc:
        pesan_aman = sanitasi_pesan_error(exc)
        if s.fallback_local_on_llm_error:
            logger.warning("LLM gagal (%s) -> fallback distiller lokal.", pesan_aman)
            return _lokal()
        raise RuntimeError(f"Distilasi LLM gagal: {pesan_aman}") from None
