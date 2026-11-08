import os

script_path = r"c:\coding\ai-trainer\frontend\script_v2.js"
with open(script_path, "r", encoding="utf-8") as f:
    text = f.read()

normalized = text.replace("\r\n", "\n")

# 1. Update the chat bubble project card
target1 = """        const chips = agenticData.created_files.map(f => {
            return `<button type="button" onclick="openAgentProjectModal('${agenticData.project_name}', '${f}')" class="btn-quiet" style="font-size:0.72rem;font-family:var(--font-mono);color:#60a5fa;border-color:rgba(96,165,250,0.3);padding:2px 8px;display:inline-flex;align-items:center;gap:4px;">
                <span>📄 ${f}</span>
            </button>`;
        }).join(' ');

        projCard.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <span style="font-size:0.76rem;font-weight:600;color:var(--text-primary);display:inline-flex;align-items:center;gap:6px;">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                    Generated Workspace Files:
                </span>
                <button type="button" onclick="openAgentProjectModal('${agenticData.project_name}')" class="btn-quiet" style="font-size:0.7rem;padding:2px 8px;color:#60a5fa;">
                    Open Workspace Explorer ↗
                </button>
            </div>
            <div style="display:flex;flex-wrap:wrap;gap:6px;">${chips}</div>
        `;"""

replacement1 = """        const hasHtml = (agenticData.created_files || []).some(f => f.toLowerCase().endsWith('.html'));
        const chips = agenticData.created_files.map(f => {
            return `<button type="button" onclick="openAgentProjectModal('${agenticData.project_name}', '${f}', 'code')" class="btn-quiet" style="font-size:0.72rem;font-family:var(--font-mono);color:#94a3b8;border-color:var(--border-subtle);padding:2px 8px;display:inline-flex;align-items:center;gap:4px;">
                <span>📄 ${f}</span>
            </button>`;
        }).join(' ');

        projCard.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;flex-wrap:wrap;gap:8px;">
                <span style="font-size:0.78rem;font-weight:600;color:var(--text-primary);display:inline-flex;align-items:center;gap:6px;">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                    Workspace (${agenticData.created_files.length} Files):
                </span>
                <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
                    ${hasHtml ? `
                        <button type="button" onclick="openAgentProjectModal('${agenticData.project_name}', null, 'preview')" class="btn-quiet" style="font-size:0.73rem;padding:3px 10px;color:#38bdf8;border-color:rgba(56,189,248,0.35);background:rgba(56,189,248,0.08);display:inline-flex;align-items:center;gap:4px;font-weight:600;" title="Live Interactive Browser Preview">
                            <span>🖥️ Live Preview</span>
                        </button>
                    ` : ''}
                    <button type="button" onclick="openProjectInVSCode('${agenticData.project_name}')" class="btn-quiet" style="font-size:0.73rem;padding:3px 10px;color:#60a5fa;border-color:rgba(96,165,250,0.3);display:inline-flex;align-items:center;gap:4px;" title="Open workspace folder in VS Code">
                        <span>💙 VS Code</span>
                    </button>
                    <button type="button" onclick="openAgentProjectModal('${agenticData.project_name}', null, 'code')" class="btn-quiet" style="font-size:0.73rem;padding:3px 9px;color:var(--text-secondary);" title="View file tree and code">
                        <span>Code ↗</span>
                    </button>
                </div>
            </div>
            <div style="display:flex;flex-wrap:wrap;gap:6px;">${chips}</div>
        `;"""

