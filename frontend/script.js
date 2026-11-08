const API_BASE = window.location.origin;

function switchAppTab(tabId) {
    console.log("Switching to tab:", tabId);
    const sections = ['train-section', 'lab-section', 'llm-section', 'chat-section'];
    sections.forEach(s => {
        const el = document.getElementById(s);
        if (el) el.style.display = (s === tabId) ? 'block' : 'none';
    });

    const btnMap = {
        'train-section': 'btn-train',
        'lab-section': 'id-lab-btn',
        'llm-section': 'btn-llm',
        'chat-section': 'btn-chat'
    };

    Object.entries(btnMap).forEach(([sec, btnId]) => {
        const btn = document.getElementById(btnId);
        if (btn) btn.classList.toggle('active', sec === tabId);
    });

    if (tabId === 'lab-section' && window.refreshLabModels) window.refreshLabModels();
    if (tabId === 'llm-section' && window.initLLMStudio) window.initLLMStudio();
    if (tabId === 'chat-section' && window.initChatArena) window.initChatArena();
}
window.showTab = switchAppTab;
window.switchAppTab = switchAppTab;

async function refreshLabModels(modelToSelect = null) {
    console.log("Refreshing Lab Models...");
    try {
        const res = await fetch(`${API_BASE}/lab/models`);
        const models = await res.json();
        const select = document.getElementById('labModelSelect');
        if (!select) return;
        
        select.innerHTML = '<option value="">-- Select a .pkl --</option>';
        models.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = m;
            if (m === modelToSelect) opt.selected = true;
            select.appendChild(opt);
        });
    } catch (err) {
        console.error("Failed to refresh models:", err);
    }
}

window.onbeforeunload = function () {
    console.log("PAGE RELOADING");
};
let userPrompt = "";
let detectedTask = "";
let currentLabAnalysis = null;
let lastInjectedFilePath = null;

async function injectCustomData() {
    const fileInput = document.getElementById("labDataInjection");
    const file = fileInput.files[0];
    const alertBox = document.getElementById("labIntelligenceAlert");
    const alertMsg = document.getElementById("labAlertMessage");
    
    if (!file) {
        lastInjectedFilePath = null;
        alertBox.style.display = "none";
        return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("target_classes", JSON.stringify(currentLabAnalysis.new_labels || []));
    formData.append("goal_description", userPrompt); // Pass the instruction for relevance check

    try {
        let res = await fetch(`${API_BASE}/lab/inject`, {
            method: "POST",
            body: formData
        });
        let data = await res.json();
        
        if (data.is_valid) {
            lastInjectedFilePath = data.file_path;
            alertBox.style.display = "block";
            
            if (data.warnings && data.warnings.length > 0) {
                const isCritical = data.warnings.some(w => w.includes("CRITICAL"));
                
                alertBox.style.background = isCritical ? "rgba(255, 0, 0, 0.1)" : "rgba(255, 165, 0, 0.15)";
                alertBox.style.borderColor = isCritical ? "red" : "orange";
                alertBox.style.color = isCritical ? "#ff4d4d" : "orange";

                let html = `<b>Intelligence Audit:</b><ul>` + 
                           data.warnings.map(w => `<li>${w}</li>`).join('') + 
                           `</ul>`;
                
                if (isCritical) {
                    html += `<div style="margin-top:10px; display:flex; gap:10px;">
                                <button onclick="discardInjection()" style="background:#444; font-size:0.75rem;">🤖 Discard & Use AI Data</button>
                                <button onclick="document.getElementById('labDataInjection').click()" style="background:#007bff; font-size:0.75rem;">📁 Upload New File</button>
                             </div>`;
                } else {
                    html += `<br><i>AI will automatically supplement the missing data.</i>`;
                }
                alertMsg.innerHTML = html;
            } else {
                alertBox.style.background = "rgba(0, 255, 0, 0.1)";
                alertBox.style.borderColor = "green";
                alertBox.style.color = "green";
                alertMsg.innerText = "✅ Data is 100% relevant and sufficient!";
            }
        } else {
            alert("❌ CSV Error: " + data.message);
            fileInput.value = "";
        }
    } catch (err) {
        console.error(err);
    }
}

function discardInjection() {
    document.getElementById("labDataInjection").value = "";
    document.getElementById("labIntelligenceAlert").style.display = "none";
    lastInjectedFilePath = null;
    alert("Discarded. System will now use its internal Knowledge Base.");
}

async function viewLineage() {
    const modelName = document.getElementById("labModelSelect").value;
    if (!modelName) return alert("Please select a model first.");

    const modal = document.getElementById("lineageModal");
    const content = document.getElementById("lineageContent");
    modal.style.display = "flex";
    content.innerHTML = "📡 Loading history...";

    try {
        let res = await fetch(`${API_BASE}/lab/lineage/${modelName}`);
        let history = await res.json();

        if (history.length === 0) {
            content.innerHTML = `<p style="color:#888;">No version history found for this model yet.</p>`;
            return;
        }

        content.innerHTML = history.map((h, i) => `
            <div style="margin-bottom: 15px; padding: 12px; background: rgba(255,255,255,0.05); border-left: 4px solid #007bff; border-radius: 4px;">
                <div style="display:flex; justify-content:space-between;">
                    <b style="color:#007bff;">Version ${h.version}</b>
                    <span style="font-size:0.8rem; color:#888;">${h.id.substring(0,8)}</span>
                </div>
                <p style="font-size:0.9rem; margin: 8px 0;">"${h.instruction}"</p>
                <div style="display:flex; justify-content:space-between; align-items:center; margin-top:5px;">
                    <span style="font-size:0.8rem; color: #28a745;">🎯 Accuracy: ${h.accuracy || 'N/A'}</span>
                    <button onclick="window.location.href='${API_BASE}/download_model?job_id=${h.id}'" style="width:auto; padding: 3px 10px; font-size:0.75rem;">📥 Download</button>
                </div>
                ${i < history.length - 1 ? '<div style="text-align:center; margin-top:10px; color:#444;">↓</div>' : ''}
            </div>
        `).join('');

    } catch (err) {
        content.innerHTML = "❌ Error fetching lineage.";
    }
}

function closeLineage() {
    document.getElementById("lineageModal").style.display = "none";
}

async function interpret() {
    userPrompt = document.getElementById("inputText").value;

    let res = await fetch(`${API_BASE}/interpret`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({task: userPrompt})
    });

    if (res.status === 429) {
        alert("Google AI Rate Limit Reached. Please wait 60 seconds.");
        return;
    }

    let data = await res.json();
    detectedTask = data.task;

    document.getElementById("result").innerText =
        "Detected task: " + detectedTask;

    document.getElementById("confirmBox").style.display = "block";
}

function confirmTrain() {
    document.getElementById("confirmBox").style.display = "none";
    document.getElementById("modeSelection").style.display = "block";
}

function editInput() {
    document.getElementById("confirmBox").style.display = "none";
}

function selectAuto() {
    document.getElementById("warningBox").style.display = "block";
}

async function confirmAuto() {
    document.getElementById("warningBox").style.display = "none";
    document.getElementById("modeSelection").style.display = "none";
    
    let username = document.getElementById("usernameInput") ? document.getElementById("usernameInput").value : "Anonymous";
    
    let res = await fetch(`${API_BASE}/auto-train`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({task: userPrompt, username: username || "Anonymous"})
    });

    let data = await res.json();
    let jobId = data.job_id;

    if (jobId) {
        alert("🤖 Job queued! ID: " + jobId + "\nWe will poll for the result...");
        pollJobStatus(jobId);
    } else {
        alert("❌ Error: Response did not include job_id. Data: " + JSON.stringify(data));
    }
}

let currentTrainModelName = null;
let currentTrainJobId = null;

