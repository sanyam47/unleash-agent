import re

# 1. Update backend/api/chat_router.py to allow model_scope="all"
router_path = r'c:\coding\ai-trainer\backend\api\chat_router.py'
with open(router_path, 'r', encoding='utf-8') as f:
    code = f.read()

# Make search_knowledge query global shared RAG docs
old_rag_call = 'retrieved_docs = search_knowledge(latest_query, top_k=2, model_scope=req.model)'
new_rag_call = 'retrieved_docs = search_knowledge(latest_query, top_k=3, model_scope="all")'

if old_rag_call in code:
    code = code.replace(old_rag_call, new_rag_call)
    with open(router_path, 'w', encoding='utf-8') as f:
        f.write(code)
    print("chat_router.py updated to search shared global RAG.")
else:
    print("WARNING: old_rag_call not found in chat_router.py")

# 2. Update frontend/index.html:
# - Clean up sidebar: remove the restrictive per-model dropdown and make conversations unified
# - Add Antigravity-style floating popover model pill directly inside bottom prompt toolbar
# - Add shared skills button directly next to the model pill
# - Add CSS styles for the floating popover and message model badge

html_path = r'c:\coding\ai-trainer\frontend\index.html'
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

# Replace sidebar model selector with a sleek All Conversations header
old_sidebar_model_sec = '''                    <!-- Model Selector in Sidebar -->
                    <div style="padding: 10px 12px; border-bottom: 1px solid var(--border-subtle); background: var(--bg-surface);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                            <label style="margin: 0; font-size: 0.68rem; color: var(--text-muted); text-transform: uppercase;">
                                Model
                            </label>
                            <div style="display: flex; gap: 6px; align-items: center;">
                                <button onclick="openAddModelModal()" class="btn-quiet" style="padding: 1px 6px; font-size: 0.68rem;">
                                    + Add
                                </button>
                                <button onclick="refreshChatModels()" class="btn-quiet" style="padding: 1px 4px; font-size: 0.68rem;" title="Refresh models">
                                    ↻
                                </button>
                            </div>
                        </div>
                        <select id="chatModelSelect" onchange="onChatModelChange()" style="font-size: 0.8rem; padding: 7px 10px;">
                            <option value="">Scanning local models...</option>
                        </select>

                        <!-- Model Associated History Controls -->
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 8px;">
                            <span style="font-size: 0.68rem; color: var(--text-muted); font-family: var(--font-mono);" id="chatModelHistoryCountBadge">
                                Chats for this model
                            </span>
                            <button type="button" onclick="openImportChatsModal()" class="btn-quiet" style="font-size: 0.68rem; padding: 2px 7px; color: var(--text-secondary); border-color: var(--border-subtle);" title="Import chats from another model">
                                ↳ Import chats
                            </button>
                        </div>
                    </div>'''

new_sidebar_model_sec = '''                    <!-- Hidden select preserved for compatibility with modal scripts -->
                    <select id="chatModelSelect" style="display: none;"></select>

                    <!-- Conversations Header -->
                    <div style="padding: 10px 14px; border-bottom: 1px solid var(--border-subtle); background: var(--bg-surface); display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted);">
                            Conversations
                        </span>
                        <span style="font-size: 0.68rem; color: var(--text-muted); font-family: var(--font-mono);" id="chatModelHistoryCountBadge">
                            Shared History
                        </span>
                    </div>'''

if old_sidebar_model_sec in html:
    html = html.replace(old_sidebar_model_sec, new_sidebar_model_sec)
    print("Replaced sidebar model selector with unified conversations header.")
else:
    print("WARNING: old_sidebar_model_sec not found exactly.")

# Now replace the bottom prompt input bar to include the Antigravity-style pill & model popover
old_input_bar = '''                        <div style="display: flex; gap: 10px; align-items: flex-end; background: var(--bg-input); border: 1px solid var(--border-medium); border-radius: var(--radius-md); padding: 8px 12px;">
                            <!-- File input for screenshots/images -->
                            <input type="file" id="chatImagePicker" accept="image/*,.png,.jpg,.jpeg,.webp,.gif,.bmp" style="display: none;" onclick="this.value=null;" onchange="onChatImagePicked(event)">
                            <button type="button" id="btnAttachPin" onclick="triggerChatImagePicker()" title="Attach Screenshot / Image (or Ctrl+V paste directly into box)" class="btn-quiet" style="padding: 8px 10px; display: flex; align-items: center; justify-content: center; border-radius: 6px;">
                                <svg class="nav-icon-svg" style="width:16px;height:16px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l7.88-7.88"/></svg>
                            </button>
                            <textarea id="chatInputMessage" placeholder="Ask your local model anything or paste a screenshot (Ctrl+V)... (Shift+Enter for newline, Enter to send)" rows="2" style="border: none; background: transparent; padding: 4px; resize: none; font-size: 0.92rem;"></textarea>
                            <button id="btnSendChat" onclick="sendChatArenaMessage()" class="btn-primary-quiet" style="padding: 9px 16px; width: auto; border-radius: var(--radius-sm); display: flex; align-items: center; gap: 6px;">
                                <span>Send</span>
                                <svg class="nav-icon-svg" style="width:14px;height:14px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                            </button>
                        </div>'''

