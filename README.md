<p align="center">
  <img src="https://raw.githubusercontent.com/Arapemula/Karjimut/main/sleep-mcp/assets/karjimut_banner.png" alt="Karjimut Banner" width="720" style="border-radius: 16px;" />
</p>

<h1 align="center">Karjimut</h1>

<p align="center">
  <strong>The Autonomous Long-Term Memory Engine for AI Coding Agents</strong><br>
  <em>Stop LLM Amnesia. Cut Active Context Token Overhead by up to 86%. Keep Cursor, Claude Code, and Antigravity Aligned Across Sessions.</em>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.10%2B-blue.svg" alt="Python 3.10+"></a>
  <a href="https://modelcontextprotocol.io/"><img src="https://img.shields.io/badge/MCP-1.2.0%2B-green.svg" alt="MCP Spec"></a>
  <a href="https://pypi.org/project/karjimut/"><img src="https://img.shields.io/pypi/v/karjimut.svg?color=blue" alt="PyPI Version"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://github.com/Arapemula/Karjimut"><img src="https://img.shields.io/badge/PRs-Welcome-orange.svg" alt="PRs Welcome"></a>
</p>


---

## 💡 The Problem with Modern AI Coding Agents

Whether you use **Cursor**, **Claude Code**, **Antigravity IDE**, **Windsurf**, or **Cline**, long-term projects always hit three painful walls:

1. 💸 **Context Window Bloat & Cost Explosions**: As sessions grow, raw conversation logs and messy trial-and-error traces accumulate, burning millions of tokens and draining your API budget.
2. 🧠 **Context Rot & Session Amnesia**: Start a fresh session or let compaction trigger, and your agent instantly forgets your core architecture rules, directory structure, and repeats the exact same bugs it spent two hours solving yesterday.
3. 🏝️ **Developer Memory Isolation**: Your AI agent's hard-won discoveries on your machine remain trapped locally—your teammates' agents will step on the exact same landmines.

**Karjimut** solves all three permanently through a **Two-Tier Bio-Inspired Memory Architecture** powered by the **Model Context Protocol (MCP)** and **Autonomous Idle-Phase Consolidation (Sleep Cycle)**.

---

## ⚡ Quick Start (Ready in 30 Seconds)

### 1. Install Karjimut
Run this single command in your terminal:

```bash
pip install karjimut
```

