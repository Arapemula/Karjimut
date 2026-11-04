<p align="center">
  <img src="https://raw.githubusercontent.com/Arapemula/Karjimut/main/sleep-mcp/assets/karjimut_banner.png" alt="Karjimut Banner" width="720" style="border-radius: 16px;" />
</p>

<h1 align="center">Karjimut</h1>

<p align="center">
  <strong>The Autonomous Long-Term Memory Engine for AI Coding Agents</strong><br>
  <em>Stop LLM Amnesia. Cut Token Costs by up to 90%. Keep Cursor, Claude Code, and Antigravity Aligned Forever.</em>
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
# Recommended (Official PyPI package)
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

## 📂 Repository Structure

```text
Karjimut/
|-- README.md                       # Official product documentation & Quick Start
|-- GEMINI.md                       # Autonomous Vibecoder Rule (Antigravity IDE)
|-- .cursorrules                    # Autonomous Vibecoder Rule (Cursor & Windsurf)
|-- .agents/rules/sleep-mcp-auto.md # Universal Agent Bootstrap Rule
|-- sleep-mcp/
    |-- assets/                     # Official brand logos, banners, and app icons
    |   |-- karjimut_banner.png
    |   |-- karjimut_logo.png
    |   |-- karjimut.ico
    |-- rules_template/             # Starter templates for new workspaces
        |-- .cursorrules
        |-- antigravity_rules.md
```

> **Distribution Architecture:**  
> Karjimut is engineered as a high-performance, standalone package. The core engine (MCP server, native GUI, SQLite WAL vector store, and background watcher) is delivered directly via verified binary packages.

---

## 🛡️ Privacy & Local-First Philosophy

- **Zero Telemetry**: Karjimut does not track your keystrokes, projects, or personal data.
- **Local Storage**: All databases, cache, and vector embeddings reside locally on your machine in SQLite WAL mode.
- **Your Keys, Your Choice**: Use your own API keys, run local Ollama models, or utilize the 100% offline rule-based distiller.

---

## 📄 License

Karjimut is open-source software licensed under the **[MIT License](LICENSE)**.  
Copyright © 2026 **Naufal Arhab Fadhil Muhammad**. All rights reserved.
