import re

# 1. Update style_v2.css
css_path = r'c:\coding\ai-trainer\frontend\style_v2.css'
with open(css_path, 'r', encoding='utf-8') as f:
    css = f.read()

# Make sure status-dot has 5px, no box-shadow
css = re.sub(
    r'\.status-dot\s*\{[^}]*\}',
    '''.status-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #10b981;
    opacity: 0.85;
    box-shadow: none !important;
}''',
    css
)

css = re.sub(
    r'\.telemetry-item\s+\.status-dot\s*\{[^}]*\}',
    '''.telemetry-item .status-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #10b981;
    opacity: 0.85;
    box-shadow: none !important;
}''',
    css
)

# Ensure no box-shadow remains
css = css.replace('box-shadow: 0 0 6px rgba(16, 185, 129, 0.35);', 'box-shadow: none !important;')

with open(css_path, 'w', encoding='utf-8') as f:
    f.write(css)
print('style_v2.css refined.')

# 2. Update script_v2.js
js_path = r'c:\coding\ai-trainer\frontend\script_v2.js'
with open(js_path, 'r', encoding='utf-8') as f:
    js = f.read()

# Replace online / offline badges in refreshChatStatus
js = re.sub(
    r'if\s*\(\s*data\.status\s*===\s*[\'"]online[\'"]\s*\)\s*\{[\s\S]*?else\s*\{[\s\S]*?\}\s*\}',
    '''if (data.status === 'online') {
            if (badge) {
                badge.style.background = 'rgba(255, 255, 255, 0.03)';
                badge.style.color = 'var(--text-secondary)';
                badge.style.borderColor = 'var(--border-subtle)';
                badge.innerHTML = '<span style="width: 5px; height: 5px; border-radius: 50%; background: #10b981; opacity: 0.85; display: inline-block;"></span> Ollama Local (11434)';
            }
            if (navBadge) {
                navBadge.style.background = 'transparent';
                navBadge.style.color = 'var(--text-secondary)';
                navBadge.style.borderColor = 'transparent';
                navBadge.innerHTML = '<span style="width: 5px; height: 5px; border-radius: 50%; background: #10b981; opacity: 0.85; display: inline-block;"></span> Ollama 11434 Ready';
            }
            if (startBtn) startBtn.style.display = 'none';
        } else {
            if (badge) {
                badge.style.background = 'rgba(255, 255, 255, 0.03)';
                badge.style.color = 'var(--text-muted)';
                badge.style.borderColor = 'var(--border-subtle)';
                badge.innerHTML = '<span style="width: 5px; height: 5px; border-radius: 50%; background: #f43f5e; opacity: 0.85; display: inline-block;"></span> Ollama Offline';
            }
            if (navBadge) {
                navBadge.style.background = 'transparent';
                navBadge.style.color = 'var(--text-muted)';
                navBadge.style.borderColor = 'transparent';
                navBadge.innerHTML = '<span style="width: 5px; height: 5px; border-radius: 50%; background: #f43f5e; opacity: 0.85; display: inline-block;"></span> Ollama Offline';
            }
            if (startBtn) startBtn.style.display = 'inline-block';
        }''',
    js,
    count=1
)

# Replace docker status in refreshDockerStatus
docker_pattern = r'if\s*\(\s*data\.status\s*===\s*[\'"]online[\'"]\s*\)\s*\{[\s\S]*?else\s*\{[\s\S]*?btnText\.textContent\s*=\s*data\.installed\s*\?\s*[\'"]Start Docker[\'"]\s*:\s*[\'"]Enable Docker[\'"];\s*\}'
js = re.sub(
    docker_pattern,
    '''if (data.status === 'online') {
            if (badge) {
                badge.style.background = 'rgba(255, 255, 255, 0.03)';
                badge.style.borderColor = 'var(--border-subtle)';
                badge.style.color = 'var(--text-secondary)';
            }
            if (dot) {
                dot.style.display = 'inline-block';
                dot.style.width = '5px';
                dot.style.height = '5px';
                dot.style.background = '#10b981';
                dot.style.opacity = '0.85';
            }
            if (text) {
                text.textContent = data.cyber_image_ready ? 'Docker: cyber-sandbox Ready' : 'Docker: Linux Online';
            }
            if (btn) {
                btn.className = 'btn-quiet';
                btn.style.background = 'transparent';
                btn.style.borderColor = 'var(--border-subtle)';
                btn.style.color = 'var(--text-secondary)';
                btn.title = 'Stop Docker and reclaim 1.5 GB RAM';
            }
            if (icon) icon.textContent = '';
            if (btnText) btnText.textContent = 'Stop Docker';
        } else {
            if (badge) {
                badge.style.background = 'rgba(255, 255, 255, 0.03)';
                badge.style.borderColor = 'var(--border-subtle)';
                badge.style.color = 'var(--text-muted)';
            }
            if (dot) {
                dot.style.display = 'inline-block';
                dot.style.width = '5px';
                dot.style.height = '5px';
                dot.style.background = 'var(--text-muted)';
            }
            if (text) text.textContent = 'Docker: Offline (Windows Sandbox)';
            if (btn) {
                btn.className = 'btn-quiet';
                btn.style.background = 'transparent';
                btn.style.borderColor = 'var(--border-subtle)';
                btn.style.color = 'var(--text-secondary)';
                btn.title = data.installed ? 'Start Docker Linux container sandbox' : 'Install or start Docker Desktop';
            }
            if (icon) icon.textContent = '';
            if (btnText) btnText.textContent = data.installed ? 'Start Docker' : 'Enable Docker';
        }''',
    js,
    count=1
)

