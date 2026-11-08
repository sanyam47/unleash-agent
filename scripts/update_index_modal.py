import os

index_path = r"c:\coding\ai-trainer\frontend\index.html"
with open(index_path, "r", encoding="utf-8") as f:
    text = f.read()

normalized = text.replace("\r\n", "\n")

target = """        <div style="font-size: 0.78rem; color: var(--text-secondary); line-height: 1.4;">
            One-click toggle skills to inject specialized tools and operational personas directly into your active model (<strong id="quickSkillTargetModelName">dolphin3:latest</strong>) without altering weights.
        </div>"""

replacement = """        <div style="font-size: 0.76rem; color: var(--text-secondary); line-height: 1.4;">
            Toggle skills to force-attach them, or leave unpinned for <strong>Antigravity Auto-Intent Routing</strong>. You can also type slash commands (e.g. <code>/rea</code>, <code>/coderabbit</code>, <code>/ralph</code>).
        </div>
        <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.03); border:1px solid var(--border-subtle); padding:6px 10px; border-radius:6px; font-size:0.73rem;">
            <span style="color:var(--text-muted);">Routing Mode:</span>
            <button type="button" onclick="clearChatPinnedSkills()" class="btn-quiet" style="font-size:0.7rem; padding:2px 8px; color:#94a3b8;">
                Reset to Auto (Idle Antigravity Mode)
            </button>
        </div>"""

if target in normalized:
    normalized = normalized.replace(target, replacement, 1)
    with open(index_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(normalized)
    print("SUCCESS: index.html updated")
else:
    print("ERROR: Target not found")