new_input_bar = '''                        <!-- Antigravity-Style Input Bar with Floating Controls -->
                        <div style="position: relative; background: var(--bg-input); border: 1px solid var(--border-medium); border-radius: var(--radius-md); padding: 8px 12px; display: flex; flex-direction: column; gap: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.2);">
                            <!-- Top Row: Prompt Textarea & Action Buttons -->
                            <div style="display: flex; gap: 10px; align-items: flex-end;">
                                <input type="file" id="chatImagePicker" accept="image/*,.png,.jpg,.jpeg,.webp,.gif,.bmp" style="display: none;" onclick="this.value=null;" onchange="onChatImagePicked(event)">
                                <button type="button" id="btnAttachPin" onclick="triggerChatImagePicker()" title="Attach Screenshot / Image (or Ctrl+V paste directly into box)" class="btn-quiet" style="padding: 7px 9px; display: flex; align-items: center; justify-content: center; border-radius: 6px;">
                                    <svg class="nav-icon-svg" style="width:15px;height:15px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l7.88-7.88"/></svg>
                                </button>
                                <textarea id="chatInputMessage" placeholder="Ask your local models anything or paste a screenshot (Shift+Enter for newline, Enter to send)..." rows="2" style="border: none; background: transparent; padding: 4px; resize: none; font-size: 0.92rem; flex: 1; min-height: 48px;"></textarea>
                                <button id="btnSendChat" onclick="sendChatArenaMessage()" class="btn-primary-quiet" style="padding: 8px 16px; border-radius: var(--radius-sm); display: flex; align-items: center; gap: 6px; font-weight: 600;">
                                    <span>Send</span>
                                    <svg class="nav-icon-svg" style="width:13px;height:13px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                                </button>
                            </div>

                            <!-- Bottom Row: Antigravity-Style Model & Skills Bar -->
                            <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 6px; border-top: 1px solid var(--border-subtle); font-size: 0.74rem;">
                                <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                                    <!-- Antigravity-Style Model Selector Pill -->
                                    <div style="position: relative;">
                                        <button type="button" id="btnModelPickerPill" onclick="toggleModelPickerPopover()" class="btn-quiet" style="padding: 3px 9px; font-size: 0.73rem; display: inline-flex; align-items: center; gap: 6px; background: rgba(255,255,255,0.03); border: 1px solid var(--border-subtle); color: var(--text-primary); border-radius: 6px;" title="Switch model for the next prompt">
                                            <span style="width: 5px; height: 5px; border-radius: 50%; background: #10b981; opacity: 0.85;"></span>
                                            <span id="promptActiveModelName">dolphin3:latest</span>
                                            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m6 9 6 6 6-6"/></svg>
                                        </button>

                                        <!-- Floating Model Selection Popover -->
                                        <div id="modelPickerPopover" style="display: none; position: absolute; bottom: calc(100% + 8px); left: 0; min-width: 280px; background: var(--bg-surface); border: 1px solid var(--border-medium); border-radius: 8px; box-shadow: 0 12px 28px rgba(0,0,0,0.5); z-index: 1000; padding: 6px 0;">
                                            <div style="padding: 6px 12px 4px; font-size: 0.68rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted); display: flex; justify-content: space-between; align-items: center;">
                                                <span>Local Models</span>
                                                <button type="button" onclick="openAddModelModal(); toggleModelPickerPopover();" class="btn-quiet" style="padding: 1px 5px; font-size: 0.65rem;">+ Add</button>
                                            </div>
                                            <div id="modelPickerPopoverList" style="max-height: 220px; overflow-y: auto; padding: 4px 0;">
                                                <!-- Populated dynamically via JS -->
                                            </div>
                                        </div>
                                    </div>

                                    <!-- Shared Skills Pill -->
                                    <button type="button" onclick="openChatSkillsQuickModal()" class="btn-quiet" style="padding: 3px 9px; font-size: 0.73rem; display: inline-flex; align-items: center; gap: 5px; border-radius: 6px; color: var(--text-secondary);" title="Attach or detach shared skills">
                                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m8 3 4 8 5-5 5 15H2L8 3z"/></svg>
                                        <span>Skills (<span id="chatActiveSkillsCountPill">1</span>)</span>
                                    </button>

                                    <!-- Shared Agentic Mode Toggle -->
                                    <button type="button" id="btnAgenticModeToggle" onclick="toggleAgenticMode()" class="btn-quiet" style="padding: 3px 9px; font-size: 0.73rem; display: inline-flex; align-items: center; gap: 5px; border-radius: 6px; color: var(--text-secondary);" title="Autonomous ReAct Mode (Multi-Step Tool Calling & Verification)">
                                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                                        <span>Agentic: <strong id="agenticStatusLabel">OFF</strong></span>
                                    </button>

                                    <!-- Shared Knowledge Base (RAG) Pill -->
                                    <button type="button" onclick="openKnowledgeBaseModal()" class="btn-quiet" style="padding: 3px 9px; font-size: 0.73rem; display: inline-flex; align-items: center; gap: 5px; border-radius: 6px; color: var(--text-secondary);" title="Shared Knowledge Base & Datasets">
                                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/><path d="M6 6h10"/><path d="M6 10h10"/></svg>
                                        <span>Knowledge</span>
                                    </button>
                                </div>

                                <div style="color: var(--text-muted); font-size: 0.68rem; font-family: var(--font-mono);">
                                    <span id="promptModelSpecsPill">8.0B • Q4_K_M</span>
                                </div>
                            </div>
                        </div>'''

if old_input_bar in html:
    html = html.replace(old_input_bar, new_input_bar)
    print("Replaced input bar with Antigravity-style floating controls.")
else:
    print("WARNING: old_input_bar not found exactly.")

# Bump cache buster
html = re.sub(r'style_v2\.css\?v=[^\"]+', 'style_v2.css?v=20261106_v9_antigravity', html)
html = re.sub(r'script_v2\.js\?v=[^\"]+', 'script_v2.js?v=20261106_v9_antigravity', html)

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
print("Updated index.html successfully with v9 cache buster.")
