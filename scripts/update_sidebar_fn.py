with open(r'c:\coding\ai-trainer\frontend\script_v2.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find renderChatSessionsSidebar
s_idx = None
e_idx = None
for i, l in enumerate(lines):
    if 'function renderChatSessionsSidebar()' in l:
        s_idx = i
    if s_idx is not None and 'modelSessions.forEach(s => {' in l:
        e_idx = i
        break

print("s_idx:", s_idx, "e_idx:", e_idx)

new_code_lines = [
    "function renderChatSessionsSidebar() {\n",
    "    const listContainer = document.getElementById('chatSessionsList');\n",
    "    if (!listContainer) return;\n",
    "    listContainer.innerHTML = '';\n",
    "\n",
    "    const allSessions = window.chatSessions || [];\n",
    "\n",
    "    const badge = document.getElementById('chatModelHistoryCountBadge');\n",
    "    if (badge) {\n",
    "        badge.textContent = `${allSessions.length} thread${allSessions.length === 1 ? '' : 's'}`;\n",
    "    }\n",
    "\n",
    "    if (allSessions.length === 0) {\n",
    "        listContainer.innerHTML = `\n",
    "            <div style=\"padding: 24px 12px; color: var(--text-muted); font-size: 0.78rem; text-align: center; line-height: 1.5;\">\n",
    "                <div style=\"margin-bottom: 4px; color: var(--text-secondary); font-weight: 500;\">No conversations yet</div>\n",
    "                <span>Type below to start an air-gapped session with your local models.</span>\n",
    "                <div style=\"margin-top: 10px; display: flex; gap: 6px; justify-content: center;\">\n",
    "                    <button type=\"button\" onclick=\"createNewChatSession(true)\" class=\"btn-quiet\" style=\"font-size: 0.72rem; padding: 3px 9px;\">+ New Chat</button>\n",
    "                </div>\n",
    "            </div>\n",
    "        `;\n",
    "        return;\n",
    "    }\n",
    "\n",
    "    allSessions.forEach(s => {\n"
]

if s_idx is not None and e_idx is not None:
    lines = lines[:s_idx] + new_code_lines + lines[e_idx+1:]
    with open(r'c:\coding\ai-trainer\frontend\script_v2.js', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print("Replaced renderChatSessionsSidebar cleanly!")
else:
    print("Failed to find boundaries")
