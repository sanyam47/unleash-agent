import os

script_path = r"c:\coding\ai-trainer\frontend\script_v2.js"
with open(script_path, "r", encoding="utf-8") as f:
    text = f.read()

normalized = text.replace("\r\n", "\n")

target = """window.toggleSkillForCurrentChat = function(skillId) {
    const session = getActiveSession();
    if (!session) return;
    if (!Array.isArray(session.activeSkills)) {
        session.activeSkills = [];
    }
    const idx = session.activeSkills.indexOf(skillId);
    if (idx > -1) {
        session.activeSkills.splice(idx, 1);
    } else {
        session.activeSkills.push(skillId);
    }
    saveChatSessions();
    updateSessionSkillsUI(session);
    renderQuickSkillsList();
    renderChatSessionsSidebar();
};"""

replacement = """window.clearChatPinnedSkills = function() {
    const session = getActiveSession();
    if (!session) return;
    session.activeSkills = [];
    saveChatSessions();
    updateSessionSkillsUI(session);
    renderQuickSkillsList();
    renderChatSessionsSidebar();
};

window.toggleSkillForCurrentChat = function(skillId) {
    const session = getActiveSession();
    if (!session) return;
    if (!Array.isArray(session.activeSkills)) {
        session.activeSkills = [];
    }
    const idx = session.activeSkills.indexOf(skillId);
    if (idx > -1) {
        session.activeSkills.splice(idx, 1);
    } else {
        session.activeSkills.push(skillId);
    }
    saveChatSessions();
    updateSessionSkillsUI(session);
    renderQuickSkillsList();
    renderChatSessionsSidebar();
};"""

target2 = """window.updateSessionSkillsUI = function(session) {
    if (!session) session = getActiveSession();
    const count = session && Array.isArray(session.activeSkills) ? session.activeSkills.length : 0;
    const pill = document.getElementById('chatActiveSkillsCountPill');
    if (pill) {
        pill.textContent = count;
    }
};"""

replacement2 = """window.updateSessionSkillsUI = function(session) {
    if (!session) session = getActiveSession();
    const count = session && Array.isArray(session.activeSkills) ? session.activeSkills.length : 0;
    const pill = document.getElementById('chatActiveSkillsCountPill');
    if (pill) {
        pill.textContent = count > 0 ? count : 'Auto';
    }
};"""

if target in normalized and target2 in normalized:
    normalized = normalized.replace(target, replacement, 1)
    normalized = normalized.replace(target2, replacement2, 1)
    with open(script_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(normalized)
    print("SUCCESS: script_v2.js updated with clearChatPinnedSkills and Auto pill label.")
else:
    print("ERROR: Targets not found in script_v2.js")
