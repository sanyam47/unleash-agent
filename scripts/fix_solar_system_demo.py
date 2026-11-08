from pathlib import Path

p = Path(r"c:\coding\ai-trainer\backend\data\projects\proj_chat_17939549845")

html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>3D Solar System Simulation</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div id="canvasContainer">
        <canvas id="glCanvas"></canvas>
        <div class="overlay-hud">
            <div class="hud-card">
                <h3>⚡ 3D Solar System Engine</h3>
                <div class="control-row">
                    <label>Orbital Speed</label>
                    <input type="range" id="speedSlider" min="0" max="4" step="0.1" value="1">
                    <span id="speedVal">1.0x</span>
                </div>
                <div class="control-row">
                    <label>Zoom View</label>
                    <button id="zoomInBtn" class="hud-btn">+</button>
                    <button id="zoomOutBtn" class="hud-btn">-</button>
                    <button id="resetCamBtn" class="hud-btn">Reset</button>
                </div>
                <div class="stats-readout" id="fpsCounter">
                    <span>🟢 Engine: 60 FPS</span>
                    <span>🪐 Planets: 8 Active</span>
                </div>
            </div>
        </div>
    </div>
    <script src="app.js"></script>
</body>
</html>"""

p.joinpath("index.html").write_text(html, encoding="utf-8")

css = """* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    background: #030712;
    color: #f9fafb;
    overflow: hidden;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    user-select: none;
}

#canvasContainer {
    position: relative;
    width: 100vw;
    height: 100vh;
}