async function pollJobStatus(jobId) {
    currentTrainJobId = jobId;
    const statusDiv = document.getElementById("result");
    statusDiv.innerText = "⏳ Training in progress (ID: " + jobId + ")...";

    const interval = setInterval(async () => {
        try {
            let res = await fetch(`${API_BASE}/jobs/${jobId}`);
            let data = await res.json();

            if (data.status === "completed") {
                clearInterval(interval);
                statusDiv.innerHTML = "✅ <b>Training Complete!</b><br>" + data.message + 
                                     `<br><button class='secondary' onclick="downloadModel('${jobId}')" style='margin-top:10px;'>📥 Download .pkl Model</button>`;
                
                // Show testing playground
                document.getElementById("trainTestingSection").style.display = "block";
                
                // Extract model name from path
                if (data.model_path) {
                    currentTrainModelName = data.model_path.split('/').pop().split('\\').pop();
                    
                    // Toggle file/text input based on modality
                    if (data.intent && data.intent.modality === "image") {
                        document.getElementById("trainTestTextInput").style.display = "none";
                        document.getElementById("trainTestFileInput").style.display = "block";
                    } else {
                        document.getElementById("trainTestTextInput").style.display = "block";
                        document.getElementById("trainTestFileInput").style.display = "none";
                    }
                }
                alert("✅ Model trained successfully!");
            } else if (data.status === "failed") {
                clearInterval(interval);
                statusDiv.innerHTML = "❌ <b>Training Failed:</b> " + data.message;
                alert("❌ Training failed: " + data.message);
            } else {
                statusDiv.innerText = "⏳ Status: " + data.status + "...";
            }
        } catch (err) {
            console.error("Poll error:", err);
        }
    }, 2000);
}

function downloadModel(jobId) {
    let url = `${API_BASE}/download_model`;
    if (jobId) {
        url += `?job_id=${jobId}`;
    }
    window.open(url);
}

function selectManual() {
    document.getElementById("uploadSection").style.display = "block";
    document.getElementById("warningBox").style.display = "none";
}

async function trainManual() {
    const fileInput = document.getElementById("fileInput");
    const files = fileInput.files;

    if (files.length === 0) {
        alert("Please select at least one CSV file!");
        return;
    }

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
        formData.append("files", files[i]);
    }
    formData.append("task", userPrompt);
    let username = document.getElementById("usernameInput") ? document.getElementById("usernameInput").value : "Anonymous";
    formData.append("username", username || "Anonymous");

    document.getElementById("uploadSection").style.display = "none";
    document.getElementById("modeSelection").style.display = "none";

    try {
        let res = await fetch(`${API_BASE}/train/manual`, {
            method: "POST",
            body: formData
        });

        let data = await res.json();
        let jobId = data.job_id;

        if (jobId) {
            alert("📁 Manual job queued! ID: " + jobId);
            pollJobStatus(jobId);
        } else {
            alert("❌ Error: " + JSON.stringify(data));
        }
    } catch (err) {
        console.error("Upload error:", err);
        alert("❌ Failed to upload dataset.");
    }
}

// --- TAB MANAGEMENT ---
function showTab(tabId) {
    document.querySelectorAll('.container').forEach(c => c.style.display = 'none');
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    
    document.getElementById(tabId).style.display = 'block';
    event.currentTarget.classList.add('active');
}

// --- MODEL LAB LOGIC ---

async function refreshLabModels() {
    const select = document.getElementById("labModelSelect");
    try {
        let res = await fetch(`${API_BASE}/lab/models`);
        let models = await res.json();
        
        select.innerHTML = '<option value="">-- Select a .pkl --</option>';
        models.forEach(m => {
            let option = document.createElement("option");
            option.value = m;
            option.text = m;
            select.appendChild(option);
        });
    } catch (err) {
        console.error("Failed to fetch models", err);
    }
}

async function uploadLabModel() {
    const fileInput = document.getElementById("labModelUpload");
    const file = fileInput.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    const resultDiv = document.getElementById("labResult");
    resultDiv.innerHTML = "📤 Uploading external model...";

    try {
        let res = await fetch(`${API_BASE}/lab/upload`, {
            method: "POST",
            body: formData
        });
        let data = await res.json();
        alert(data.message);
        await refreshLabModels();
        document.getElementById("labModelSelect").value = data.filename;
        resultDiv.innerHTML = `✅ Model ${data.filename} ready for analysis.`;
    } catch (err) {
        console.error("Upload error", err);
        alert("❌ Failed to upload model.");
    }
}

async function analyzeLab() {
    const modelName = document.getElementById("labModelSelect").value;
    const instruction = document.getElementById("labInstruction").value;
    const resultDiv = document.getElementById("labResult");

    if (!modelName || !instruction) {
        alert("Please select a model and provide an instruction.");
        return;
    }

    resultDiv.innerHTML = "🧪 Analyzing model metadata & instruction...";
    
    try {
        let res = await fetch(`${API_BASE}/lab/analyze`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                model_name: modelName,
                instruction: instruction
            })
        });
        
        if (res.status === 429) {
            alert("Google AI Rate Limit Reached. Please wait 60 seconds.");
            resultDiv.innerHTML = "❌ Rate Limit Reached.";
            return;
        }
        
        currentLabAnalysis = await res.json();
        
        document.getElementById("labActionText").innerHTML = 
            `<b>Action:</b> ${currentLabAnalysis.action}<br>` +
            `<b>Strategy:</b> ${currentLabAnalysis.message}<br>` +
            `<b>Classes to Add:</b> ${currentLabAnalysis.new_labels?.join(', ') || 'None'}<br>` +
            `<b>Classes to Remove:</b> ${currentLabAnalysis.remove_labels?.join(', ') || 'None'}`;
        
        document.getElementById("labProposal").style.display = "block";
        resultDiv.innerHTML = "✅ Analysis complete. Ready to execute.";
    } catch (err) {
        resultDiv.innerHTML = "❌ Failed to analyze instruction.";
    }
}

async function executeLab() {
    const modelName = document.getElementById("labModelSelect").value;
    const instruction = document.getElementById("labInstruction").value;
    const resultDiv = document.getElementById("labResult");

    document.getElementById("labProposal").style.display = "none";
    resultDiv.innerHTML = "⚡ Initiating Deep Manipulation (Knowledge Distillation)...";

    try {
        let res = await fetch(`${API_BASE}/lab/execute`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                model_name: modelName,
                instruction: instruction,
                analysis: currentLabAnalysis,
                injected_file_path: lastInjectedFilePath,
                auto_fill_gaps: document.getElementById("labAutoFillGaps").checked
            })
        });
        
        let data = await res.json();
        if (data.job_id) {
            pollLabStatus(data.job_id);
        }
    } catch (err) {
        resultDiv.innerHTML = "❌ Execution failed.";
    }
}

async function sendLabFeedback() {
    const feedback = document.getElementById("labChatInput").value;
    const modelName = document.getElementById("labModelSelect").value;
    const resultDiv = document.getElementById("labResult");

    if (!feedback) return;

    resultDiv.innerHTML = "💬 Refining requirements...";
    
    try {
        let res = await fetch(`${API_BASE}/lab/chat`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                model_name: modelName,
                feedback: feedback,
                previous_analysis: currentLabAnalysis,
                history: [] 
            })
        });
        
        if (res.status === 429) {
            alert("Google AI Rate Limit Reached. Please wait 60 seconds.");
            resultDiv.innerHTML = "❌ Rate Limit Reached.";
            return;
        }
        
        currentLabAnalysis = await res.json();
        
        // Update the display with the new analysis
        document.getElementById("labActionText").innerHTML = 
            `<b>Action:</b> ${currentLabAnalysis.action}<br>` +
            `<b>Strategy:</b> ${currentLabAnalysis.message}<br>` +
            `<b>Classes to Add:</b> ${currentLabAnalysis.new_labels?.join(', ') || 'None'}<br>` +
            `<b>Classes to Remove:</b> ${currentLabAnalysis.remove_labels?.join(', ') || 'None'}`;
        
        document.getElementById("labChatInput").value = "";
        resultDiv.innerHTML = "✅ Proposal refined.";
    } catch (err) {
        console.error("Refine error", err);
        resultDiv.innerHTML = "❌ Failed to refine proposal.";
    }
}

