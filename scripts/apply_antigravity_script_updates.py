import re

js_path = r'c:\coding\ai-trainer\frontend\script_v2.js'
with open(js_path, 'r', encoding='utf-8') as f:
    js = f.read()

# 1. Update renderChatSessionsSidebar to show all shared conversations instead of filtering by model
old_sidebar_fn = """function renderChatSessionsSidebar() {
    const listContainer = document.getElementById('chatSessionsList');
    if (!listContainer) return;
    listContainer.innerHTML = '';

    const currentModel = document.getElementById('chatModelSelect')?.value || (window.chatModels && window.chatModels.length > 0 ? window.chatModels[0].name : '');
    
    // Filter sessions strictly associated with the selected model
    const modelSessions = (window.chatSessions || []).filter(s => {
        if (!currentModel) return true;
        return s.model === currentModel;
    });

    const badge = document.getElementById('chatModelHistoryCountBadge');
    if (badge) {
        badge.textContent = `${modelSessions.length} chat${modelSessions.length === 1 ? '' : 's'} for this model`;
    }

    if (modelSessions.length === 0) {
        listContainer.innerHTML = `
            <div style="padding: 24px 12px; color: var(--text-muted); font-size: 0.78rem; text-align: center; line-height: 1.5;">
                <div style="margin-bottom: 4px; color: var(--text-secondary); font-weight: 500;">No chats for ${currentModel || 'this model'}</div>
                <span>Start a new thread or import previous chats from another model.</span>
                <div style="margin-top: 10px; display: flex; gap: 6px; justify-content: center;">
                    <button type="button" onclick="createNewChatSession(true)" class="btn-quiet" style="font-size: 0.72rem; padding: 3px 9px;">+ New Chat</button>
                    <button type="button" onclick="openImportChatsModal()" class="btn-quiet" style="font-size: 0.72rem; padding: 3px 9px; color: #60a5fa; border-color: rgba(59, 130, 246, 0.3);">↳ Import chats</button>
                </div>
            </div>
        `;
        return;
    }

    modelSessions.forEach(s => {"""

new_sidebar_fn = """function renderChatSessionsSidebar() {
    const listContainer = document.getElementById('chatSessionsList');
    if (!listContainer) return;
    listContainer.innerHTML = '';

    const allSessions = window.chatSessions || [];

    const badge = document.getElementById('chatModelHistoryCountBadge');
    if (badge) {
        badge.textContent = `${allSessions.length} thread${allSessions.length === 1 ? '' : 's'}`;
    }

    if (allSessions.length === 0) {
        listContainer.innerHTML = `
            <div style="padding: 24px 12px; color: var(--text-muted); font-size: 0.78rem; text-align: center; line-height: 1.5;">
                <div style="margin-bottom: 4px; color: var(--text-secondary); font-weight: 500;">No conversations yet</div>
                <span>Type below to start an air-gapped session with your local models.</span>
                <div style="margin-top: 10px; display: flex; gap: 6px; justify-content: center;">
                    <button type="button" onclick="createNewChatSession(true)" class="btn-quiet" style="font-size: 0.72rem; padding: 3px 9px;">+ New Chat</button>
                </div>
            </div>
        `;
        return;
    }

    allSessions.forEach(s => {"""

if old_sidebar_fn in js:
    js = js.replace(old_sidebar_fn, new_sidebar_fn)
    print("Replaced renderChatSessionsSidebar with unified conversations.")
else:
    print("WARNING: old_sidebar_fn not found exactly.")

# Also update the meta line in sidebar items to show model name if present
old_meta = """        const skillCount = (s.activeSkills || []).length;
        const skillSnippet = skillCount > 0 ? ` • ${skillCount} skill${skillCount > 1 ? 's' : ''}` : '';
        metaDiv.textContent = `${s.messages ? s.messages.length : 0} msgs${skillSnippet}`;"""

new_meta = """        const skillCount = (s.activeSkills || []).length;
        const skillSnippet = skillCount > 0 ? ` • ${skillCount} skill${skillCount > 1 ? 's' : ''}` : '';
        const lastModel = (s.messages && s.messages.length > 0 && s.messages[s.messages.length - 1].model_used) || s.model || '';
        const modelSnippet = lastModel ? ` • ${lastModel.split(':')[0]}` : '';
        metaDiv.textContent = `${s.messages ? s.messages.length : 0} msgs${modelSnippet}${skillSnippet}`;"""

if old_meta in js:
    js = js.replace(old_meta, new_meta)
    print("Updated session sidebar meta snippet.")
else:
    print("WARNING: old_meta not found.")

