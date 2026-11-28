<div align="center">

<img src="frontend/assets/logo.svg" width="88" height="88" alt="Unleash-Agent Studio Logo" />

# ⚡ Unleash-Agent Studio

### The Offline-First Voice OS Pilot, Floating 3D HUD & Parameter-Adaptive AI Studio

**Empower compact `1.5B`, `8B`, and `14B` local models — or scale seamlessly to frontier models — with real-time executive OS control, offline Silero VAD + Whisper voice, a floating 3D Gyro Sphere HUD, cloud QLoRA fine-tuning, and zero-crash sequential swarms on consumer GPUs.**

[![GitHub stars](https://img.shields.io/badge/GitHub-Stars%20Welcome-yellow?style=flat-square&logo=github)](https://github.com/sanyam47/unleash-agent)
[![Hardware](https://img.shields.io/badge/Hardware-Any%20GPU%20%7C%20RTX%203050%20(6GB)%20Safe-green?style=flat-square)](#)
[![Ollama Engine](https://img.shields.io/badge/Ollama-100%25%20Offline-black?style=flat-square&logo=ollama)](#)
[![Voice Engine](https://img.shields.io/badge/Piper%20TTS-Offline%20Neural-purple?style=flat-square)](#)
[![Docker Test Gate](https://img.shields.io/badge/Docker%20Sandbox---network%20none-blue?style=flat-square&logo=docker)](#)
[![Dual License](https://img.shields.io/badge/License-Dual%20(Community%20%7C%20Enterprise)-purple.svg?style=flat-square)](LICENSE)

<br/>

*Zero Cloud LLM Dependency • Parameter-Adaptive Harness (`1.5B`–Frontier) • Floating 3D Gyro Sphere HUD • Silero VAD + Whisper • Cloud QLoRA Bridge*

</div>

---

## 💡 What is Unleash-Agent Studio?

Most AI tools on the market are superficial prompt wrappers around cloud APIs. If internet drops, they die; if tokens run out, they halt; and they have zero real access to your PC hardware or operating system.

**Unleash-Agent Studio** is a **local-first Autonomous AI Operating System and Training Platform**. It gives lightweight consumer hardware (like a 6GB RTX 3050 laptop) the capabilities of a high-end agentic cluster through intelligent orchestration, weight-level persona baking, and deterministic OS hooks.

---

## 🏛️ The 6 Core Frontier Pillars

```
                               ┌────────────────────────────────────────────────────────┐
                               │                 UNLEASH-AGENT STUDIO                   │
                               └──────────────────────────┬─────────────────────────────┘
                                                          │
          ┌───────────────────────┬───────────────────────┼───────────────────────┬───────────────────────┐
          ▼                       ▼                       ▼                       ▼                       ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   1. CHAT ARENA  │    │  2. LLM STUDIO   │    │ 3. DYNAMIC SWARM │    │ 4. DUPLEX VOICE  │    │  5. 6-LAYER DOD  │
│ Unleash Executive│    │ Cloud QLoRA / T4 │    │ Sequential Relay │    │ Wake Word / Piper│    │ Docker / AST     │
│  Win32 Telemetry │    │ Ollama GGUF Bake │    │ Zero-Crash 6GB   │    │ Sub-15ms Barge-in│    │ Acceptance Gates │
└──────────────────┘    └──────────────────┘    └──────────────────┘    └──────────────────┘    └──────────────────┘
```

### 1️⃣ Parameter-Adaptive Executive OS Pilot & Dynamic Discovery
* **Parameter-Adaptive Architecture (`adaptive_tier.py`):** Automatically detects the active model size (`COMPACT ≤4B`, `BALANCED 5B–15B`, `FRONTIER ≥16B / Cloud`) and dynamically toggles compact context budgets, few-shot hints, Dynamic App/Search Grounding, and JSON auto-repair — extracting peak accuracy even from a **`1.5B` (`986 MB`)** model (`jarvis-qlora`) while dropping crutches on larger models.
* **Sub-20ms Telemetry & Lazy Docker:** Direct Win32 C-types hooks (`kernel32.GlobalMemoryStatusEx`, `nvidia-smi`) monitor RAM, VRAM, and thermals in `<20ms`, while Docker isolation starts lazily on demand for high-risk executions.
* **Dynamic Application Discovery (`app_discovery.py`):** Auto-indexes installed **Microsoft Store / UWP apps (`Get-StartApps`)**, **Start Menu `.lnk` shortcuts**, **Windows Registry (`App Paths`)**, and system `PATH` with fuzzy matching — zero static app lists.
* **Fast Live `web_lookup` & Browser Routing:** Opens Google/YouTube in your visible browser (`open_url`) when requested, or runs a 1-step `web_lookup` summary aloud for real-time internet facts while keeping reasoning local.

### 2️⃣ Full-Duplex Offline Voice & Floating 3D Gyro Sphere HUD
* **Offline Silero VAD + `faster-whisper` (`base`, INT8 CPU):** Rejects room noise before STT runs, with `hotwords` decoding, PCM gain/padding conditioning, and start-anchored wake-word matching (`"Hey Jarvis"`, or custom phrases in `voice_config.json`).
* **Sub-15ms Duplex Barge-In & Anti-Self-Echo Guard:** Hardware-level audio interrupt via Windows `winmm.dll` halts host speaker playback in `<15ms` on explicit stop/wake commands while ignoring speaker self-echo.
* **Floating 3D Gyro Sphere HUD (`jarvis_desktop_hud.py`):** Per-pixel alpha Win32 desktop widget (`0` GDI leaks) with steady idle light, voice-reactive **Listening pop** driven by live `mic_energy`, sapphire thinking sweep, and **Jarvis speech pop** — backed by offline **Piper ONNX TTS** (`jarvis-medium.onnx`).

### 3️⃣ LLM Studio & Cloud QLoRA Bridge
* **Zero-Overheating Dual-Tier Architecture:** Heavy fine-tuning runs on free cloud GPUs (Kaggle Dual T4), protecting local laptop GPUs from thermal stress.
* **Weight-Level Persona Grounding:** Compiles fine-tuned LoRA adapters into quantized GGUFs (`Q4_K_M`) and bakes Modelfiles directly into local Ollama—creating true synaptic identity rather than fragile system prompt wrappers.

### 4️⃣ Dynamic Hardware-Aware Swarm (Builder ➔ Verifier ➔ Auditor)
* **Sequential GPU Relay Mode:** On modest GPUs (≤16GB VRAM / RTX 3050 6GB), workers run in a synchronized relay, reusing in-memory resident weights with **zero display driver crashes and zero out-of-memory (OOM) errors**.
* **Parallel Cloud Mode:** Scales automatically to concurrent worker swarms when high-VRAM or cloud inference (Groq, OpenRouter) is active.

### 5️⃣ The 6-Layer Definition of Done (DoD) Gate
No code is marked "complete" without passing deterministic automated verification:
1. **Layer 1: AST Syntax Gate:** Validates AST tree integrity (`node -c`, Python `ast.parse`).
2. **Layer 2: Semantic Layout Parity:** Intercepts hollow, empty mockups.
3. **Layer 3: DOM Event Contract:** Validates that buttons and inputs are bound to working JS listeners.
4. **Layer 4: Anti-Placeholder Shield:** Catches lazy comment stubs like `// TODO: Implement` and auto-triggers self-repairs.
5. **Layer 5A & 5B: Isolated Docker & Browser Gates:** Headless Chromium DOM testing and air-gapped Docker test suites (`--network none`).
6. **Layer 6: AppSec & Secret Leakage Gate:** Scans for hardcoded credentials, API keys, and unsafe OS calls.

### 6️⃣ Mount Existing Repository & 3-Pass Surgical Diff
* **Instant Indexing:** Intelligently prunes `node_modules`, `venv`, and `.git`, indexing 20,000+ file projects in sub-second time.
* **Git Shadow Checkpoints:** Takes automated pre-execution snapshots with instant 1-click rollback.
* **3-Pass Surgical Diff:** Exact byte matching, line-ending normalization, and whitespace-trimmed block anchoring to modify files without token-burning full rewrites.

---

## ⚔️ How Unleash-Agent Studio Compares

| Feature | Raw Ollama CLI | Proprietary Cloud (Cursor / Copilot) | **Unleash-Agent Studio** |
| :--- | :---: | :---: | :---: |
| **Cost** | Free | \$20 – \$200+ / mo | **100% Free & Self-Hosted** |
| **Privacy & Air-Gap** | ✅ Local | ❌ Cloud telemetry / logging | **✅ 100% Offline Capable** |
| **OS & Hardware Telemetry** | ❌ None | ❌ None | **✅ Sub-20ms Win32 C-Types** |
| **Hands-Free Duplex Voice** | ❌ None | ❌ Basic Web Speech | **✅ Sub-15ms Barge-in + Piper ONNX** |
| **Weight-Level Fine-Tuning** | ❌ None | ❌ Closed proprietary models | **✅ 1-Click Kaggle Dual T4 Bridge** |
| **6GB Laptop GPU Stability** | ⚠️ OOM crashes | N/A (Cloud hosted) | **✅ 0-Crash VRAM Relay Guard** |
| **Task Execution** | ❌ Single turn text | ⚠️ Code diffs only | **✅ Dynamic App Discovery & Vision** |

---

## 🚀 Quickstart

### Prerequisites
* Windows 10/11, Linux, or macOS
* Python 3.10+
* [Ollama](https://ollama.com/) (for offline local models)
* [Docker Desktop](https://www.docker.com/) *(optional, for isolated backend container testing)*

### 1. Clone & Set Up Environment
```bash
git clone https://github.com/sanyam47/unleash-agent.git
cd unleash-agent

# Create virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate
# Mac / Linux:
source venv/bin/activate

# Install dependencies & Playwright
pip install -r requirements.txt
playwright install chromium
```

### 2. Launch Local Engine & Studio

#### ⚡ 1-Click Launch (Windows, macOS & Linux)
* **Windows:** Double-click `start_studio.bat` (or run `start_studio.bat` in cmd).
* **macOS / Linux:**
```bash
chmod +x start_studio.sh
./start_studio.sh
```
*Automatically audits Ollama status, frees stale port 8001, sets PYTHONPATH, and opens `http://localhost:8001` in your browser.*

#### Manual Launch (Terminal)
```bash
# Terminal 1: Start local Ollama daemon
ollama serve

# Terminal 2: Start Unleash-Agent Studio
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8001
```

Open your browser at **`http://127.0.0.1:8001`**.

---

## 🔒 Security & Air-Gap Guarantee
* **Zero Egress in Sandboxes:** Test containers execute strictly with `--network none` and `--read-only` root filesystems.
* **Path Traversal Protection:** Built-in path validators block agents from accessing or modifying OS system roots (`C:\Windows`, `/etc`, `/sys`).
* **Hardware Thermals First:** Adaptive compute tiers enforce VRAM safety quotas to protect physical consumer hardware.

---

## 📄 License & Commercial Rights

Unleash-Agent Studio is licensed under the **PolyForm Noncommercial License 1.0.0** with an available **Commercial Enterprise License**:

* **Community Non-Commercial Use (Free Forever):** Free for individuals, students, researchers, and hobbyists to study, run, and build on their personal machines.
* **Commercial Enterprise License:** Any commercial deployment, hosting as a paid SaaS/API, white-labeling, or enterprise internal deployment requires a written Commercial Enterprise License.
* **Author & Lead Architect:** Designed and engineered by **Sanyam** ([@sanyam47](https://github.com/sanyam47)).
* **Commercial Inquiries:** Contact [sanyam4747@gmail.com](mailto:sanyam4747@gmail.com).

See full terms in the [LICENSE](LICENSE) file.