function pollLabStatus(jobId) {
    const resultDiv = document.getElementById("labResult");
    const interval = setInterval(async () => {
        try {
            let res = await fetch(`${API_BASE}/jobs/${jobId}`);
            let data = await res.json();
            
            if (data.status === "completed") {
                clearInterval(interval);
                let analyticsHtml = "";
                if (data.accuracy && data.accuracy.overall) {
                    const stats = data.accuracy;
                    analyticsHtml = `
                        <div style="margin-top:15px; padding:12px; background:rgba(0,0,0,0.2); border-radius:8px; font-size:0.85rem; text-align:left;">
                            <p style="color:#007bff; font-weight:bold; margin-bottom:10px;">📊 Performance Comparison:</p>
                            <table style="width:100%; border-collapse:collapse;">
                                <tr style="border-bottom:1px solid #333;">
                                    <th style="text-align:left;">Model</th>
                                    <th style="text-align:left;">Accuracy</th>
                                </tr>
                                <tr>
                                    <td>Parent</td>
                                    <td>${(stats.overall.parent_accuracy * 100).toFixed(1)}%</td>
                                </tr>
                                <tr style="color:#28a745; font-weight:bold;">
                                    <td>Student</td>
                                    <td>${(stats.overall.student_accuracy * 100).toFixed(1)}%</td>
                                </tr>
                            </table>
                        </div>`;
                }
                
                resultDiv.innerHTML = `
                    🏁 <b>Manipulation Complete!</b><br>
                    ${data.message}<br>
                    ${analyticsHtml}
                    <br>
                    <div style="display: flex; gap: 10px;">
                        <button class="primary" style="flex:1;" onclick="window.location.href='${API_BASE}/lab/download_model?job_id=${jobId}'">
                            📥 Download Model (.pkl)
                        </button>
                        <button class="secondary" style="flex:1;" onclick="window.location.href='${API_BASE}/lab/download_report/${jobId}'">
                            📑 Download Audit Report
                        </button>
                    </div>
                    <p style="font-size: 0.8rem; color: #888; margin-top: 10px;">The model has been saved to your /models folder as well.</p>
                `;
                
                // Show Live Test Lab
                document.getElementById('liveTestArea').style.display = 'block';
                currentJobId = jobId; // Store for testing
                
                alert("Deep Manipulation Successful!");
                refreshLabModels();
            } else if (data.status === "failed") {
                clearInterval(interval);
                resultDiv.innerHTML = `❌ <b>Failed:</b> ${data.message}`;
            } else {
                resultDiv.innerText = `⚡ Status: ${data.status}...`;
            }
        } catch (err) { console.error(err); }
    }, 2000);
}

async function uploadLabModel() {
    const fileInput = document.getElementById('labModelUpload');
    const resultDiv = document.getElementById('labResult');
    const statusBadge = document.getElementById('labUploadStatus');
    
    if (fileInput.files.length === 0) return;

    // Step 1: Initialize Intake
    statusBadge.style.display = 'block';
    statusBadge.innerHTML = `📦 Intake: <b>${fileInput.files[0].name}</b>`;
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = `📡 <b>Step 1/3:</b> Preparing data...`;

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    try {
        resultDiv.innerHTML = `🚀 <b>Step 2/3:</b> Transmitting to Intelligence Lab...`;
        
        // Using relative path for maximum stability
        let res = await fetch(`/lab/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!res.ok) {
            const error = await res.json();
            throw new Error(error.detail || "Server rejected the model");
        }
        
        resultDiv.innerHTML = `🧠 <b>Step 3/3:</b> Processing intelligence...`;
        let data = await res.json();
        
        resultDiv.innerHTML = `✅ <b>Final:</b> ${data.message}`;
        statusBadge.innerHTML = `✅ <b>Stored:</b> ${fileInput.files[0].name}`;
        statusBadge.style.borderColor = "#28a745";
        statusBadge.style.animation = "none";
        
        refreshLabModels(fileInput.files[0].name);
    } catch (err) {
        resultDiv.innerHTML = `❌ <b>Transmission Error:</b> ${err.message}`;
        statusBadge.innerHTML = `❌ <b>Failed:</b> ${fileInput.files[0].name}`;
        statusBadge.style.background = "rgba(220, 53, 69, 0.1)";
        statusBadge.style.borderColor = "#dc3545";
        statusBadge.style.animation = "none";
    }
}

async function analyzeLab() {
    let model = document.getElementById('labModelSelect').value;
    const instruction = document.getElementById('labInstruction').value;
    const proposalDiv = document.getElementById('labProposal');
    const actionText = document.getElementById('labActionText');
    const statusBadge = document.getElementById('labUploadStatus');

    // Fallback: If dropdown is empty but they just uploaded a file, use that file
    if (!model && statusBadge.innerHTML.includes("Stored:")) {
        const fileInput = document.getElementById('labModelUpload');
        if (fileInput.files.length > 0) {
            model = fileInput.files[0].name;
            // Also update the dropdown visually so they see it
            const select = document.getElementById('labModelSelect');
            if (select) select.value = model;
        }
    }

    if (!model || !instruction) return alert("Please select a model and describe the modification.");

    proposalDiv.style.display = 'block';
    actionText.innerHTML = "📡 AI is interpreting manipulation plan...";

    try {
        let res = await fetch(`${API_BASE}/lab/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model_name: model, instruction: instruction })
        });
        currentLabAnalysis = await res.json();
        
        actionText.innerHTML = `
            <div style="color: #60a5fa; font-weight: bold; margin-bottom: 5px;">PROPOSED ACTION: ${currentLabAnalysis.action}</div>
            <div style="font-size: 0.9rem; color: #ccc;">${currentLabAnalysis.reasoning}</div>
            <div style="margin-top: 10px; font-size: 0.8rem; color: #888;">New Targets: ${currentLabAnalysis.new_labels.join(', ')}</div>
        `;
    } catch (err) {
        actionText.innerHTML = `<span style="color:red;">Error: ${err.message}</span>`;
    }
}