# 2. Update openAgentProjectModal and add VS Code / Folder launchers
target2 = """window.openAgentProjectModal = async function(projectName, initialFile = null) {
    const modal = document.getElementById('agentProjectModal');
    const titleEl = document.getElementById('agentProjectModalTitle');
    const bodyEl = document.getElementById('agentProjectModalBody');
    if (!modal || !bodyEl) return;

    if (titleEl) titleEl.textContent = `Project Workspace: ${projectName}`;
    bodyEl.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-muted);">Loading project files...</div>';
    modal.style.display = 'flex';

    try {
        const res = await fetch(`/api/chat/agent/projects/${encodeURIComponent(projectName)}/files`);
        const data = await res.json();
        const files = data.files || [];

        if (files.length === 0) {
            bodyEl.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-muted);">No files found in this workspace yet.</div>';
            return;
        }

        let currentActiveFile = initialFile || files[0].path;

        const renderModalContent = async (selectedFilePath) => {
            currentActiveFile = selectedFilePath;
            let fileContent = 'Loading...';
            try {
                const fRes = await fetch(`/api/chat/agent/projects/${encodeURIComponent(projectName)}/file?file_path=${encodeURIComponent(selectedFilePath)}`);
                const fData = await fRes.json();
                fileContent = fData.content || '(Empty file)';
            } catch (err) {
                fileContent = 'Error reading file: ' + err.message;
            }

            bodyEl.innerHTML = `
                <div style="display: flex; gap: 14px; flex: 1; min-height: 380px;">
                    <!-- File tree sidebar -->
                    <div style="width: 220px; border-right: 1px solid var(--border-subtle); padding-right: 12px; display: flex; flex-direction: column; gap: 4px;">
                        <span style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; margin-bottom: 4px;">Files (${files.length})</span>
                        ${files.map(f => {
                            const isSel = f.path === currentActiveFile;
                            return `
                                <div onclick="window._onProjectFileSelect('${projectName}', '${f.path}')" style="cursor: pointer; padding: 6px 10px; border-radius: 6px; font-size: 0.78rem; font-family: var(--font-mono); display: flex; justify-content: space-between; align-items: center; background: ${isSel ? 'rgba(96, 165, 250, 0.15)' : 'transparent'}; color: ${isSel ? '#60a5fa' : 'var(--text-secondary)'}; border: 1px solid ${isSel ? 'rgba(96, 165, 250, 0.3)' : 'transparent'};">
                                    <span>${f.path}</span>
                                    <span style="font-size: 0.65rem; color: var(--text-muted);">${Math.round(f.size_bytes / 1024 * 10) / 10}KB</span>
                                </div>
                            `;
                        }).join('')}
                    </div>

                    <!-- Code / Content Viewer -->
                    <div style="flex: 1; display: flex; flex-direction: column; min-width: 0;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <span style="font-size: 0.8rem; font-weight: 600; color: var(--text-primary); font-family: var(--font-mono);">${currentActiveFile}</span>
                            <button type="button" onclick="navigator.clipboard.writeText(document.getElementById('projectFileViewerCode').innerText); alert('Code copied to clipboard!');" class="btn-quiet" style="font-size: 0.72rem; padding: 3px 8px;">
                                Copy File Code
                            </button>
                        </div>
                        <pre id="projectFileViewerCode" style="flex: 1; margin: 0; background: var(--bg-base); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 12px; font-family: var(--font-mono); font-size: 0.78rem; color: var(--text-primary); overflow: auto; line-height: 1.5; white-space: pre-wrap;">${escapeHtml(fileContent)}</pre>
                    </div>
                </div>
            `;
        };

        window._onProjectFileSelect = (proj, file) => {
            renderModalContent(file);
        };

        renderModalContent(currentActiveFile);

    } catch (err) {
        bodyEl.innerHTML = `<div style="padding: 20px; text-align: center; color: var(--danger);">Failed to load project: ${err.message}</div>`;
    }
};

window.closeAgentProjectModal = function() {
    const modal = document.getElementById('agentProjectModal');
    if (modal) modal.style.display = 'none';
};"""