# 2. Add Floating Model Selector Popover logic
model_popover_code = """
// =============================================================
// ANTIGRAVITY-STYLE FLOATING MODEL SELECTOR POPOVER
// =============================================================

window.activeChatModel = localStorage.getItem('chat_arena_last_model') || 'dolphin3:latest';

window.toggleModelPickerPopover = function() {
    const popover = document.getElementById('modelPickerPopover');
    if (!popover) return;
    const isVisible = popover.style.display === 'block';
    popover.style.display = isVisible ? 'none' : 'block';
    if (!isVisible) {
        renderModelPickerPopoverList();
    }
};

window.renderModelPickerPopoverList = function() {
    const list = document.getElementById('modelPickerPopoverList');
    if (!list) return;
    list.innerHTML = '';

    const models = window.chatModels || [];
    if (models.length === 0) {
        list.innerHTML = '<div style="padding: 10px 14px; font-size: 0.74rem; color: var(--text-muted);">No local models loaded</div>';
        return;
    }

    models.forEach(m => {
        const item = document.createElement('div');
        const isSelected = (m.name === window.activeChatModel);
        item.style.padding = '8px 12px';
        item.style.display = 'flex';
        item.style.alignItems = 'center';
        item.style.justifyContent = 'space-between';
        item.style.cursor = 'pointer';
        item.style.transition = 'background 0.15s ease';
        item.style.background = isSelected ? 'rgba(255, 255, 255, 0.05)' : 'transparent';
        item.onmouseenter = () => item.style.background = 'rgba(255, 255, 255, 0.07)';
        item.onmouseleave = () => item.style.background = isSelected ? 'rgba(255, 255, 255, 0.05)' : 'transparent';

        const left = document.createElement('div');
        left.style.display = 'flex';
        left.style.flexDirection = 'column';
        left.style.gap = '2px';

        const nameSpan = document.createElement('span');
        nameSpan.style.fontSize = '0.78rem';
        nameSpan.style.fontWeight = isSelected ? '600' : '400';
        nameSpan.style.color = isSelected ? 'var(--text-primary)' : 'var(--text-secondary)';
        nameSpan.textContent = m.name;

        const specSpan = document.createElement('span');
        specSpan.style.fontSize = '0.68rem';
        specSpan.style.fontFamily = 'var(--font-mono)';
        specSpan.style.color = 'var(--text-muted)';
        specSpan.textContent = `${m.parameter_size || '8B'} • ${m.quantization || 'Q4_K_M'} • ${m.size_gb || 4.5} GB`;

        left.appendChild(nameSpan);
        left.appendChild(specSpan);

        item.appendChild(left);

        if (isSelected) {
            const check = document.createElement('span');
            check.style.fontSize = '0.75rem';
            check.style.color = '#10b981';
            check.textContent = '✓';
            item.appendChild(check);
        }

        item.onclick = () => {
            selectPromptModel(m.name);
            window.toggleModelPickerPopover();
        };

        list.appendChild(item);
    });
};

window.selectPromptModel = function(modelName) {
    window.activeChatModel = modelName;
    try {
        localStorage.setItem('chat_arena_last_model', modelName);
    } catch(e) {}

    // Update prompt pill text & specs
    const nameEl = document.getElementById('promptActiveModelName');
    if (nameEl) nameEl.textContent = modelName;

    const modelObj = (window.chatModels || []).find(m => m.name === modelName);
    const specsEl = document.getElementById('promptModelSpecsPill');
    if (specsEl && modelObj) {
        specsEl.textContent = `${modelObj.parameter_size || '8B'} • ${modelObj.quantization || 'Q4_K_M'}`;
    }

    const badge = document.getElementById('chatModelDetailsBadge');
    if (badge && modelObj) {
        badge.textContent = `${modelObj.parameter_size} • ${modelObj.quantization} • ${modelObj.size_gb} GB`;
    }

    // Keep hidden select in sync
    const sel = document.getElementById('chatModelSelect');
    if (sel) sel.value = modelName;
};

// Close popover when clicking outside
document.addEventListener('click', function(e) {
    const popover = document.getElementById('modelPickerPopover');
    const pill = document.getElementById('btnModelPickerPill');
    if (!popover || !pill) return;
    if (popover.style.display === 'block' && !popover.contains(e.target) && !pill.contains(e.target)) {
        popover.style.display = 'none';
    }
});
"""

# Append model_popover_code to script_v2.js
js += "\n" + model_popover_code
print("Appended floating model selector logic to script_v2.js.")

# 3. Update refreshChatModels to populate popover list and sync promptActiveModelName
old_refresh_chat_models = """        window.chatModels = data.models;
        select.innerHTML = '';
        
        let foundSelected = false;
        data.models.forEach((m, idx) => {
            const opt = document.createElement('option');
            opt.value = m.name;
            opt.textContent = `${m.name} (${m.parameter_size} • ${m.size_gb} GB)`;
            
            const preferredModel = modelToSelect || localStorage.getItem('chat_arena_last_model');
            if (preferredModel) {
                const target = preferredModel.toLowerCase();
                const mName = m.name.toLowerCase();
                if (mName === target || mName === target + ':latest' || mName.startsWith(target + ':') || target.startsWith(mName)) {
                    opt.selected = true;
                    foundSelected = true;
                }
            } else if (!foundSelected && (m.name.includes('dolphin3') || (idx === 0 && !select.value))) {
                opt.selected = true;
            }
            select.appendChild(opt);
        });

        onChatModelChange();"""