async function sendLabFeedback() {
    const feedback = document.getElementById('labChatInput').value;
    const actionText = document.getElementById('labActionText');
    if (!feedback) return;

    actionText.innerHTML = "🔄 Refining plan based on feedback...";
    try {
        let res = await fetch(`${API_BASE}/lab/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                model_name: document.getElementById('labModelSelect').value,
                instruction: document.getElementById('labInstruction').value,
                feedback: feedback,
                previous_analysis: currentLabAnalysis
            })
        });
        currentLabAnalysis = await res.json();
        
        actionText.innerHTML = `
            <div style="color: #a78bfa; font-weight: bold; margin-bottom: 5px;">REFINED ACTION: ${currentLabAnalysis.action}</div>
            <div style="font-size: 0.9rem; color: #ccc;">${currentLabAnalysis.reasoning}</div>
            <div style="margin-top: 10px; font-size: 0.8rem; color: #888;">Updated Targets: ${currentLabAnalysis.new_labels.join(', ')}</div>
        `;
    } catch (err) { console.error(err); }
}

async function injectCustomData() {
    const file = document.getElementById('labDataInjection').files[0];
    const alertBox = document.getElementById('labIntelligenceAlert');
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);
    formData.append("target_classes", JSON.stringify(currentLabAnalysis.new_labels || []));
    formData.append("goal_description", document.getElementById('labInstruction').value);

    alertBox.style.display = "block";
    alertBox.className = "card intelligence-alert";
    alertBox.innerHTML = "🛡️ Auditing Data Relevance...";

    try {
        let res = await fetch(`${API_BASE}/lab/inject`, {
            method: "POST",
            body: formData
        });
        let data = await res.json();
        
        if (data.status === "REJECTED" || data.status === "CRITICAL") {
            alertBox.style.background = "rgba(220, 53, 69, 0.2)";
            alertBox.style.borderColor = "#dc3545";
            alertBox.innerHTML = `
                ❌ <b>RELEVANCE GUARD:</b> ${data.message}
                <br><br>
                <div style="display: flex; gap: 10px;">
                    <button class="primary" onclick="discardInjection()">🤖 Discard & Use AI Data</button>
                    <button class="secondary" onclick="document.getElementById('labDataInjection').click()">📁 Upload New File</button>
                </div>
            `;
        } else {
            alertBox.style.background = "rgba(40, 167, 69, 0.2)";
            alertBox.style.borderColor = "#28a745";
            alertBox.innerHTML = `✅ <b>DATA VERIFIED:</b> ${data.message}`;
        }
    } catch (err) { console.error(err); }
}

async function executeLab() {
    const model = document.getElementById('labModelSelect').value;
    const resultDiv = document.getElementById('labResult');
    const autoFill = document.getElementById('labAutoFillGaps').checked;

    resultDiv.style.display = 'block';
    resultDiv.innerHTML = "⚡ Initializing Deep Manipulation Engine...";

    try {
        let res = await fetch(`${API_BASE}/lab/execute`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                model_name: model,
                instruction: document.getElementById('labInstruction').value,
                analysis: currentLabAnalysis,
                auto_fill_gaps: autoFill
            })
        });
        let data = await res.json();
        pollLabStatus(data.job_id);
    } catch (err) {
        resultDiv.innerHTML = `<span style="color:red;">Execution failed: ${err.message}</span>`;
    }
}

async function testLabModel() {
    let model = document.getElementById('labModelSelect').value;
    const text = document.getElementById('labTestInput').value;
    const resultBox = document.getElementById('labTestResult');
    const predText = document.getElementById('testPredictionText');
    const confText = document.getElementById('testConfidenceText');
    const probBox = document.getElementById('testProbabilities');
    const statusBadge = document.getElementById('labUploadStatus');

    if (!model && statusBadge.innerHTML.includes("Stored:")) {
        const fileInput = document.getElementById('labModelUpload');
        if (fileInput.files.length > 0) {
            model = fileInput.files[0].name;
            const select = document.getElementById('labModelSelect');
            if (select) select.value = model;
        }
    }

    if (!model) return alert("Please select a model to test.");
    if (!text) return alert("Please enter some text to test.");

    resultBox.style.display = "block";
    predText.innerHTML = "⏳ Predicting...";
    confText.innerHTML = "--";
    probBox.innerHTML = "";

    try {
        const formData = new FormData();
        formData.append("model_name", model);
        
        const fileInput = document.getElementById('labTestFileInput');
        if (fileInput.files.length > 0) {
            formData.append("file", fileInput.files[0]);
        } else {
            formData.append("text", text);
        }

        let res = await fetch(`${API_BASE}/lab/predict`, {
            method: 'POST',
            body: formData
        });
        
        let data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Prediction failed");

        predText.innerHTML = data.prediction;
        confText.innerHTML = (data.confidence * 100).toFixed(1);
        
        let probHtml = "<b>All Probabilities:</b><br>";
        for (const [cls, prob] of Object.entries(data.all_probs || {})) {
            probHtml += `${cls}: ${(prob * 100).toFixed(1)}%<br>`;
        }
        probBox.innerHTML = probHtml;
        
        let fbContainer = document.getElementById('labFeedbackContainer');
        if(fbContainer) fbContainer.style.display = 'block';
    } catch (err) {
        predText.innerHTML = `<span style="color:red;">Error: ${err.message}</span>`;
        confText.innerHTML = "--";
    }
}

async function testTrainModel() {
    if (!currentTrainModelName) return alert("No trained model found.");
    
    const textInput = document.getElementById('trainTestTextInput').value;
    const fileInput = document.getElementById('trainTestFileInput');
    const resultBox = document.getElementById('trainTestResult');
    const predText = document.getElementById('trainTestPredictionText');
    const confText = document.getElementById('trainTestConfidenceText');
    const probBox = document.getElementById('trainTestProbabilities');

    resultBox.style.display = "block";
    predText.innerHTML = "⏳ Predicting...";
    confText.innerHTML = "--";
    probBox.innerHTML = "";

    try {
        const formData = new FormData();
        formData.append("model_name", currentTrainModelName);
        
        if (fileInput.files.length > 0) {
            formData.append("file", fileInput.files[0]);
        } else {
            formData.append("text", textInput);
        }

        let res = await fetch(`${API_BASE}/lab/predict`, {
            method: 'POST',
            body: formData
        });
        
        let data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Prediction failed");

        predText.innerHTML = data.prediction;
        confText.innerHTML = (data.confidence * 100).toFixed(1);
        
        let probHtml = "<b>All Probabilities:</b><br>";
        for (const [cls, prob] of Object.entries(data.all_probs || {})) {
            probHtml += `${cls}: ${(prob * 100).toFixed(1)}%<br>`;
        }
        probBox.innerHTML = probHtml;
        
        let fbContainer = document.getElementById('trainFeedbackContainer');
        if(fbContainer) fbContainer.style.display = 'block';
    } catch (err) {
        predText.innerHTML = `<span style="color:red;">Error: ${err.message}</span>`;
        confText.innerHTML = "--";
    }
}

async function refineTrainModel() {
    if (!currentTrainModelName) return alert("No model to refine.");
    
    const instruction = document.getElementById('trainRefineInstruction').value;
    if (!instruction) return alert("Please tell the AI what is wrong with the model.");
    
    const autoFill = document.getElementById('trainRefineAutoFill').checked;
    const fileInput = document.getElementById('trainRefineData');
    
    const resultDiv = document.getElementById("result");
    resultDiv.innerHTML = "🧠 AI is analyzing your refinement request...";
    
    // Hide testing sections during training
    document.getElementById("trainTestingSection").style.display = "none";
    
    try {
        // 1. Analyze what needs to be done
        let res = await fetch(`${API_BASE}/lab/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model_name: currentTrainModelName, instruction: instruction })
        });
        let analysis = await res.json();
        
        // 2. Upload file if needed
        let injected_path = null;
        if (fileInput.files.length > 0) {
            resultDiv.innerHTML = "📤 Uploading correct data...";
            const formData = new FormData();
            formData.append("file", fileInput.files[0]);
            formData.append("target_classes", JSON.stringify(analysis.new_labels || []));
            formData.append("goal_description", instruction);
            
            let injectRes = await fetch(`${API_BASE}/lab/inject`, { method: "POST", body: formData });
            let injectData = await injectRes.json();
            injected_path = injectData.path || null;
        }
        
        // 3. Execute
        resultDiv.innerHTML = "🚀 Dispatching Deep Manipulation Engine...";
        let execRes = await fetch(`${API_BASE}/lab/execute`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                model_name: currentTrainModelName,
                instruction: instruction,
                analysis: analysis,
                auto_fill_gaps: autoFill,
                injected_file_path: injected_path
            })
        });
        
        let execData = await execRes.json();
        
        // 4. Poll
        pollJobStatus(execData.job_id);
        
    } catch (err) {
        resultDiv.innerHTML = `<span style="color:red;">Refinement failed: ${err.message}</span>`;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const analyzeBtn = document.getElementById("analyzeLabBtn");
    if (analyzeBtn) analyzeBtn.onclick = analyzeLab;

    const executeBtn = document.getElementById("executeLabBtn");
    if (executeBtn) executeBtn.onclick = executeLab;

    const injectInput = document.getElementById("labDataInjection");
    if (injectInput) injectInput.onchange = injectCustomData;

    const btn = document.getElementById("trainBtn");
    if (btn) btn.onclick = trainManual;
});

async function loadCommunityFeed() {
    // Community feed disabled - this is a 100% private personal app
    return;
}

async function submitTrainFeedback() {
    const rating = document.querySelector('input[name="train-rating"]:checked');
    const comment = document.getElementById("trainFeedbackComment").value;
    if(!rating) return alert("Please select a star rating");
    if(!currentTrainJobId) return alert("No active job to rate.");
    
    try {
        let res = await fetch(`${API_BASE}/jobs/${currentTrainJobId}/feedback`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ rating: parseInt(rating.value), comment: comment })
        });
        if(res.ok) {
            document.getElementById("trainFeedbackContainer").innerHTML = "<p class='success-text' style='text-align:center;'>✅ Thanks for your feedback!</p>";
            loadCommunityFeed();
        }
    } catch(err) { console.error(err); }
}

async function submitLabFeedback() {
    document.getElementById("labFeedbackContainer").innerHTML = "<p class='success-text' style='text-align:center;'>✅ Thanks for your feedback!</p>";
}

// ==========================================
// 🔥 LLM FINE-TUNING & DATA STUDIO MODULE
// ==========================================
window.llmSessionId = null;
window.llmSamples = [];

window.initLLMStudio = async function() {
    try {
        const res = await fetch('/api/llm/models');
        if (res.ok) {
            const data = await res.json();
            const select = document.getElementById("llmBaseModel");
            if (select && data.models) {
                select.innerHTML = "";
                data.models.forEach(m => {
                    const opt = document.createElement("option");
                    opt.value = m.id;
                    opt.textContent = `${m.name} (${m.params}) - ${m.ideal_for}`;
                    select.appendChild(opt);
                });
            }
        }
    } catch (err) {
        console.error("Failed to load LLM models:", err);
    }
};