replacement2 = """window.openProjectInVSCode = async function(projectName) {
    try {
        const res = await fetch(`/api/chat/agent/projects/${encodeURIComponent(projectName)}/open_vscode`, { method: 'POST' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Could not open VS Code');
        // Flash subtle confirmation
        const note = document.createElement('div');
        note.style.position = 'fixed';
        note.style.bottom = '24px';
        note.style.right = '24px';
        note.style.background = '#1e2229';
        note.style.border = '1px solid #3b4252';
        note.style.color = '#38bdf8';
        note.style.padding = '10px 16px';
        note.style.borderRadius = '8px';
        note.style.fontSize = '0.8rem';
        note.style.boxShadow = '0 8px 24px rgba(0,0,0,0.5)';
        note.style.zIndex = '99999';
        note.innerHTML = `<span>💙 Workspace '${escapeHtml(projectName)}' opened in VS Code!</span>`;
        document.body.appendChild(note);
        setTimeout(() => note.remove(), 3500);
    } catch (err) {
        alert("VS Code Launcher: " + err.message);
    }
};

window.openProjectFolder = async function(projectName) {
    try {
        await fetch(`/api/chat/agent/projects/${encodeURIComponent(projectName)}/open_folder`, { method: 'POST' });
    } catch (err) {
        alert("Folder Launcher: " + err.message);
    }
};

window.openAgentProjectModal = async function(projectName, initialFile = null, initialView = null) {
    const modal = document.getElementById('agentProjectModal');
    const titleEl = document.getElementById('agentProjectModalTitle');
    const actionsEl = document.getElementById('agentProjectModalActions');
    const bodyEl = document.getElementById('agentProjectModalBody');
    if (!modal || !bodyEl) return;

    if (titleEl) titleEl.textContent = `Project Workspace: ${projectName}`;
    if (actionsEl) actionsEl.innerHTML = '';
    bodyEl.innerHTML = '<div style="padding: 40px; text-align: center; color: var(--text-muted); font-size: 0.85rem;">Loading workspace files...</div>';
    modal.style.display = 'flex';

    try {
        const res = await fetch(`/api/chat/agent/projects/${encodeURIComponent(projectName)}/files`);
        const data = await res.json();
        const files = data.files || [];

        if (files.length === 0) {
            bodyEl.innerHTML = '<div style="padding: 40px; text-align: center; color: var(--text-muted);">No files generated in this workspace yet.</div>';
            return;
        }

        const hasHtml = files.some(f => f.path.toLowerCase().endsWith('.html'));
        let currentView = initialView || (hasHtml ? 'preview' : 'code');
        let currentActiveFile = initialFile || files[0].path;

        const renderView = async () => {
            // Update top action bar buttons
            if (actionsEl) {
                actionsEl.innerHTML = `
                    <div style="display: flex; background: rgba(255,255,255,0.04); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 2px;">
                        ${hasHtml ? `
                            <button type="button" onclick="window._setWorkspaceView('preview')" style="font-size: 0.74rem; font-weight: 600; padding: 3px 10px; border: none; border-radius: 4px; cursor: pointer; background: ${currentView === 'preview' ? 'var(--accent)' : 'transparent'}; color: ${currentView === 'preview' ? '#ffffff' : 'var(--text-secondary)'};">
                                🖥️ Live Preview
                            </button>
                        ` : ''}
                        <button type="button" onclick="window._setWorkspaceView('code')" style="font-size: 0.74rem; font-weight: 600; padding: 3px 10px; border: none; border-radius: 4px; cursor: pointer; background: ${currentView === 'code' ? 'var(--accent)' : 'transparent'}; color: ${currentView === 'code' ? '#ffffff' : 'var(--text-secondary)'};">
                            📄 Code View
                        </button>
                    </div>

                    ${hasHtml ? `
                        <a href="/api/chat/agent/projects/${encodeURIComponent(projectName)}/preview" target="_blank" class="btn-quiet" style="font-size: 0.72rem; padding: 4px 10px; text-decoration: none; color: #38bdf8; display: inline-flex; align-items: center; gap: 4px;" title="Open live website in full browser tab">
                            <span>↗ Open in Tab</span>
                        </a>
                    ` : ''}

                    <button type="button" onclick="openProjectInVSCode('${projectName}')" class="btn-quiet" style="font-size: 0.72rem; padding: 4px 10px; color: #60a5fa; display: inline-flex; align-items: center; gap: 4px;" title="Open this workspace in VS Code">
                        <span>💙 VS Code</span>
                    </button>

                    <button type="button" onclick="openProjectFolder('${projectName}')" class="btn-quiet" style="font-size: 0.72rem; padding: 4px 10px; color: var(--text-secondary); display: inline-flex; align-items: center; gap: 4px;" title="Open directory in Windows Explorer">
                        <span>📁 Folder</span>
                    </button>
                `;
            }

            if (currentView === 'preview' && hasHtml) {
                // Live Browser Rendering View (Antigravity-style)
                const previewUrl = `/api/chat/agent/projects/${encodeURIComponent(projectName)}/preview`;
                bodyEl.innerHTML = `
                    <div style="display: flex; flex-direction: column; flex: 1; border-radius: 8px; overflow: hidden; border: 1px solid var(--border-subtle); background: #ffffff;">
                        <!-- Browser Header Strip -->
                        <div style="background: #14171a; padding: 8px 12px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #242930;">
                            <div style="display: flex; align-items: center; gap: 6px;">
                                <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: #ef4444; opacity: 0.8;"></span>
                                <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: #f59e0b; opacity: 0.8;"></span>
                                <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: #10b981; opacity: 0.8;"></span>
                                <div style="margin-left: 10px; background: #0d0f11; border: 1px solid #242930; padding: 2px 12px; border-radius: 4px; font-family: var(--font-mono); font-size: 0.72rem; color: #94a3b8; display: inline-flex; align-items: center; gap: 6px;">
                                    <span style="color: #10b981;">🔒</span>
                                    <span>http://127.0.0.1:8001${previewUrl}</span>
                                </div>
                            </div>
                            <div style="display: flex; align-items: center; gap: 6px;">
                                <button type="button" onclick="const f = document.getElementById('projectPreviewIframe'); if (f) f.src = f.src;" class="btn-quiet" style="font-size: 0.7rem; padding: 2px 8px; color: #94a3b8;" title="Reload preview">
                                    ⟳ Refresh
                                </button>
                                <a href="${previewUrl}" target="_blank" class="btn-quiet" style="font-size: 0.7rem; padding: 2px 8px; text-decoration: none; color: #38bdf8;">
                                    ↗ Full Screen
                                </a>
                            </div>
                        </div>

                        <!-- Live Iframe View -->
                        <iframe id="projectPreviewIframe" src="${previewUrl}" style="flex: 1; width: 100%; border: none; background: #ffffff;" sandbox="allow-scripts allow-forms allow-same-origin allow-modals"></iframe>
                    </div>
                `;
            } else {
                // Code Explorer View
                let fileContent = 'Loading...';
                try {
                    const fRes = await fetch(`/api/chat/agent/projects/${encodeURIComponent(projectName)}/file?file_path=${encodeURIComponent(currentActiveFile)}`);
                    const fData = await fRes.json();
                    fileContent = fData.content || '(Empty file)';
                } catch (err) {
                    fileContent = 'Error reading file: ' + err.message;
                }

                bodyEl.innerHTML = `
                    <div style="display: flex; gap: 14px; flex: 1; min-height: 0; overflow: hidden;">
                        <!-- File tree sidebar -->
                        <div style="width: 220px; border-right: 1px solid var(--border-subtle); padding-right: 12px; display: flex; flex-direction: column; gap: 4px; overflow-y: auto;">
                            <span style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; margin-bottom: 6px; font-weight: 600;">Workspace Files (${files.length})</span>
                            ${files.map(f => {
                                const isSel = f.path === currentActiveFile;
                                return `
                                    <div onclick="window._onProjectFileSelect('${projectName}', '${f.path}')" style="cursor: pointer; padding: 6px 10px; border-radius: 6px; font-size: 0.78rem; font-family: var(--font-mono); display: flex; justify-content: space-between; align-items: center; background: ${isSel ? 'rgba(96, 165, 250, 0.15)' : 'transparent'}; color: ${isSel ? '#60a5fa' : 'var(--text-secondary)'}; border: 1px solid ${isSel ? 'rgba(96, 165, 250, 0.3)' : 'transparent'}; transition: 0.15s;">
                                        <span>${f.path}</span>
                                        <span style="font-size: 0.65rem; color: var(--text-muted);">${Math.round(f.size_bytes / 1024 * 10) / 10}KB</span>
                                    </div>
                                `;
                            }).join('')}
                        </div>

                        <!-- Code / Content Viewer -->
                        <div style="flex: 1; display: flex; flex-direction: column; min-width: 0; overflow: hidden;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                <span style="font-size: 0.82rem; font-weight: 600; color: var(--text-primary); font-family: var(--font-mono);">${currentActiveFile}</span>
                                <button type="button" onclick="navigator.clipboard.writeText(document.getElementById('projectFileViewerCode').innerText); alert('Code copied to clipboard!');" class="btn-quiet" style="font-size: 0.72rem; padding: 3px 8px;">
                                    Copy File Code
                                </button>
                            </div>
                            <pre id="projectFileViewerCode" style="flex: 1; margin: 0; background: var(--bg-base); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 12px; font-family: var(--font-mono); font-size: 0.78rem; color: var(--text-primary); overflow: auto; line-height: 1.5; white-space: pre-wrap;">${escapeHtml(fileContent)}</pre>
                        </div>
                    </div>
                `;
            }
        };

        window._setWorkspaceView = (view) => {
            currentView = view;
            renderView();
        };

        window._onProjectFileSelect = (proj, file) => {
            currentActiveFile = file;
            currentView = 'code';
            renderView();
        };

        renderView();

    } catch (err) {
        bodyEl.innerHTML = `<div style="padding: 20px; text-align: center; color: var(--danger);">Failed to load project: ${err.message}</div>`;
    }
};

window.closeAgentProjectModal = function() {
    const modal = document.getElementById('agentProjectModal');
    if (modal) modal.style.display = 'none';
};"""

if target1 not in normalized:
    print("ERROR: target1 not found in script_v2.js")
elif target2 not in normalized:
    print("ERROR: target2 not found in script_v2.js")
else:
    normalized = normalized.replace(target1, replacement1, 1)
    normalized = normalized.replace(target2, replacement2, 1)
    with open(script_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(normalized)
    print("SUCCESS: script_v2.js updated with Antigravity-style Live Browser Preview and VS Code launcher.")
