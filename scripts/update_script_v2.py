import os

script_path = r"c:\coding\ai-trainer\frontend\script_v2.js"
with open(script_path, "r", encoding="utf-8") as f:
    text = f.read()

normalized = text.replace("\r\n", "\n")

target1 = """        const assistantMsg = {
            role: 'assistant',
            content: data.reply,
            model_used: model,
            telemetry: data.telemetry,
            rag_sources: data.rag_sources,
            active_skills: data.active_skills,
            agentic_data: agenticData
        };
        session.messages.push(assistantMsg);
        saveChatSessions();
        renderChatSessionsSidebar();

        appendMessageElement('assistant', data.reply, data.telemetry, true, null, data.rag_sources, data.active_skills, agenticData, model);"""

replacement1 = """        const assistantMsg = {
            role: 'assistant',
            content: data.reply,
            model_used: model,
            telemetry: data.telemetry,
            rag_sources: data.rag_sources,
            active_skills: data.active_skills,
            bake_recommendation: data.bake_recommendation,
            agentic_data: agenticData
        };
        session.messages.push(assistantMsg);
        saveChatSessions();
        renderChatSessionsSidebar();

        appendMessageElement('assistant', data.reply, data.telemetry, true, null, data.rag_sources, data.active_skills, agenticData, model, data.bake_recommendation);"""

target2 = """function appendMessageElement(role, content, telemetry = null, autoScroll = true, images = null, ragSources = null, activeSkills = null, agenticData = null, modelUsed = null) {"""

replacement2 = """function appendMessageElement(role, content, telemetry = null, autoScroll = true, images = null, ragSources = null, activeSkills = null, agenticData = null, modelUsed = null, bakeRec = null) {"""

target3 = """    // Render Antigravity ReAct Steps Trace if present"""

replacement3 = """    // Render Bake Recommendation Card if multiple skills cause cognitive overload / efficiency drop
    if (!isUser && bakeRec && bakeRec.needed) {
        const bakeCard = document.createElement('div');
        bakeCard.style.margin = '10px 0 12px 0';
        bakeCard.style.padding = '12px 14px';
        bakeCard.style.background = '#15171a';
        bakeCard.style.border = '1px solid #2d3139';
        bakeCard.style.borderRadius = '8px';
        bakeCard.style.display = 'flex';
        bakeCard.style.flexDirection = 'column';
        bakeCard.style.gap = '8px';
        bakeCard.style.color = '#c9d1d9';

        const skillNamesStr = (bakeRec.skill_names || []).join(', ');
        const recBaseModel = bakeRec.base_model || 'model';
        const recSuggName = bakeRec.suggested_model_name || 'specialist-model';

        bakeCard.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="display: flex; align-items: center; gap: 7px; font-size: 0.8rem; font-weight: 600; color: #94a3b8;">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
                    <span>Efficiency Warning: High Multi-Skill Overhead</span>
                </div>
                <span style="font-size: 0.68rem; font-family: var(--font-mono); color: #64748b; background: #0d0f11; padding: 2px 7px; border-radius: 4px; border: 1px solid #242930;">~${bakeRec.estimated_overhead_tokens || 1200} prompt tokens</span>
            </div>
            <div style="font-size: 0.77rem; color: #8b949e; line-height: 1.45;">
                Running <strong>${bakeRec.skill_count} simultaneous skills</strong> (<em>${escapeHtml(skillNamesStr)}</em>) adds runtime prompt bloat and degrades 7B/8B reasoning. Antigravity recommends <strong>baking these skills</strong> directly into a dedicated specialist model for 2x faster inference and 100% precision.
            </div>
            <div style="display: flex; gap: 8px; align-items: center; margin-top: 4px;">
                <button type="button" onclick="triggerBakeRecommendation('${recBaseModel}', '${recSuggName}', ${JSON.stringify(bakeRec.skill_ids || []).replace(/"/g, '&apos;')})" class="btn-quiet" style="font-size: 0.75rem; padding: 5px 14px; font-weight: 600; cursor: pointer; background: #1e2229; border: 1px solid #3b4252; color: #e2e8f0; border-radius: 6px;">
                    ⚡ Bake into Dedicated Model (1-Click)
                </button>
            </div>
        `;
        bubble.appendChild(bakeCard);
    }

    // Render Antigravity ReAct Steps Trace if present"""

target4 = """    session.messages.forEach(m => {
        appendMessageElement(m.role, m.content, m.telemetry, false, m.images, m.rag_sources, m.active_skills, m.agentic_data, m.model_used);
    });"""

replacement4 = """    session.messages.forEach(m => {
        appendMessageElement(m.role, m.content, m.telemetry, false, m.images, m.rag_sources, m.active_skills, m.agentic_data, m.model_used, m.bake_recommendation);
    });"""

