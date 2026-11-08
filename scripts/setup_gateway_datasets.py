import json
from pathlib import Path

DATASETS_DIR = Path(r"c:\coding\ai-trainer\backend\data\gateway_datasets")
DATASETS_DIR.mkdir(parents=True, exist_ok=True)

datasets = [
    {
        "id": "webgl_3d_graphics",
        "name": "3D WebGL & Canvas Graphics Engine",
        "description": "Interactive 3D scenes, solar systems, particle networks, and spatial camera controls",
        "keywords": ["3d", "solar system", "webgl", "threejs", "three.js", "planet", "orbit", "space", "particles", "cube", "sphere", "camera"],
        "architecture": {
            "archetype": "3D Interactive Graphics",
            "html_scaffold": "<div id='canvasContainer'><canvas id='glCanvas'></canvas><div class='overlay-hud'><div class='hud-card'><h3>3D Scene Controls</h3><div class='control-row'><label>Rotation Speed</label><input type='range' id='speedSlider' min='0' max='5' step='0.1' value='1'></div><div class='control-row'><label>Orbit Zoom</label><button id='zoomInBtn'>+</button><button id='zoomOutBtn'>-</button></div><div class='stats-readout' id='fpsCounter'>FPS: 60 | Entities: Active</div></div></div></div>",
            "css_design_system": "* { margin: 0; padding: 0; box-sizing: border-box; } body { background: #030712; color: #f9fafb; overflow: hidden; font-family: -apple-system, sans-serif; } #canvasContainer { position: relative; width: 100vw; height: 100vh; } canvas { display: block; width: 100%; height: 100%; } .overlay-hud { position: absolute; top: 20px; left: 20px; z-index: 10; pointer-events: none; } .hud-card { pointer-events: auto; background: rgba(15, 23, 42, 0.85); backdrop-filter: blur(12px); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 10px; padding: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); min-width: 240px; }",
            "js_state_machine": "const state = { speed: 1.0, zoom: 1.0, angle: 0, entities: [] }; function initScene() { const canvas = document.getElementById('glCanvas'); const ctx = canvas.getContext('2d'); function resize() { canvas.width = window.innerWidth; canvas.height = window.innerHeight; } window.addEventListener('resize', resize); resize(); // Render loop with 3D projection math requestAnimationFrame(renderLoop); } function renderLoop(timestamp) { // Projection, lighting math, orbital angles requestAnimationFrame(renderLoop); }"
        }
    },
    {
        "id": "audio_music_synthesis",
        "name": "Web Audio API Synthesizer & Sound Deck",
        "description": "Interactive sound generation, audio nodes, oscillators, musical keys, and visualizers",
        "keywords": ["audio", "synthesizer", "synth", "piano", "sound", "frequency", "oscillator", "music", "notes", "waveform", "volume", "beats"],
        "architecture": {
            "archetype": "Web Audio Synthesis",
            "html_scaffold": "<header class='audio-header'><h2>⚡ CyberSynth FX-800</h2><span class='badge'>Web Audio API Active</span></header><main class='rack-container'><div class='dial-rack'><div class='dial-group'><label>Waveform</label><select id='waveSelect'><option value='sine'>Sine (Smooth)</option><option value='sawtooth'>Sawtooth (Buzzy)</option><option value='square'>Square (Retro 8-Bit)</option><option value='triangle'>Triangle (Flute)</option></select></div><div class='dial-group'><label>Master Gain</label><input type='range' id='volSlider' min='0' max='1' step='0.05' value='0.3'></div><div class='dial-group'><label>Filter Cutoff (Hz)</label><input type='range' id='filterSlider' min='200' max='8000' value='2500'></div></div><div class='piano-keyboard' id='keyboard'></div><canvas id='oscilloscope' width='600' height='120'></canvas></main>",
            "css_design_system": "body { background: #0b0f19; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; display: flex; flex-direction: column; align-items: center; min-height: 100vh; padding: 24px; } .rack-container { background: #161e2e; border: 2px solid #2d3748; border-radius: 12px; padding: 24px; width: 100%; max-width: 800px; box-shadow: 0 20px 40px rgba(0,0,0,0.6); } .dial-rack { display: flex; gap: 20px; margin-bottom: 24px; flex-wrap: wrap; } .piano-keyboard { display: flex; height: 160px; position: relative; border-radius: 6px; overflow: hidden; background: #fff; border: 1px solid #111; } .key-white { flex: 1; background: #fff; border-right: 1px solid #ccc; cursor: pointer; transition: 0.1s; } .key-white:active, .key-white.active { background: #60a5fa; }",
            "js_state_machine": "let audioCtx = null; function getAudioContext() { if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)(); return audioCtx; } function playTone(freq) { const ctx = getAudioContext(); const osc = ctx.createOscillator(); const gain = ctx.createGain(); osc.type = document.getElementById('waveSelect').value; osc.frequency.setValueAtTime(freq, ctx.currentTime); gain.gain.setValueAtTime(parseFloat(document.getElementById('volSlider').value), ctx.currentTime); gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.6); osc.connect(gain); gain.connect(ctx.destination); osc.start(); osc.stop(ctx.currentTime + 0.6); }"
        }
    },
    {
        "id": "arcade_canvas_gaming",
        "name": "HTML5 Canvas 2D Game Loop Engine",
        "description": "High-performance arcade games, state machines, physics, collision detection, and score persistence",
        "keywords": ["game", "snake", "pong", "arcade", "tetris", "breakout", "flappy", "canvas", "score", "collision", "arrow keys"],
        "architecture": {
            "archetype": "Arcade 2D Game",
            "html_scaffold": "<div class='game-wrapper'><header class='score-banner'><div>SCORE: <span id='currentScore' class='highlight'>0</span></div><div>HIGH SCORE: <span id='highScore'>0</span></div></header><canvas id='gameCanvas' width='500' height='500'></canvas><div class='game-controls'><button id='startBtn' class='btn-primary'>Start Game</button><span class='hint'>Use Arrow Keys [↑ ↓ ← →] or WASD to navigate</span></div></div>",
            "css_design_system": "body { background: #090d16; color: #fff; font-family: monospace; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; } .game-wrapper { display: flex; flex-direction: column; align-items: center; gap: 14px; background: #131b2e; padding: 20px; border-radius: 12px; border: 2px solid #2563eb; box-shadow: 0 0 30px rgba(37,99,235,0.3); } canvas { background: #050811; border: 2px solid #1e293b; border-radius: 8px; image-rendering: pixelated; } .highlight { color: #10b981; font-weight: bold; }",
            "js_state_machine": "const state = { running: false, score: 0, highScore: parseInt(localStorage.getItem('hiScore') || '0'), grid: 20 }; const canvas = document.getElementById('gameCanvas'); const ctx = canvas.getContext('2d'); window.addEventListener('keydown', (e) => { /* handle inputs */ }); function gameLoop(time) { if (!state.running) return; update(); render(); requestAnimationFrame(gameLoop); }"
        }
    },
    {
        "id": "saas_analytics_telemetry",
        "name": "SaaS Analytics & Telemetry Dashboard",
        "description": "Executive metrics, KPI cards, SVG trend charts, time-range toggles, and searchable data tables",
        "keywords": ["dashboard", "analytics", "saas", "kpi", "metrics", "chart", "telemetry", "monitoring", "crypto", "table", "admin"],
        "architecture": {
            "archetype": "Analytics Dashboard",
            "html_scaffold": "<div class='app-layout'><aside class='sidebar'><div class='brand'>⚡ PulseAI</div><nav class='nav-links'><a href='#' class='active'>📊 Overview</a><a href='#'>📈 Telemetry</a><a href='#'>🔒 Security</a><a href='#'>⚙️ Settings</a></nav></aside><main class='content-area'><header class='topbar'><h2>Operations Telemetry</h2><div class='time-pills'><button class='pill active' data-range='24h'>24h</button><button class='pill' data-range='7d'>7d</button><button class='pill' data-range='30d'>30d</button></div></header><div class='kpi-grid' id='kpiContainer'></div><div class='chart-card'><h3>Requests & Throughput (req/sec)</h3><div class='svg-chart-wrap' id='chartArea'></div></div><div class='table-card'><div class='table-header'><h3>Service Health</h3><input type='text' id='tableFilter' placeholder='Search services...'></div><table id='dataTable'><thead><tr><th>Service</th><th>Latency</th><th>Uptime</th><th>Status</th></tr></thead><tbody id='tableBody'></tbody></table></div></main></div>",
            "css_design_system": ":root { --bg: #090b10; --card: #121620; --border: #232a3b; --text: #f1f5f9; --accent: #38bdf8; } body { background: var(--bg); color: var(--text); font-family: -apple-system, sans-serif; margin: 0; } .app-layout { display: flex; min-height: 100vh; } .sidebar { width: 220px; background: #0d1117; border-right: 1px solid var(--border); padding: 20px; } .content-area { flex: 1; padding: 24px; overflow-y: auto; } .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; } .kpi-card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 18px; }",
            "js_state_machine": "const dataset = [ { name: 'Auth Gateway', latency: '24ms', uptime: '99.98%', status: 'Healthy' }, { name: 'Neural Inference Engine', latency: '68ms', uptime: '99.91%', status: 'Healthy' }, { name: 'Vector Database RAG', latency: '112ms', uptime: '99.85%', status: 'Warning' } ]; function renderTable(items) { const tbody = document.getElementById('tableBody'); tbody.innerHTML = items.map(i => `<tr><td>${i.name}</td><td>${i.latency}</td><td>${i.uptime}</td><td><span class='badge ${i.status.toLowerCase()}'>${i.status}</span></td></tr>`).join(''); } document.getElementById('tableFilter').addEventListener('input', (e) => { const q = e.target.value.toLowerCase(); renderTable(dataset.filter(d => d.name.toLowerCase().includes(q))); }); renderTable(dataset);"
        }
    },
    {
        "id": "productivity_task_tools",
        "name": "Stateful Web Productivity & Kanban Tool",
        "description": "Interactive workflow applications, task boards, markdown previewers, and local state persistence",
        "keywords": ["kanban", "todo", "task", "markdown", "editor", "calculator", "notes", "pomodoro", "timer", "drag and drop", "board"],
        "architecture": {
            "archetype": "Productivity Application",
            "html_scaffold": "<header class='app-header'><h1>⚡ FlowTask Kanban</h1><div class='header-actions'><input type='text' id='newTaskInput' placeholder='New task title...'><button id='addTaskBtn' class='btn-add'>+ Add Task</button></div></header><main class='board-container'><div class='column' id='colTodo'><h3>To Do (<span class='count'>0</span>)</h3><div class='card-list' data-status='todo'></div></div><div class='column' id='colProgress'><h3>In Progress (<span class='count'>0</span>)</h3><div class='card-list' data-status='progress'></div></div><div class='column' id='colDone'><h3>Completed (<span class='count'>0</span>)</h3><div class='card-list' data-status='done'></div></div></main>",
            "css_design_system": "body { background: #0f172a; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 0; padding: 20px; } .board-container { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; max-width: 1200px; margin: 20px auto; } .column { background: #1e293b; border-radius: 10px; padding: 16px; border: 1px solid #334155; min-height: 400px; } .task-card { background: #0f172a; border: 1px solid #475569; border-radius: 6px; padding: 12px; margin-bottom: 10px; cursor: pointer; transition: 0.15s; } .task-card:hover { border-color: #38bdf8; transform: translateY(-2px); }",
            "js_state_machine": "let tasks = JSON.parse(localStorage.getItem('flow_tasks') || '[]'); function saveAndRender() { localStorage.setItem('flow_tasks', JSON.stringify(tasks)); renderBoard(); } function renderBoard() { ['todo', 'progress', 'done'].forEach(status => { const list = document.querySelector(`.card-list[data-status='${status}']`); const filtered = tasks.filter(t => t.status === status); list.innerHTML = filtered.map(t => `<div class='task-card' onclick='cycleStatus(${t.id})'><span>${t.title}</span><button onclick='deleteTask(${t.id}, event)'>&times;</button></div>`).join(''); }); }"
        }
    },
    {
        "id": "ecommerce_marketplace",
        "name": "E-Commerce Store & Shopping Cart Engine",
        "description": "Retail catalog, department filters, search autocomplete, responsive product grid, and slide-out cart",
        "keywords": ["ecommerce", "e-commerce", "store", "shop", "amazon", "cart", "product", "checkout", "marketplace", "retail", "buy"],
        "architecture": {
            "archetype": "E-Commerce Marketplace",
            "html_scaffold": "<header class='nav-bar'><div class='nav-brand'>⚡ HyperStore</div><div class='nav-search'><select id='catFilter'><option value='all'>All Depts</option><option value='gear'>Hardware</option><option value='audio'>Audio</option></select><input type='text' id='searchInput' placeholder='Search catalog...'></div><div class='cart-trigger' id='openCartBtn'>🛒 Cart (<span id='cartCount'>0</span>)</div></header><main class='store-grid' id='productGrid'></main><div class='cart-drawer' id='cartDrawer'><div class='drawer-header'><h3>Cart (<span id='drawerCount'>0</span>)</h3><button id='closeCartBtn'>&times;</button></div><div class='drawer-body' id='cartList'></div><div class='drawer-footer'><div class='total-row'><span>Total:</span><strong id='cartSubtotal'>$0.00</strong></div><button class='btn-checkout' id='checkoutBtn'>Checkout</button></div></div>",
            "css_design_system": ":root { --bg: #eaeded; --header: #131921; --accent: #f0c14b; --card: #ffffff; } body { background: var(--bg); margin: 0; font-family: -apple-system, sans-serif; } .nav-bar { background: var(--header); color: #fff; padding: 12px 20px; display: flex; align-items: center; justify-content: space-between; gap: 16px; position: sticky; top: 0; z-index: 100; } .store-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; max-width: 1400px; margin: 24px auto; padding: 0 16px; } .product-card { background: var(--card); border: 1px solid #d5d9d9; border-radius: 8px; padding: 16px; display: flex; flex-direction: column; justify-content: space-between; }",
            "js_state_machine": "const catalog = [ { id: 1, name: 'Neural Processor NX', price: 599.99, cat: 'gear', rating: 4.8 }, { id: 2, name: 'Quantum Headset', price: 249.50, cat: 'audio', rating: 4.6 } ]; let cart = []; function addToCart(id) { const item = catalog.find(p => p.id === id); const inCart = cart.find(c => c.id === id); if (inCart) inCart.qty++; else cart.push({...item, qty: 1}); updateCart(); } function updateCart() { document.getElementById('cartCount').textContent = cart.reduce((s,i) => s + i.qty, 0); }"
        }
    },
    {
        "id": "developer_portfolio_agency",
        "name": "Developer Portfolio & Agency Showcase",
        "description": "Interactive developer portfolio, live project showcase modal, skills grid, and contact form validation",
        "keywords": ["portfolio", "resume", "agency", "cv", "personal", "showcase", "developer", "freelancer", "designer portfolio"],
        "architecture": {
            "archetype": "Developer Portfolio",
            "html_scaffold": "<header class='nav-header'><div class='logo'>&lt;Developer /&gt;</div><nav class='nav-menu'><a href='#about'>About</a><a href='#projects'>Projects</a><a href='#skills'>Skills</a><a href='#contact'>Contact</a></nav></header><section class='hero' id='about'><span class='status-pill'>🟢 Available for Opportunities</span><h1>Senior Full-Stack & Systems Architect</h1><p>Crafting high-throughput, air-gapped systems and polished user experiences.</p></section><section class='projects' id='projects'><h2>Featured Projects</h2><div class='filters'><button class='f-btn active' data-filter='all'>All</button><button class='f-btn' data-filter='ai'>AI & Systems</button><button class='f-btn' data-filter='web'>Web Apps</button></div><div class='project-grid' id='projGrid'></div></section>",
            "css_design_system": "body { background: #0a0e17; color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 0; line-height: 1.6; } .nav-header { display: flex; justify-content: space-between; align-items: center; padding: 20px 40px; background: rgba(10, 14, 23, 0.8); backdrop-filter: blur(10px); position: sticky; top: 0; z-index: 100; border-bottom: 1px solid #1e293b; } .hero { max-width: 900px; margin: 80px auto; text-align: center; padding: 0 20px; } .project-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px; max-width: 1100px; margin: 40px auto; padding: 0 20px; }",
            "js_state_machine": "const projects = [ { title: 'Local AI Trainer Studio', cat: 'ai', desc: 'Air-gapped LLM orchestration engine with ReAct agent loop.', tech: ['Python', 'FastAPI', 'Ollama'] }, { title: 'CyberStore Prime', cat: 'web', desc: 'Modern responsive e-commerce application with live preview.', tech: ['HTML5', 'CSS Grid', 'Vanilla JS'] } ]; function renderProjects(items) { document.getElementById('projGrid').innerHTML = items.map(p => `<div class='card'><h3>${p.title}</h3><p>${p.desc}</p><div class='tags'>${p.tech.map(t => `<span>${t}</span>`).join('')}</div></div>`).join(''); } renderProjects(projects);"
        }
    },
    {
        "id": "cybersecurity_terminal_tools",
        "name": "Cybersecurity & Terminal Matrix Workstation",
        "description": "Interactive retro/cyber hacker terminal, matrix rain canvas, real-time command parser, and security log analyzer",
        "keywords": ["terminal", "hacker", "cyber", "matrix", "security", "cli", "console", "packet", "scanner", "shell", "soc"],
        "architecture": {
            "archetype": "Cyber Terminal & Security Console",
            "html_scaffold": "<div class='terminal-frame'><div class='terminal-titlebar'><div class='dots'><span class='dot r'></span><span class='dot y'></span><span class='dot g'></span></div><span class='title'>CYBER_OS v4.2 [SECURE CONNECTION]</span></div><div class='terminal-body' id='terminalBody'><div class='log-line'>System initialized. Type <span class='cmd'>help</span> to list commands.</div><div class='input-line'><span class='prompt'>root@cyber-deck:~$</span><input type='text' id='termInput' autofocus autocomplete='off'></div></div></div><canvas id='matrixBg'></canvas>",
            "css_design_system": "body { background: #000; color: #00ff66; font-family: 'Courier New', Courier, monospace; margin: 0; overflow: hidden; height: 100vh; display: flex; justify-content: center; align-items: center; } #matrixBg { position: fixed; inset: 0; z-index: 1; opacity: 0.35; } .terminal-frame { position: relative; z-index: 10; width: 850px; max-width: 95%; height: 520px; background: rgba(5, 10, 8, 0.92); border: 1px solid #00ff66; border-radius: 8px; box-shadow: 0 0 30px rgba(0,255,102,0.25); display: flex; flex-direction: column; overflow: hidden; } .terminal-titlebar { background: #0d1a12; padding: 8px 12px; display: flex; align-items: center; border-bottom: 1px solid #00ff66; } .terminal-body { flex: 1; padding: 16px; overflow-y: auto; } input { background: transparent; border: none; color: #fff; font-family: inherit; font-size: 1rem; outline: none; flex: 1; margin-left: 8px; }",
            "js_state_machine": "const commands = { help: 'Available: scan, status, matrix, clear, date', status: 'All local defenses active. Air-gapped isolation: 100%.', scan: 'Scanning ports... 80: OPEN, 443: OPEN, 8001: AIR-GAPPED.', clear: () => { document.getElementById('terminalBody').innerHTML = ''; } }; document.getElementById('termInput').addEventListener('keydown', (e) => { if (e.key === 'Enter') { const cmd = e.target.value.trim().toLowerCase(); handleCommand(cmd); e.target.value = ''; } });"
        }
    }
]

for ds in datasets:
    out_file = DATASETS_DIR / f"{ds['id']}.json"
    out_file.write_text(json.dumps(ds, indent=2), encoding="utf-8")
    print(f"Created dataset: {out_file.name}")

print(f"\nSUCCESS: Populated {len(datasets)} modular gateway datasets in {DATASETS_DIR}")
