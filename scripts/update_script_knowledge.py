import os

script_path = r"c:\coding\ai-trainer\frontend\script_v2.js"
with open(script_path, "r", encoding="utf-8") as f:
    text = f.read()

normalized = text.replace("\r\n", "\n")

# 1. Update appendMessageElement to handle [KNOWLEDGE_ACQUIRE_PROPOSAL:...]
target1 = """    textSpan.innerHTML = formatMarkdown(cleanText);
    bubble.appendChild(textSpan);"""

replacement1 = """    // Detect Autonomous Knowledge Acquisition Proposal
    const knowledgeMatch = cleanText.match(/\\[KNOWLEDGE_ACQUIRE_PROPOSAL:([^:]+):([^:]+):([^:]+):([^\\]]+)\\]/);
    if (knowledgeMatch) {
        cleanText = cleanText.replace(knowledgeMatch[0], '').trim();
        const kDomain = knowledgeMatch[1];
        const kDbName = knowledgeMatch[2];
        const kDesc = knowledgeMatch[3];
        const kUrl = knowledgeMatch[4];

        const kCard = document.createElement('div');
        kCard.style.margin = '12px 0';
        kCard.style.padding = '14px 16px';
        kCard.style.background = '#14171a';
        kCard.style.border = '1px solid #2d323b';
        kCard.style.borderRadius = '8px';
        kCard.style.display = 'flex';
        kCard.style.flexDirection = 'column';
        kCard.style.gap = '10px';
        kCard.style.color = '#c9d1d9';

        kCard.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #22262e; padding-bottom: 8px;">
                <div style="display: flex; align-items: center; gap: 8px; font-size: 0.82rem; font-weight: 600; color: #94a3b8;">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
                    <span>Knowledge Gap: ${escapeHtml(kDomain.toUpperCase())}</span>
                </div>
                <span style="font-size: 0.68rem; font-family: var(--font-mono); color: #64748b; background: #0d0f11; padding: 2px 7px; border-radius: 4px; border: 1px solid #242930;">Ungrounded Domain</span>
            </div>
            <div style="font-size: 0.77rem; color: #8b949e; line-height: 1.45;">
                The model recognizes its base weights lack verified ground truth for this entity. It has identified the premier authoritative database:
            </div>
            <div style="background: #0d0f11; border: 1px solid #242930; border-radius: 6px; padding: 10px 12px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                    <strong style="color: #e2e8f0; font-size: 0.82rem;">${escapeHtml(kDbName)}</strong>
                    <a href="${escapeHtml(kUrl)}" target="_blank" style="color: #60a5fa; font-size: 0.7rem; text-decoration: none;">Official Source ↗</a>
                </div>
                <div style="font-size: 0.73rem; color: #717d8a; line-height: 1.4;">
                    ${escapeHtml(kDesc)}
                </div>
            </div>
            <div style="display: flex; gap: 8px; align-items: center; margin-top: 4px;">
                <button type="button" onclick="executeKnowledgeAcquire(this, '${escapeHtml(kDomain)}', '${escapeHtml(kDbName)}')" class="btn-quiet" style="font-size: 0.76rem; padding: 6px 16px; font-weight: 600; cursor: pointer; background: #1e2229; border: 1px solid #3b4252; color: #e2e8f0; border-radius: 6px; display: inline-flex; align-items: center; gap: 6px;">
                    <span>⚡ Download & Setup into Model (1-Click)</span>
                </button>
            </div>
        `;
        bubble.appendChild(kCard);
    }

    textSpan.innerHTML = formatMarkdown(cleanText);
    bubble.appendChild(textSpan);"""

# 2. Add executeKnowledgeAcquire function to script_v2.js
target2 = """// Human-In-The-Loop Package Installer Action"""

replacement2 = """// Autonomous Knowledge Acquisition & Model Grounding Action
window.executeKnowledgeAcquire = async function(btn, domainKey, dbName) {
    if (!btn) return;
    const parent = btn.parentElement;
    btn.disabled = true;
    btn.innerHTML = `<span>⏳ Downloading & Indexing ${escapeHtml(dbName)}...</span>`;

    try {
        const activeModel = window.activeChatModel || document.getElementById('chatModelSelect')?.value || 'dolphin3:latest';
        const res = await fetch('/api/chat/knowledge/acquire', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ domain_key: domainKey, model: activeModel })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Knowledge acquisition failed');

        btn.style.background = 'rgba(16, 185, 129, 0.12)';
        btn.style.color = '#10b981';
        btn.style.borderColor = 'rgba(16, 185, 129, 0.35)';
        btn.innerHTML = `<span>✓ ${data.records_indexed || 'All'} Records Indexed into Model Memory</span>`;

        if (parent) {
            const notice = document.createElement('div');
            notice.style.fontSize = '0.74rem';
            notice.style.color = '#10b981';
            notice.style.marginTop = '6px';
            notice.style.fontFamily = 'var(--font-mono)';
            notice.innerHTML = `<span>Grounded in ${escapeHtml(dbName)}. Re-analyzing your prompt with full accuracy...</span>`;
            parent.appendChild(notice);
        }

        // Enable Cyber RAG so subsequent query incorporates the new vector knowledge
        window.cyberRAGEnabled = true;

        // Automatically re-run the user's prompt through the newly grounded model!
        setTimeout(() => {
            const session = getActiveSession();
            if (session && session.messages && session.messages.length > 0) {
                const lastUserMsg = [...session.messages].reverse().find(m => m.role === 'user');
                if (lastUserMsg) {
                    const input = document.getElementById('chatInputMessage');
                    if (input) {
                        input.value = lastUserMsg.content;
                        sendChatArenaMessage();
                    }
                }
            }
        }, 1200);

    } catch (err) {
        btn.disabled = false;
        btn.innerHTML = 'Retry Setup';
        alert("Failed to setup knowledge database: " + err.message);
    }
};

// Human-In-The-Loop Package Installer Action"""

errors = []
if target1 not in normalized: errors.append("target1")
if target2 not in normalized: errors.append("target2")

if errors:
    print(f"ERROR: Missing targets: {errors}")
else:
    normalized = normalized.replace(target1, replacement1, 1)
    normalized = normalized.replace(target2, replacement2, 1)
    with open(script_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(normalized)
    print("SUCCESS: script_v2.js updated with Knowledge Card & 1-click auto-setup.")
