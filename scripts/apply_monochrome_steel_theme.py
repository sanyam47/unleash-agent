import re

css_path = r'c:\coding\ai-trainer\frontend\style_v2.css'
with open(css_path, 'r', encoding='utf-8') as f:
    css = f.read()

# Replace Dark Theme Tokens with Option 2: Monochrome Pure Steel
old_tokens_pattern = r':root,\s*\[data-theme="dark"\]\s*\{[\s\S]*?\/\* Clean Shadows'

new_tokens = """:root,
[data-theme="dark"] {
    /* Option 2: Monochrome Pure Steel Workstation Palette */
    --bg-base: #000000;                /* Pitch black main background */
    --bg-surface: #0C0C0C;             /* Deep slate-black secondary background */
    --bg-surface-elevated: #141414;    /* Elevated panels & cards */
    --bg-input: #0A0A0A;               /* Crisp inset input background */
    --bg-hover: rgba(255, 255, 255, 0.05); /* Clean monochrome hover */
    --bg-active: rgba(255, 255, 255, 0.10); /* Clean monochrome active */

    /* Precision Titanium Steel 1px Borders */
    --border-subtle: #1F1F1F;           /* Subtle divider */
    --border-medium: #282828;           /* Cards & panel perimeter */
    --border-strong: #3D3D3D;           /* Active / hovered perimeter */
    --border-focus: #FFFFFF;            /* Stark white focus ring */

    /* Stark White & Pure Titanium Accents */
    --accent: #FFFFFF;                 /* Primary accent: Crisp Stark White */
    --accent-primary: #FFFFFF;
    --accent-secondary: #D4D4D8;       /* Secondary accent: Zinc 300 */
    --accent-hover: #E4E4E7;           /* Interactive hover state */
    --accent-active: #A1A1AA;          /* Active press state */
    --accent-subtle: rgba(255, 255, 255, 0.08);
    --accent-border: rgba(255, 255, 255, 0.20);
    --accent-text: #FFFFFF;

    /* Input & Card Aliases */
    --input-bg: #0A0A0A;
    --input-border: #282828;
    --bg-card: #141414;

    /* Semantic Meaning-Only Accents (Calibrated for pure black/monochrome) */
    --success: #22c55e;
    --success-bg: rgba(34, 197, 94, 0.08);
    --success-border: rgba(34, 197, 94, 0.25);
    
    --warning: #eab308;
    --warning-bg: rgba(234, 179, 8, 0.08);
    --warning-border: rgba(234, 179, 8, 0.25);
    
    --danger: #ef4444;
    --danger-bg: rgba(239, 68, 68, 0.08);
    --danger-border: rgba(239, 68, 68, 0.25);

    /* High-Legibility Zinc Typography Hierarchy */
    --text-primary: #FFFFFF;           /* Crisp Stark White */
    --text-secondary: #A1A1AA;         /* Zinc 400 */
    --text-muted: #71717A;             /* Zinc 500 */

    /* Chat specifics */
    --chat-bubble-user: #1C1C1E;
    --chat-bubble-user-border: #2E2E32;
    --chat-bubble-user-text: #FFFFFF;
    --chat-bubble-bot: #111113;
    --chat-bubble-bot-border: #242428;
    --chat-bubble-bot-text: #EDEDED;
    --chat-sidebar-bg: #080808;

    /* Clean Shadows"""

if re.search(old_tokens_pattern, css):
    css = re.sub(old_tokens_pattern, new_tokens, css, count=1)
    print("Tokens replaced successfully!")
else:
    print("Pattern for tokens NOT matched!")

# Replace button.primary styles to crisp stark white with black text
css = re.sub(
    r'button\.primary\s*\{\s*background:\s*#[a-fA-F0-9]+;\s*color:\s*#[a-fA-F0-9]+;\s*border-color:\s*#[a-fA-F0-9]+;',
    'button.primary {\n    background: #FFFFFF;\n    color: #000000;\n    border-color: #E5E5E5;',
    css
)

# Replace .btn-primary-quiet styles
css = re.sub(
    r'\.btn-primary-quiet\s*\{\s*background:\s*#[a-fA-F0-9]+;\s*border:\s*1px solid #[a-fA-F0-9]+;\s*color:\s*#[a-fA-F0-9]+;',
    '.btn-primary-quiet {\n    background: #FFFFFF;\n    border: 1px solid #E5E5E5;\n    color: #000000;',
    css
)

css = re.sub(
    r'\.btn-primary-quiet:hover\s*\{\s*background:\s*#[a-fA-F0-9]+;\s*border-color:\s*#[a-fA-F0-9]+;\s*color:\s*#[a-fA-F0-9]+;[^}]*?\}',
    '.btn-primary-quiet:hover {\n    background: #E5E5E5;\n    border-color: #D4D4D4;\n    color: #000000;\n    box-shadow: 0 2px 8px rgba(255, 255, 255, 0.15);\n    transform: translateY(-1px);\n}',
    css
)

# Clean remaining hardcoded warm brown accents
css = re.sub(r'border-bottom:\s*2px solid #C08A45;', 'border-bottom: 2px solid #FFFFFF;', css)
css = re.sub(r'border-left:\s*3px solid #C08A45;', 'border-left: 3px solid #FFFFFF;', css)
css = re.sub(r'color:\s*#B99D73;', 'color: #D4D4D8;', css)

with open(css_path, 'w', encoding='utf-8') as f:
    f.write(css)

print("Monochrome Pure Steel theme applied successfully!")