*(Or run instantly without installation using [uv](https://github.com/astral-sh/uv): `uvx karjimut setup`)*

### 2. Auto-Setup All Your IDEs (Zero Manual Steps)
Run:

```bash
karjimut setup
```

Karjimut automatically detects installed IDEs (**Cursor**, **Claude Desktop**, **Windsurf**, **Antigravity / Gemini CLI**, and **VS Code Cline/Roo Code**) and safely injects:
- ✅ MCP server configuration directly into each IDE's configuration file.
- ✅ Global Autonomous Rules (`karjimut.mdc` & `sleep-mcp-auto.md`) so you don't have to copy-paste `.cursorrules` to every new project folder!

### 3. Open Your IDE & Start Vibecoding
Open your project in Cursor, Claude Desktop, or your preferred IDE. Your AI coding agent will now autonomously retain project identity, prevent amnesia, and recall solutions without any manual intervention.

---

## 🖥️ Native Desktop Dashboard

Prefer a visual control center? Simply open your terminal and type:

```bash
karjimut
```

<p align="center">
  <img src="https://raw.githubusercontent.com/Arapemula/Karjimut/main/sleep-mcp/assets/karjimut_logo.png" alt="Karjimut Desktop App" width="120" />
</p>

Karjimut includes a modern, high-performance desktop application built with CustomTkinter:
- **1-Column Smart Onboarding**: Automatically detects your API keys (Google Gemini, Groq, OpenRouter, Claude, OpenAI) or operates in 100% offline rule-based mode.
- **Elastic Core Editor**: View and fine-tune your project's active identity and mandatory rules, complete with a 1-click rollback mechanism.
- **Proven Solution Vault**: Search, curate, and review distilled bug resolutions.
- **Real-Time Sustainability Analytics**: Live tracking of token savings, raw vs. compressed token efficiency, and AI retention metrics.

---

## 🚀 Key Features

### 🧠 Two-Tier Bio-Inspired Memory
* **Tier 1: Elastic Project Core (Lapis 1)**: Holds your tech stack, core directory layout, and non-negotiable architecture rules. Always compressed, deduplicated, and instant ($O(1)$ overhead at session start).
* **Tier 2: On-Demand Solution Vault (Lapis 2)**: Zero token cost during normal coding! Solutions to tricky bugs are retrieved on-demand only when a matching error or stack trace occurs.

### 🌙 Autonomous Sleep Cycle (Idle Consolidation)
During coding sessions, your agent leaves lightweight milestone notes in an asynchronous queue. When you take a coffee break ($\ge 5$ minutes of inactivity), Karjimut's background daemon activates the **Sleep Cycle**—distilling raw logs, updating core rules, and archiving proven solutions into persistent memory.

### 🤝 Multi-Team Git Synchronization
Karjimut serializes project memory into clean, git-friendly `.karjimut/team_memory.json` files. When you push and pull via Git, your entire team's AI agents automatically inherit everyone's bug fixes and updated rules—completely free of binary database merge conflicts.

### 🔍 High-Precision Hybrid Search
Combines lexical keyword matching (for exact error codes like `SQLITE_BUSY` or `#nextjs-15`) with 384-dimensional semantic vector embeddings (`BAAI/bge-small-en-v1.5` via CPU-accelerated ONNX + bilingual ID–EN technical synonym expansion & offline feature-hashing fallback) using Reciprocal Rank Fusion (RRF).

### 🤖 100% Autonomous (Zero-Prompt Vibecoder Protocol)
You don't need to remind your AI agent to use Karjimut. With the workspace rules attached, the agent operates autonomously:
1. **At Session Start**: Automatically fetches the latest Project Core and imports any new team memory.
2. **During Coding**: Automatically checkpoints progress and technical rules after completing features.
3. **When Errors Strike**: Automatically searches the Solution Vault for a one-shot fix before wasting tokens on hallucinated trial-and-error.

---

## 📊 Empirical Evaluation & Benchmark Results

All metrics are measured deterministically via `tests/benchmark.py` using `tiktoken` (`cl100k_base`) and `time.perf_counter()` without synthetic or hardcoded baselines:

| Evaluation Metric | Empirical Result | Methodology |
| :--- | :--- | :--- |
| **Active Context Window Efficiency** | **86.86%** | Measured across 5 multi-step coding sessions (40 steps) against cumulative transcript replay |
| **Net Token Savings (Full Overhead)** | **57.22% (+15,699 tokens)** | Includes full deduction of Sleep Consolidation tokens + `.cursorrules` + 4 MCP tool schemas; Break-Even Point reached at **Session 2** |
| **Rule Retention & Unlearning** | **100.0% (10/10)** | 9 active architectural rules retained + 1 deprecated rule (`Basic Auth`) cleanly unlearned |
| **Changelog Noise Rejection** | **100.0%** | Filters release version notes, file cleanups, and test pass logs out of KTP architectural rules |
| **Hybrid Retrieval Precision@1 / MRR** | **100.0% / 1.0000** | Evaluated across $N=15$ bilingual (ID/EN) stack trace, natural language, and tag queries |
| **Out-of-Domain False Positive Rate** | **0.0% (10/10 rejected)** | Tested against $N=10$ out-of-domain & cross-project negative queries (e.g., `No module named ruff`) |

---

## 📂 Repository Structure

```text
Karjimut/
|-- README.md                       # Official product documentation & Quick Start
|-- .cursorrules                    # Compact Vibecoder Rule (Cursor & Windsurf)
|-- .agents/rules/sleep-mcp-auto.md # Compact Agent Bootstrap Rule (Antigravity / Gemini)
|-- official-site/                  # Bilingual official landing page & design system spec
|-- sleep-mcp/
    |-- pyproject.toml              # PyPI package configuration (karjimut)
    |-- src/                        # Core engine (MCP server, SQLite WAL + sqlite-vec, GUI)
    |-- tests/                      # Automated pytest suite (43 tests) & empirical benchmark
    |-- assets/                     # Official brand logos, banners, and app icons
```

---

## 🛡️ Privacy & Local-First Philosophy

- **Zero Telemetry**: Karjimut does not track your keystrokes, projects, or personal data.
- **Local Storage**: All databases, cache, and vector embeddings reside locally on your machine in SQLite WAL mode.
- **Your Keys, Your Choice**: Use your own API keys, run local Ollama models, or utilize the 100% offline rule-based distiller.

---

## 📄 License

Karjimut is open-source software licensed under the **[MIT License](LICENSE)**.  
Copyright © 2026 **Naufal Arhab Fadhil Muhammad**. All rights reserved.
