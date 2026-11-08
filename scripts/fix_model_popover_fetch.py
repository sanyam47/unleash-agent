with open(r'c:\coding\ai-trainer\frontend\script_v2.js', 'r', encoding='utf-8') as f:
    text = f.read()

# Make toggleModelPickerPopover async and auto-fetch models if empty!
old_toggle = """window.toggleModelPickerPopover = function() {
    const popover = document.getElementById('modelPickerPopover');
    if (!popover) return;
    const isVisible = popover.style.display === 'block';
    popover.style.display = isVisible ? 'none' : 'block';
    if (!isVisible) {
        renderModelPickerPopoverList();
    }
};"""

new_toggle = """window.toggleModelPickerPopover = async function() {
    const popover = document.getElementById('modelPickerPopover');
    if (!popover) return;
    const isVisible = popover.style.display === 'block';
    popover.style.display = isVisible ? 'none' : 'block';
    if (!isVisible) {
        if (!window.chatModels || window.chatModels.length === 0) {
            await refreshChatModels();
        }
        renderModelPickerPopoverList();
    }
};"""

if old_toggle in text:
    text = text.replace(old_toggle, new_toggle)
    print("Replaced toggleModelPickerPopover with auto-fetch version.")
else:
    print("WARNING: old_toggle not found.")

# Also in renderModelPickerPopoverList, show a Refresh Models button if list is empty
old_empty = """    if (models.length === 0) {
        list.innerHTML = '<div style="padding: 10px 14px; font-size: 0.74rem; color: var(--text-muted);">No local models loaded</div>';
        return;
    }"""

new_empty = """    if (models.length === 0) {
        list.innerHTML = `
            <div style="padding: 12px 14px; text-align: center; font-size: 0.74rem; color: var(--text-muted);">
                <div style="margin-bottom: 6px;">No local models loaded in memory</div>
                <button type="button" onclick="refreshChatModels().then(() => renderModelPickerPopoverList())" class="btn-quiet" style="font-size: 0.7rem; padding: 2px 8px;">↻ Scan Ollama</button>
            </div>
        `;
        return;
    }"""

if old_empty in text:
    text = text.replace(old_empty, new_empty)
    print("Replaced empty list with scan button.")
else:
    print("WARNING: old_empty not found.")

with open(r'c:\coding\ai-trainer\frontend\script_v2.js', 'w', encoding='utf-8') as f:
    f.write(text)

# Also update index.html cache buster
with open(r'c:\coding\ai-trainer\frontend\index.html', 'r', encoding='utf-8') as f:
    html = f.read()

import re
html = re.sub(r'script_v2\.js\?v=[^\"]+', 'script_v2.js?v=20261106_v10_models_fix', html)

with open(r'c:\coding\ai-trainer\frontend\index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Bumped index.html to v10_models_fix.")
