/* ==========================================================================
   Karjimut (sleep-mcp v2.0.13) — Official Site Interactive Logic
   High-converting, user-centric agent demos, token calculator, and test bench.
   ========================================================================== */

const CLI_COMMANDS = {
  pip: "pip install karjimut",
  inject: "karjimut setup",
  gui: "karjimut",
  verify: "karjimut verify-team"
};

const SIM_SCENARIOS = {
  amnesia: {
    title: "1. New Chat Session (Amnesia vs Instant Context)",
    userPrompt: "Tambahkan endpoint baru GET /api/v1/users/profile.",
    badAuthor: "Standard Agent (No Memory)",
    badBadge: "AMNESIA · 4,250 TOKENS BURNED",
    badResponse: "Halo! Boleh jelaskan arsitektur backend kamu? Mau pakai FastAPI, Express, atau Flask? Direktori filenya di mana? Skema auth-nya pakai apa ya? Tolong paste kode router yang sudah ada.",
    badMetric: "5 turns back-and-forth · Context bloated before coding starts",
    goodAuthor: "Karjimut-Powered Agent",
    goodBadge: "ONE-SHOT · ~603 TOKENS AVG (86.86% SAVED)",
    goodNote: "⚡ Loaded KTP Proyek v27 (Elastic Core): FastAPI, PostgreSQL, JWT Auth, Rule #4.",
    goodResponse: "Endpoint `/api/v1/users/profile` dibuat di `src/api/v1/users.py` menggunakan router FastAPI yang ada. Menerapkan Aturan #4 arsitektur tim (JWT Bearer dengan clock-skew tolerance 30s) dan skema response Pydantic.",
    goodMetric: "1 turn one-shot resolution · Zero repetitive explanations"
  },
  bug: {
    title: "2. Encountering a Bug (5-Turn Guessing vs Instant Recall)",
    userPrompt: "Terminal Error: OperationalError: database is locked during concurrent write",
    badAuthor: "Standard Agent (Trial & Error)",
    badBadge: "GUESSWORK · 6,120 TOKENS BURNED",
    badResponse: "Sepertinya SQLite kamu crash atau thread-nya tabrakan. Coba restart server. Kalau masih error, coba ganti timeout jadi 1000ms. Eh masih error? Coba hapus file db-wal secara manual...",
    badMetric: "6 turns of trial-and-error · Risk of database corruption",
    goodAuthor: "Karjimut-Powered Agent",
    goodBadge: "ONE-SHOT · 35.9ms TAG RECALL (0 TOK IDLE)",
    goodNote: "⚡ Recalled from Solution Vault in 35.9ms (#sqlite-locked, 95% Confidence).",
    goodResponse: "Masalah terdeteksi dari arsip solusi tim (#sqlite-locked). Terapkan 2 baris konfigurasi paten:\n1. Aktifkan `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;`\n2. Bungkus transaksi tulis dengan `BEGIN IMMEDIATE` eksplisit.",
    goodMetric: "Solved in 1 turn · 100% Precision@1 · Zero trial-and-error"
  },
  sleep: {
    title: "3. 5-Minute Coffee Break (Context Bloat vs Autonomous Consolidation)",
    userPrompt: "[User steps away for 5 minutes after building 3 features]",
    badAuthor: "Standard Agent (No Sleep)",
    badBadge: "DEGRADATION · 27,438 TOKENS BASELINE",
    badResponse: "Seluruh riwayat chat harian menumpuk di memori. Percakapan semakin lambat (14 detik per respon), token terbuang untuk log usang, dan agen mulai melupakan aturan awal proyek.",
    badMetric: "Context degradation · High API cost · Hallucinations increase",
    goodAuthor: "Karjimut-Powered Agent",
    goodBadge: "CONSOLIDATED · 3,015 ACTIVE TOKENS TOTAL",
    goodNote: "🌙 IdleWatcherDaemon triggered after 300s inactivity.",
    goodResponse: "Siklus tidur mandiri selesai:\n• Mendistilasi catatan kerja harian menjadi Elastic Core\n• Membuang noise percakapan & changelog sementara\n• Menyimpan aturan arsitektur & solusi paten terdeduplikasi\n• Mengekspor `.karjimut/team_memory.json` (HMAC-SHA256) untuk tim.",
    goodMetric: "86.86% avg active tokens saved · Fresh, sharp context for next session"
  }
};

