<div align="center">

# ⚡ Unleash-Agent

### Autonomous Local Code Studio & Multi-Agent Swarm Engine

**Empower modest 8B & 14B local models to build, audit, and refactor production software on your local machine with zero API costs, zero data leaks, and zero VRAM crashes.**

[![GitHub stars](https://img.shields.io/badge/GitHub-Stars%20Welcome-yellow?style=flat-square&logo=github)](https://github.com/sanyam47/unleash-agent)
[![Local Inference](https://img.shields.io/badge/Local%20GPU-RTX%203050%2B%20(6GB)-green?style=flat-square)](#)
[![Ollama Engine](https://img.shields.io/badge/Ollama-100%25%20Offline-black?style=flat-square&logo=ollama)](#)
[![Docker Test Gate](https://img.shields.io/badge/Docker%20Sandbox---network%20none-blue?style=flat-square&logo=docker)](#)
[![Dual License](https://img.shields.io/badge/License-Dual%20(Community%20%7C%20Enterprise)-purple.svg?style=flat-square)](LICENSE)

<br/>

*Zero API Costs • 100% Air-Gapped Privacy • 6-Layer Acceptance Gates • Dynamic Hardware-Aware Swarm*

</div>

---

## 💡 Why Unleash-Agent?

Most developers assume lightweight local models (like **Llama 3 8B**, **Qwen 2.5 Coder 7B**, or **Dolphin 3**) cannot write reliable, full-stack software. When prompted directly without a harness, smaller models inevitably fail:
1. **Full-File Rewrite Fatigue:** Rewriting 200+ line files causes models to drop features, hallucinate APIs, or omit crucial logic.
2. **Comment Stubs & Placeholders:** They cut corners with `// Logic goes here` or `<!-- ... (no changes needed) -->`.
3. **Hardware Crashes (OOM):** Running multi-agent swarms concurrently on a 6GB laptop GPU (like an RTX 3050) immediately triggers display driver timeouts and out-of-memory crashes.

**Unleash-Agent eliminates these failure modes through an intelligent harness.** Rather than expecting an 8B model to be an all-knowing frontier giant, Unleash-Agent provides spatial awareness, a multi-pass surgical diff editor, an isolated Docker test gate, and a hardware-aware sequential swarm relay.

---

## ⚔️ How It Compares

| Capability | Raw Local LLM (Ollama) | Cloud Subscriptions (Cursor / Claude Code) | **Unleash-Agent** |
|:---|:---:|:---:|:---:|
| **Cost & Freedom** | Free | \$20 – \$200+ / month | **100% Free & Self-Hosted** |
| **Privacy & Air-Gap** | ✅ Local | ❌ Proprietary cloud logging | **✅ 100% Offline Capable** |
| **Code Editing Precision** | ❌ Full-file rewrites (Truncation risk) | ⚠️ High token burn | **✅ 3-Pass Surgical Diff Editor** |
| **Multi-Agent Architecture** | ❌ Single turn | ⚠️ Cloud parallel only | **✅ Dynamic Hardware-Aware Swarm** |
| **Verification & Testing** | ❌ Hallucinates & stops | ⚠️ Basic linter / static check | **✅ 6-Layer Docker & Playwright Gate** |
| **Hardware Resilience** | ❌ Driver crashes on 6GB GPUs | N/A (Cloud hosted) | **✅ 0-Crash VRAM Relay Guard** |
| **Workspace Mounting** | ❌ Isolated playground | ⚠️ Manual Git commands | **✅ 1-Click Shadow Checkpoints & Rollback** |

---

## 🐝 The Dynamic Swarm Engine (Builder ➔ Verifier ➔ Auditor)

Unleash-Agent dynamically adapts its multi-agent architecture based on your active hardware:

```
                              ┌─────────────────────────────┐
                              │     User Prompt / Task      │
                              └──────────────┬──────────────┘
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       ▼                                           ▼
          [Local GPU (≤ 16GB VRAM)]                    [Cloud / High VRAM (≥ 16GB)]
           Sequential GPU Relay Mode                     Concurrent Parallel Mode
         (RTX 3050 / 6GB Zero-Crash)                     (Groq / OpenRouter / Cloud)
                       │                                           │
                       └─────────────────────┬─────────────────────┘
                                             │
                                             ▼
                      ┌─────────────────────────────────────────────┐
                      │          WORKER 1: THE BUILDER              │
                      │  - Scans workspace tree & AST symbol table  │
                      │  - Surgically generates modular code files  │
                      └──────────────────────┬──────────────────────┘
                                             │ (Reuses model in VRAM)
                                             ▼
                      ┌─────────────────────────────────────────────┐
                      │      WORKER 2: ADVERSARIAL QA & VERIFIER    │
                      │  - Executes Playwright headless browser     │
                      │  - Runs Backend Docker Test Gate            │
                      │  - Auto-triggers targeted self-repairs      │
                      └──────────────────────┬──────────────────────┘
                                             │ (Reuses model in VRAM)
                                             ▼
                      ┌─────────────────────────────────────────────┐
                      │          WORKER 3: APPSEC AUDITOR           │
                      │  - Secret leakage & credential scanning     │
                      │  - Local air-gap & OWASP validation         │
                      └─────────────────────────────────────────────┘
```

* **On Local RTX 3050 (6GB VRAM):** Executes in **Sequential GPU Relay**. Worker 1 completes code generation and releases its turn, allowing Worker 2 and Worker 3 to reuse the same resident VRAM model weights without memory thrashing, driver reboots, or OOM crashes.
* **On Cloud / High VRAM:** Automatically scales to **Concurrent Parallel Workers** for blazing sub-second multi-agent throughput.

---

## 🛡️ The 6-Layer Definition of Done (DoD) Gate

No code is accepted or shown as "Complete" without passing 6 deterministic verification layers:

1. **Layer 1: Syntax & Compilation Gate:** Validates AST tree integrity (`node -c` for JavaScript, `ast.parse` / `compile` for Python, `json.loads` for JSON).
2. **Layer 2: Semantic Layout Parity:** Intercepts hollow, empty single-div HTML mockups.
3. **Layer 3: DOM Event Contract:** Ensures every interactive HTML button and element is bound to real, working JavaScript listeners.
4. **Layer 4: Anti-Placeholder Shield:** Catches lazy comment stubs like `// TODO: Implement` or empty function bodies and triggers an autonomous self-repair turn.
5. **Layer 5A: Headless Browser Runtime Gate:** Spawns a real headless Chromium instance, executes client code, verifies DOM mutations, and traps unhandled console exceptions.
6. **Layer 5B: Universal Backend Docker Test Gate (`--network none`):** Mounts generated Python/Node backends into an isolated, air-gapped Docker container to run `pytest` / `unittest` suites with zero network egress.
7. **Layer 6: AppSec & Secret Leakage Gate:** Scans the active workspace for accidentally hardcoded API keys, private certificates, unhashed credentials, and unsafe OS execution.

---

## 🎯 Key Frontier Systems

### 📁 Mount Existing Repository Mode
Mount any directory on your local filesystem (e.g. `C:\coding\my-app`):
* **Instant Traversal Pruning:** Intelligently ignores `node_modules`, `venv`, `__pycache__`, and `.git` using optimized `os.walk` pruning, indexing 20,000+ file projects in sub-second time.
* **Git Shadow Checkpoints & 1-Click Rollback:** Creates an immutable pre-execution snapshot before any file modification. If an edit fails, rollback instantly with a single click.

### 🎯 3-Pass Surgical Diff Editor (`edit_project_file`)
Say goodbye to entire-file rewrites that burn tokens and break working code:
* **Pass 1:** Exact byte substring match.
* **Pass 2:** Line-ending normalization (`\r\n` vs `\n`).
* **Pass 3:** Whitespace-trimmed contiguous line-block anchor matching for indentation drift.
* **Syntax Assurance:** Edits are immediately tested against Python AST and Node syntax parsers before writing to disk.

### ☁️ Multi-Provider BYOK Cloud Engine
Bring your own API keys for instant cloud frontier access alongside local Ollama:
* **Direct Providers:** Groq, OpenRouter, Cerebras, DeepSeek, Cohere.
* **Real-time Telemetry:** Tracks tokens/second, eval tokens, and duration across all providers.

---

## 🚀 Quickstart

### Prerequisites
* Python 3.10+
* [Ollama](https://ollama.com/) (for offline local models)
* [Docker Desktop](https://www.docker.com/) *(optional, for isolated backend container testing)*

### 1. Clone & Install
```bash
git clone https://github.com/sanyam47/unleash-agent.git
cd unleash-agent

python -m venv venv
# Windows:
venv\Scripts\activate
# Mac / Linux:
source venv/bin/activate

pip install -r requirements.txt
playwright install chromium
```

### 2. Pull a Local Coding Model
```bash
ollama pull qwen2.5-coder:7b
# Or lightweight reasoning:
ollama pull dolphin3:latest
```

### 3. Start Unleash-Agent
```bash
# Terminal 1: Start Ollama daemon
ollama serve

# Terminal 2: Start Unleash-Agent Studio
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8001
```

Open your browser at **`http://127.0.0.1:8001`**.

---

## 🔒 Security & Air-Gap Guarantee
* **100% Offline Capable:** Runs entirely without internet access using local Ollama models.
* **Docker Isolation:** Container test runners execute with `--network none` and `--read-only` root filesystems.
* **OS Protection:** Built-in path validation blocks agents from touching OS system roots (`C:\Windows`, `/etc`, `/sys`).

---

## 📄 License & Commercial Rights

Unleash-Agent is licensed under a **Dual-License Model**:

* **Community Open-Source License (Free Forever):** Free for individuals, students, researchers, hobbyists, and non-commercial developers to study, run, and modify.
* **Commercial Enterprise License:** Any commercial deployment, hosting as a paid SaaS/API, white-labeling, or enterprise internal deployment requires a written Commercial Enterprise License.

For commercial licensing and enterprise inquiries, contact:
* **Author:** Sanyam
* **Email:** [sanyam4747@gmail.com](mailto:sanyam4747@gmail.com)
* **GitHub:** [https://github.com/sanyam47/unleash-agent](https://github.com/sanyam47/unleash-agent)

See full terms in the [LICENSE](LICENSE) file.