target5 = """window.openBakeSkillsModal = async function() {
    const modal = document.getElementById('bakeSkillsModal');
    if (!modal) return;
    modal.style.display = 'flex';

    // Populate base model select from chatModelSelect
    const baseSel = document.getElementById('bakeBaseModelSelect');
    const chatSel = document.getElementById('chatModelSelect');
    if (baseSel && chatSel) {
        baseSel.innerHTML = '';
        for (let i = 0; i < chatSel.options.length; i++) {
            if (chatSel.options[i].value) {
                const opt = document.createElement('option');
                opt.value = chatSel.options[i].value;
                opt.textContent = chatSel.options[i].text;
                baseSel.appendChild(opt);
            }
        }
        if (baseSel.options.length === 0) {
            baseSel.innerHTML = '<option value="dolphin3:latest">dolphin3:latest</option>';
        }
        baseSel.value = chatSel.value || baseSel.options[0].value;
    }

    // Populate skills checkboxes
    const cbContainer = document.getElementById('bakeSkillsCheckboxes');
    if (cbContainer) {
        const installed = window.currentSkillsData.installed || [];
        cbContainer.innerHTML = installed.map(s => `
            <label style="display: flex; align-items: center; gap: 8px; font-size: 0.78rem; color: var(--text-primary); cursor: pointer;">
                <input type="checkbox" value="${s.id}" ${s.is_active ? 'checked' : ''} class="bake-skill-cb">
                <span><strong>${s.name}</strong> <span style="color: var(--text-muted); font-size: 0.7rem;">(${s.category})</span></span>
            </label>
        `).join('') || '<span style="font-size:0.75rem; color:var(--text-muted);">No installed skills to bake.</span>';
    }

    // Reset mode to in-place by default
    window.setBakeMode('inplace');
    window.onBakeTargetChange();

    const feedback = document.getElementById('bakeStatusFeedback');
    if (feedback) feedback.style.display = 'none';
};"""

replacement5 = """window.triggerBakeRecommendation = function(baseModel, suggestedName, skillIds) {
    window.openBakeSkillsModal(skillIds, baseModel, suggestedName);
};

window.openBakeSkillsModal = async function(preSelectedSkillIds = null, targetBaseModel = null, suggestedName = null) {
    const modal = document.getElementById('bakeSkillsModal');
    if (!modal) return;
    modal.style.display = 'flex';

    // Populate base model select from chatModelSelect
    const baseSel = document.getElementById('bakeBaseModelSelect');
    const chatSel = document.getElementById('chatModelSelect');
    if (baseSel && chatSel) {
        baseSel.innerHTML = '';
        for (let i = 0; i < chatSel.options.length; i++) {
            if (chatSel.options[i].value) {
                const opt = document.createElement('option');
                opt.value = chatSel.options[i].value;
                opt.textContent = chatSel.options[i].text;
                baseSel.appendChild(opt);
            }
        }
        if (baseSel.options.length === 0) {
            baseSel.innerHTML = '<option value="dolphin3:latest">dolphin3:latest</option>';
        }
        if (targetBaseModel) {
            baseSel.value = targetBaseModel;
        } else {
            baseSel.value = chatSel.value || baseSel.options[0].value;
        }
    }

    // Ensure skills data is loaded
    if (!window.currentSkillsData || !window.currentSkillsData.installed) {
        await window.loadSkillsData();
    }

    // Populate skills checkboxes
    const cbContainer = document.getElementById('bakeSkillsCheckboxes');
    if (cbContainer) {
        const installed = window.currentSkillsData.installed || [];
        cbContainer.innerHTML = installed.map(s => {
            const isChecked = preSelectedSkillIds && Array.isArray(preSelectedSkillIds)
                ? preSelectedSkillIds.includes(s.id)
                : s.is_active;
            return `
                <label style="display: flex; align-items: center; gap: 8px; font-size: 0.78rem; color: var(--text-primary); cursor: pointer;">
                    <input type="checkbox" value="${s.id}" ${isChecked ? 'checked' : ''} class="bake-skill-cb">
                    <span><strong>${s.name}</strong> <span style="color: var(--text-muted); font-size: 0.7rem;">(${s.category})</span></span>
                </label>
            `;
        }).join('') || '<span style="font-size:0.75rem; color:var(--text-muted);">No installed skills to bake.</span>';
    }

    // If a suggested custom name is provided, default to new standalone model mode
    if (suggestedName) {
        window.setBakeMode('new');
        const nameInput = document.getElementById('bakeNewModelNameInput');
        if (nameInput) nameInput.value = suggestedName;
    } else {
        window.setBakeMode('inplace');
        window.onBakeTargetChange();
    }

    const feedback = document.getElementById('bakeStatusFeedback');
    if (feedback) feedback.style.display = 'none';
};"""

errors = []
if target1 not in normalized: errors.append("target1")
if target2 not in normalized: errors.append("target2")
if target3 not in normalized: errors.append("target3")
if target4 not in normalized: errors.append("target4")
if target5 not in normalized: errors.append("target5")

if errors:
    print(f"ERROR: Could not find targets: {errors}")
else:
    normalized = normalized.replace(target1, replacement1, 1)
    normalized = normalized.replace(target2, replacement2, 1)
    normalized = normalized.replace(target3, replacement3, 1)
    normalized = normalized.replace(target4, replacement4, 1)
    normalized = normalized.replace(target5, replacement5, 1)
    with open(script_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(normalized)
    print("SUCCESS: script_v2.js updated with Bake Recommendation Card and pre-selection triggers.")