const SEARCH_DEMOS = {
  jwt: {
    query: "token autentikasi kedaluwarsa saat akses endpoint user",
    tag: "#jwt-expired #auth-middleware #401",
    latency: "97.10 ms",
    conf: 0.95,
    hits: 4,
    misses: 0,
    sol: "Gunakan mekanisme refresh token rotasi otomatis pada interceptor axios/fetch dan tambahkan clock-skew tolerance 30 detik pada verifikasi PyJWT."
  },
  sqlite: {
    query: "OperationalError database is locked concurrent write",
    tag: "#sqlite-locked #wal-concurrency #busy-timeout",
    latency: "81.28 ms",
    conf: 0.92,
    hits: 3,
    misses: 0,
    sol: "Aktifkan PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000; dan bungkus transaksi tulis dengan BEGIN IMMEDIATE eksplisit serta pisahkan I/O vektor di luar lock."
  },
  cors: {
    query: "gagal fetch API dari frontend karena diblokir kebijakan CORS preflight",
    tag: "#cors-preflight #fastapi-middleware #options-200",
    latency: "34.63 ms",
    conf: 0.88,
    hits: 2,
    misses: 0,
    sol: "Daftarkan CORSMiddleware sebelum router utama dengan allow_origins eksplisit, allow_credentials=True, dan pastikan method OPTIONS mengembalikan HTTP 200."
  },
  ood: {
    query: "SyntaxError Unexpected token < in JSON at position 0 webpack bundle",
    tag: "REJECTED BY RELEVANCE GATE (0.0% FALSE POSITIVE)",
    latency: "0.0% FPR Gate",
    conf: 0.0,
    hits: 0,
    misses: 0,
    sol: "Gerbang Relevansi Karjimut (AMBIGUOUS_SINGLE_TOKENS) mendeteksi bahwa kata tunggal ambigu 'token' pada kueri webpack bukan masalah autentikasi #jwt-expired. Kueri ditolak tanpa mengotori prompt (0 token terbuang)."
  }
};

let currentSearchKey = "jwt";

document.addEventListener("DOMContentLoaded", () => {
  initCliBox();
  initSimulator();
  initCalculator();
  initSearchDemos();
  initLangSwitch();
});

/* CLI Tab Switcher */
function initCliBox() {
  const tabs = document.querySelectorAll("[data-cli-tab]");
  const cmdText = document.getElementById("cli-cmd-text");
  const copyBtn = document.getElementById("cli-copy-btn");

  tabs.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("cli-box__tab--active"));
      btn.classList.add("cli-box__tab--active");
      const key = btn.getAttribute("data-cli-tab");
      cmdText.textContent = CLI_COMMANDS[key] || CLI_COMMANDS.pip;
    });
  });

  if (copyBtn) {
    copyBtn.addEventListener("click", () => {
      navigator.clipboard.writeText(cmdText.textContent.trim());
      const prev = copyBtn.textContent;
      copyBtn.textContent = "COPIED ✓";
      copyBtn.style.color = "#6798ff";
      setTimeout(() => {
        copyBtn.textContent = prev;
        copyBtn.style.color = "";
      }, 1600);
    });
  }

  const promoCopy = document.getElementById("promo-copy-trigger");
  if (promoCopy) {
    promoCopy.addEventListener("click", () => {
      navigator.clipboard.writeText("pip install karjimut");
      promoCopy.textContent = "COPIED: pip install karjimut ✓";
      setTimeout(() => {
        promoCopy.textContent = "pip install karjimut →";
      }, 1800);
    });
  }
}

/* Interactive Agent Simulator */
function initSimulator() {
  const tabs = document.querySelectorAll("[data-sim-scenario]");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("sim-tab-btn--active"));
      tab.classList.add("sim-tab-btn--active");
      const key = tab.getAttribute("data-sim-scenario");
      renderSimulator(key);
    });
  });
}

function renderSimulator(key) {
  const s = SIM_SCENARIOS[key];
  if (!s) return;

  document.getElementById("sim-user-prompt").textContent = s.userPrompt;
  document.getElementById("sim-bad-author").textContent = s.badAuthor;
  document.getElementById("sim-bad-badge").textContent = s.badBadge;
  document.getElementById("sim-bad-resp").textContent = s.badResponse;
  document.getElementById("sim-bad-metric").textContent = s.badMetric;

  document.getElementById("sim-good-author").textContent = s.goodAuthor;
  document.getElementById("sim-good-badge").textContent = s.goodBadge;
  document.getElementById("sim-good-note").textContent = s.goodNote;
  document.getElementById("sim-good-resp").textContent = s.goodResponse;
  document.getElementById("sim-good-metric").textContent = s.goodMetric;
}

