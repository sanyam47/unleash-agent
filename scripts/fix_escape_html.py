import os

script_path = r"c:\coding\ai-trainer\frontend\script_v2.js"
with open(script_path, "r", encoding="utf-8") as f:
    text = f.read()

normalized = text.replace("\r\n", "\n")

target = """function appendMessageElement(role, content, telemetry = null, autoScroll = true, images = null, ragSources = null, activeSkills = null, agenticData = null, modelUsed = null, bakeRec = null) {"""

replacement = """function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
window.escapeHtml = escapeHtml;

function appendMessageElement(role, content, telemetry = null, autoScroll = true, images = null, ragSources = null, activeSkills = null, agenticData = null, modelUsed = null, bakeRec = null) {"""

if target in normalized:
    normalized = normalized.replace(target, replacement, 1)
    with open(script_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(normalized)
    print("SUCCESS: escapeHtml defined in script_v2.js")
else:
    print("ERROR: Target not found in script_v2.js")