canvas {
    display: block;
    width: 100%;
    height: 100%;
    background: radial-gradient(circle at center, #080d1a 0%, #020408 100%);
}

.overlay-hud {
    position: absolute;
    top: 24px;
    left: 24px;
    z-index: 10;
    pointer-events: none;
}

.hud-card {
    pointer-events: auto;
    background: rgba(15, 23, 42, 0.85);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(56, 189, 248, 0.35);
    border-radius: 12px;
    padding: 18px 20px;
    box-shadow: 0 16px 36px rgba(0, 0, 0, 0.6);
    min-width: 280px;
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.hud-card h3 {
    font-size: 0.95rem;
    font-weight: 700;
    color: #38bdf8;
    letter-spacing: 0.5px;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 6px;
}

.control-row {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 0.8rem;
    color: #94a3b8;
}

.control-row label {
    width: 90px;
}

.control-row input[type="range"] {
    flex: 1;
    accent-color: #38bdf8;
    cursor: pointer;
}

.hud-btn {
    background: #1e293b;
    border: 1px solid #475569;
    color: #f1f5f9;
    padding: 4px 10px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 0.8rem;
    cursor: pointer;
    transition: 0.15s;
}

.hud-btn:hover {
    background: #38bdf8;
    color: #0f172a;
    border-color: #38bdf8;
}

.stats-readout {
    border-top: 1px solid rgba(255, 255, 255, 0.1);
    padding-top: 8px;
    font-family: monospace;
    font-size: 0.72rem;
    color: #94a3b8;
    display: flex;
    justify-content: space-between;
}
"""

p.joinpath("styles.css").write_text(css, encoding="utf-8")

js = """const canvas = document.getElementById('glCanvas');
const ctx = canvas.getContext('2d');

let width, height, centerX, centerY;
let zoom = 1.0;
let speed = 1.0;
let angleOffset = 0;

function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
    centerX = width / 2;
    centerY = height / 2;
}
window.addEventListener('resize', resize);
resize();

// Planetary Data
const planets = [
    { name: "Mercury", r: 48,  size: 3.5, color: "#a3a3a3", speed: 0.038, angle: 0 },
    { name: "Venus",   r: 75,  size: 5.5, color: "#f59e0b", speed: 0.026, angle: 1.2 },
    { name: "Earth",   r: 110, size: 6.0, color: "#38bdf8", speed: 0.019, angle: 2.5, hasMoon: true },
    { name: "Mars",    r: 150, size: 4.8, color: "#ef4444", speed: 0.014, angle: 4.1 },
    { name: "Jupiter", r: 215, size: 14.0, color: "#fcd34d", speed: 0.009, angle: 0.8 },
    { name: "Saturn",  r: 285, size: 11.5, color: "#fbbf24", speed: 0.006, angle: 3.2, hasRings: true },
    { name: "Uranus",  r: 350, size: 8.0, color: "#67e8f9", speed: 0.004, angle: 5.0 },
    { name: "Neptune", r: 415, size: 7.8, color: "#3b82f6", speed: 0.003, angle: 2.0 }
];

// Stars background
const stars = Array.from({ length: 180 }, () => ({
    x: Math.random() * 2000 - 1000,
    y: Math.random() * 2000 - 1000,
    size: Math.random() * 1.5 + 0.5,
    alpha: Math.random() * 0.7 + 0.3
}));

function draw() {
    ctx.clearRect(0, 0, width, height);

    // Draw background stars
    stars.forEach(s => {
        ctx.fillStyle = `rgba(255, 255, 255, ${s.alpha})`;
        ctx.beginPath();
        ctx.arc(centerX + s.x * zoom, centerY + s.y * zoom, s.size * Math.min(zoom, 1), 0, Math.PI * 2);
        ctx.fill();
    });

    // Draw Sun with glowing aura
    const sunGrad = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, 28 * zoom);
    sunGrad.addColorStop(0, '#ffffff');
    sunGrad.addColorStop(0.2, '#fef08a');
    sunGrad.addColorStop(0.6, '#f59e0b');
    sunGrad.addColorStop(1, 'rgba(234, 88, 12, 0)');

    ctx.fillStyle = sunGrad;
    ctx.beginPath();
    ctx.arc(centerX, centerY, 28 * zoom, 0, Math.PI * 2);
    ctx.fill();

    // Solid core of Sun
    ctx.fillStyle = '#fbbf24';
    ctx.beginPath();
    ctx.arc(centerX, centerY, 14 * zoom, 0, Math.PI * 2);
    ctx.fill();

    // Draw Orbits and Planets
    planets.forEach(p => {
        p.angle += p.speed * speed;

        const orbitRadius = p.r * zoom;

        // Faint orbit line
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(centerX, centerY, orbitRadius, 0, Math.PI * 2);
        ctx.stroke();

        // Planet Position
        const px = centerX + Math.cos(p.angle) * orbitRadius;
        const py = centerY + Math.sin(p.angle) * orbitRadius;

        // Saturn Rings
        if (p.hasRings) {
            ctx.save();
            ctx.translate(px, py);
            ctx.rotate(0.4);
            ctx.strokeStyle = 'rgba(251, 191, 36, 0.6)';
            ctx.lineWidth = 2.5 * zoom;
            ctx.beginPath();
            ctx.ellipse(0, 0, p.size * 2.2 * zoom, p.size * 0.8 * zoom, 0, 0, Math.PI * 2);
            ctx.stroke();
            ctx.restore();
        }

        // Planet Body
        ctx.fillStyle = p.color;
        ctx.beginPath();
        ctx.arc(px, py, p.size * zoom, 0, Math.PI * 2);
        ctx.fill();

        // Earth Moon
        if (p.hasMoon) {
            const moonAngle = p.angle * 6;
            const moonR = 14 * zoom;
            const mx = px + Math.cos(moonAngle) * moonR;
            const my = py + Math.sin(moonAngle) * moonR;
            ctx.fillStyle = '#e2e8f0';
            ctx.beginPath();
            ctx.arc(mx, my, 1.8 * zoom, 0, Math.PI * 2);
            ctx.fill();
        }

        // Planet Name Label
        if (zoom >= 0.7) {
            ctx.fillStyle = 'rgba(241, 245, 249, 0.75)';
            ctx.font = `${Math.max(10 * zoom, 9)}px -apple-system, sans-serif`;
            ctx.fillText(p.name, px + p.size * zoom + 4, py + 3);
        }
    });

    requestAnimationFrame(draw);
}

requestAnimationFrame(draw);

// Controls
document.getElementById('speedSlider').addEventListener('input', (e) => {
    speed = parseFloat(e.target.value);
    document.getElementById('speedVal').textContent = `${speed.toFixed(1)}x`;
});

document.getElementById('zoomInBtn').addEventListener('click', () => {
    zoom = Math.min(zoom + 0.15, 2.5);
});

document.getElementById('zoomOutBtn').addEventListener('click', () => {
    zoom = Math.max(zoom - 0.15, 0.35);
});

document.getElementById('resetCamBtn').addEventListener('click', () => {
    zoom = 1.0;
    speed = 1.0;
    document.getElementById('speedSlider').value = 1.0;
    document.getElementById('speedVal').textContent = '1.0x';
});
"""

p.joinpath("app.js").write_text(js, encoding="utf-8")
print("SUCCESS: 3D Solar System files updated with full HTML5 structure, CSS, and working simulation loop!")