window.huntLLMData = async function() {
    const promptInput = document.getElementById("llmPromptInput");
    const prompt = promptInput ? promptInput.value.trim() : "";
    if (!prompt) {
        alert("Please enter a domain or task description for your LLM!");
        return;
    }

    const targetCount = parseInt(document.getElementById("llmTargetCount").value) || 40;
    const includeHf = document.getElementById("chkHf").checked;
    const includeKaggle = document.getElementById("chkKaggle").checked;
    const includeAi = document.getElementById("chkAi").checked;

    const btn = document.getElementById("btnHunt");
    const statusDiv = document.getElementById("huntStatus");

    btn.disabled = true;
    btn.innerHTML = "⏳ Harvesting Datasets...";
    statusDiv.style.display = "block";
    statusDiv.innerHTML = `<span style="color:#60a5fa;">Hunting high-precision data across selected repositories for <strong>"${prompt}"</strong>...</span>`;

    try {
        const res = await fetch('/api/llm/hunt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt: prompt,
                include_huggingface: includeHf,
                include_kaggle: includeKaggle,
                include_ai_synthesis: includeAi,
                target_samples: targetCount
            })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Data hunting failed");
        }

        const data = await res.json();
        window.llmSessionId = data.session_id;
        window.llmSamples = data.samples;

        statusDiv.innerHTML = `✅ Successfully harvested <strong>${data.total_samples} samples</strong> from: <em>${data.sources.join(', ')}</em>! Proceed to curation below.`;

        // Reveal sections
        document.getElementById("llmCurationSection").style.display = "block";
        document.getElementById("llmTrainingConfigSection").style.display = "block";

        // Render initial stats & table
        renderLLMData(data.samples, {
            initial_samples: data.total_samples,
            retained_samples: data.samples.length,
            retention_rate: 100,
            avg_tokens: Math.round(data.samples.reduce((a, b) => a + (b.token_count || 0), 0) / Math.max(1, data.samples.length))
        });

    } catch (err) {
        statusDiv.innerHTML = `<span style="color:#ef4444;">❌ Error: ${err.message}</span>`;
    } finally {
        btn.disabled = false;
        btn.innerHTML = "🏹 Hunt Data";
    }
};

window.applyLLMFilters = async function() {
    if (!window.llmSessionId) return;

    const minTokens = parseInt(document.getElementById("filterMinTokens").value) || 10;
    const maxTokens = parseInt(document.getElementById("filterMaxTokens").value) || 2048;
    const minQuality = parseFloat(document.getElementById("filterMinQuality").value) || 0.70;
    const deduplicate = document.getElementById("filterDedupe").checked;
    const keyword = document.getElementById("filterKeyword").value.trim();
    const exclude = document.getElementById("filterExclude").value.trim();

    try {
        const res = await fetch('/api/llm/filter', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: window.llmSessionId,
                min_tokens: minTokens,
                max_tokens: maxTokens,
                min_quality: minQuality,
                deduplicate: deduplicate,
                keyword_filter: keyword,
                exclude_keyword: exclude
            })
        });

        if (!res.ok) throw new Error("Filter request failed");
        const data = await res.json();
        window.llmSamples = data.samples;
        renderLLMData(data.samples, data.stats);
    } catch (err) {
        alert("Filter error: " + err.message);
    }
};