# Replace Agentic toggle in updateAgenticModeUI
agentic_pattern = r'if\s*\(\s*window\.agenticModeEnabled\s*\)\s*\{[\s\S]*?title\s*=\s*[\'"][^\'"]*Standard Chat Mode[^\'"]*[\'"];\s*\}'
js = re.sub(
    agentic_pattern,
    '''if (window.agenticModeEnabled) {
        label.textContent = 'ON';
        btn.style.color = 'var(--text-primary)';
        btn.style.borderColor = 'var(--border-strong)';
        btn.style.background = 'rgba(255, 255, 255, 0.08)';
        btn.title = 'Antigravity ReAct Agent Active: Multi-Step Tool Calling & Project File Creation Enabled';
    } else {
        label.textContent = 'OFF';
        btn.style.color = 'var(--text-muted)';
        btn.style.borderColor = 'var(--border-subtle)';
        btn.style.background = 'transparent';
        btn.title = 'Standard Chat Mode (Click to enable Antigravity ReAct Agent)';
    }''',
    js,
    count=1
)

with open(js_path, 'w', encoding='utf-8') as f:
    f.write(js)
print('script_v2.js refined.')

# 3. Update index.html
html_path = r'c:\coding\ai-trainer\frontend\index.html'
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

# In header:
# Replace command palette trigger button style
html = html.replace(
    '<button type="button" onclick="openCommandPalette()" class="cmd-palette-trigger" title="Open Command Palette (Ctrl+K)">',
    '<button type="button" onclick="openCommandPalette()" class="cmd-palette-trigger" title="Open Command Palette (Ctrl+K)" style="background: transparent; border: 1px solid var(--border-subtle); color: var(--text-secondary);">'
)

# Replace themeToggleBtn style
html = html.replace(
    '<button id="themeToggleBtn" type="button" onclick="toggleTheme()" class="btn-quiet" style="font-size: 0.74rem; padding: 3px 8px;" title="Toggle Light / Dark theme">',
    '<button id="themeToggleBtn" type="button" onclick="toggleTheme()" class="btn-quiet" style="font-size: 0.74rem; padding: 3px 8px; background: transparent; border: 1px solid var(--border-subtle); color: var(--text-muted);" title="Toggle Light / Dark theme">'
)

# In Chat Arena:
# Replace Import chats button
html = html.replace(
    '<button type="button" onclick="openImportChatsModal()" class="btn-quiet" style="font-size: 0.68rem; padding: 2px 7px; color: #60a5fa; border-color: rgba(59, 130, 246, 0.3);" title="Import chats from another model">',
    '<button type="button" onclick="openImportChatsModal()" class="btn-quiet" style="font-size: 0.68rem; padding: 2px 7px; color: var(--text-secondary); border-color: var(--border-subtle);" title="Import chats from another model">'
)

# Replace Skills button in Chat Arena toolbar
html = html.replace(
    '<button type="button" onclick="openChatSkillsQuickModal()" id="btnChatSkillsToggle" class="btn-quiet" style="font-size: 0.74rem; display: inline-flex; align-items: center; gap: 5px; color: #60a5fa; border-color: rgba(59, 130, 246, 0.3);">',
    '<button type="button" onclick="openChatSkillsQuickModal()" id="btnChatSkillsToggle" class="btn-quiet" style="font-size: 0.74rem; display: inline-flex; align-items: center; gap: 5px; color: var(--text-secondary); border-color: var(--border-subtle);">'
)

# Replace Agentic button initial inline style in Chat Arena toolbar
html = html.replace(
    '<button type="button" id="btnAgenticModeToggle" onclick="toggleAgenticMode()" class="btn-quiet" style="font-size: 0.74rem; display: inline-flex; align-items: center; gap: 5px; color: #38bdf8; border-color: rgba(56, 189, 248, 0.3); background: rgba(56, 189, 248, 0.06); font-weight: 600;"',
    '<button type="button" id="btnAgenticModeToggle" onclick="toggleAgenticMode()" class="btn-quiet" style="font-size: 0.74rem; display: inline-flex; align-items: center; gap: 5px; color: var(--text-secondary); border-color: var(--border-subtle); background: transparent; font-weight: 500;"'
)

# Replace Clear All button inline hover styling in Chat Arena sidebar footer
html = html.replace(
    """onmouseenter="this.style.color='#f43f5e'" onmouseleave="this.style.color='var(--text-muted)'">Clear All</button>""",
    """onmouseenter="this.style.color='var(--text-primary)'" onmouseleave="this.style.color='var(--text-muted)'">Clear All</button>"""
)

# In footer telemetry bar:
# Replace telemetry-cmd-btn
html = html.replace(
    '<button type="button" class="telemetry-cmd-btn" onclick="openCommandPalette()" title="Press Ctrl+K to open">',
    '<button type="button" class="telemetry-cmd-btn" onclick="openCommandPalette()" title="Press Ctrl+K to open" style="background: transparent; border: none; color: var(--text-muted);">'
)

# Update cache buster to force browser fresh reload
html = html.replace(
    'style_v2.css?v=20261106_v6_clean',
    'style_v2.css?v=20261106_v8_subtle'
)
html = html.replace(
    'script_v2.js?v=20261106_v6_clean',
    'script_v2.js?v=20261106_v8_subtle'
)

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
print('index.html refined with v8_subtle cache buster.')