new_refresh_chat_models = """        window.chatModels = data.models;
        select.innerHTML = '';
        
        let targetModel = modelToSelect || localStorage.getItem('chat_arena_last_model') || (data.models[0] && data.models[0].name) || 'dolphin3:latest';
        
        data.models.forEach((m) => {
            const opt = document.createElement('option');
            opt.value = m.name;
            opt.textContent = `${m.name} (${m.parameter_size} • ${m.size_gb} GB)`;
            if (m.name === targetModel) opt.selected = true;
            select.appendChild(opt);
        });

        selectPromptModel(targetModel);
        renderChatSessionsSidebar();"""

if old_refresh_chat_models in js:
    js = js.replace(old_refresh_chat_models, new_refresh_chat_models)
    print("Replaced refreshChatModels logic.")
else:
    print("WARNING: old_refresh_chat_models not found.")

# 4. Update sendChatArenaMessage to use window.activeChatModel and record model_used per message
old_send_model = """    const model = document.getElementById('chatModelSelect').value || session.model || 'dolphin3:latest';"""
new_send_model = """    const model = window.activeChatModel || document.getElementById('chatModelSelect')?.value || 'dolphin3:latest';
    session.model = model;"""

if old_send_model in js:
    js = js.replace(old_send_model, new_send_model)
    print("Updated sendChatArenaMessage model resolver.")
else:
    print("WARNING: old_send_model not found.")

# In assistant message creation, save model_used
old_asst_msg = """        const assistantMsg = {
            role: 'assistant',
            content: data.reply,
            telemetry: data.telemetry,
            rag_sources: data.rag_sources,
            active_skills: data.active_skills,
            agentic_data: agenticData
        };"""

new_asst_msg = """        const assistantMsg = {
            role: 'assistant',
            content: data.reply,
            model_used: model,
            telemetry: data.telemetry,
            rag_sources: data.rag_sources,
            active_skills: data.active_skills,
            agentic_data: agenticData
        };"""

if old_asst_msg in js:
    js = js.replace(old_asst_msg, new_asst_msg)
    print("Updated assistantMsg to record model_used.")
else:
    print("WARNING: old_asst_msg not found.")

# In appendMessageElement, add a subtle model badge above assistant message!
old_bubble_start = """    // Render attached images if present
    if (images && images.length > 0) {"""

new_bubble_start = """    // Render subtle Model Identity Tag if provided
    if (!isUser && modelUsed) {
        const modelTag = document.createElement('div');
        modelTag.style.display = 'inline-flex';
        modelTag.style.alignItems = 'center';
        modelTag.style.gap = '4px';
        modelTag.style.marginBottom = '6px';
        modelTag.style.padding = '1px 6px';
        modelTag.style.borderRadius = '4px';
        modelTag.style.background = 'rgba(255, 255, 255, 0.04)';
        modelTag.style.border = '1px solid var(--border-subtle)';
        modelTag.style.fontFamily = 'var(--font-mono)';
        modelTag.style.fontSize = '0.66rem';
        modelTag.style.color = 'var(--text-muted)';
        modelTag.innerHTML = `<span style="width: 4px; height: 4px; border-radius: 50%; background: #10b981; opacity: 0.85;"></span> ${escapeHtml(modelUsed)}`;
        bubble.appendChild(modelTag);
    }

    // Render attached images if present
    if (images && images.length > 0) {"""

# Also update appendMessageElement signature to accept modelUsed
old_sig = "function appendMessageElement(role, content, telemetry = null, autoScroll = true, images = null, ragSources = null, activeSkills = null, agenticData = null) {"
new_sig = "function appendMessageElement(role, content, telemetry = null, autoScroll = true, images = null, ragSources = null, activeSkills = null, agenticData = null, modelUsed = null) {"

if old_sig in js and old_bubble_start in js:
    js = js.replace(old_sig, new_sig)
    js = js.replace(old_bubble_start, new_bubble_start)
    print("Updated appendMessageElement with model identity tag.")
else:
    print("WARNING: appendMessageElement signature not found.")

# Update calls to appendMessageElement in renderActiveThread and sendChatArenaMessage
old_thread_call = "appendMessageElement(m.role, m.content, m.telemetry, false, m.images, m.rag_sources, m.active_skills, m.agentic_data);"
new_thread_call = "appendMessageElement(m.role, m.content, m.telemetry, false, m.images, m.rag_sources, m.active_skills, m.agentic_data, m.model_used);"

if old_thread_call in js:
    js = js.replace(old_thread_call, new_thread_call)
    print("Updated renderActiveThread appendMessageElement call.")
else:
    print("WARNING: old_thread_call not found.")

old_send_call = "appendMessageElement('assistant', data.reply, data.telemetry, true, null, data.rag_sources, data.active_skills, agenticData);"
new_send_call = "appendMessageElement('assistant', data.reply, data.telemetry, true, null, data.rag_sources, data.active_skills, agenticData, model);"

if old_send_call in js:
    js = js.replace(old_send_call, new_send_call)
    print("Updated sendChatArenaMessage appendMessageElement call.")
else:
    print("WARNING: old_send_call not found.")

with open(js_path, 'w', encoding='utf-8') as f:
    f.write(js)
print("script_v2.js fully updated.")
