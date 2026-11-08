import re

css_path = r'c:\coding\ai-trainer\frontend\style_v2.css'
with open(css_path, 'r', encoding='utf-8') as f:
    css = f.read()

# Replace Dark Theme Tokens with Steel Grey & Midnight Charcoal
old_tokens_pattern = r':root,\s*\[data-theme="dark"\]\s*\{[\s\S]*?\/\* Clean Shadows'

new_tokens = """:root,
[data-theme="dark"] {
    /* Industrial Midnight Charcoal & Cool Steel Grey Palette */
    --bg-base: #0f1115;
    --bg-surface: #16181d;
    --bg-surface-elevated: #1e2229;
    --bg-input: #121418;
    --bg-hover: rgba(148, 163, 184, 0.08);
    --bg-active: rgba(148, 163, 184, 0.14);

    /* Cool Slate & Steel 1px Borders */
    --border-subtle: rgba(148, 163, 184, 0.10);
    --border-medium: rgba(148, 163, 184, 0.18);
    --border-strong: rgba(148, 163, 184, 0.30);
    --border-focus: #64748b;

    /* Cool Brushed Steel Accents */
    --accent: #64748b;
    --accent-primary: #334155;
    --accent-secondary: #94a3b8;
    --accent-hover: #475569;
    --accent-active: #1e293b;
    --accent-subtle: rgba(148, 163, 184, 0.08);
    --accent-border: rgba(148, 163, 184, 0.18);
    --accent-text: #cbd5e1;

    /* Input & Card Aliases */
    --input-bg: #121418;
    --input-border: rgba(148, 163, 184, 0.14);
    --bg-card: #16181d;

    /* Semantic Meaning-Only Accents (Subtle & Calibrated) */
    --success: #10b981;
    --success-bg: rgba(16, 185, 129, 0.06);
    --success-border: rgba(16, 185, 129, 0.20);
    
    --warning: #f59e0b;
    --warning-bg: rgba(245, 158, 11, 0.08);
    --warning-border: rgba(245, 158, 11, 0.22);
    
    --danger: #f43f5e;
    --danger-bg: rgba(244, 63, 94, 0.08);
    --danger-border: rgba(244, 63, 94, 0.22);

    /* Typography Hierarchy (Silvery Steel Greys) */
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;

    /* Chat specifics */
    --chat-bubble-user: #1f242d;
    --chat-bubble-user-border: rgba(148, 163, 184, 0.18);
    --chat-bubble-user-text: #f8fafc;
    --chat-bubble-bot: #16181d;
    --chat-bubble-bot-border: rgba(148, 163, 184, 0.12);
    --chat-bubble-bot-text: #e2e8f0;
    --chat-sidebar-bg: #111317;

    /* Clean Shadows"""

css = re.sub(old_tokens_pattern, new_tokens, css)

# Make body have a subtle metallic depth gradient
old_body = """body {
    background-color: var(--bg-base);"""
new_body = """body {
    background: radial-gradient(circle at 50% 0%, #161a22 0%, #0e1014 75%);
    background-color: var(--bg-base);"""

if old_body in css:
    css = css.replace(old_body, new_body)

# Upgrade navbar to steel glassmorphism
old_nav = """.app-navbar {
    position: sticky;
    top: 0;
    z-index: 1000;
    background: var(--bg-surface);
    border-bottom: 1px solid var(--border-subtle);"""

new_nav = """.app-navbar {
    position: sticky;
    top: 0;
    z-index: 1000;
    background: rgba(22, 24, 29, 0.85);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border-subtle);"""

if old_nav in css:
    css = css.replace(old_nav, new_nav)

# Upgrade prompt-tag to cool steel badge
old_prompt_tag = """.prompt-tag {
    display: inline-block;
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 2px 7px;
    border-radius: var(--radius-sm);
    background: var(--accent-subtle);
    color: var(--accent-text);
    border: 1px solid var(--border-subtle);
    margin-bottom: 6px;
}"""

new_prompt_tag = """.prompt-tag {
    display: inline-block;
    font-size: 0.66rem;
    font-weight: 600;
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.6px;
    padding: 2px 7px;
    border-radius: 4px;
    background: rgba(148, 163, 184, 0.08);
    color: #94a3b8;
    border: 1px solid rgba(148, 163, 184, 0.18);
    margin-bottom: 6px;
}"""

if old_prompt_tag in css:
    css = css.replace(old_prompt_tag, new_prompt_tag)

with open(css_path, 'w', encoding='utf-8') as f:
    f.write(css)

print("style_v2.css updated with Steel Grey & Midnight Charcoal palette.")

# Update script_v2.js chatEmptyHero styling for a refined look
js_path = r'c:\coding\ai-trainer\frontend\script_v2.js'
with open(js_path, 'r', encoding='utf-8') as f:
    js = f.read()

old_hero_icon = """<div style="width: 44px; height: 44px; border-radius: 10px; background: var(--bg-surface-elevated); border: 1px solid var(--border-medium); display: flex; align-items: center; justify-content: center; margin: 0 auto 16px; color: var(--accent);">"""
new_hero_icon = """<div style="width: 44px; height: 44px; border-radius: 10px; background: rgba(148, 163, 184, 0.06); border: 1px solid rgba(148, 163, 184, 0.16); display: flex; align-items: center; justify-content: center; margin: 0 auto 16px; color: #94a3b8;">"""

if old_hero_icon in js:
    js = js.replace(old_hero_icon, new_hero_icon)

# Prompt cards hover styling
old_card_style = """style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); padding: 14px; border-radius: 8px; text-align: left; cursor: pointer; transition: 0.2s;" onmouseenter="this.style.borderColor='var(--accent)'" onmouseleave="this.style.borderColor='var(--border-subtle)'" """
new_card_style = """style="background: rgba(22, 24, 29, 0.7); border: 1px solid rgba(148, 163, 184, 0.12); padding: 14px 16px; border-radius: 8px; text-align: left; cursor: pointer; transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1); box-shadow: 0 2px 6px rgba(0,0,0,0.15);" onmouseenter="this.style.borderColor='rgba(148, 163, 184, 0.35)'; this.style.transform='translateY(-1px)';" onmouseleave="this.style.borderColor='rgba(148, 163, 184, 0.12)'; this.style.transform='none';" """

js = js.replace(old_card_style, new_card_style)

with open(js_path, 'w', encoding='utf-8') as f:
    f.write(js)
print("script_v2.js hero cards updated.")

# Bump index.html cache busters
html_path = r'c:\coding\ai-trainer\frontend\index.html'
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

html = re.sub(r'style_v2\.css\?v=[^\"]+', 'style_v2.css?v=20261106_v11_steel_charcoal', html)
html = re.sub(r'script_v2\.js\?v=[^\"]+', 'script_v2.js?v=20261106_v11_steel_charcoal', html)

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
print("index.html cache buster bumped to v11_steel_charcoal.")
