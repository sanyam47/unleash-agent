import os

index_path = r"c:\coding\ai-trainer\frontend\index.html"
with open(index_path, "r", encoding="utf-8") as f:
    text = f.read()

normalized = text.replace("\r\n", "\n")

target = """<div id="agentProjectModal" class="modal-overlay" style="display: none; position: fixed; inset: 0; background: rgba(0, 0, 0, 0.75); backdrop-filter: blur(8px); z-index: 9999; justify-content: center; align-items: center; padding: 20px;">
    <div class="modal-card" style="background: var(--bg-surface); border: 1px solid var(--border-medium); border-radius: 14px; max-width: 820px; width: 100%; max-height: 85vh; display: flex; flex-direction: column; padding: 20px; box-shadow: var(--shadow-xl);">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-subtle); padding-bottom: 12px; margin-bottom: 12px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                <h3 id="agentProjectModalTitle" style="margin: 0; font-size: 1.05rem; font-weight: 600;">Project Workspace Explorer</h3>
            </div>
            <button onclick="closeAgentProjectModal()" style="background: transparent; border: none; font-size: 1.2rem; cursor: pointer; color: var(--text-muted);">&times;</button>
        </div>
        <div id="agentProjectModalBody" style="flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 10px;">
            <!-- Populated dynamically via JS -->
        </div>
    </div>
</div>"""

replacement = """<div id="agentProjectModal" class="modal-overlay" style="display: none; position: fixed; inset: 0; background: rgba(0, 0, 0, 0.8); backdrop-filter: blur(8px); z-index: 9999; justify-content: center; align-items: center; padding: 16px;">
    <div class="modal-card" style="background: var(--bg-surface); border: 1px solid var(--border-medium); border-radius: 14px; max-width: 1140px; width: 96%; height: 90vh; display: flex; flex-direction: column; padding: 16px 20px; box-shadow: var(--shadow-xl);">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-subtle); padding-bottom: 10px; margin-bottom: 10px; flex-wrap: wrap; gap: 10px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                <h3 id="agentProjectModalTitle" style="margin: 0; font-size: 0.95rem; font-weight: 600; color: var(--text-primary); font-family: var(--font-mono);">Project Workspace</h3>
            </div>
            <div id="agentProjectModalActions" style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                <!-- Populated dynamically: Preview/Code Switcher, Open in VS Code, Open Tab -->
            </div>
            <button onclick="closeAgentProjectModal()" style="background: transparent; border: none; font-size: 1.3rem; cursor: pointer; color: var(--text-muted); line-height: 1;" title="Close">&times;</button>
        </div>
        <div id="agentProjectModalBody" style="flex: 1; overflow: hidden; display: flex; flex-direction: column;">
            <!-- Populated dynamically via JS -->
        </div>
    </div>
</div>"""

if target in normalized:
    normalized = normalized.replace(target, replacement, 1)
    with open(index_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(normalized)
    print("SUCCESS: index.html modal updated.")
else:
    print("ERROR: Target not found in index.html")
