<div align="center">



# ⚡ Unleash-Agent

### The Autonomous Coding Agent Harness for Local & Cloud LLMs



**Unleash modest 8B & 14B open-source models to build real, interactive, full-stack web applications completely offline.**



[![GitHub stars](https://img.shields.io/badge/GitHub-Stars%20Welcome-yellow?style=flat-square&logo=github)](https://github.com/sanyam47/unleash-agent)

[![Local Inference](https://img.shields.io/badge/Local%20GPU-RTX%203050%2B-green?style=flat-square)](#)

[![Ollama Engine](https://img.shields.io/badge/Ollama-100%25%20Offline-black?style=flat-square&logo=ollama)](#)

[![Free Cloud Bridge](https://img.shields.io/badge/Free%20Cloud-Kaggle%20(30h)%20%7C%20Colab-blue?style=flat-square)](#)

[![License: MIT](https://img.shields.io/badge/License-MIT-purple.svg?style=flat-square)](LICENSE)



<br/>



*Zero API costs • Zero data leaks • Zero hallucinated DOM • Real OS Workspace persistence*



</div>



---



## 💡 Why Unleash-Agent?



Most developers assume lightweight local models (like **Llama 3 8B**, **Dolphin 3**, or **Qwen 2.5 Coder**) cannot write production software. Left to raw prompting, smaller models hit three walls:

1. **DOM Hallucinations:** They guess random element IDs and non-existent CSS selectors.

2. **Context Truncation:** Rewriting 200+ line files causes them to drop features or emit truncated snippets.

3. **Lazy Comment Stubs:** They cut corners with `// Logic goes here` or `<!-- ... (no changes needed) -->`.



**Unleash-Agent solves this through a deterministic agent harness.** Instead of trying to make the 8B model "smarter", we give it the spatial awareness, surgical tools, and compilation gates required to build working software reliably.



---



## 🛠️ The 6 Core Frontier Systems



```

                      ┌────────────────────────────────────────┐

                      │             User Prompt                │

                      │ ("Build a Cyberpunk Pomodoro Station") │

                      └───────────────────┬────────────────────┘

                                          │

                                          ▼

                      ┌────────────────────────────────────────┐

                      │    Autonomous Scout & Manifest Engine  │

                      │  (Architecture Contract & Goal Memory) │

                      └───────────────────┬────────────────────┘

                                          │

                                          ▼

            ┌────────────────────────────────────────────────────────────┐

            │            Antigravity Multi-Turn ReAct Loop               │

            │                                                            │

            │  1. Workspace Tree: Scans files & sizes before coding      │

            │  2. AST Symbol Table: Extracts active HTML IDs & JS state  │

            │  3. Surgical Patcher: Search & Replace (5-line diffs)      │

            │  4. Real OS Jail: Saves to default or chosen Windows path  │

            └─────────────────────────────┬──────────────────────────────┘

                                          │

                                          ▼

                      ┌────────────────────────────────────────┐

                      │  4-Layer Acceptance Gate (DoD Audit)   │

                      │  - Node.js syntax & JS compilation     │

                      │  - DOM listener & HTML ID contract     │

                      │  - Anti-placeholder & stub interception│

                      └───────────────────┬────────────────────┘

                                    │           │

                          [Errors Found]     [Passed 100%]

                                    │           │

                                    ▼           ▼

                      Autonomous Self-Repair   Live Interactive

                            Loop                 Browser App

```



### 1. 🌲 Interactive Workspace Tree Awareness

Before the model writes or edits code, the engine scans the active directory and injects a clean directory tree (`|-- index.html (1.2KB)`, `|-- styles.css (800B)`, `|-- app.js (2.1KB)`). The model always knows what files already exist before taking action.



### 2. 🧬 AST & DOM Symbol Table Injection

An AST and regex parsing engine extracts all active HTML IDs, CSS variables, and JavaScript state variables. When you ask to "add a button" or "fix the search", the model hooks directly into existing functions without inventing random new names.



### 3. 🎯 Surgical Code Patching (`edit_project_file`)

Instead of rewriting 200–400 lines of code across turns (which causes token truncation), the agent surgically searches and replaces only the 5–10 lines needed, keeping 100% of the surrounding styling and logic intact.



### 4. 🛡️ 5-Layer "Definition of Done" Acceptance Gate

The model is not allowed to simply declare "Done". A deterministic background gate audits:

* **Layer 1:** Node.js syntax & compilation check (`node -c`).

* **Layer 2:** Semantic layout & entity parity (no 1-div stubs).

* **Layer 3:** HTML-to-JS interactive contract (every button must have a listener).

* **Layer 4:** **Anti-Placeholder Shield:** Catches lazy comment stubs like `// Logic to handle search` or empty event listener callbacks and triggers an autonomous self-repair loop until the app actually functions!
* **Layer 5:** **Antigravity Headless Browser Runtime Gate:** Boots headless Chromium to execute the app live, traps unhandled exceptions/console crashes, dispatches synthetic user clicks to buttons, and verifies DOM state mutations before accepting the build!



### 5. 💻 Real OS Workspace Target & Memory

Unleash-Agent is not trapped in an isolated browser playground. You can target any real folder on your host machine:

> *"Create a portfolio site at `C:\coding\my-portfolio`"*



The engine safely validates OS paths (protecting system directories) and persists workspace bindings in `workspace_registry.json` across reboots.



### 6. 🔁 Autonomous Goal-Completion Loop (Micro-Goal Stepper)

Inspired by Devin and SWE-agent, Unleash-Agent never stops halfway. A dynamic goal decomposer breaks prompts into 2–4 atomic milestones (e.g. Layout & Theme, Feature Logic, Sound Feedback, Task Queue). A background stepper audits the workspace disk state after every turn, actively intercepting premature 'Final Answers' and driving autonomous continuation turns until all feature milestones are verified green.



---



## ⚡ 1-Click Free Cloud GPU Bridge (Kaggle & Colab)



Don't have a high-end local GPU? Unleash-Agent includes an on-demand Cloud Bridge:



| Provider | VRAM | Free Tier Limit | Runs Models |

| :--- | :--- | :--- | :--- |

| **Local Offline** | Your GPU (e.g. RTX 3050 6GB) | Unlimited / Free | 1.5B – 8B |

| **Kaggle Cloud** | **Dual Tesla T4 (30 GB VRAM)** | **30 Hours / Week (Free)** | 14B – 32B (Qwen 2.5 Coder) |

| **Google Colab** | **Tesla T4 (16 GB VRAM)** | **12 Hours / Session (Free)** | 14B (Qwen / DeepSeek) |

| **Paid On-Demand** | A100 / H100 / RTX 4090 | Live Credit Tracking ($) | 70B+ Frontier Weights |



Click **📋 Copy 1-Click Cloud Script** in the UI, run the 3-line notebook on Kaggle or Colab, paste your tunnel URL, and Unleash-Agent immediately begins streaming high-end 32B coding inference for free!



---



## 🚀 Quickstart



### Prerequisites

* Python 3.10+

* [Ollama](https://ollama.com/) (for offline local inference)



### 1. Clone & Install

```bash

git clone https://github.com/sanyam47/unleash-agent.git unleash-agent

cd unleash-agent

python -m venv venv

# Windows:

venv\Scripts\activate

# Mac/Linux:

source venv/bin/activate



pip install -r requirements.txt

```



### 2. Pull a Local Coding Model

```bash

ollama pull dolphin3:latest

# Or high-efficiency code specialist:

ollama pull qwen2.5-coder:7b

```



### 3. Launch Unleash-Agent

```bash

python scripts/run_server.py

```

Open your browser at **`http://127.0.0.1:8001/`** and start building!



---



## 🎮 Example Prompts to Try



* **Cyberpunk Focus Station:**  

  `"Build a modern Cyberpunk Focus & Pomodoro Station with a dark theme (#0d0f17, neon cyan #00f2fe and violet #8a2be2 accents). Include a 25-minute timer, controls, and task list with completion checkmarks."`



* **Real OS Workspace Target:**  

  `"Build a modern e-commerce storefront at C:\coding\my-store with shopping cart drawer and price calculations."`



* **Surgical Edit on Existing App:**  

  `"Add a sound effect toggle and filter tasks by completed status."`



---



## ⭐ Community & Feedback



If Unleash-Agent helps you run local agents without API costs, consider giving it a ⭐ on GitHub!



Found a bug or have a suggestion? Feel free to open an issue.



---



## 📄 License

This project is open-source under the [MIT License](LICENSE).