function renderLLMData(samples, stats) {
    if (stats) {
        document.getElementById("statHarvested").textContent = stats.initial_samples || samples.length;
        document.getElementById("statRetained").textContent = stats.retained_samples !== undefined ? stats.retained_samples : samples.length;
        document.getElementById("statRate").textContent = (stats.retention_rate || 100) + "%";
        document.getElementById("statAvgTokens").textContent = stats.avg_tokens || 0;
        document.getElementById("badgeCount").textContent = stats.retained_samples !== undefined ? stats.retained_samples : samples.length;
    }

    const tbody = document.getElementById("llmSamplesTbody");
    if (!tbody) return;
    tbody.innerHTML = "";

    if (!samples || samples.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding: 20px; color:#888;">No samples matching current filters.</td></tr>`;
        return;
    }

    samples.forEach(s => {
        const tr = document.createElement("tr");
        tr.style.borderBottom = "1px solid #333";
        const shortInst = s.instruction.length > 70 ? s.instruction.substring(0, 70) + "..." : s.instruction;
        const shortOut = s.output.length > 80 ? s.output.substring(0, 80) + "..." : s.output;

        tr.innerHTML = `
            <td style="padding: 8px; color: #60a5fa; font-size: 0.75rem;">${s.source || 'General'}</td>
            <td style="padding: 8px;"><span style="color:#4ade80; font-weight:bold;">${Math.round((s.quality_score || 0.85)*100)}%</span></td>
            <td style="padding: 8px; max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${s.instruction.replace(/"/g, '&quot;')}">${shortInst}</td>
            <td style="padding: 8px; max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color:#aaa;" title="${s.output.replace(/"/g, '&quot;')}">${shortOut}</td>
            <td style="padding: 8px; text-align: center;">
                <button onclick="deleteLLMSample('${s.id}')" style="background: transparent; color: #ef4444; border: 1px solid #ef4444; border-radius: 4px; padding: 2px 6px; font-size: 0.75rem; cursor: pointer;">✕</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

window.deleteLLMSample = async function(sampleId) {
    if (!window.llmSessionId) return;
    try {
        const res = await fetch('/api/llm/sample/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: window.llmSessionId,
                sample_id: sampleId,
                action: 'delete'
            })
        });
        if (res.ok) {
            window.llmSamples = window.llmSamples.filter(s => s.id !== sampleId);
            renderLLMData(window.llmSamples, {
                retained_samples: window.llmSamples.length,
                avg_tokens: Math.round(window.llmSamples.reduce((a, b) => a + (b.token_count || 0), 0) / Math.max(1, window.llmSamples.length))
            });
        }
    } catch (err) {
        console.error("Delete failed:", err);
    }
};

window.packageCloudTraining = async function() {
    if (!window.llmSessionId) {
        alert("Please hunt and curate a dataset first!");
        return;
    }

    const baseModel = document.getElementById("llmBaseModel").value;
    const outputName = document.getElementById("llmOutputName").value.trim() || "my-custom-llm";
    const loraRank = parseInt(document.getElementById("llmLoraRank").value) || 16;
    const loraAlpha = parseInt(document.getElementById("llmLoraAlpha").value) || 32;
    const epochs = parseInt(document.getElementById("llmEpochs").value) || 3;
    const lr = parseFloat(document.getElementById("llmLearningRate").value) || 0.0002;

    const resultDiv = document.getElementById("llmExportResult");
    resultDiv.style.display = "block";
    resultDiv.innerHTML = `<span style="color:#60a5fa;">⏳ Packaging dataset and generating cloud notebook for <strong>${baseModel}</strong>...</span>`;

    try {
        const res = await fetch('/api/llm/package/cloud', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: window.llmSessionId,
                base_model: baseModel,
                output_model_name: outputName,
                lora_rank: loraRank,
                lora_alpha: loraAlpha,
                epochs: epochs,
                learning_rate: lr
            })
        });

        if (!res.ok) throw new Error("Packaging failed");
        const data = await res.json();

        resultDiv.innerHTML = `
            <h4 style="color:#4ade80; margin-bottom: 8px;">🎉 1-Click Cloud Training Bundle Ready!</h4>
            <p style="font-size:0.9rem; color:#ccc; margin-bottom: 10px;">
                Contains <strong>${data.sample_count} curated samples</strong> (<code>dataset.jsonl</code>), standalone Jupyter Notebook (<code>train_unsloth_colab.ipynb</code>), and headless script for RunPod/Vast.ai.
            </p>
            <a href="${data.download_url}" download style="display:inline-block; background:#059669; color:#fff; text-decoration:none; padding:10px 20px; border-radius:6px; font-weight:bold; margin-bottom: 10px;">
                ⬇️ Download Cloud Training ZIP (${data.zip_filename})
            </a>
            <div style="font-size:0.8rem; color:#aaa; background:rgba(0,0,0,0.4); padding:10px; border-radius:4px; margin-top:10px;">
                <strong>Quick Run Guide:</strong><br>
                1. Upload this ZIP to RunPod, Vast.ai, or open the <code>.ipynb</code> in Google Colab.<br>
                2. Run all cells to fine-tune your model using 4-bit QLoRA.<br>
                3. The script automatically exports a <code>.gguf</code> model for local Ollama/LM Studio use!
            </div>
        `;
    } catch (err) {
        resultDiv.innerHTML = `<span style="color:#ef4444;">❌ Packaging Error: ${err.message}</span>`;
    }
};

window.downloadOllamaModelfile = function() {
    if (!window.llmSessionId) {
        alert("Please hunt data or generate a package first!");
        return;
    }
    const outputName = document.getElementById("llmOutputName").value.trim() || "my-custom-llm";
    window.open(`/api/llm/download/ollama/${window.llmSessionId}`, '_blank');
    
    const resultDiv = document.getElementById("llmExportResult");
    resultDiv.style.display = "block";
    resultDiv.innerHTML = `
        <h4 style="color:#38bdf8; margin-bottom: 8px;">🦙 Ollama Modelfile Downloaded!</h4>
        <p style="font-size:0.85rem; color:#ccc;">To serve your fine-tuned model locally in Ollama:</p>
        <pre style="background:#000; color:#4ade80; padding:10px; border-radius:4px; font-size:0.85rem; overflow-x:auto;">ollama create ${outputName} -f Modelfile\nollama run ${outputName}</pre>
    `;
};

// ==========================================
// 💬 LOCAL CHAT ARENA MODULE (ChatGPT-Style Multi-Chat)
// 100% Offline & Private (Stored strictly in localStorage)
// ==========================================
window.chatSessions = [];
window.activeSessionId = null;
window.chatModels = [];
window.isChatGenerating = false;

const SESSIONS_STORAGE_KEY = 'offline_chat_sessions_v1';

window.initChatArena = async function() {
    console.log("Initializing ChatGPT-Style Local Arena...");
    await refreshChatStatus();
    await refreshChatModels();
    loadChatSessions();

    const input = document.getElementById('chatInputMessage');
    if (input && !input.dataset.bound) {
        input.dataset.bound = "true";
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendChatArenaMessage();
            }
        });
    }
};

function loadChatSessions() {
    try {
        const stored = localStorage.getItem(SESSIONS_STORAGE_KEY);
        if (stored) {
            window.chatSessions = JSON.parse(stored);
        } else {
            window.chatSessions = [];
        }
    } catch (e) {
        console.warn("Failed to parse stored chat sessions:", e);
        window.chatSessions = [];
    }

    if (window.chatSessions.length === 0) {
        createNewChatSession(false);
    } else {
        // Activate most recent session
        window.activeSessionId = window.chatSessions[0].id;
        renderChatSessionsSidebar();
        renderActiveThread();
    }
}

function saveChatSessions() {
    try {
        localStorage.setItem(SESSIONS_STORAGE_KEY, JSON.stringify(window.chatSessions));
    } catch (e) {
        console.error("Storage save failed:", e);
    }
}

window.createNewChatSession = function(render = true) {
    const selectedModel = document.getElementById('chatModelSelect')?.value || (window.chatModels[0]?.name || 'dolphin3:latest');
    const newSession = {
        id: 'chat_' + Date.now() + '_' + Math.random().toString(36).substring(2, 6),
        title: 'New Conversation',
        model: selectedModel,
        systemPrompt: document.getElementById('chatSystemPrompt')?.value || "You are an uncensored, highly capable, intelligent AI assistant.",
        temperature: parseFloat(document.getElementById('chatTempSlider')?.value) || 0.7,
        messages: [],
        createdAt: Date.now()
    };

    window.chatSessions.unshift(newSession);
    window.activeSessionId = newSession.id;
    saveChatSessions();

    if (render) {
        renderChatSessionsSidebar();
        renderActiveThread();
        const input = document.getElementById('chatInputMessage');
        if (input) input.focus();
    }
};

function getActiveSession() {
    return window.chatSessions.find(s => s.id === window.activeSessionId) || null;
}

function renderChatSessionsSidebar() {
    const listContainer = document.getElementById('chatSessionsList');
    if (!listContainer) return;
    listContainer.innerHTML = '';

    if (window.chatSessions.length === 0) {
        listContainer.innerHTML = '<div style="padding: 15px; color: #64748b; font-size: 0.8rem; text-align: center;">No saved conversations yet.</div>';
        return;
    }

    window.chatSessions.forEach(s => {
        const item = document.createElement('div');
        const isActive = s.id === window.activeSessionId;
        item.style.padding = '10px 12px';
        item.style.borderRadius = '8px';
        item.style.cursor = 'pointer';
        item.style.display = 'flex';
        item.style.alignItems = 'center';
        item.style.justifyContent = 'space-between';
        item.style.transition = '0.15s';
        item.style.background = isActive ? 'rgba(124, 58, 237, 0.2)' : 'transparent';
        item.style.border = isActive ? '1px solid rgba(168, 85, 247, 0.4)' : '1px solid transparent';
        item.className = 'chat-session-item';

        const textDiv = document.createElement('div');
        textDiv.style.flex = '1';
        textDiv.style.overflow = 'hidden';
        textDiv.style.marginRight = '8px';
        textDiv.onclick = () => switchChatSession(s.id);

        const titleDiv = document.createElement('div');
        titleDiv.style.fontSize = '0.85rem';
        titleDiv.style.fontWeight = isActive ? 'bold' : 'normal';
        titleDiv.style.color = isActive ? '#fff' : '#cbd5e1';
        titleDiv.style.whiteSpace = 'nowrap';
        titleDiv.style.overflow = 'hidden';
        titleDiv.style.textOverflow = 'ellipsis';
        titleDiv.textContent = s.title || 'New Conversation';

        const metaDiv = document.createElement('div');
        metaDiv.style.fontSize = '0.7rem';
        metaDiv.style.color = '#64748b';
        metaDiv.style.marginTop = '2px';
        metaDiv.textContent = `${s.model || 'model'} • ${s.messages ? s.messages.length : 0} msgs`;

        textDiv.appendChild(titleDiv);
        textDiv.appendChild(metaDiv);

        // Delete button
        const delBtn = document.createElement('button');
        delBtn.innerHTML = '✕';
        delBtn.title = 'Delete Chat';
        delBtn.style.background = 'transparent';
        delBtn.style.border = 'none';
        delBtn.style.color = '#64748b';
        delBtn.style.cursor = 'pointer';
        delBtn.style.fontSize = '0.85rem';
        delBtn.style.padding = '4px 6px';
        delBtn.style.borderRadius = '4px';
        delBtn.onmouseenter = () => delBtn.style.color = '#ef4444';
        delBtn.onmouseleave = () => delBtn.style.color = '#64748b';
        delBtn.onclick = (e) => {
            e.stopPropagation();
            deleteChatSession(s.id);
        };

        item.appendChild(textDiv);
        item.appendChild(delBtn);
        listContainer.appendChild(item);
    });
}

window.switchChatSession = function(sessionId) {
    if (window.activeSessionId === sessionId) return;
    window.activeSessionId = sessionId;
    renderChatSessionsSidebar();
    renderActiveThread();
};

window.deleteChatSession = function(sessionId) {
    window.chatSessions = window.chatSessions.filter(s => s.id !== sessionId);
    if (window.activeSessionId === sessionId) {
        window.activeSessionId = window.chatSessions.length > 0 ? window.chatSessions[0].id : null;
    }
    saveChatSessions();
    if (!window.activeSessionId) {
        createNewChatSession(true);
    } else {
        renderChatSessionsSidebar();
        renderActiveThread();
    }
};

window.clearAllChatSessions = function() {
    if (!confirm("Are you sure you want to permanently delete all local chat sessions?")) return;
    window.chatSessions = [];
    window.activeSessionId = null;
    saveChatSessions();
    createNewChatSession(true);
};

function renderActiveThread() {
    const session = getActiveSession();
    const thread = document.getElementById('chatMessagesThread');
    const titleEl = document.getElementById('chatActiveTitle');
    if (!thread) return;

    if (!session) {
        thread.innerHTML = '';
        return;
    }

    if (titleEl) titleEl.textContent = session.title || 'New Conversation';
    
    // Sync model dropdown to session model
    const modelSelect = document.getElementById('chatModelSelect');
    if (modelSelect && session.model) {
        modelSelect.value = session.model;
        onChatModelChange();
    }

    thread.innerHTML = '';

    if (!session.messages || session.messages.length === 0) {
        // Render Empty Welcome Hero
        thread.innerHTML = `
            <div id="chatEmptyHero" style="text-align: center; margin: auto 0; padding: 40px 10px;">
                <div style="font-size: 2.8rem; margin-bottom: 12px;">⚡</div>
                <h3 style="color: #fff; margin-bottom: 8px; font-size: 1.3rem;">Local Offline Chat Arena</h3>
                <p style="color: #888; font-size: 0.9rem; max-width: 520px; margin: 0 auto 24px; line-height: 1.5;">
                    Operating directly on your <strong>NVIDIA GeForce RTX 3050 Laptop GPU</strong>.<br>
                    100% private, zero internet connectivity required, and zero censorship.
                </p>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; max-width: 650px; margin: 0 auto;">
                    <div onclick="selectQuickPrompt(this.innerText)" style="background: #161622; border: 1px solid #27273a; padding: 14px; border-radius: 8px; text-align: left; cursor: pointer; font-size: 0.85rem; color: #cbd5e1; transition: 0.2s;" onmouseenter="this.style.borderColor='#a855f7'" onmouseleave="this.style.borderColor='#27273a'">
                        🛡️ Write a Python vulnerability scanner for common CVEs
                    </div>
                    <div onclick="selectQuickPrompt(this.innerText)" style="background: #161622; border: 1px solid #27273a; padding: 14px; border-radius: 8px; text-align: left; cursor: pointer; font-size: 0.85rem; color: #cbd5e1; transition: 0.2s;" onmouseenter="this.style.borderColor='#a855f7'" onmouseleave="this.style.borderColor='#27273a'">
                        ⚡ Write an optimized C++ program demonstrating memory heap safety
                    </div>
                    <div onclick="selectQuickPrompt(this.innerText)" style="background: #161622; border: 1px solid #27273a; padding: 14px; border-radius: 8px; text-align: left; cursor: pointer; font-size: 0.85rem; color: #cbd5e1; transition: 0.2s;" onmouseenter="this.style.borderColor='#a855f7'" onmouseleave="this.style.borderColor='#27273a'">
                        🐍 Build a fast asynchronous network probe in Python
                    </div>
                    <div onclick="selectQuickPrompt(this.innerText)" style="background: #161622; border: 1px solid #27273a; padding: 14px; border-radius: 8px; text-align: left; cursor: pointer; font-size: 0.85rem; color: #cbd5e1; transition: 0.2s;" onmouseenter="this.style.borderColor='#a855f7'" onmouseleave="this.style.borderColor='#27273a'">
                        🧠 Explain how abliteration mathematically removes refusal vectors
                    </div>
                </div>
            </div>
        `;
        return;
    }

    session.messages.forEach(m => {
        appendMessageElement(m.role, m.content, m.telemetry, false);
    });

    thread.scrollTop = thread.scrollHeight;
}

window.refreshChatStatus = async function() {
    try {
        const res = await fetch('/api/chat/status');
        const data = await res.json();
        const badge = document.getElementById('chatOllamaStatusBadge');
        const startBtn = document.getElementById('btnStartOllama');
        
        if (data.status === 'online') {
            if (badge) {
                badge.style.background = 'rgba(34, 197, 94, 0.15)';
                badge.style.color = '#4ade80';
                badge.style.borderColor = '#22c55e';
                badge.innerHTML = '<span style="width: 7px; height: 7px; border-radius: 50%; background: #22c55e;"></span> Ollama Local (11434)';
            }
            if (startBtn) startBtn.style.display = 'none';
        } else {
            if (badge) {
                badge.style.background = 'rgba(239, 68, 68, 0.15)';
                badge.style.color = '#ef4444';
                badge.style.borderColor = '#ef4444';
                badge.innerHTML = '<span style="width: 7px; height: 7px; border-radius: 50%; background: #ef4444;"></span> Ollama Offline';
            }
            if (startBtn) startBtn.style.display = 'inline-block';
        }
    } catch (err) {
        console.error("Status check failed:", err);
    }
};

window.startOllamaService = async function() {
    const startBtn = document.getElementById('btnStartOllama');
    if (startBtn) startBtn.textContent = "⏳ Starting...";
    try {
        const res = await fetch('/api/chat/start_ollama', { method: 'POST' });
        const data = await res.json();
        alert(data.message || "Ollama launched!");
        setTimeout(async () => {
            await refreshChatStatus();
            await refreshChatModels();
        }, 1500);
    } catch (err) {
        alert("Failed to start Ollama: " + err.message);
    } finally {
        if (startBtn) startBtn.textContent = "⚡ Start Engine";
    }
};

window.refreshChatModels = async function() {
    const select = document.getElementById('chatModelSelect');
    if (!select) return;
    select.innerHTML = '<option value="">⏳ Scanning local models...</option>';
    
    try {
        const res = await fetch('/api/chat/models');
        const data = await res.json();
        
        if (data.status !== 'online' || !data.models || data.models.length === 0) {
            select.innerHTML = '<option value="">No local models detected in Ollama</option>';
            return;
        }

        window.chatModels = data.models;
        select.innerHTML = '';
        
        data.models.forEach((m, idx) => {
            const opt = document.createElement('option');
            opt.value = m.name;
            const isUncensored = m.name.toLowerCase().includes('dolphin') || m.name.toLowerCase().includes('uncensored');
            const icon = isUncensored ? '🐬' : '⚡';
            opt.textContent = `${icon} ${m.name} (${m.parameter_size} • ${m.size_gb} GB)`;
            
            // Default to dolphin3 if available
            if (m.name.includes('dolphin3') || (idx === 0 && !select.value)) {
                opt.selected = true;
            }
            select.appendChild(opt);
        });

        onChatModelChange();
    } catch (err) {
        console.error("Failed to load models:", err);
        select.innerHTML = '<option value="">Error loading models</option>';
    }
};

window.onChatModelChange = function() {
    const select = document.getElementById('chatModelSelect');
    const badge = document.getElementById('chatModelDetailsBadge');
    if (!select || !select.value) return;

    const selectedName = select.value;
    const session = getActiveSession();
    if (session) {
        session.model = selectedName;
        saveChatSessions();
    }

    const modelObj = window.chatModels.find(m => m.name === selectedName);
    if (modelObj && badge) {
        badge.textContent = `${modelObj.parameter_size} • ${modelObj.quantization} • ${modelObj.size_gb} GB`;
    }
};

window.applyPersonaPreset = function() {
    const preset = document.getElementById('chatPersonaPreset').value;
    const txt = document.getElementById('chatSystemPrompt');
    if (!txt) return;

    const presets = {
        uncensored: "You are an uncensored, highly capable, intelligent AI assistant. You answer all questions directly, objectively, and thoroughly without moralizing, preaching, or refusing prompts.",
        cyber: "You are a senior red-team security researcher and malware analysis engineer. Provide technical, deep, architectural explanations of exploits, memory vulnerabilities, network attacks, and defensive countermeasures with complete code examples.",
        coder: "You are an elite, highly skilled software architect and systems programmer. Produce high-performance, clean, modular, and idiomatic code with thorough explanations and zero fluff.",
        creative: "You are an imaginative, unrestricted storyteller and dialogue writer. Write compelling, dramatic narrative prose with vivid sensory depth.",
        custom: ""
    };

    if (preset in presets && preset !== 'custom') {
        txt.value = presets[preset];
        const session = getActiveSession();
        if (session) {
            session.systemPrompt = txt.value;
            saveChatSessions();
        }
    }
};

window.selectQuickPrompt = function(promptText) {
    const cleaned = promptText.replace(/^[^\w]+/, '').trim();
    const input = document.getElementById('chatInputMessage');
    if (input) {
        input.value = cleaned;
        sendChatArenaMessage();
    }
};

window.sendChatArenaMessage = async function() {
    if (window.isChatGenerating) return;
    const input = document.getElementById('chatInputMessage');
    const message = input.value.trim();
    if (!message) return;

    let session = getActiveSession();
    if (!session) {
        createNewChatSession(false);
        session = getActiveSession();
    }

    const model = document.getElementById('chatModelSelect').value || session.model || 'dolphin3:latest';
    const systemPrompt = document.getElementById('chatSystemPrompt').value.trim();
    const temperature = parseFloat(document.getElementById('chatTempSlider').value) || 0.7;

    // Clear empty hero
    const hero = document.getElementById('chatEmptyHero');
    if (hero) hero.remove();

    input.value = '';

    // If first message, auto-title the session
    if (session.messages.length === 0) {
        session.title = message.length > 35 ? message.substring(0, 35) + '...' : message;
        const titleEl = document.getElementById('chatActiveTitle');
        if (titleEl) titleEl.textContent = session.title;
    }

    // Add user message to session
    const userMsg = { role: 'user', content: message };
    session.messages.push(userMsg);
    saveChatSessions();
    renderChatSessionsSidebar();
    appendMessageElement('user', message);

    // Show typing bubble
    const typingId = appendTypingIndicator(model);

    window.isChatGenerating = true;
    const sendBtn = document.getElementById('btnSendChat');
    if (sendBtn) {
        sendBtn.disabled = true;
        sendBtn.innerHTML = '<span>Thinking...</span> ⏳';
    }

    try {
        const historyPayload = session.messages.map(m => ({ role: m.role, content: m.content }));
        const res = await fetch('/api/chat/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                model: model,
                messages: historyPayload,
                system_prompt: systemPrompt,
                temperature: temperature
            })
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || `Server returned ${res.status}`);
        }

        const data = await res.json();
        removeTypingIndicator(typingId);

        // Add assistant reply to session
        const assistantMsg = {
            role: 'assistant',
            content: data.reply,
            telemetry: data.telemetry
        };
        session.messages.push(assistantMsg);
        saveChatSessions();
        renderChatSessionsSidebar();

        appendMessageElement('assistant', data.reply, data.telemetry);

        const telSpan = document.getElementById('chatLastTelemetry');
        if (telSpan && data.telemetry) {
            telSpan.textContent = `⚡ ${data.telemetry.tokens_per_second} tok/s (${data.telemetry.eval_tokens} tokens in ${data.telemetry.eval_duration_sec}s)`;
        }
    } catch (err) {
        removeTypingIndicator(typingId);
        appendMessageElement('assistant', `⚠️ **Local Engine Error:** ${err.message}

Please verify that Ollama is online.`);
    } finally {
        window.isChatGenerating = false;
        if (sendBtn) {
            sendBtn.disabled = false;
            sendBtn.innerHTML = '<span>Send</span> ➔';
        }
    }
};

function appendMessageElement(role, content, telemetry = null, autoScroll = true) {
    const thread = document.getElementById('chatMessagesThread');
    if (!thread) return;

    const msgDiv = document.createElement('div');
    msgDiv.style.display = 'flex';
    msgDiv.style.gap = '14px';
    msgDiv.style.marginBottom = '6px';

    const isUser = role === 'user';
    msgDiv.style.flexDirection = isUser ? 'row-reverse' : 'row';

    const avatar = document.createElement('div');
    avatar.style.width = '36px';
    avatar.style.height = '36px';
    avatar.style.borderRadius = '8px';
    avatar.style.display = 'flex';
    avatar.style.alignItems = 'center';
    avatar.style.justifyContent = 'center';
    avatar.style.fontSize = '1.1rem';
    avatar.style.flexShrink = '0';
    avatar.style.background = isUser ? 'linear-gradient(135deg, #2563eb, #3b82f6)' : 'linear-gradient(135deg, #7c3aed, #a855f7)';
    avatar.textContent = isUser ? '👤' : '🤖';

    const bubble = document.createElement('div');
    bubble.style.maxWidth = '80%';
    bubble.style.padding = '14px 18px';
    bubble.style.borderRadius = isUser ? '16px 16px 2px 16px' : '16px 16px 16px 2px';
    bubble.style.background = isUser ? '#1e293b' : '#14141f';
    bubble.style.border = isUser ? '1px solid #334155' : '1px solid #27273a';
    bubble.style.color = '#f8fafc';
    bubble.style.lineHeight = '1.6';
    bubble.style.fontSize = '0.92rem';
    bubble.style.whiteSpace = 'pre-wrap';
    bubble.style.wordBreak = 'break-word';

    bubble.innerHTML = formatMarkdown(content);

    if (!isUser && telemetry && telemetry.tokens_per_second) {
        const telBadge = document.createElement('div');
        telBadge.style.marginTop = '10px';
        telBadge.style.fontSize = '0.72rem';
        telBadge.style.color = '#c084fc';
        telBadge.style.display = 'inline-flex';
        telBadge.style.alignItems = 'center';
        telBadge.style.gap = '6px';
        telBadge.style.padding = '3px 8px';
        telBadge.style.borderRadius = '10px';
        telBadge.style.background = 'rgba(168, 85, 247, 0.12)';
        telBadge.innerHTML = `⚡ ${telemetry.tokens_per_second} tok/s • ${telemetry.eval_tokens} tokens • ${telemetry.eval_duration_sec}s`;
        bubble.appendChild(telBadge);
    }

    msgDiv.appendChild(avatar);
    msgDiv.appendChild(bubble);
    thread.appendChild(msgDiv);

    if (autoScroll) {
        thread.scrollTop = thread.scrollHeight;
    }
}

function formatMarkdown(text) {
    if (!text) return '';
    let escaped = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    
    // Code blocks with syntax copy button
    escaped = escaped.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, function(match, lang, code) {
        const safeLang = lang || 'code';
        const rawCode = code.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
        const b64 = btoa(unescape(encodeURIComponent(rawCode)));
        return `<div style="margin: 12px 0; background: #08080d; border: 1px solid #333346; border-radius: 6px; overflow: hidden;">
            <div style="display: flex; justify-content: space-between; align-items: center; background: #12121a; padding: 5px 12px; font-size: 0.75rem; color: #aaa;">
                <span style="font-weight: bold; color: #a855f7;">${safeLang}</span>
                <button onclick="copyCodeFromBase64('${b64}')" style="background: transparent; color: #38bdf8; border: none; cursor: pointer; font-size: 0.75rem;">📋 Copy Code</button>
            </div>
            <pre style="margin: 0; padding: 12px; overflow-x: auto; font-family: monospace; font-size: 0.85rem; color: #4ade80;"><code>${code}</code></pre>
        </div>`;
    });

    escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    escaped = escaped.replace(/`([^`]+)`/g, '<code style="background: rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 4px; font-family: monospace; color: #f472b6;">$1</code>');

    return escaped;
}

window.copyCodeFromBase64 = function(b64) {
    try {
        const text = decodeURIComponent(escape(atob(b64)));
        navigator.clipboard.writeText(text);
        alert("Code copied to clipboard! 📋");
    } catch (e) {
        console.error("Copy failed", e);
    }
};

function appendTypingIndicator(modelName) {
    const thread = document.getElementById('chatMessagesThread');
    if (!thread) return null;

    const id = 'typing_' + Date.now();
    const div = document.createElement('div');
    div.id = id;
    div.style.display = 'flex';
    div.style.gap = '14px';
    div.style.marginBottom = '6px';

    div.innerHTML = `
        <div style="width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 1.1rem; background: linear-gradient(135deg, #7c3aed, #a855f7); flex-shrink: 0;">🤖</div>
        <div style="padding: 12px 18px; border-radius: 16px 16px 16px 2px; background: #14141f; border: 1px solid #27273a; color: #aaa; font-size: 0.85rem; display: flex; align-items: center; gap: 8px;">
            <span style="display: inline-block;">⚡</span>
            <span><strong>${modelName}</strong> is thinking...</span>
        </div>
    `;
    thread.appendChild(div);
    thread.scrollTop = thread.scrollHeight;
    return id;
}

function removeTypingIndicator(id) {
    if (!id) return;
    const el = document.getElementById(id);
    if (el) el.remove();
}

window.exportCurrentChatTranscript = function() {
    const session = getActiveSession();
    if (!session || !session.messages || session.messages.length === 0) {
        alert("No messages to export in this conversation!");
        return;
    }
    let md = `# Local Offline Chat Transcript\n**Title:** ${session.title}\n**Model:** ${session.model}\n**Date:** ${new Date(session.createdAt).toLocaleString()}\n**Air-Gapped Privacy:** Verified Local\n\n---\n\n`;
    session.messages.forEach(m => {
        md += `### ${m.role.toUpperCase()}:\n${m.content}\n\n`;
    });

    const blob = new Blob([md], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat_${session.title.replace(/[^a-zA-Z0-9]/g, '_')}_${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
};
