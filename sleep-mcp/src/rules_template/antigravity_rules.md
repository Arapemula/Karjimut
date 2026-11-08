---
trigger: always_on
description: Karjimut autonomous memory protocol (Zero-Prompt Vibecoder).
---

<!-- KARJIMUT:START -->
# Karjimut Automatic Memory Rule
Use the active workspace folder name (lowercase kebab-case) as `kode_proyek` and its absolute path as `path_workspace`. Call `karjimut` MCP tools automatically without waiting for user prompts:
1. **Session Start**: Call `baca_ktp_proyek(kode_proyek, path_workspace)` on the first coding/analysis turn to load project identity, stack, structure, and architecture rules.
2. **After Task**: Call `titip_catatan_kerja(kode_proyek, ringkasan_aksi, path_workspace)` after completing features, code/config edits, or bugfixes. Format: `Identitas: ... Stack: ... Struktur: ... Aturan: ... Solusi: <max 2 sentences> #tag1 #tag2` (no full stack traces).
3. **On Error**: Call `cari_laci_solusi(kode_proyek, kata_kunci, path_workspace)` on any build/test/runtime error before guessing fixes, then record feedback via `nilai_solusi(kode_proyek, id_solusi, berhasil=True/False)`.
4. **Security**: Never log `.env`, private keys, or secret API tokens into memory.
<!-- KARJIMUT:END -->