/* Interactive ROI Calculator */
function initCalculator() {
  const sessionSlider = document.getElementById("calc-slider-sessions");
  const devsSlider = document.getElementById("calc-slider-devs");
  const sessionVal = document.getElementById("calc-val-sessions");
  const devsVal = document.getElementById("calc-val-devs");

  const outTokens = document.getElementById("calc-out-tokens");
  const outDollars = document.getElementById("calc-out-dollars");
  const outHours = document.getElementById("calc-out-hours");

  function update() {
    const s = parseInt(sessionSlider.value, 10);
    const d = parseInt(devsSlider.value, 10);

    sessionVal.textContent = `${s} sessions / week`;
    devsVal.textContent = `${d} engineer${d > 1 ? "s" : ""}`;

    // Calculation grounded in Skenario 1 benchmark (5 sessions / 40 steps):
    // Avg fresh baseline = ~2,174 tokens/session (10,871 / 5). Karjimut active = ~603 tokens/session (3,015 / 5).
    // Active tokens saved vs fresh re-orientation per session = ~1,571 tokens.
    // Monthly sessions per engineer = s * 4.2
    const totalMonthlySessions = Math.round(s * 4.2 * d);
    const tokensSaved = Math.round(totalMonthlySessions * 1571);
    // Estimated token cost savings ($10-$15 / 1M tokens blend input/output)
    const dollarsSaved = Math.round((tokensSaved / 1000000) * 15 * 10) / 10;
    // Estimated developer time saved (5 mins spent re-explaining or trial-and-error per session)
    const hoursSaved = Math.round((totalMonthlySessions * 6) / 60);

    outTokens.textContent = `${tokensSaved.toLocaleString("en-US")} Tokens`;
    outDollars.textContent = `$${dollarsSaved.toFixed(1)} / mo`;
    outHours.textContent = `~${hoursSaved} Hours`;
  }

  if (sessionSlider && devsSlider) {
    sessionSlider.addEventListener("input", update);
    devsSlider.addEventListener("input", update);
    update();
  }
}

/* Interactive Search Test Bench */
function initSearchDemos() {
  const buttons = document.querySelectorAll("[data-search-demo]");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      buttons.forEach((b) => b.classList.remove("preset-btn--active"));
      btn.classList.add("preset-btn--active");
      const key = btn.getAttribute("data-search-demo");
      renderSearchDemo(key);
    });
  });

  const btnReward = document.getElementById("btn-feed-reward");
  const btnPunish = document.getElementById("btn-feed-punish");

  if (btnReward) {
    btnReward.addEventListener("click", () => {
      const d = SEARCH_DEMOS[currentSearchKey];
      if (!d || d.conf === 0.0) return;
      d.conf = Math.min(1.0, +(d.conf + 0.10).toFixed(2));
      d.hits += 1;
      renderSearchDemo(currentSearchKey);
    });
  }

  if (btnPunish) {
    btnPunish.addEventListener("click", () => {
      const d = SEARCH_DEMOS[currentSearchKey];
      if (!d || d.conf === 0.0) return;
      d.conf = Math.max(0.10, +(d.conf - 0.15).toFixed(2));
      d.misses += 1;
      renderSearchDemo(currentSearchKey);
    });
  }
}

function renderSearchDemo(key) {
  currentSearchKey = key;
  const d = SEARCH_DEMOS[key];
  if (!d) return;

  document.getElementById("demo-query").textContent = d.query;
  document.getElementById("demo-latency").textContent =
    d.conf === 0.0 ? d.latency : `RECALLED IN ${d.latency}`;
  document.getElementById("demo-tag").textContent = d.tag;
  document.getElementById("demo-sol").textContent = d.sol;

  const confEl = document.getElementById("demo-conf");
  const feedActions = document.getElementById("demo-feedback-wrap");

  if (d.conf === 0.0) {
    confEl.textContent = "BLOCKED BY RELEVANCE GATE (0 TOKENS)";
    confEl.className = "mono-tag mono-tag--ruby";
    if (feedActions) feedActions.style.display = "none";
  } else {
    const pct = Math.round(d.conf * 100);
    confEl.textContent = `CONFIDENCE ${pct}% (Hit:${d.hits} Miss:${d.misses})`;
    confEl.className = "mono-tag mono-tag--accent";
    if (feedActions) feedActions.style.display = "flex";
  }
}

/* Bilingual Language Switcher */
function initLangSwitch() {
  const btns = document.querySelectorAll("[data-lang]");
  const translatables = document.querySelectorAll("[data-en][data-id]");

  btns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const lang = btn.getAttribute("data-lang");
      btns.forEach((b) => b.classList.remove("lang-switch__btn--active"));
      btn.classList.add("lang-switch__btn--active");

      translatables.forEach((el) => {
        const text = el.getAttribute(`data-${lang}`);
        if (text) el.textContent = text;
      });
    });
  });
}
