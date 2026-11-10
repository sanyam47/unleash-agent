const API_BASE = window.location.origin;

function switchAppTab(tabId) {
    console.log("Switching to tab:", tabId);
    const sections = ['train-section', 'lab-section', 'llm-section', 'synth-section', 'skills-section', 'chat-section'];
    sections.forEach(s => {
        const el = document.getElementById(s);
        if (el) el.style.display = (s === tabId) ? 'block' : 'none';
    });

    const btnMap = {
        'train-section': 'btn-train',
        'lab-section': 'id-lab-btn',
        'llm-section': 'btn-llm',
        'synth-section': 'btn-synth',
        'skills-section': 'btn-skills',
        'chat-section': 'btn-chat'
    };

    Object.entries(btnMap).forEach(([sec, btnId]) => {
        const btn = document.getElementById(btnId);
        if (btn) btn.classList.toggle('active', sec === tabId);
    });

    if (tabId === 'lab-section' && window.refreshLabModels) window.refreshLabModels();
    if (tabId === 'llm-section') {
        if (window.initLLMStudio) window.initLLMStudio();
        if (window.refreshCloudQuota) window.refreshCloudQuota();
    }
    if (tabId === 'synth-section' && window.initSyntheticStudio) window.initSyntheticStudio();
    if (tabId === 'skills-section' && window.initSkillsStudio) window.initSkillsStudio();
    if (tabId === 'chat-section') {
        if (!window._chatArenaInitialized) {
            if (window.initChatArena) window.initChatArena();
            window._chatArenaInitialized = true;
        } else {
            if (typeof renderChatSessionsSidebar === 'function') renderChatSessionsSidebar();
            if (typeof renderActiveThread === 'function') renderActiveThread();
        }
    }
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
                                <button onclick="discardInjection()" style="background:#444; font-size:0.75rem;">Discard & Use AI Data</button>
                                <button onclick="document.getElementById('labDataInjection').click()" style="background:#007bff; font-size:0.75rem;">Upload New File</button>
                             </div>`;
                } else {
                    html += `<br><i>AI will automatically supplement the missing data.</i>`;
                }
                alertMsg.innerHTML = html;
            } else {
                alertBox.style.background = "rgba(0, 255, 0, 0.1)";
                alertBox.style.borderColor = "green";
                alertBox.style.color = "green";
                alertMsg.innerText = "Data is 100% relevant and sufficient!";
            }
        } else {
            alert("CSV Error: " + data.message);
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
    content.innerHTML = "Loading history...";

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
                    <span style="font-size:0.8rem; color: #28a745;">Accuracy: ${h.accuracy || 'N/A'}</span>
                    <button onclick="window.location.href='${API_BASE}/download_model?job_id=${h.id}'" style="width:auto; padding: 3px 10px; font-size:0.75rem;">Download</button>
                </div>
                ${i < history.length - 1 ? '<div style="text-align:center; margin-top:10px; color:#444;">↓</div>' : ''}
            </div>
        `).join('');

    } catch (err) {
        content.innerHTML = "Error fetching lineage.";
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

    const taskTypeEl = document.getElementById("trainArchTaskType");
    if (taskTypeEl) taskTypeEl.textContent = detectedTask;
    const modelEl = document.getElementById("trainArchModel");
    if (modelEl) {
        modelEl.textContent = detectedTask.toLowerCase().includes("regress") ? "Ridge / GradientBoosting" : "LightGBM / RandomForest";
    }

    const archContainer = document.getElementById("trainArchSpecContainer");
    if (archContainer) archContainer.style.display = "block";

    document.getElementById("confirmBox").style.display = "block";
}

window.fillObjectivePrompt = function(txt) {
    const input = document.getElementById("inputText");
    if (input) {
        input.value = txt;
        input.focus();
    }
};

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
        alert("Job queued! ID: " + jobId + "\nWe will poll for the result...");
        pollJobStatus(jobId);
    } else {
        alert("Error: Response did not include job_id. Data: " + JSON.stringify(data));
    }
}

let currentTrainModelName = null;
let currentTrainJobId = null;

async function pollJobStatus(jobId) {
    currentTrainJobId = jobId;
    const statusDiv = document.getElementById("result");
    statusDiv.innerText = "Training in progress (ID: " + jobId + ")...";

    const interval = setInterval(async () => {
        try {
            let res = await fetch(`${API_BASE}/jobs/${jobId}`);
            let data = await res.json();

            if (data.status === "completed") {
                clearInterval(interval);
                statusDiv.innerHTML = "<b>Training Complete!</b><br>" + data.message + 
                                     `<br><button class='secondary' onclick="downloadModel('${jobId}')" style='margin-top:10px;'>Download .pkl Model</button>`;
                
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
                alert("Model trained successfully!");
            } else if (data.status === "failed") {
                clearInterval(interval);
                statusDiv.innerHTML = "<b style=\"color:var(--accent-danger);\">Training Failed:</b> " + data.message;
                alert("Training failed: " + data.message);
            } else {
                statusDiv.innerText = "Status: " + data.status + "...";
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
            alert("Manual job queued! ID: " + jobId);
            pollJobStatus(jobId);
        } else {
            alert("Error: " + JSON.stringify(data));
        }
    } catch (err) {
        console.error("Upload error:", err);
        alert("Failed to upload dataset.");
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
    resultDiv.innerHTML = "Uploading external model...";

    try {
        let res = await fetch(`${API_BASE}/lab/upload`, {
            method: "POST",
            body: formData
        });
        let data = await res.json();
        alert(data.message);
        await refreshLabModels();
        document.getElementById("labModelSelect").value = data.filename;
        resultDiv.innerHTML = `Model ${data.filename} ready for analysis.`;
    } catch (err) {
        console.error("Upload error", err);
        alert("Failed to upload model.");
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

    resultDiv.innerHTML = "Analyzing model metadata & instruction...";
    
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
            resultDiv.innerHTML = "<span style=\"color:var(--accent-danger);\">Rate Limit Reached.</span>";
            return;
        }
        
        currentLabAnalysis = await res.json();
        
        document.getElementById("labActionText").innerHTML = 
            `<b>Action:</b> ${currentLabAnalysis.action}<br>` +
            `<b>Strategy:</b> ${currentLabAnalysis.message}<br>` +
            `<b>Classes to Add:</b> ${currentLabAnalysis.new_labels?.join(', ') || 'None'}<br>` +
            `<b>Classes to Remove:</b> ${currentLabAnalysis.remove_labels?.join(', ') || 'None'}`;
        
        document.getElementById("labProposal").style.display = "block";
        resultDiv.innerHTML = "<span style=\"color:var(--accent-success);\">Analysis complete. Ready to execute.</span>";
    } catch (err) {
        resultDiv.innerHTML = "<span style=\"color:var(--accent-danger);\">Failed to analyze instruction.</span>";
    }
}

async function executeLab() {
    const modelName = document.getElementById("labModelSelect").value;
    const instruction = document.getElementById("labInstruction").value;
    const resultDiv = document.getElementById("labResult");

    document.getElementById("labProposal").style.display = "none";
    resultDiv.innerHTML = "Initiating Deep Manipulation (Knowledge Distillation)...";

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
        resultDiv.innerHTML = "<span style=\"color:var(--accent-danger);\">Execution failed.</span>";
    }
}

async function sendLabFeedback() {
    const feedback = document.getElementById("labChatInput").value;
    const modelName = document.getElementById("labModelSelect").value;
    const resultDiv = document.getElementById("labResult");

    if (!feedback) return;

    resultDiv.innerHTML = "Refining requirements...";
    
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
            resultDiv.innerHTML = "<span style=\"color:var(--accent-danger);\">Rate Limit Reached.</span>";
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
        resultDiv.innerHTML = "<span style=\"color:var(--accent-success);\">Proposal refined.</span>";
    } catch (err) {
        console.error("Refine error", err);
        resultDiv.innerHTML = "<span style=\"color:var(--accent-danger);\">Failed to refine proposal.</span>";
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
                            <p style="color:#007bff; font-weight:bold; margin-bottom:10px;">Performance Comparison:</p>
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
                    <b>Manipulation Complete!</b><br>
                    ${data.message}<br>
                    ${analyticsHtml}
                    <br>
                    <div style="display: flex; gap: 10px;">
                        <button class="primary" style="flex:1;" onclick="window.location.href='${API_BASE}/lab/download_model?job_id=${jobId}'">
                            Download Model (.pkl)
                        </button>
                        <button class="secondary" style="flex:1;" onclick="window.location.href='${API_BASE}/lab/download_report/${jobId}'">
                            Download Audit Report
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
                resultDiv.innerHTML = `<b>Failed:</b> ${data.message}`;
            } else {
                resultDiv.innerText = `Status: ${data.status}...`;
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
    statusBadge.innerHTML = `Intake: <b>${fileInput.files[0].name}</b>`;
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = `<b>Step 1/3:</b> Preparing data...`;

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    try {
        resultDiv.innerHTML = `<b>Step 2/3:</b> Transmitting to Intelligence Lab...`;
        
        // Using relative path for maximum stability
        let res = await fetch(`/lab/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!res.ok) {
            const error = await res.json();
            throw new Error(error.detail || "Server rejected the model");
        }
        
        resultDiv.innerHTML = `<b>Step 3/3:</b> Processing intelligence...`;
        let data = await res.json();
        
        resultDiv.innerHTML = `<b>Final:</b> ${data.message}`;
        statusBadge.innerHTML = `<b>Stored:</b> ${fileInput.files[0].name}`;
        statusBadge.style.borderColor = "#28a745";
        statusBadge.style.animation = "none";
        
        refreshLabModels(fileInput.files[0].name);
    } catch (err) {
        resultDiv.innerHTML = `<b style=\"color:var(--accent-danger);\">Transmission Error:</b> ${err.message}`;
        statusBadge.innerHTML = `<b style=\"color:var(--accent-danger);\">Failed:</b> ${fileInput.files[0].name}`;
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
    actionText.innerHTML = "AI is interpreting manipulation plan...";

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

    actionText.innerHTML = "Refining plan based on feedback...";
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
            <div style="color: #818cf8; font-weight: bold; margin-bottom: 5px;">REFINED ACTION: ${currentLabAnalysis.action}</div>
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
    alertBox.innerHTML = "Auditing Data Relevance...";

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
                <b>RELEVANCE GUARD:</b> ${data.message}
                <br><br>
                <div style="display: flex; gap: 10px;">
                    <button class="primary" onclick="discardInjection()">Discard & Use AI Data</button>
                    <button class="secondary" onclick="document.getElementById('labDataInjection').click()">Upload New File</button>
                </div>
            `;
        } else {
            alertBox.style.background = "rgba(40, 167, 69, 0.2)";
            alertBox.style.borderColor = "#28a745";
            alertBox.innerHTML = `<b>DATA VERIFIED:</b> ${data.message}`;
        }
    } catch (err) { console.error(err); }
}

async function executeLab() {
    const model = document.getElementById('labModelSelect').value;
    const resultDiv = document.getElementById('labResult');
    const autoFill = document.getElementById('labAutoFillGaps').checked;

    resultDiv.style.display = 'block';
    resultDiv.innerHTML = "Initializing Deep Manipulation Engine...";

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
    predText.innerHTML = "Predicting...";
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
    predText.innerHTML = "Predicting...";
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
    resultDiv.innerHTML = "AI is analyzing your refinement request...";
    
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
            resultDiv.innerHTML = "Uploading correct data...";
            const formData = new FormData();
            formData.append("file", fileInput.files[0]);
            formData.append("target_classes", JSON.stringify(analysis.new_labels || []));
            formData.append("goal_description", instruction);
            
            let injectRes = await fetch(`${API_BASE}/lab/inject`, { method: "POST", body: formData });
            let injectData = await injectRes.json();
            injected_path = injectData.path || null;
        }
        
        // 3. Execute
        resultDiv.innerHTML = "Dispatching Deep Manipulation Engine...";
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

    // Pre-check Ollama status & refresh lab models
    if (window.refreshChatStatus) window.refreshChatStatus();
    if (window.refreshLabModels) window.refreshLabModels();
    if (window.initLLMStudio) window.initLLMStudio();
    if (window.initChatArena) window.initChatArena();
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
            document.getElementById("trainFeedbackContainer").innerHTML = "<p class='success-text' style='text-align:center;'>Thanks for your feedback!</p>";
            loadCommunityFeed();
        }
    } catch(err) { console.error(err); }
}

async function submitLabFeedback() {
    document.getElementById("labFeedbackContainer").innerHTML = "<p class='success-text' style='text-align:center;'>Thanks for your feedback!</p>";
}

// ==========================================
// ==========================================
// SMART SITUATION ADVISOR & RECOMMENDATION ENGINE
// ==========================================
window.currentSituationRecommendation = null;
window.recommendationDebounceTimer = null;

// Synchronous client-side fallback analyzer for 100% offline reliability
function fallbackSituationAnalysis(prompt, sampleCount, selectedModel) {
    const p = (prompt || "").toLowerCase().trim();
    let domainId = "general";
    let domainLabel = "General Knowledge & Instruction Following";
    let recModel = "meta-llama/Llama-3.2-3B-Instruct";
    let modelReason = "Llama 3.2 3B is the current gold standard sweet spot between 8B intelligence and 1B speed.";
    let recTemp = 0.7;
    let tempReason = "Temperature 0.7 provides natural, creative, and engaging conversational responses.";
    let recRank = 16;
    let recAlpha = 32;
    let rankReason = "Rank 16 is optimal for general instruction fine-tuning.";
    let suggestedName = "expert-assistant";
    let persona = "uncensored";
    let modelAliases = ["meta-llama/Llama-3.2-3B-Instruct", "mlabonne/Llama-3.2-3B-Instruct-abliterated", "llama3.2:3b", "llama-3.2-3b"];

    if (["code", "coding", "python", "javascript", "developer", "sql", "bug", "html", "api", "backend", "frontend", "rust", "c++", "function", "script", "git", "linux", "terminal"].some(k => p.includes(k))) {
        domainId = "coding";
        domainLabel = "Software Engineering & Code Syntax";
        recModel = "Qwen/Qwen2.5-Coder-1.5B-Instruct";
        modelAliases = ["huihui-ai/Qwen2.5-Coder-1.5B-Instruct-abliterated", "qwen2.5-coder:1.5b", "Qwen/Qwen2.5-Coder-1.5B-Instruct", "qwen", "coder"];
        modelReason = "Qwen 2.5 Coder is the state-of-the-art open-weights architecture for indentation, AST parsing, and programming languages.";
        recTemp = 0.2;
        tempReason = "Low temperature (0.2) eliminates hallucinations and enforces strict syntax correctness.";
        recRank = 32;
        recAlpha = 64;
        rankReason = "Rank 32 provides high expressivity for nested control flows and data structures.";
        suggestedName = "code-expert-assistant";
        persona = "coder";
    } else if (["malware", "cybersecurity", "hack", "pentest", "uncensored", "security", "exploit", "vulnerability", "virus", "bypass", "payload", "cve", "injection", "reverse", "audit"].some(k => p.includes(k))) {
        domainId = "cybersecurity";
        domainLabel = "Cybersecurity & Exploit Analysis";
        recModel = "cognitivecomputations/dolphin-2.9-llama3-8b";
        modelAliases = ["cognitivecomputations/dolphin-2.9-llama3-8b", "dolphin3:latest", "dolphin", "dolphin-2.9"];
        modelReason = "Dolphin 3 (8B) is stripped of artificial alignment filters, ensuring it analyzes sensitive exploit payloads without refusal.";
        recTemp = 0.4;
        tempReason = "Moderate-low temperature (0.4) balances factual disassembly analysis with creative attack vector mitigation.";
        recRank = 64;
        recAlpha = 128;
        rankReason = "Rank 64 captures complex assembly heuristics and multi-stage payload analysis.";
        suggestedName = "cyber-exploit-analyst";
        persona = "cyber";
    } else if (["math", "logic", "proof", "solve", "equation", "algorithm", "calculation", "calculus", "algebra", "theorem"].some(k => p.includes(k))) {
        domainId = "math_logic";
        domainLabel = "Mathematical Logic & Formal Reasoning";
        recModel = "microsoft/Phi-3.5-mini-instruct";
        modelAliases = ["microsoft/Phi-3.5-mini-instruct", "aifeifei9/Phi-3.5-mini-instruct-abliterated", "phi3.5:latest", "phi-3.5", "phi"];
        modelReason = "Phi-3.5 Mini (3.8B) has the highest concentration of synthetic textbook and formal mathematical reasoning data.";
        recTemp = 0.1;
        tempReason = "Near-zero temperature (0.1) prevents arithmetic drift and enforces step-by-step chain-of-thought proofs.";
        recRank = 32;
        recAlpha = 64;
        rankReason = "Rank 32 ensures precise step-by-step logical transformation.";
        suggestedName = "math-logic-reasoner";
        persona = "custom";
    } else if (["law", "legal", "complex", "analysis", "enterprise", "medical", "contract", "compliance", "finance", "clinical", "patient"].some(k => p.includes(k))) {
        domainId = "enterprise_legal";
        domainLabel = "Deep Analytical & Enterprise Reasoning";
        recModel = "mistralai/Mistral-7B-Instruct-v0.3";
        modelAliases = ["mistralai/Mistral-7B-Instruct-v0.3", "MaziyarPanahi/Mistral-7B-Instruct-v0.3-abliterated", "mistral:latest", "mistral", "mistral-7b"];
        modelReason = "Mistral 7B v0.3 excels at long-context comprehension, document extraction, and nuanced policy analysis.";
        recTemp = 0.3;
        tempReason = "Low temperature (0.3) ensures high factual fidelity to legal and technical source documents.";
        recRank = 64;
        recAlpha = 128;
        rankReason = "Rank 64 captures intricate domain terminologies and regulatory taxonomies.";
        suggestedName = "legal-policy-analyst";
        persona = "custom";
    } else if (["fast", "tiny", "small", "mobile", "edge", "lightweight", "instant", "quick", "low latency"].some(k => p.includes(k))) {
        domainId = "ultra_fast";
        domainLabel = "Ultra-Fast Low-Latency Assistant";
        recModel = "meta-llama/Llama-3.2-1B-Instruct";
        modelAliases = ["meta-llama/Llama-3.2-1B-Instruct", "mlabonne/Llama-3.2-1B-Instruct-abliterated", "llama3.2:1b", "llama-3.2-1b"];
        modelReason = "Llama 3.2 1B fits entirely into minimal VRAM and produces instantaneous token streams (>60 tok/sec).";
        recTemp = 0.6;
        tempReason = "Temperature 0.6 balances fast conversational fluency with coherence.";
        recRank = 16;
        recAlpha = 32;
        rankReason = "Rank 16 maintains minimal parameter overhead for fast adaptation.";
        suggestedName = "fast-assistant-1b";
        persona = "uncensored";
    }

    const activeModel = (selectedModel || recModel).toLowerCase();
    const isLarge = ["7b", "8b", "14b", "32b", "dolphin", "mistral"].some(k => activeModel.includes(k));
    const isMed = ["3b", "3.8b", "phi"].some(k => activeModel.includes(k));

    let recPlatform = "local";
    let platformTitle = "Local RTX 3050 (1-Click • 2 Seconds • Zero Quota)";
    let platformReason = "1B–1.5B models compile directly on your RTX 3050 GPU in seconds with zero cloud quota burned.";
    let platformWarning = null;

    if (sampleCount <= 5) {
        recPlatform = "local";
        platformTitle = "Local RTX 3050 (Instant Prototype • Zero Quota)";
        platformReason = `With only ${sampleCount} sample${sampleCount > 1 ? 's' : ''}, local RTX 3050 executes in seconds without needing cloud clusters.`;
        platformWarning = null;
    } else if (isLarge) {
        recPlatform = "kaggle";
        platformTitle = "Kaggle Cloud (Dual T4 • 32 GB VRAM • 30h Free)";
        platformReason = "7B–8B models require 24GB+ VRAM during DoRA gradient backpropagation. Kaggle Dual T4 (32GB) is strongly recommended.";
        platformWarning = "Google Colab free tier (16GB) may crash with Out-Of-Memory (OOM) on 8B models. Use Kaggle (32GB) or Local 1-Click.";
    } else if (isMed) {
        recPlatform = "colab";
        platformTitle = "Google Colab or Kaggle (16 GB - 32 GB VRAM)";
        platformReason = "3B–4B models fit comfortably within Colab's 16GB T4 VRAM or Kaggle's Dual T4s.";
    }

    let recEpochs = sampleCount <= 2 ? 1 : (sampleCount <= 40 ? 4 : (sampleCount <= 150 ? 3 : 2));
    let epochReason = sampleCount <= 2
        ? `Micro-dataset (${sampleCount} sample): 1 epoch prevents immediate single-sample memorization and overfitting.`
        : (sampleCount <= 40 
            ? "Small dataset (≤40 samples) requires 4 epochs to memorize domain patterns." 
            : (sampleCount <= 150 ? "Balanced dataset size: 3 epochs provides ideal convergence without overfitting." : "Large dataset (>150 samples): 2 epochs prevents catastrophic loss of general reasoning."));

    return {
        domain: { id: domainId, label: domainLabel },
        recommendations: {
            base_model: { value: recModel, aliases: modelAliases, reason: modelReason },
            suggested_name: suggestedName,
            persona: persona,
            platform: { value: recPlatform, title: platformTitle, reason: platformReason, warning: platformWarning },
            algorithm: { value: "dora", reason: "DoRA (Weight-Decomposed LoRA) is state-of-the-art; it learns directional weight vectors independently from magnitude, consistently outperforming standard QLoRA." },
            lora_rank: { value: recRank, reason: rankReason },
            lora_alpha: { value: recAlpha, reason: `Standard scaling rule: Alpha = ${recAlpha} (2x Rank) ensures stable gradient scaling.` },
            epochs: { value: recEpochs, reason: epochReason },
            learning_rate: { value: "0.0002", reason: `Optimal AdamW-8bit learning rate for DoRA on ${domainId} domain.` },
            temperature: { value: recTemp, reason: tempReason },
            catastrophic_shield: { value: true, reason: "Always keep shield enabled to protect core logic and reasoning from degradation." }
        },
        summary_sentence: `For ${domainLabel}, we recommend ${recModel.split('/').pop()} with DoRA Rank ${recRank} & Temperature ${recTemp} running on ${platformTitle}.`
    };
}

window.onBaseModelChange = function() {
    window.updateSituationRecommendations();
};

window.updateSituationRecommendations = async function() {
    const prompt = document.getElementById("llmPromptInput")?.value.trim() || "";
    const sampleCount = (window.llmSamples && window.llmSamples.length > 0) 
        ? window.llmSamples.length 
        : (parseInt(document.getElementById("llmTargetCount")?.value) || 40);
    const selectedModel = document.getElementById("llmBaseModel")?.value || null;

    let recData = null;
    try {
        const res = await fetch('/api/llm/recommend_situation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt: prompt,
                sample_count: sampleCount,
                selected_model: selectedModel
            })
        });
        if (res.ok) {
            recData = await res.json();
        }
    } catch (e) {
        console.warn("API recommendation call failed, using fallback:", e);
    }

    if (!recData) {
        recData = fallbackSituationAnalysis(prompt, sampleCount, selectedModel);
    }

    window.currentSituationRecommendation = recData;
    const recs = recData.recommendations;
    const domain = recData.domain;

    // 1. Update Advisor Card in Step 1
    const domainPill = document.getElementById("advisorDomainPill");
    if (domainPill) domainPill.textContent = domain.label;

    const summaryText = document.getElementById("advisorSummaryText");
    if (summaryText) summaryText.style.display = "none";

    const pillsContainer = document.getElementById("advisorPrescriptionPills");
    if (pillsContainer) {
        pillsContainer.innerHTML = `
            <table class="config-table" style="margin-top: 6px;">
                <tbody>
                    <tr>
                        <td class="config-key">Base model</td>
                        <td class="config-val">${recs.base_model.value.split('/').pop()}</td>
                    </tr>
                    <tr>
                        <td class="config-key">Fine-tuning method</td>
                        <td class="config-val">DoRA (Weight-Decomposed LoRA)</td>
                    </tr>
                    <tr>
                        <td class="config-key">Rank (r) / Alpha (α)</td>
                        <td class="config-val">r = ${recs.lora_rank.value} · α = ${recs.lora_alpha.value}</td>
                    </tr>
                    <tr>
                        <td class="config-key">Epochs</td>
                        <td class="config-val">${recs.epochs.value}</td>
                    </tr>
                    <tr>
                        <td class="config-key">Target runtime</td>
                        <td class="config-val">${recs.platform.title.split('(')[0].trim()}</td>
                    </tr>
                </tbody>
            </table>
        `;
    }

    // 2. Step 3 Quick Situation Summary Bar
    const step3Text = document.getElementById("step3AdvisorPrescriptionText");
    if (step3Text) {
        step3Text.innerHTML = `${domain.label}: Recommend <strong>${recs.base_model.value.split('/').pop()}</strong> with DoRA Rank ${recs.lora_rank.value} on ${recs.platform.title.split('(')[0].trim()}`;
    }

    // 3. Base Model Select & Badges
    const modelSelect = document.getElementById("llmBaseModel");
    if (modelSelect) {
        const targetVal = recs.base_model.value;
        const aliases = recs.base_model.aliases || [targetVal];
        
        for (let i = 0; i < modelSelect.options.length; i++) {
            const opt = modelSelect.options[i];
            const cleanText = opt.text.replace(/\s*\(Recommended[^)]*\)/gi, '').trim();
            const optVal = opt.value.toLowerCase();
            const optTextLow = cleanText.toLowerCase();

            const isMatch = aliases.some(a => {
                const al = a.toLowerCase();
                return optVal.includes(al) || optTextLow.includes(al) || al.includes(optVal);
            });

            if (isMatch) {
                opt.text = `${cleanText} (Recommended for this domain)`;
            } else {
                opt.text = cleanText;
            }
        }
    }

    const recBaseModelTag = document.getElementById("recBaseModelTag");
    if (recBaseModelTag) recBaseModelTag.textContent = `Recommended: ${recs.base_model.value.split('/').pop()}`;

    const recBadgeBaseModel = document.getElementById("recBadgeBaseModel");
    if (recBadgeBaseModel) recBadgeBaseModel.innerHTML = `<strong>Recommended:</strong> ${recs.base_model.reason}`;

    // 4. Algorithm Select & Badges
    const algoSelect = document.getElementById("llmAlgorithm");
    if (algoSelect) {
        for (let i = 0; i < algoSelect.options.length; i++) {
            const opt = algoSelect.options[i];
            const cleanText = opt.text.replace(/\s*\(Recommended[^)]*\)/gi, '').trim();
            if (opt.value === recs.algorithm.value) {
                opt.text = `${cleanText} (Recommended - SOTA Directional Weights)`;
            } else {
                opt.text = cleanText;
            }
        }
    }
    const recAlgoTag = document.getElementById("recAlgoTag");
    if (recAlgoTag) recAlgoTag.textContent = `Recommended: ${recs.algorithm.value.toUpperCase()}`;

    const recBadgeAlgorithm = document.getElementById("recBadgeAlgorithm");
    if (recBadgeAlgorithm) recBadgeAlgorithm.innerHTML = `<strong>Recommended:</strong> ${recs.algorithm.reason}`;

    // 5. LoRA Rank Select & Badges
    const rankSelect = document.getElementById("llmLoraRank");
    if (rankSelect) {
        for (let i = 0; i < rankSelect.options.length; i++) {
            const opt = rankSelect.options[i];
            const cleanText = opt.text.replace(/\s*\(Recommended[^)]*\)/gi, '').trim();
            if (parseInt(opt.value) === recs.lora_rank.value) {
                opt.text = `${cleanText} (Recommended: Rank ${recs.lora_rank.value})`;
            } else {
                opt.text = cleanText;
            }
        }
    }
    const recBadgeLoraRank = document.getElementById("recBadgeLoraRank");
    if (recBadgeLoraRank) recBadgeLoraRank.innerHTML = `<strong>Recommended Rank ${recs.lora_rank.value}:</strong> ${recs.lora_rank.reason}`;

    // 6. LoRA Alpha Select & Badges
    const alphaSelect = document.getElementById("llmLoraAlpha");
    if (alphaSelect) {
        for (let i = 0; i < alphaSelect.options.length; i++) {
            const opt = alphaSelect.options[i];
            const cleanText = opt.text.replace(/\s*\(Recommended[^)]*\)/gi, '').trim();
            if (parseInt(opt.value) === recs.lora_alpha.value) {
                opt.text = `${cleanText} (Recommended: Alpha ${recs.lora_alpha.value})`;
            } else {
                opt.text = cleanText;
            }
        }
    }
    const recBadgeLoraAlpha = document.getElementById("recBadgeLoraAlpha");
    if (recBadgeLoraAlpha) recBadgeLoraAlpha.innerHTML = `<strong>Recommended Alpha ${recs.lora_alpha.value}:</strong> ${recs.lora_alpha.reason}`;

    // 7. Epochs & Learning Rate
    const recBadgeEpochs = document.getElementById("recBadgeEpochs");
    if (recBadgeEpochs) recBadgeEpochs.innerHTML = `<strong>Recommended:</strong> ${recs.epochs.value} Epochs (${recs.epochs.reason})`;

    const recBadgeLearningRate = document.getElementById("recBadgeLearningRate");
    if (recBadgeLearningRate) recBadgeLearningRate.innerHTML = `<strong>Recommended:</strong> ${recs.learning_rate.value} (${recs.learning_rate.reason})`;

    // 8. Platform Cards Highlighting in Quota Tracker
    const cardKaggle = document.getElementById("platformCardKaggle");
    const recKaggle = document.getElementById("platformRecKaggle");
    const cardColab = document.getElementById("platformCardColab");
    const recColab = document.getElementById("platformRecColab");
    const cardLocal = document.getElementById("platformCardLocal");
    const recLocal = document.getElementById("platformRecLocal");
    const colabWarning = document.getElementById("platformColabWarning");

    // Reset styles
    if (cardKaggle) { cardKaggle.style.border = "1px solid rgba(56, 189, 248, 0.3)"; cardKaggle.style.boxShadow = "none"; }
    if (recKaggle) recKaggle.style.display = "none";
    if (cardColab) { cardColab.style.border = "1px solid var(--border-medium)"; cardColab.style.boxShadow = "none"; }
    if (recColab) recColab.style.display = "none";
    if (cardLocal) { cardLocal.style.border = "1px solid var(--border-medium)"; cardLocal.style.boxShadow = "none"; }
    if (recLocal) recLocal.style.display = "none";

    const winningPlatform = recs.platform.value;
    if (winningPlatform === "kaggle") {
        if (cardKaggle) {
            cardKaggle.style.border = "2px solid #38bdf8";
            cardKaggle.style.boxShadow = "0 0 20px rgba(56, 189, 248, 0.4)";
        }
        if (recKaggle) {
            recKaggle.style.display = "block";
            recKaggle.textContent = "RECOMMENDED FOR THIS MODEL (32 GB VRAM)";
        }
    } else if (winningPlatform === "colab") {
        if (cardColab) {
            cardColab.style.border = "2px solid #fbbf24";
            cardColab.style.boxShadow = "0 0 20px rgba(245, 158, 11, 0.4)";
        }
        if (recColab) {
            recColab.style.display = "block";
            recColab.textContent = "RECOMMENDED FOR THIS MODEL";
        }
    } else if (winningPlatform === "local") {
        if (cardLocal) {
            cardLocal.style.border = "2px solid #10b981";
            cardLocal.style.boxShadow = "0 0 20px rgba(16, 185, 129, 0.4)";
        }
        if (recLocal) {
            recLocal.style.display = "block";
            recLocal.textContent = "RECOMMENDED: 1-CLICK LOCAL RUNTIME";
        }
    }

    if (colabWarning) {
        if (recs.platform.warning) {
            colabWarning.style.display = "block";
            colabWarning.innerHTML = recs.platform.warning;
        } else {
            colabWarning.style.display = "none";
        }
    }

    // Auto-select recommended platform if user hasn't explicitly clicked a choice
    if (!window.hasUserManuallySelectedPlatform && recs.platform?.value) {
        window.selectTrainingPlatform(recs.platform.value, false);
    }
};

window.selectedTrainingPlatform = 'local';
window.hasUserManuallySelectedPlatform = false;

window.selectTrainingPlatform = function(platformId, autoScroll = false) {
    window.selectedTrainingPlatform = platformId;
    window.hasUserManuallySelectedPlatform = true;

    // 1. Update Step 4 Selector Cards
    const cardLocal = document.getElementById("selectCardLocal");
    const badgeLocal = document.getElementById("badgeSelectLocal");
    const cardKaggle = document.getElementById("selectCardKaggle");
    const badgeKaggle = document.getElementById("badgeSelectKaggle");
    const cardColab = document.getElementById("selectCardColab");
    const badgeColab = document.getElementById("badgeSelectColab");
    const indicator = document.getElementById("selectedPlatformIndicator");
    const execBtn = document.getElementById("btnExecuteTraining");

    // Reset styles
    if (cardLocal) {
        cardLocal.style.border = "1px solid var(--border-medium)";
        cardLocal.style.boxShadow = "none";
        cardLocal.style.background = "var(--bg-surface-elevated)";
    }
    if (badgeLocal) {
        badgeLocal.textContent = "Offline";
        badgeLocal.style.background = "rgba(16, 185, 129, 0.15)";
        badgeLocal.style.color = "#10b981";
    }

    if (cardKaggle) {
        cardKaggle.style.border = "1px solid var(--border-medium)";
        cardKaggle.style.boxShadow = "none";
        cardKaggle.style.background = "var(--bg-surface-elevated)";
    }
    if (badgeKaggle) {
        badgeKaggle.textContent = "30h Free";
        badgeKaggle.style.background = "rgba(56, 189, 248, 0.15)";
        badgeKaggle.style.color = "#38bdf8";
    }

    if (cardColab) {
        cardColab.style.border = "1px solid var(--border-medium)";
        cardColab.style.boxShadow = "none";
        cardColab.style.background = "var(--bg-surface-elevated)";
    }
    if (badgeColab) {
        badgeColab.textContent = "12h Session";
        badgeColab.style.background = "rgba(245, 158, 11, 0.15)";
        badgeColab.style.color = "#fbbf24";
    }

    // Apply Active Highlight
    if (platformId === 'local') {
        if (cardLocal) {
            cardLocal.style.border = "1px solid var(--accent)";
            cardLocal.style.boxShadow = "none";
            cardLocal.style.background = "var(--bg-surface-elevated)";
        }
        if (badgeLocal) {
            badgeLocal.textContent = "ACTIVE";
            badgeLocal.style.background = "var(--accent)";
            badgeLocal.style.color = "#ffffff";
        }
        if (indicator) {
            indicator.textContent = "Local GPU Selected (RTX 3050 · 5.8 GB VRAM)";
            indicator.style.color = "var(--accent-text)";
        }
        if (execBtn) {
            execBtn.innerHTML = `<span>Train & Register to Arena (Local GPU)</span>`;
            execBtn.style.background = "var(--accent)";
            execBtn.style.boxShadow = "none";
        }
    } else if (platformId === 'kaggle') {
        if (cardKaggle) {
            cardKaggle.style.border = "1px solid var(--accent)";
            cardKaggle.style.boxShadow = "none";
            cardKaggle.style.background = "var(--bg-surface-elevated)";
        }
        if (badgeKaggle) {
            badgeKaggle.textContent = "ACTIVE";
            badgeKaggle.style.background = "var(--accent)";
            badgeKaggle.style.color = "#ffffff";
        }
        if (indicator) {
            indicator.textContent = "Kaggle Cloud Selected (Dual T4 · 32 GB VRAM)";
            indicator.style.color = "var(--accent-text)";
        }
        if (execBtn) {
            if (window.kaggleConnected) {
                execBtn.innerHTML = `<span>Launch on Kaggle Cloud (Dual T4 32 GB)</span>`;
            } else {
                execBtn.innerHTML = `<span>Connect Kaggle API for Cloud Training</span>`;
            }
            execBtn.style.background = "var(--accent)";
            execBtn.style.boxShadow = "none";
        }
    } else if (platformId === 'colab') {
        if (cardColab) {
            cardColab.style.border = "1px solid var(--accent)";
            cardColab.style.boxShadow = "none";
            cardColab.style.background = "var(--bg-surface-elevated)";
        }
        if (badgeColab) {
            badgeColab.textContent = "ACTIVE";
            badgeColab.style.background = "var(--accent)";
            badgeColab.style.color = "#ffffff";
        }
        if (indicator) {
            indicator.textContent = "Google Colab Selected (Tesla T4 · 16 GB VRAM)";
            indicator.style.color = "var(--accent-text)";
        }
        if (execBtn) {
            execBtn.innerHTML = `<span>Package for Google Colab (Tesla T4 · 16 GB Free)</span>`;
            execBtn.style.background = "var(--accent)";
            execBtn.style.boxShadow = "none";
        }
    }

    // 2. Sync Quota Tracker Buttons
    const btnKaggle = document.getElementById("btnCardSelectKaggle");
    const btnColab = document.getElementById("btnCardSelectColab");
    const btnLocal = document.getElementById("btnCardSelectLocal");

    if (btnKaggle) {
        btnKaggle.innerHTML = platformId === 'kaggle' ? '<span>Selected Target (Kaggle Cloud)</span>' : '<span>Select Kaggle Cloud</span>';
        btnKaggle.className = platformId === 'kaggle' ? 'primary' : 'secondary';
        if (platformId === 'kaggle') btnKaggle.style.background = 'linear-gradient(135deg, #0284c7, #0ea5e9)';
        else btnKaggle.style.background = 'transparent';
    }
    if (btnColab) {
        btnColab.innerHTML = platformId === 'colab' ? '<span>Selected Target (Google Colab)</span>' : '<span>Select Google Colab</span>';
        btnColab.className = platformId === 'colab' ? 'primary' : 'secondary';
        if (platformId === 'colab') btnColab.style.background = 'linear-gradient(135deg, #d97706, #f59e0b)';
        else btnColab.style.background = 'transparent';
    }
    if (btnLocal) {
        btnLocal.innerHTML = platformId === 'local' ? '<span>Selected Target (Local GPU)</span>' : '<span>Select Local GPU</span>';
        btnLocal.className = platformId === 'local' ? 'primary' : 'secondary';
        if (platformId === 'local') btnLocal.style.background = 'linear-gradient(135deg, #10b981, #059669)';
        else btnLocal.style.background = 'transparent';
    }

    if (autoScroll) {
        const step4 = document.getElementById("llmOutputName");
        if (step4) step4.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
};

window.executeSelectedTraining = async function() {
    if (window.selectedTrainingPlatform === 'local') {
        await window.trainLocalOllamaStudioModel();
    } else if (window.selectedTrainingPlatform === 'kaggle') {
        if (window.kaggleConnected) {
            await window.launchKaggleAutoPilot();
        } else {
            window.openKaggleModal();
        }
    } else {
        await window.packageCloudTraining(window.selectedTrainingPlatform);
    }
};

window.applySmartRecommendations = async function() {
    if (!window.currentSituationRecommendation) {
        await window.updateSituationRecommendations();
    }
    const recs = window.currentSituationRecommendation?.recommendations;
    if (!recs) return;

    // 1. Base Model
    const modelSelect = document.getElementById("llmBaseModel");
    if (modelSelect) {
        const targetVal = recs.base_model.value;
        const aliases = recs.base_model.aliases || [targetVal];
        for (let i = 0; i < modelSelect.options.length; i++) {
            const opt = modelSelect.options[i];
            const optVal = opt.value.toLowerCase();
            const optText = opt.text.toLowerCase();
            if (aliases.some(a => {
                const al = a.toLowerCase();
                return optVal.includes(al) || optText.includes(al) || al.includes(optVal);
            })) {
                modelSelect.selectedIndex = i;
                break;
            }
        }
    }

    // 2. Algorithm
    const algoSelect = document.getElementById("llmAlgorithm");
    if (algoSelect) {
        for (let i = 0; i < algoSelect.options.length; i++) {
            if (algoSelect.options[i].value === recs.algorithm.value) {
                algoSelect.selectedIndex = i;
                break;
            }
        }
    }

    // 3. LoRA Rank
    const rankSelect = document.getElementById("llmLoraRank");
    if (rankSelect) {
        for (let i = 0; i < rankSelect.options.length; i++) {
            if (parseInt(rankSelect.options[i].value) === recs.lora_rank.value) {
                rankSelect.selectedIndex = i;
                break;
            }
        }
    }

    // 4. LoRA Alpha
    const alphaSelect = document.getElementById("llmLoraAlpha");
    if (alphaSelect) {
        for (let i = 0; i < alphaSelect.options.length; i++) {
            if (parseInt(alphaSelect.options[i].value) === recs.lora_alpha.value) {
                alphaSelect.selectedIndex = i;
                break;
            }
        }
    }

    // 5. Epochs & Learning Rate
    const epochsInput = document.getElementById("llmEpochs");
    if (epochsInput) epochsInput.value = recs.epochs.value;

    const lrInput = document.getElementById("llmLearningRate");
    if (lrInput) lrInput.value = recs.learning_rate.value;

    // 6. Safeguard Shield
    const chkShield = document.getElementById("chkReplayAnchors");
    if (chkShield) chkShield.checked = true;

    // 7. Output Name
    const outputNameInput = document.getElementById("llmOutputName");
    if (outputNameInput && (!outputNameInput.value || outputNameInput.value === "my-custom-llm")) {
        outputNameInput.value = recs.suggested_name || "expert-llm";
    }

    // 8. Arena Temperature & Persona Presets
    const tempSlider = document.getElementById("chatTempSlider");
    const tempVal = document.getElementById("chatTempValue");
    if (tempSlider && recs.temperature?.value !== undefined) {
        tempSlider.value = recs.temperature.value;
        if (tempVal) tempVal.textContent = recs.temperature.value;
    }
    const personaSelect = document.getElementById("chatPersonaPreset");
    if (personaSelect && recs.persona) {
        personaSelect.value = recs.persona;
    }

    // 9. Sync Recommended Training Platform
    if (recs.platform?.value) {
        window.selectTrainingPlatform(recs.platform.value, false);
    }

    // Re-trigger update to refresh badges with newly selected model
    await window.updateSituationRecommendations();

    // Visual button feedback
    const btn = document.getElementById("btnApplyRecommendations");
    if (btn) {
        const originalHtml = btn.innerHTML;
        btn.innerHTML = `<span>Applied All Recommendations</span>`;
        btn.style.background = "#10b981";
        setTimeout(() => {
            btn.innerHTML = originalHtml;
            btn.style.background = "";
        }, 2200);
    }
};

function setupAdvisorListeners() {
    const promptInput = document.getElementById("llmPromptInput");
    if (promptInput && !promptInput.dataset.advisorBound) {
        promptInput.dataset.advisorBound = "true";
        promptInput.addEventListener("input", () => {
            clearTimeout(window.recommendationDebounceTimer);
            window.recommendationDebounceTimer = setTimeout(() => {
                window.updateSituationRecommendations();
            }, 300);
        });
    }

    const targetInput = document.getElementById("llmTargetCount");
    if (targetInput && !targetInput.dataset.advisorBound) {
        targetInput.dataset.advisorBound = "true";
        targetInput.addEventListener("change", () => {
            window.updateSituationRecommendations();
        });
        targetInput.addEventListener("input", () => {
            clearTimeout(window.recommendationDebounceTimer);
            window.recommendationDebounceTimer = setTimeout(() => {
                window.updateSituationRecommendations();
            }, 300);
        });
    }
}

// ==========================================
// LLM FINE-TUNING & DATA STUDIO MODULE
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

    setupAdvisorListeners();
    await window.updateSituationRecommendations();
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
    btn.innerHTML = "Harvesting Datasets...";
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

        // Group samples by source for clear developer breakdown table
        const sourceCounts = {};
        (data.samples || []).forEach(s => {
            const src = s.source || "Hugging Face";
            sourceCounts[src] = (sourceCounts[src] || 0) + 1;
        });

        let sourceRowsHtml = "";
        for (const [srcName, count] of Object.entries(sourceCounts)) {
            sourceRowsHtml += `
                <tr>
                    <td style="padding: 6px 12px; color: var(--text-primary); font-family: var(--font-mono);">${srcName}</td>
                    <td style="padding: 6px 12px; text-align: right; color: var(--text-primary); font-family: var(--font-mono);">${count}</td>
                    <td style="padding: 6px 12px; text-align: right; color: var(--text-muted); font-family: var(--font-mono);">0.88</td>
                </tr>
            `;
        }

        statusDiv.innerHTML = `
            <div style="margin-bottom: 10px; font-weight: 500; color: var(--text-primary); font-size: 0.82rem;">Harvested sources</div>
            <table style="width: 100%; border-collapse: collapse; font-size: 0.78rem; margin-bottom: 12px;">
                <thead>
                    <tr style="border-bottom: 1px solid var(--border-subtle); color: var(--text-muted); text-align: left;">
                        <th style="padding: 4px 12px; font-weight: 500;">Source</th>
                        <th style="padding: 4px 12px; font-weight: 500; text-align: right;">Samples</th>
                        <th style="padding: 4px 12px; font-weight: 500; text-align: right;">Quality</th>
                    </tr>
                </thead>
                <tbody>
                    ${sourceRowsHtml}
                </tbody>
            </table>
            <div style="font-size: 0.78rem; color: var(--text-muted);">
                ${data.total_samples} samples selected. Proceed to curation below.
            </div>
        `;

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
        statusDiv.innerHTML = `<span style="color:var(--danger);">Error: ${err.message}</span>`;
    } finally {
        btn.disabled = false;
        btn.innerHTML = "Harvest datasets →";
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
            <td style="padding: 8px;"><span style="color:#10b981; font-weight:bold;">${Math.round((s.quality_score || 0.85)*100)}%</span></td>
            <td style="padding: 8px; max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${s.instruction.replace(/"/g, '&quot;')}">${shortInst}</td>
            <td style="padding: 8px; max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color:#aaa;" title="${s.output.replace(/"/g, '&quot;')}">${shortOut}</td>
            <td style="padding: 8px; text-align: center;">
                <button onclick="deleteLLMSample('${s.id}')" style="background: transparent; color: var(--accent-danger); border: 1px solid var(--accent-danger); border-radius: 4px; padding: 2px 6px; font-size: 0.85rem; cursor: pointer; line-height: 1;" title="Delete sample">&times;</button>
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

window.trainLocalOllamaStudioModel = async function() {
    const outputName = document.getElementById("llmOutputName")?.value.trim() || "my-custom-llm";
    const baseModel = document.getElementById("llmBaseModel")?.value || "dolphin3:latest";
    const btn = document.getElementById("btnTrainLocalOllama");
    const resultDiv = document.getElementById("llmExportResult");

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span>Training & Compiling on Local GPU...</span>`;
    }
    if (resultDiv) {
        resultDiv.style.display = "block";
        resultDiv.innerHTML = `<span style="color:#60a5fa;">Compiling custom model <strong>${outputName}</strong> into local GPU runtime with domain knowledge base...</span>`;
    }

    try {
        const res = await fetch('/api/llm/train_local_ollama', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: window.llmSessionId || "",
                output_model_name: outputName,
                base_model: baseModel,
                temperature: 0.7,
                top_p: 0.9
            })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Local compilation failed");

        if (resultDiv) {
            resultDiv.innerHTML = `
                <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid #10b981; border-radius: 8px; padding: 14px;">
                    <h4 style="color:#10b981; margin: 0 0 6px 0;">Model Successfully Trained & Registered</h4>
                    <p style="font-size: 0.88rem; color: #e2e8f0; margin: 0 0 10px 0;">
                        Compiled <strong>${data.model_name}</strong> (based on ${data.base_model} with ${data.sample_count} curated knowledge exemplars) into your local GPU runtime.
                    </p>
                    <button type="button" onclick="window.switchTab('chat-section'); window.refreshChatModels('${data.model_name}');" class="primary" style="padding: 8px 18px; font-weight: 600; font-size: 0.84rem;">
                        Open in Chat Arena
                    </button>
                </div>
            `;
        }

        setTimeout(async () => {
            if (window.switchTab) window.switchTab('chat-section');
            if (window.refreshChatModels) await window.refreshChatModels(data.model_name);
        }, 1500);

    } catch (err) {
        if (resultDiv) {
            resultDiv.innerHTML = `<span style="color:#f43f5e;">Training error: ${err.message}</span>`;
        }
        alert("Error: " + err.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<span>Train & Add to Arena (Local GPU)</span>`;
        }
    }
};

window.packageCloudTraining = async function(targetPlatform = null) {
    const platform = targetPlatform || window.selectedTrainingPlatform || 'kaggle';
    if (!window.llmSessionId) {
        alert("Please hunt and curate a dataset first!");
        return;
    }

    const baseModel = document.getElementById("llmBaseModel").value;
    const outputName = document.getElementById("llmOutputName")?.value.trim() || "my-custom-llm";
    const algorithm = document.getElementById("llmAlgorithm")?.value || "dora";
    const enableAnchors = document.getElementById("chkReplayAnchors")?.checked ?? true;
    const loraRank = parseInt(document.getElementById("llmLoraRank").value) || 16;
    const loraAlpha = parseInt(document.getElementById("llmLoraAlpha").value) || 32;
    const epochs = parseInt(document.getElementById("llmEpochs").value) || 3;
    const lr = parseFloat(document.getElementById("llmLearningRate").value) || 0.0002;

    const resultDiv = document.getElementById("llmExportResult");
    const execBtn = document.getElementById("btnExecuteTraining");
    if (execBtn) {
        execBtn.disabled = true;
        execBtn.innerHTML = `<span>1-Click Packaging for ${platform === 'kaggle' ? 'Kaggle Cloud (Dual T4)' : 'Google Colab (T4)'}...</span>`;
    }

    resultDiv.style.display = "block";
    resultDiv.innerHTML = `<span style="color:var(--accent);">Packaging ${algorithm.toUpperCase()} bundle with Holdout Benchmark for <strong>${baseModel}</strong> on ${platform.toUpperCase()}...</span>`;

    try {
        const res = await fetch('/api/llm/package/cloud', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: window.llmSessionId,
                base_model: baseModel,
                output_model_name: outputName,
                algorithm: algorithm,
                enable_anchors: enableAnchors,
                test_split_ratio: 0.2,
                lora_rank: loraRank,
                lora_alpha: loraAlpha,
                epochs: epochs,
                learning_rate: lr
            })
        });

        if (!res.ok) throw new Error("Packaging failed");
        const data = await res.json();

        const platformTitle = platform === 'kaggle' ? 'Kaggle Cloud (Dual T4 • 32 GB VRAM)' : 'Google Colab (Tesla T4 • 16 GB)';
        const notebookFile = platform === 'kaggle' ? 'train_kaggle_dual_t4.ipynb' : 'train_unsloth_colab.ipynb';
        const optionalUrl = platform === 'kaggle' ? 'https://www.kaggle.com/code?new=true' : 'https://colab.research.google.com/#create=true';

        resultDiv.innerHTML = `
            <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid ${platform === 'kaggle' ? 'rgba(56, 189, 248, 0.4)' : 'rgba(245, 158, 11, 0.4)'}; border-radius: 10px; padding: 16px;">
                <h4 style="color: ${platform === 'kaggle' ? '#38bdf8' : '#fbbf24'}; margin: 0 0 8px 0; font-size: 1.05rem;">
                    1-Click Training Package Ready for ${platformTitle}!
                </h4>
                <p style="font-size:0.86rem; color:#cbd5e1; margin-bottom: 12px; line-height: 1.5;">
                    Contains <strong>${data.sample_count} curated samples</strong> (<code>dataset.jsonl</code>), holdout validation set (<code>dataset_eval.jsonl</code>), and pre-configured GPU notebook (<code>${notebookFile}</code>) tuned for <strong>${baseModel}</strong>.
                </p>
                <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 12px;">
                    <a href="${data.download_url}" download style="display:inline-flex; align-items: center; gap: 6px; background:#059669; color:#fff; text-decoration:none; padding:10px 18px; border-radius:6px; font-weight:bold; font-size: 0.85rem;">
                        Download Training Bundle (${data.zip_filename})
                    </a>
                    <a href="${optionalUrl}" target="_blank" style="display:inline-flex; align-items: center; gap: 6px; background: rgba(255, 255, 255, 0.08); color: ${platform === 'kaggle' ? '#38bdf8' : '#fbbf24'}; border: 1px solid rgba(255, 255, 255, 0.2); text-decoration:none; padding:10px 16px; border-radius:6px; font-size: 0.85rem; font-weight: 600;">
                        Open ${platform === 'kaggle' ? 'Kaggle' : 'Colab'} (Optional)
                    </a>
                </div>
                <div style="font-size:0.78rem; color:#94a3b8; background:rgba(0,0,0,0.4); padding:10px 12px; border-radius:6px; line-height: 1.4;">
                    <strong>Safe & Zero Setup:</strong> Drag <code>${notebookFile}</code> into ${platform === 'kaggle' ? 'Kaggle' : 'Colab'} and click 'Run All'. It trains on free cloud GPU and exports your GGUF model directly for Chat Arena!
                </div>
            </div>
        `;

        // Reveal Step 5: Benchmark Section
        const benchSec = document.getElementById("llmBenchmarkSection");
        if (benchSec) {
            benchSec.style.display = "block";
            benchSec.scrollIntoView({ behavior: 'smooth' });
        }
    } catch (err) {
        resultDiv.innerHTML = `<span style="color:var(--accent-danger);">Packaging Error: ${err.message}</span>`;
    } finally {
        if (execBtn) {
            execBtn.disabled = false;
            window.selectTrainingPlatform(platform, false);
        }
    }
};

window.refreshCloudQuota = async function() {
    try {
        const res = await fetch('/api/llm/cloud_quota');
        const data = await res.json();
        
        // Kaggle Quota
        const kaggle = data.kaggle;
        if (kaggle) {
            window.kaggleConnected = !!kaggle.connected;
            window.kaggleUsername = kaggle.username;

            const hoursEl = document.getElementById('kaggleHoursText');
            const progressEl = document.getElementById('kaggleProgressBar');
            const badgeEl = document.getElementById('kaggleStatusBadge');
            const resetEl = document.getElementById('kaggleResetText');

            if (hoursEl) hoursEl.textContent = `${kaggle.remaining_hours.toFixed(1)} / ${kaggle.total_hours.toFixed(1)} hrs`;
            if (progressEl) {
                const pct = Math.max(0, Math.min(100, (kaggle.remaining_hours / Math.max(1, kaggle.total_hours)) * 100));
                progressEl.style.width = `${pct}%`;
                progressEl.style.background = pct < 20 ? 'linear-gradient(90deg, #f43f5e, #f59e0b)' : 'linear-gradient(90deg, #38bdf8, #10b981)';
            }
            if (badgeEl) {
                badgeEl.textContent = kaggle.connected ? `Connected (${kaggle.username || 'User'})` : '30h / Week Free';
                badgeEl.style.color = kaggle.connected ? '#10b981' : '#38bdf8';
                badgeEl.style.borderColor = kaggle.connected ? 'rgba(16, 185, 129, 0.4)' : 'rgba(56, 189, 248, 0.3)';
            }
            if (resetEl) resetEl.textContent = kaggle.refresh_schedule || 'Every Saturday 00:00 UTC';

            // Refresh execution button label if Kaggle is active
            if (window.selectedTrainingPlatform === 'kaggle') {
                window.selectTrainingPlatform('kaggle', false);
            }
        }

        // Colab Quota
        const colab = data.colab;
        if (colab) {
            const colabHoursEl = document.getElementById('colabHoursText');
            if (colabHoursEl) colabHoursEl.textContent = `~${colab.remaining_hours.toFixed(1)} hrs`;
        }
    } catch (err) {
        console.error("Failed to refresh cloud quota:", err);
    }
};

window.openKaggleModal = function() {
    const modal = document.getElementById('kaggleConnectModal');
    if (modal) modal.style.display = 'flex';
};

window.closeKaggleModal = function() {
    const modal = document.getElementById('kaggleConnectModal');
    if (modal) modal.style.display = 'none';
};

window.handleKaggleJsonUpload = function(event) {
    const file = event.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async function(e) {
        try {
            const data = JSON.parse(e.target.result);
            const userInput = document.getElementById('kaggleUsernameInput');
            const keyInput = document.getElementById('kaggleApiKeyInput');
            if (data.username && userInput) userInput.value = data.username;
            if (data.key && keyInput) keyInput.value = data.key;
            else if (data.token && keyInput) keyInput.value = data.token;
            // Submit immediately
            await window.submitKaggleCredentials();
        } catch (err) {
            alert("Could not parse kaggle.json: " + err.message);
        }
    };
    reader.readAsText(file);
};

window.submitKaggleCredentials = async function() {
    const userInput = document.getElementById('kaggleUsernameInput');
    const keyInput = document.getElementById('kaggleApiKeyInput');
    const btn = document.getElementById('btnSaveKaggleCreds');

    const username = userInput ? userInput.value.trim() : '';
    const key = keyInput ? keyInput.value.trim() : '';

    if (!key) {
        alert("Please enter your Kaggle API token or key.");
        if (keyInput) keyInput.focus();
        return;
    }

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span>Connecting & Checking Live Quota...</span>';
    }

    try {
        const res = await fetch('/api/llm/connect_kaggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                token_or_username: username || key,
                key: username ? key : null
            })
        });

        const data = await res.json();
        alert(data.message);
        window.closeKaggleModal();
        await window.refreshCloudQuota();
    } catch (err) {
        alert("Connection failed: " + err.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<span>Save & Connect Kaggle</span>';
        }
    }
};

window.launchKaggleAutoPilot = async function() {
    if (!window.llmSessionId) {
        alert("Please hunt or load a dataset first!");
        return;
    }

    const baseModel = document.getElementById("llmBaseModel")?.value || "meta-llama/Llama-3.2-1B-Instruct";
    const outputName = document.getElementById("llmOutputName")?.value.trim() || "my-custom-llm";
    const algorithm = document.getElementById("llmAlgorithm")?.value || "dora";
    const loraRank = parseInt(document.getElementById("llmLoraRank")?.value) || 16;
    const loraAlpha = parseInt(document.getElementById("llmLoraAlpha")?.value) || 32;
    const epochs = parseInt(document.getElementById("llmEpochs")?.value) || 3;
    const lr = parseFloat(document.getElementById("llmLearningRate")?.value) || 0.0002;

    const resultDiv = document.getElementById("llmExportResult");
    const execBtn = document.getElementById("btnExecuteTraining");
    if (execBtn) {
        execBtn.disabled = true;
        execBtn.innerHTML = `<span>Dispatching to Kaggle Cloud (Dual T4)...</span>`;
    }

    resultDiv.style.display = "block";
    resultDiv.innerHTML = `
        <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(56, 189, 248, 0.5); border-radius: 10px; padding: 18px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 10px;">
                <h4 style="color: #38bdf8; margin: 0; font-size: 1.05rem; display: flex; align-items: center; gap: 8px;">
                    <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:#38bdf8;"></span>
                    Kaggle Cloud Auto-Pilot: Launching Job...
                </h4>
                <span id="kaggleLiveBadge" style="background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); padding: 3px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 600;">QUEUED</span>
            </div>
            <p id="kaggleLiveDesc" style="font-size: 0.86rem; color: #cbd5e1; margin-bottom: 12px; line-height: 1.5;">
                Generating self-contained GPU kernel with curated dataset for <strong>${baseModel}</strong> and allocating Kaggle <strong>Dual Tesla T4 (32 GB VRAM)</strong> cluster...
            </p>
            <div id="kaggleActionRow" style="display: flex; gap: 10px; flex-wrap: wrap;">
                <span style="font-size: 0.82rem; color: #94a3b8;">Connecting to Kaggle API cluster...</span>
            </div>
        </div>
    `;

    try {
        const res = await fetch('/api/llm/kaggle/launch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: window.llmSessionId,
                base_model: baseModel,
                output_model_name: outputName,
                algorithm: algorithm,
                lora_rank: loraRank,
                lora_alpha: loraAlpha,
                epochs: epochs,
                learning_rate: lr
            })
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            if (res.status === 401) {
                window.openKaggleModal();
                throw new Error("Kaggle API credentials not found. Please connect your Kaggle account.");
            }
            throw new Error(errData.detail || "Dispatch failed");
        }

        const data = await res.json();
        const kernelSlug = data.kernel_slug;
        const [owner, slug] = kernelSlug.split('/');

        const badge = document.getElementById("kaggleLiveBadge");
        const desc = document.getElementById("kaggleLiveDesc");
        const actionRow = document.getElementById("kaggleActionRow");

        if (desc) {
            desc.innerHTML = `
                Kernel successfully queued on Kaggle Cloud! Running <strong>${algorithm.toUpperCase()}</strong> fine-tuning for <strong>${outputName}</strong> across Dual T4 GPUs (32 GB VRAM).
            `;
        }

        if (actionRow) {
            actionRow.innerHTML = `
                <a href="${data.kernel_url}" target="_blank" style="display:inline-flex; align-items:center; gap:6px; background:#0284c7; color:#fff; text-decoration:none; padding:8px 14px; border-radius:6px; font-weight:600; font-size:0.82rem;">
                    View Live Run on Kaggle
                </a>
                <button type="button" onclick="packageCloudTraining('kaggle')" class="secondary" style="font-size:0.82rem; padding:8px 14px;">
                    Download Offline Bundle (.zip)
                </button>
            `;
        }

        // Live polling status
        let pollCount = 0;
        const pollInterval = setInterval(async () => {
            pollCount++;
            try {
                const sRes = await fetch(`/api/llm/kaggle/status/${owner}/${slug}`);
                if (!sRes.ok) return;
                const sData = await sRes.json();
                const rawStatus = (sData.remote_status || '').toLowerCase();
                const isRunning = rawStatus.includes('running') || rawStatus === 'running';
                const isComplete = rawStatus.includes('complete') || rawStatus === 'complete';
                const isError = rawStatus.includes('error') || rawStatus.includes('fail');

                if (badge) {
                    const cleanStatus = rawStatus.replace('kernelworkerstatus.', '').toUpperCase();
                    badge.textContent = cleanStatus || 'RUNNING';
                    if (isRunning) {
                        badge.style.background = 'rgba(16, 185, 129, 0.15)';
                        badge.style.color = '#10b981';
                        badge.style.borderColor = 'rgba(16, 185, 129, 0.3)';
                    }
                }

                if (isRunning) {
                    if (desc) {
                        desc.innerHTML = `<strong>Dual Tesla T4 GPUs Active (32 GB VRAM)</strong>: Cloud training in progress on Kaggle cluster... (Elapsed: ~${pollCount * 10}s)`;
                    }
                } else if (isComplete) {
                    clearInterval(pollInterval);
                    if (badge) {
                        badge.textContent = 'SYNCING MODEL';
                        badge.style.color = 'var(--accent-text)';
                    }
                    if (desc) {
                        desc.innerHTML = `<strong>Training Complete on Dual T4 Cloud!</strong> Pulling GGUF weights to your local machine and registering with Ollama...`;
                    }

                    const syncRes = await fetch(`/api/llm/kaggle/sync/${owner}/${slug}`, { method: 'POST' });
                    const syncData = await syncRes.json();

                    if (badge) {
                        badge.textContent = 'READY IN ARENA';
                        badge.style.color = '#10b981';
                        badge.style.background = 'rgba(16, 185, 129, 0.2)';
                    }
                    if (desc) {
                        desc.innerHTML = `<strong>Success!</strong> Model <code>${syncData.model_name || outputName}</code> was fine-tuned on Kaggle Dual T4 and is now active in your local Ollama runtime and Chat Arena!`;
                    }
                    if (actionRow) {
                        actionRow.innerHTML = `
                            <button type="button" onclick="document.querySelector('[data-tab=\\'chat\\']').click()" class="primary" style="padding:10px 18px; font-weight:bold; font-size:0.85rem; background:linear-gradient(135deg, #10b981, #059669);">
                                Open Chat Arena & Test Model
                            </button>
                            <a href="${data.kernel_url}" target="_blank" class="secondary" style="text-decoration:none; display:inline-flex; align-items:center; padding:9px 14px; font-size:0.82rem;">
                                Kaggle Logs
                            </a>
                        `;
                    }
                    await window.refreshCloudQuota();
                } else if (isError) {
                    clearInterval(pollInterval);
                    if (badge) {
                        badge.textContent = 'ERROR';
                        badge.style.color = '#f43f5e';
                    }
                    if (desc) {
                        desc.innerHTML = `<span style="color:#f43f5e;">Cloud run error: ${sData.failure_message || 'Kernel execution encountered an error. Check Kaggle logs for details.'}</span>`;
                    }
                }
            } catch (pErr) {
                console.warn("Kaggle status polling:", pErr);
            }
        }, 10000);

    } catch (err) {
        resultDiv.innerHTML = `<span style="color:#f43f5e;">Cloud Launch Error: ${err.message}</span>`;
    } finally {
        if (execBtn) {
            execBtn.disabled = false;
            window.selectTrainingPlatform('kaggle', false);
        }
    }
};

window.startKaggleCloudTraining = function() {
    window.selectTrainingPlatform('kaggle', true);
    window.executeSelectedTraining();
};

window.runDataDoctorAudit = async function() {
    if (!window.llmSessionId) {
        alert("Please hunt or load a dataset first!");
        return;
    }
    const banner = document.getElementById("dataDoctorBanner");
    if (!banner) return;
    banner.style.display = "block";
    banner.innerHTML = `<span style="color:#60a5fa;">Running Pre-Flight Data Health Audit... Scanning token distributions and duplicates...</span>`;

    try {
        const res = await fetch('/api/llm/data/audit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: window.llmSessionId })
        });
        const data = await res.json();

        const isGood = data.health_score >= 75;
        const color = isGood ? '#10b981' : '#f59e0b';
        const bg = isGood ? 'rgba(16, 185, 129, 0.12)' : 'rgba(245, 158, 11, 0.12)';
        const border = isGood ? '#10b981' : '#f59e0b';

        banner.style.background = bg;
        banner.style.borderColor = border;

        let warningsHtml = '';
        if (data.warnings && data.warnings.length > 0) {
            warningsHtml = `<div style="margin-top: 8px; font-size: 0.78rem; color: #fca5a5;">
                <strong>Detected Issues:</strong> ${data.warnings.join(' • ')}
            </div>`;
        }

        banner.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-weight: 700; color: ${color}; font-size: 0.95rem;">
                    Pre-Flight Data Doctor: ${data.status} (Health Score: ${data.health_score}/100)
                </span>
                <span style="font-size: 0.78rem; padding: 2px 10px; border-radius: 999px; background: rgba(0,0,0,0.3); color: #cbd5e1;">
                    Schema Valid: ChatML / Alpaca
                </span>
            </div>
            <div style="display: flex; gap: 16px; font-size: 0.82rem; color: #cbd5e1; flex-wrap: wrap;">
                <span>Total Samples: <strong>${data.total_samples}</strong></span>
                <span>Avg Length: <strong>${data.avg_token_count} tokens</strong></span>
                <span>Outliers Flagged: <strong>${data.outliers_count}</strong></span>
                <span>Duplicates: <strong>${data.duplicates_count}</strong></span>
                <span>Forgetting Risk: <strong>${data.catastrophic_forgetting_risk}</strong></span>
            </div>
            ${warningsHtml}
        `;
    } catch (err) {
        banner.innerHTML = `<span style="color:#f43f5e;">Failed to run audit: ${err.message}</span>`;
    }
};

window.runModelBenchmarkEvaluation = async function() {
    if (!window.llmSessionId) {
        alert("Please generate or curate a dataset first!");
        return;
    }

    const loadDiv = document.getElementById("benchmarkLoadingStatus");
    const statsGrid = document.getElementById("benchmarkStatsGrid");
    const tableContainer = document.getElementById("benchmarkTableContainer");
    const forgettingBadge = document.getElementById("benchForgettingBadge");
    const tbody = document.getElementById("benchmarkResultsTbody");
    const btn = document.getElementById("btnRunBenchmark");

    if (btn) btn.disabled = true;
    if (loadDiv) loadDiv.style.display = "block";
    if (statsGrid) statsGrid.style.display = "none";
    if (tableContainer) tableContainer.style.display = "none";
    if (forgettingBadge) forgettingBadge.style.display = "none";

    const baseModel = document.getElementById("llmBaseModel")?.value || "dolphin3:latest";
    const trainedModel = document.getElementById("llmOutputName")?.value || "my-custom-llm";

    try {
        const res = await fetch('/api/llm/benchmark/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: window.llmSessionId,
                base_model: baseModel,
                trained_model: trainedModel
            })
        });

        if (!res.ok) throw new Error("Benchmark evaluation failed");
        const report = await res.json();

        // Update scorecards
        document.getElementById("benchWinRate").textContent = `${report.win_rate_percent}%`;
        document.getElementById("benchDomainLift").textContent = `+${report.domain_lift_percent}%`;
        document.getElementById("benchBaseScore").textContent = `${report.avg_base_score} / 10`;
        document.getElementById("benchTrainedScore").textContent = `${report.avg_trained_score} / 10`;
        document.getElementById("benchRetentionText").textContent = report.catastrophic_forgetting_retention;

        // Render table rows
        tbody.innerHTML = '';
        report.benchmark_items.forEach(item => {
            const tr = document.createElement("tr");
            const isWin = item.verdict.includes("Wins");
            const verdictBadge = isWin 
                ? `<span style="padding: 2px 8px; border-radius: 4px; background: rgba(16, 185, 129, 0.2); color: #10b981; font-weight: 600; font-size: 0.75rem;">${item.verdict}</span>`
                : `<span style="padding: 2px 8px; border-radius: 4px; background: rgba(255, 255, 255, 0.1); color: #94a3b8; font-size: 0.75rem;">${item.verdict}</span>`;

            tr.innerHTML = `
                <td style="font-size: 0.82rem; font-weight: 600; color: #fff;">
                    ${item.prompt}
                    ${item.is_simulated ? '<div style="font-size: 0.68rem; color: #f59e0b; margin-top: 4px;">Ground-truth reference (Model not yet compiled into Ollama)</div>' : ''}
                </td>
                <td style="font-size: 0.8rem; color: #94a3b8; line-height: 1.4;">
                    <div style="font-size: 0.7rem; color: #64748b; margin-bottom: 2px;">Score: ${item.base_score}/10</div>
                    ${item.base_response}
                </td>
                <td style="font-size: 0.8rem; color: #cbd5e1; line-height: 1.4; border-left: 1px solid var(--border-subtle);">
                    <div style="font-size: 0.7rem; color: var(--accent-text); margin-bottom: 2px; font-weight: 600;">Score: ${item.trained_score}/10</div>
                    ${item.trained_response}
                </td>
                <td style="text-align: center; vertical-align: middle;">
                    ${verdictBadge}
                    ${item.judge_critique ? `<div style="font-size: 0.68rem; color: #94a3b8; margin-top: 6px; text-align: left; line-height: 1.3; font-style: italic;">"${item.judge_critique}"</div>` : ''}
                </td>
            `;
            tbody.appendChild(tr);
        });

        if (loadDiv) loadDiv.style.display = "none";
        if (statsGrid) statsGrid.style.display = "grid";
        if (tableContainer) tableContainer.style.display = "block";
        if (forgettingBadge) forgettingBadge.style.display = "block";

    } catch (err) {
        if (loadDiv) loadDiv.innerHTML = `<span style="color:#f43f5e;">Evaluation failed: ${err.message}</span>`;
    } finally {
        if (btn) btn.disabled = false;
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
        <h4 style="color:#38bdf8; margin-bottom: 8px;">Ollama Modelfile Downloaded!</h4>
        <p style="font-size:0.85rem; color:#ccc;">To serve your fine-tuned model locally in Ollama:</p>
        <pre style="background:#000; color:#10b981; padding:10px; border-radius:4px; font-size:0.85rem; overflow-x:auto;">ollama create ${outputName} -f Modelfile\nollama run ${outputName}</pre>
    `;
};

// ==========================================
// LOCAL CHAT ARENA MODULE (ChatGPT-Style Multi-Chat)
// 100% Offline & Private (Stored strictly in localStorage)
// ==========================================
window.chatSessions = [];
window.activeSessionId = null;
window.chatModels = [];
window.isChatGenerating = false;
window.attachedChatImages = [];

const SESSIONS_STORAGE_KEY = 'offline_chat_sessions_v1';

function compressImageForChat(blob, callback) {
    const reader = new FileReader();
    reader.onload = function(e) {
        const img = new Image();
        img.onload = function() {
            let maxDim = 1200;
            let width = img.width;
            let height = img.height;
            if (width > maxDim || height > maxDim) {
                if (width > height) {
                    height = Math.round((height * maxDim) / width);
                    width = maxDim;
                } else {
                    width = Math.round((width * maxDim) / height);
                    height = maxDim;
                }
            }
            const canvas = document.createElement('canvas');
            canvas.width = width;
            canvas.height = height;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0, width, height);
            const compressedDataUrl = canvas.toDataURL('image/jpeg', 0.85);
            const base64 = compressedDataUrl.split(',')[1];
            callback(compressedDataUrl, base64);
        };
        img.onerror = function() {
            // Fallback to raw data url
            const rawUrl = e.target.result;
            callback(rawUrl, rawUrl.split(',')[1]);
        };
        img.src = e.target.result;
    };
    reader.readAsDataURL(blob);
}

window.attachChatImage = function(dataUrl, base64, filename) {
    window.attachedChatImages = [{ dataUrl, base64, filename }];
    const tray = document.getElementById('chatImagePreviewTray');
    const imgEl = document.getElementById('chatAttachedPreviewImg');
    const nameEl = document.getElementById('chatAttachedFileName');
    if (tray && imgEl) {
        imgEl.src = dataUrl;
        if (nameEl) nameEl.textContent = filename || 'screenshot.png';
        tray.style.display = 'flex';
    }
    const input = document.getElementById('chatInputMessage');
    if (input) input.focus();
};

window.clearAttachedChatImage = function() {
    window.attachedChatImages = [];
    const tray = document.getElementById('chatImagePreviewTray');
    if (tray) tray.style.display = 'none';
    const picker = document.getElementById('chatImagePicker');
    if (picker) picker.value = '';
};

window.onChatImagePicked = function(event) {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    compressImageForChat(file, function(dataUrl, base64) {
        window.attachChatImage(dataUrl, base64, file.name);
    });
};

window.autoExecuteSandbox = localStorage.getItem('auto_execute_sandbox') === 'true';

window.toggleAutoSandbox = function(enabled) {
    window.autoExecuteSandbox = enabled;
    localStorage.setItem('auto_execute_sandbox', enabled ? 'true' : 'false');
    const toggleEl = document.getElementById('chatAutoSandboxToggle');
    if (toggleEl) toggleEl.checked = enabled;
    console.log("Auto-Execute Sandbox:", enabled ? "Enabled" : "Disabled");
};

window.cyberRAGEnabled = localStorage.getItem('cyber_rag_enabled') !== 'false';

window.toggleCyberRAG = function(enabled) {
    window.cyberRAGEnabled = enabled;
    localStorage.setItem('cyber_rag_enabled', enabled ? 'true' : 'false');
    const toggleEl = document.getElementById('chatRAGToggle');
    if (toggleEl) toggleEl.checked = enabled;
    console.log("Cyber RAG Knowledge Retrieval:", enabled ? "Enabled" : "Disabled");
};

window.initChatArena = async function() {
    console.log("Initializing Antigravity-Style Local Arena...");

    // Initialize Auto-Sandbox checkbox
    const autoToggle = document.getElementById('chatAutoSandboxToggle');
    if (autoToggle) autoToggle.checked = window.autoExecuteSandbox;

    // Initialize Cyber RAG checkbox
    const ragToggle = document.getElementById('chatRAGToggle');
    if (ragToggle) ragToggle.checked = window.cyberRAGEnabled;

    // Initialize Sidebar State (Desktop open by default, restore user preference)
    if (!window._sidebarKeyboardBound) {
        window._sidebarKeyboardBound = true;
        window.addEventListener('keydown', function(e) {
            if ((e.ctrlKey || e.metaKey) && (e.key === 'b' || e.key === 'B')) {
                const chatSec = document.getElementById('chat-section');
                if (chatSec && chatSec.style.display !== 'none') {
                    e.preventDefault();
                    toggleChatSidebar();
                }
            }
        });
    }

    const savedCollapsed = localStorage.getItem('chat_sidebar_collapsed');
    if (savedCollapsed === 'true' && window.innerWidth <= 1024) {
        toggleChatSidebar(false);
    } else {
        // Ensure sidebar is visible on standard desktops
        const sidebar = document.getElementById('chatSidebar');
        if (sidebar) sidebar.classList.remove('collapsed');
    }

    // Load and render existing sessions immediately
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

        // Clipboard paste listener for direct screenshot pasting (Ctrl+V)
        input.addEventListener('paste', function(e) {
            const items = (e.clipboardData || window.clipboardData)?.items;
            if (!items) return;
            for (let i = 0; i < items.length; i++) {
                if (items[i].type.indexOf('image') !== -1) {
                    const blob = items[i].getAsFile();
                    if (!blob) continue;
                    e.preventDefault();
                    compressImageForChat(blob, function(dataUrl, base64) {
                        window.attachChatImage(dataUrl, base64, `Pasted_Screenshot_${new Date().toLocaleTimeString().replace(/:/g, '-')}.jpg`);
                    });
                    break;
                }
            }
        });
    }

    // Initialize Agentic Mode Toggle
    if (typeof updateAgenticModeUI === 'function') {
        updateAgenticModeUI();
    }

    // Refresh model status and catalog in background
    refreshChatStatus();
    refreshDockerStatus();
    await refreshChatModels();
};

window.toggleChatSidebar = function(forceOpen) {
    const sidebar = document.getElementById('chatSidebar');
    const backdrop = document.getElementById('chatSidebarBackdrop');
    if (!sidebar) return;

    let isCurrentlyCollapsed = sidebar.classList.contains('collapsed');
    let shouldCollapse;
    if (forceOpen !== undefined) {
        shouldCollapse = !forceOpen;
    } else {
        shouldCollapse = !isCurrentlyCollapsed;
    }

    sidebar.classList.toggle('collapsed', shouldCollapse);
    if (backdrop) {
        backdrop.style.display = (!shouldCollapse && window.innerWidth <= 900) ? 'block' : 'none';
    }
    localStorage.setItem('chat_sidebar_collapsed', shouldCollapse ? 'true' : 'false');
};

window.chatSearchQuery = '';
window.filterChatSessions = function(query) {
    window.chatSearchQuery = (query || '').toLowerCase().trim();
    renderChatSessionsSidebar();
};

function formatRelativeTime(ts) {
    if (!ts) return '';
    const now = Date.now();
    const diffMs = now - ts;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 2) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays}d ago`;

    const d = new Date(ts);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function loadChatSessions() {
    try {
        let stored = localStorage.getItem(SESSIONS_STORAGE_KEY);
        let sessions = null;

        if (stored) {
            try { sessions = JSON.parse(stored); } catch (e) {}
        }

        // Automatic Recovery from legacy storage keys
        if (!sessions || !Array.isArray(sessions) || sessions.length === 0) {
            const fallbackKeys = [
                'offline_chat_sessions',
                'chat_sessions',
                'chatHistory',
                'chat_history',
                'ollama_chat_history',
                'offline_chat_sessions_backup'
            ];
            for (const key of fallbackKeys) {
                const legacyVal = localStorage.getItem(key);
                if (legacyVal) {
                    try {
                        const parsed = JSON.parse(legacyVal);
                        if (Array.isArray(parsed) && parsed.length > 0) {
                            if (parsed[0].messages) {
                                sessions = parsed;
                                break;
                            } else if (parsed[0].role) {
                                sessions = [{
                                    id: 'chat_recovered_' + Date.now(),
                                    title: parsed[0].content ? (parsed[0].content.substring(0, 36) + '...') : 'Recovered Conversation',
                                    model: 'dolphin3:latest',
                                    messages: parsed,
                                    createdAt: Date.now()
                                }];
                                break;
                            }
                        }
                    } catch (pe) {}
                }
            }
        }

        const validSessions = Array.isArray(sessions) ? sessions : [];
        // Antigravity Rule: Filter out empty 0-message sessions if valid sessions exist
        const nonEmpty = validSessions.filter(s => s && s.messages && s.messages.length > 0);
        window.chatSessions = nonEmpty.length > 0 ? nonEmpty : validSessions;
    } catch (e) {
        console.warn("Failed to parse stored chat sessions:", e);
        window.chatSessions = [];
    }

    // Determine initial active conversation
    const savedActiveId = localStorage.getItem('active_chat_session_id');
    const matched = savedActiveId ? window.chatSessions.find(s => s && s.id === savedActiveId) : null;

    if (matched && matched.messages && matched.messages.length > 0) {
        window.activeSessionId = matched.id;
    } else {
        // Antigravity Priority: Always select the most active conversation with real messages!
        const bestSession = window.chatSessions.find(s => s && s.messages && s.messages.length > 0) || window.chatSessions[0];
        if (bestSession) {
            window.activeSessionId = bestSession.id;
        } else {
            // Only create draft if zero sessions exist anywhere
            createNewChatSession(false);
        }
    }

    if (window.activeSessionId) {
        localStorage.setItem('active_chat_session_id', window.activeSessionId);
    }

    renderChatSessionsSidebar();
    renderActiveThread();

    // Immediately fetch disk-persisted authoritative sessions from backend
    syncChatSessionsWithServer();
}

async function syncChatSessionsWithServer() {
    try {
        const res = await fetch('/api/chat/sessions');
        if (res.ok) {
            const data = await res.json();
            const serverSessions = (data && Array.isArray(data.sessions)) ? data.sessions : [];
            const localSessions = (window.chatSessions && Array.isArray(window.chatSessions)) ? window.chatSessions : [];

            // Filter out 0-message empty ghost sessions from server list
            const cleanedServer = serverSessions.filter(s => s && s.messages && s.messages.length > 0);
            const cleanedLocal = localSessions.filter(s => s && s.messages && s.messages.length > 0);

            if (cleanedServer.length > 0 || cleanedLocal.length > 0) {
                const mergedMap = new Map();

                // 1. Add server sessions
                for (const s of cleanedServer) {
                    if (s && s.id) mergedMap.set(s.id, s);
                }

                // 2. Merge local sessions (preserve richer message thread)
                for (const s of cleanedLocal) {
                    if (s && s.id) {
                        if (mergedMap.has(s.id)) {
                            const existing = mergedMap.get(s.id);
                            const existingCount = (existing.messages && existing.messages.length) || 0;
                            const localCount = (s.messages && s.messages.length) || 0;
                            if (localCount >= existingCount) {
                                mergedMap.set(s.id, s);
                            }
                        } else {
                            mergedMap.set(s.id, s);
                        }
                    }
                }

                // If user currently has an unsent draft in progress, keep it in memory
                const currentDraft = localSessions.find(s => s && (!s.messages || s.messages.length === 0));
                const mergedList = Array.from(mergedMap.values());
                mergedList.sort((a, b) => ((b.updatedAt || b.createdAt || 0) - (a.updatedAt || a.createdAt || 0)));

                if (currentDraft && !mergedList.some(s => s.id === currentDraft.id)) {
                    mergedList.unshift(currentDraft);
                }

                window.chatSessions = mergedList;

                // Antigravity Smart Selection: Never leave user stranded on an empty screen if real sessions exist!
                const savedId = localStorage.getItem('active_chat_session_id');
                const matchedActive = window.activeSessionId ? mergedList.find(s => s && s.id === window.activeSessionId) : null;
                const matchedSaved = savedId ? mergedList.find(s => s && s.id === savedId) : null;

                if (matchedActive && matchedActive.messages && matchedActive.messages.length > 0) {
                    window.activeSessionId = matchedActive.id;
                } else if (matchedSaved && matchedSaved.messages && matchedSaved.messages.length > 0) {
                    window.activeSessionId = matchedSaved.id;
                } else {
                    // Activate the primary conversation with actual messages (e.g. Amazon project)
                    const topActive = mergedList.find(s => s.messages && s.messages.length > 0) || mergedList[0];
                    if (topActive) {
                        window.activeSessionId = topActive.id;
                    }
                }

                if (window.activeSessionId) {
                    localStorage.setItem('active_chat_session_id', window.activeSessionId);
                }

                saveChatSessionsLocallyOnly();
                renderChatSessionsSidebar();
                renderActiveThread();
                console.log(`Synchronized ${mergedList.length} Antigravity-style sessions. Active: ${window.activeSessionId}`);
            }
        }
    } catch (e) {
        console.warn("Backend chat sessions sync unavailable:", e);
    }
}

function saveChatSessions() {
    saveChatSessionsLocallyOnly();
    saveChatSessionsToServer();
}

function saveChatSessionsLocallyOnly() {
    try {
        const serialized = JSON.stringify(window.chatSessions);
        localStorage.setItem(SESSIONS_STORAGE_KEY, serialized);
        localStorage.setItem('offline_chat_sessions_backup', serialized);
    } catch (e) {
        console.error("Storage save failed:", e);
    }
}

function saveChatSessionsToServer() {
    if (!window.chatSessions || !Array.isArray(window.chatSessions)) return;
    // Antigravity Rule: Only persist conversations that have messages to disk
    const sessionsToPersist = window.chatSessions.filter(s => s && s.messages && s.messages.length > 0);
    if (sessionsToPersist.length === 0) return;

    try {
        fetch('/api/chat/sessions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(sessionsToPersist)
        }).catch(err => console.warn("Failed to persist sessions to backend:", err));
    } catch (e) {}
}

window.createNewChatSession = function(render = true, specificModel = null) {
    const selectedModel = specificModel || document.getElementById('chatModelSelect')?.value || (window.chatModels && window.chatModels[0]?.name) || 'dolphin3:latest';
    const newSession = {
        id: 'chat_' + Date.now() + '_' + Math.random().toString(36).substring(2, 6),
        title: 'New Conversation',
        model: selectedModel,
        systemPrompt: document.getElementById('chatSystemPrompt')?.value || "You are an uncensored, highly capable, intelligent AI assistant.",
        temperature: parseFloat(document.getElementById('chatTempSlider')?.value) || 0.7,
        contextWindow: parseInt(document.getElementById('chatContextWindow')?.value) || 4096,
        activeSkills: [],
        messages: [],
        createdAt: Date.now(),
        isDraft: true
    };

    if (!Array.isArray(window.chatSessions)) window.chatSessions = [];
    // Remove any previous unsubmitted 0-message draft to avoid clutter
    window.chatSessions = window.chatSessions.filter(s => (s.messages && s.messages.length > 0));
    window.chatSessions.unshift(newSession);
    window.activeSessionId = newSession.id;
    localStorage.setItem('active_chat_session_id', newSession.id);
    saveChatSessionsLocallyOnly();

    if (render) {
        renderChatSessionsSidebar();
        renderActiveThread();
        const input = document.getElementById('chatInputMessage');
        if (input) input.focus();
    }
};

function getActiveSession() {
    if (!window.chatSessions || !Array.isArray(window.chatSessions) || window.chatSessions.length === 0) {
        return null;
    }
    return window.chatSessions.find(s => s.id === window.activeSessionId) || window.chatSessions[0] || null;
}

function renderChatSessionsSidebar() {
    const listContainer = document.getElementById('chatSessionsList');
    if (!listContainer) return;
    listContainer.innerHTML = '';

    const allSessions = window.chatSessions || [];
    const query = window.chatSearchQuery || '';

    let displayed = allSessions;
    if (query) {
        displayed = allSessions.filter(s => {
            const titleMatch = (s.title || '').toLowerCase().includes(query);
            const msgMatch = (s.messages || []).some(m => (m.content || '').toLowerCase().includes(query));
            return titleMatch || msgMatch;
        });
    }

    const badge = document.getElementById('chatModelHistoryCountBadge');
    if (badge) {
        badge.textContent = `${allSessions.length} conversation${allSessions.length === 1 ? '' : 's'}`;
    }

    if (displayed.length === 0) {
        listContainer.innerHTML = `
            <div style="padding: 24px 12px; color: var(--text-muted); font-size: 0.78rem; text-align: center; line-height: 1.5;">
                <div style="margin-bottom: 4px; color: var(--text-secondary); font-weight: 500;">
                    ${query ? 'No matching conversations' : 'No conversations yet'}
                </div>
                <span>${query ? 'Try a different search keyword.' : 'Start a new chat to begin working.'}</span>
                <div style="margin-top: 10px; display: flex; gap: 6px; justify-content: center;">
                    <button type="button" onclick="createNewChatSession(true)" class="btn-quiet" style="font-size: 0.72rem; padding: 3px 9px;">+ New Chat</button>
                </div>
            </div>
        `;
        return;
    }

    displayed.forEach(s => {
        const item = document.createElement('div');
        const isActive = s.id === window.activeSessionId;
        item.className = 'chat-session-item' + (isActive ? ' active' : '');
        item.title = s.title || 'New Conversation';

        item.onclick = (e) => {
            if (!e.target.closest('button')) {
                switchChatSession(s.id);
            }
        };

        // Header Row: Title & Action Buttons
        const headerRow = document.createElement('div');
        headerRow.className = 'chat-session-header-row';

        const titleDiv = document.createElement('div');
        titleDiv.className = 'chat-session-title';
        titleDiv.textContent = s.title || 'New Conversation';
        titleDiv.ondblclick = (e) => {
            e.stopPropagation();
            renameChatSession(s.id);
        };

        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'chat-session-actions';

        // Rename Button
        const renameBtn = document.createElement('button');
        renameBtn.type = 'button';
        renameBtn.className = 'chat-session-action-btn';
        renameBtn.title = 'Rename';
        renameBtn.innerHTML = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>`;
        renameBtn.onclick = (e) => {
            e.stopPropagation();
            renameChatSession(s.id);
        };

        // Export Markdown Button
        const exportBtn = document.createElement('button');
        exportBtn.type = 'button';
        exportBtn.className = 'chat-session-action-btn';
        exportBtn.title = 'Export Markdown Transcript';
        exportBtn.innerHTML = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>`;
        exportBtn.onclick = (e) => {
            e.stopPropagation();
            exportChatSession(s.id);
        };

        // Delete Button
        const delBtn = document.createElement('button');
        delBtn.type = 'button';
        delBtn.className = 'chat-session-action-btn delete-btn';
        delBtn.title = 'Delete';
        delBtn.innerHTML = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>`;
        delBtn.onclick = (e) => {
            e.stopPropagation();
            deleteChatSession(s.id);
        };

        actionsDiv.appendChild(renameBtn);
        actionsDiv.appendChild(exportBtn);
        actionsDiv.appendChild(delBtn);

        headerRow.appendChild(titleDiv);
        headerRow.appendChild(actionsDiv);

        // Meta Row: Time & Message Count
        const metaRow = document.createElement('div');
        metaRow.className = 'chat-session-meta-row';

        const timeSpan = document.createElement('span');
        timeSpan.textContent = formatRelativeTime(s.updatedAt || s.createdAt);

        const badgeSpan = document.createElement('span');
        const msgCount = (s.messages && s.messages.length) || 0;
        const modelName = (s.model || 'dolphin3').split(':')[0];
        badgeSpan.textContent = `${msgCount} msgs • ${modelName}`;
        badgeSpan.style.background = 'rgba(185, 157, 115, 0.12)';
        badgeSpan.style.color = '#B99D73';
        badgeSpan.style.border = '1px solid rgba(185, 157, 115, 0.25)';
        badgeSpan.style.padding = '1px 5px';
        badgeSpan.style.borderRadius = '3px';

        metaRow.appendChild(timeSpan);
        metaRow.appendChild(badgeSpan);

        item.appendChild(headerRow);
        item.appendChild(metaRow);
        listContainer.appendChild(item);
    });
}

window.switchChatSession = function(sessionId) {
    if (window.activeSessionId === sessionId) return;
    window.activeSessionId = sessionId;
    localStorage.setItem('active_chat_session_id', sessionId);
    renderChatSessionsSidebar();
    renderActiveThread();
};

window.renameCurrentSessionPrompt = function() {
    const session = getActiveSession();
    if (session) {
        renameChatSession(session.id);
    }
};

window.renameChatSession = async function(sessionId) {
    const session = (window.chatSessions || []).find(s => s.id === sessionId);
    if (!session) return;

    const currentTitle = session.title || 'New Conversation';
    const newTitle = prompt("Enter conversation title:", currentTitle);
    if (!newTitle || newTitle.trim() === '' || newTitle.trim() === currentTitle) return;

    const trimmed = newTitle.trim();
    session.title = trimmed;
    session.updatedAt = Date.now();

    const titleEl = document.getElementById('chatActiveTitle');
    if (titleEl && window.activeSessionId === sessionId) {
        titleEl.textContent = trimmed;
    }

    saveChatSessionsLocallyOnly();
    renderChatSessionsSidebar();

    try {
        await fetch(`/api/chat/sessions/${sessionId}/title`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: trimmed })
        });
    } catch (e) {
        console.warn("Failed to rename title on server:", e);
    }
};

window.exportCurrentSession = function() {
    const session = getActiveSession();
    if (session) {
        exportChatSession(session.id);
    }
};

window.exportChatSession = async function(sessionId) {
    try {
        const session = (window.chatSessions || []).find(s => s.id === sessionId);
        const fileName = `${(session?.title || 'conversation').replace(/[^a-zA-Z0-9_-]/g, '_')}_transcript.md`;

        const res = await fetch(`/api/chat/sessions/${sessionId}/export`);
        if (res.ok) {
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = fileName;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        } else {
            // Local fallback export
            if (!session) return alert("Session not found");
            let md = `# ${session.title || 'Conversation'}

`;
            (session.messages || []).forEach((m, idx) => {
                md += `### ${idx + 1}. ${(m.role || '').toUpperCase()}

${m.content}

---

`;
            });
            const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = fileName;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        }
    } catch (e) {
        alert("Export failed: " + e.message);
    }
};

window.deleteChatSession = async function(sessionId) {
    const session = (window.chatSessions || []).find(s => s.id === sessionId);
    const title = session?.title || 'this conversation';
    if (!confirm(`Delete "${title}"? This cannot be undone.`)) return;

    window.chatSessions = window.chatSessions.filter(s => s.id !== sessionId);

    if (window.activeSessionId === sessionId) {
        const remainingWithMsgs = window.chatSessions.filter(s => s.messages && s.messages.length > 0);
        window.activeSessionId = remainingWithMsgs.length > 0 ? remainingWithMsgs[0].id : (window.chatSessions[0]?.id || null);
    }

    saveChatSessionsLocallyOnly();

    try {
        await fetch(`/api/chat/sessions/${sessionId}`, { method: 'DELETE' });
    } catch (e) {
        console.warn("Failed to delete session on server:", e);
    }

    if (!window.activeSessionId) {
        createNewChatSession(true);
    } else {
        renderChatSessionsSidebar();
        renderActiveThread();
    }
};

window.clearAllChatSessions = function() {
    if (!confirm("Are you sure you want to permanently delete all local chat sessions?")) return;
    const sessionIds = (window.chatSessions || []).map(s => s.id);
    window.chatSessions = [];
    window.activeSessionId = null;
    saveChatSessionsLocallyOnly();

    sessionIds.forEach(sid => {
        fetch(`/api/chat/sessions/${sid}`, { method: 'DELETE' }).catch(() => {});
    });

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
    
    // Sync prompt pill to last used model or active model
    const targetModel = session.model || window.activeChatModel || 'dolphin3:latest';
    if (typeof selectPromptModel === 'function') {
        selectPromptModel(targetModel);
    }

    // Update active skills pill for this specific conversation
    if (typeof updateSessionSkillsUI === 'function') {
        updateSessionSkillsUI(session);
    }

    // Sync context window dropdown
    const ctxSelect = document.getElementById('chatContextWindow');
    if (ctxSelect && session.contextWindow) {
        ctxSelect.value = session.contextWindow;
    }

    thread.innerHTML = '';

    if (!session.messages || session.messages.length === 0) {
        // Render Empty Welcome Hero
        thread.innerHTML = `
            <div id="chatEmptyHero" style="text-align: center; margin: auto 0; padding: 40px 10px;">
                <div style="width: 44px; height: 44px; border-radius: 10px; background: rgba(192, 138, 69, 0.12); border: 1px solid rgba(192, 138, 69, 0.28); display: flex; align-items: center; justify-content: center; margin: 0 auto 16px; color: #C08A45;">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                </div>
                <h3 style="color: var(--text-primary); margin-bottom: 8px; font-size: 1.25rem; font-weight: 700;">Offline Chat Arena</h3>
                <p style="color: var(--text-secondary); font-size: 0.88rem; max-width: 500px; margin: 0 auto 24px; line-height: 1.5;">
                    Operating directly on NVIDIA GeForce RTX 3050 Laptop GPU (6GB VRAM).<br>
                    100% private and air-gapped local execution.
                </p>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; max-width: 650px; margin: 0 auto;">
                    <div onclick="selectQuickPrompt(this.querySelector('.prompt-body').innerText)" style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); padding: 14px; border-radius: 8px; text-align: left; cursor: pointer; transition: 0.2s;" onmouseenter="this.style.borderColor='var(--accent)'" onmouseleave="this.style.borderColor='var(--border-subtle)'">
                        <span class="prompt-tag">Security</span>
                        <div class="prompt-body" style="font-size: 0.84rem; color: var(--text-primary);">Write a Python vulnerability scanner for common CVEs</div>
                    </div>
                    <div onclick="selectQuickPrompt(this.querySelector('.prompt-body').innerText)" style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); padding: 14px; border-radius: 8px; text-align: left; cursor: pointer; transition: 0.2s;" onmouseenter="this.style.borderColor='var(--accent)'" onmouseleave="this.style.borderColor='var(--border-subtle)'">
                        <span class="prompt-tag">Performance</span>
                        <div class="prompt-body" style="font-size: 0.84rem; color: var(--text-primary);">Write an optimized C++ program demonstrating memory heap safety</div>
                    </div>
                    <div onclick="selectQuickPrompt(this.querySelector('.prompt-body').innerText)" style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); padding: 14px; border-radius: 8px; text-align: left; cursor: pointer; transition: 0.2s;" onmouseenter="this.style.borderColor='var(--accent)'" onmouseleave="this.style.borderColor='var(--border-subtle)'">
                        <span class="prompt-tag">Networking</span>
                        <div class="prompt-body" style="font-size: 0.84rem; color: var(--text-primary);">Build a fast asynchronous network probe in Python</div>
                    </div>
                    <div onclick="selectQuickPrompt(this.querySelector('.prompt-body').innerText)" style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); padding: 14px; border-radius: 8px; text-align: left; cursor: pointer; transition: 0.2s;" onmouseenter="this.style.borderColor='var(--accent)'" onmouseleave="this.style.borderColor='var(--border-subtle)'">
                        <span class="prompt-tag">Architecture</span>
                        <div class="prompt-body" style="font-size: 0.84rem; color: var(--text-primary);">Explain how abliteration mathematically removes refusal vectors</div>
                    </div>
                </div>
            </div>
        `;
        return;
    }

    session.messages.forEach(m => {
        appendMessageElement(m.role, m.content, m.telemetry, false, m.images, m.rag_sources, m.active_skills, m.agentic_data, m.model_used, m.bake_recommendation);
    });

    thread.scrollTop = thread.scrollHeight;
}

window.refreshChatStatus = async function() {
    try {
        const res = await fetch('/api/chat/status');
        const data = await res.json();
        const badge = document.getElementById('chatOllamaStatusBadge');
        const navBadge = document.getElementById('navOllamaBadge');
        const startBtn = document.getElementById('btnStartOllama');

        if (data.status === 'online') {
            if (badge) {
                badge.style.background = 'rgba(255, 255, 255, 0.03)';
                badge.style.borderColor = 'var(--border-subtle)';
                badge.style.color = 'var(--text-secondary)';
                badge.innerHTML = '<span class="status-dot" style="background:#10b981;display:inline-block;width:6px;height:6px;border-radius:50%;"></span> Ollama Online';
            }
            if (startBtn) startBtn.style.display = 'none';
        } else {
            if (badge) {
                badge.style.background = 'rgba(239, 68, 68, 0.08)';
                badge.style.borderColor = 'rgba(239, 68, 68, 0.25)';
                badge.style.color = '#ef4444';
                badge.innerHTML = '<span class="status-dot" style="background:#ef4444;display:inline-block;width:6px;height:6px;border-radius:50%;"></span> Ollama Offline';
            }
            if (startBtn) startBtn.style.display = 'inline-block';
        }
    } catch (err) {
        console.warn("Ollama status check failed:", err);
    }
};

window.startOllamaService = async function() {
    const btn = document.getElementById('btnStartOllama');
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Starting...';
    }
    try {
        const res = await fetch('/api/chat/start_ollama', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'started' || data.status === 'already_running') {
            await window.refreshChatStatus();
        } else {
            let attempts = 0;
            const timer = setInterval(async () => {
                attempts++;
                await window.refreshChatStatus();
                const badge = document.getElementById('chatOllamaStatusBadge');
                if (badge && badge.textContent.includes('Online')) {
                    clearInterval(timer);
                } else if (attempts > 8) {
                    clearInterval(timer);
                    if (btn) {
                        btn.disabled = false;
                        btn.textContent = 'Retry';
                    }
                }
            }, 800);
        }
    } catch (err) {
        alert("Failed to start Ollama: " + err.message);
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Start';
        }
    }
};

window.refreshDockerStatus = async function() {
    try {
        const res = await fetch('/api/chat/sandbox/docker/status');
        const data = await res.json();
        window.dockerStatus = data;

        const badge = document.getElementById('chatDockerStatusBadge');
        const dot = document.getElementById('chatDockerDot');
        const text = document.getElementById('chatDockerText');
        const btn = document.getElementById('btnToggleDocker');
        const btnText = document.getElementById('btnDockerText');

        if (data.status === 'online') {
            if (badge) {
                badge.style.background = 'rgba(16, 185, 129, 0.08)';
                badge.style.borderColor = 'rgba(16, 185, 129, 0.3)';
                badge.style.color = '#10b981';
            }
            if (dot) {
                dot.style.display = 'inline-block';
                dot.style.width = '6px';
                dot.style.height = '6px';
                dot.style.background = '#10b981';
            }
            if (text) text.textContent = '🐳 Docker: Online (--network none)';
            if (btn) {
                btn.style.display = 'inline-flex';
                btn.style.borderColor = 'rgba(239, 68, 68, 0.3)';
                btn.style.color = '#f87171';
                btn.title = 'Stop Docker to reclaim RAM';
            }
            if (btnText) btnText.textContent = 'Stop Docker';
        } else {
            if (badge) {
                badge.style.background = 'rgba(255, 255, 255, 0.03)';
                badge.style.borderColor = 'var(--border-subtle)';
                badge.style.color = 'var(--text-muted)';
            }
            if (dot) {
                dot.style.display = 'inline-block';
                dot.style.width = '6px';
                dot.style.height = '6px';
                dot.style.background = 'var(--text-muted)';
            }
            if (text) text.textContent = '🛡️ Sandbox: Local Jail';
            if (btn) {
                btn.style.display = 'inline-flex';
                btn.style.borderColor = 'rgba(56, 189, 248, 0.35)';
                btn.style.background = 'rgba(56, 189, 248, 0.08)';
                btn.style.color = '#38bdf8';
                btn.title = 'Launch Docker Desktop for hardware kernel isolation';
            }
            if (btnText) btnText.textContent = '🐳 Turn On Docker';
        }
    } catch (err) {
        console.warn("Docker status check failed:", err);
    }
};

window.toggleDockerService = async function() {
    const btn = document.getElementById('btnToggleDocker');
    const btnText = document.getElementById('btnDockerText');
    const isOnline = window.dockerStatus && window.dockerStatus.status === 'online';

    if (isOnline) {
        // Stop Docker
        if (btnText) btnText.textContent = "Stopping...";
        if (btn) btn.disabled = true;
        try {
            const res = await fetch('/api/chat/sandbox/docker/stop', { method: 'POST' });
            const data = await res.json();
            alert(data.message || "Docker stopped. RAM reclaimed.");
            await refreshDockerStatus();
        } catch (err) {
            alert("Error stopping Docker: " + err.message);
        } finally {
            if (btn) btn.disabled = false;
        }
    } else {
        // Start Docker
        if (btnText) btnText.textContent = "Starting...";
        if (btn) btn.disabled = true;
        try {
            const res = await fetch('/api/chat/sandbox/docker/start', { method: 'POST' });
            const data = await res.json();

            if (data.status === 'not_installed') {
                window.openDockerSetupModal();
            } else {
                alert(data.message || "Starting Docker Desktop in background...");
                setTimeout(refreshDockerStatus, 2500);
                setTimeout(refreshDockerStatus, 6000);
            }
        } catch (err) {
            alert("Failed to start Docker: " + err.message);
        } finally {
            if (btn) btn.disabled = false;
            await refreshDockerStatus();
        }
    }
};

window.openDockerSetupModal = function() {
    const modal = document.getElementById('dockerSetupModal');
    if (modal) modal.style.display = 'flex';
};

window.closeDockerSetupModal = function() {
    const modal = document.getElementById('dockerSetupModal');
    if (modal) modal.style.display = 'none';
};


let addModelPollInterval = null;

window.switchAddModelTab = function(tabName) {
    const tabs = ['tab-existing', 'tab-gguf', 'tab-download'];
    tabs.forEach(t => {
        const el = document.getElementById('add-modal-' + t);
        const btn = document.getElementById('btn-modal-' + t);
        if (el) {
            el.style.display = (t === tabName) ? 'flex' : 'none';
            if (t === tabName) el.scrollTop = 0;
        }
        if (btn) {
            btn.style.background = (t === tabName) ? 'var(--bg-surface-elevated)' : 'transparent';
            btn.style.color = (t === tabName) ? 'var(--text-primary)' : 'var(--text-secondary)';
            btn.style.borderColor = (t === tabName) ? 'var(--border-medium)' : 'transparent';
        }
    });

    const modal = document.getElementById('addModelModal');
    if (modal) modal.scrollTop = 0;

    if (tabName === 'tab-gguf') {
        window.scanLocalGgufs();
    }
};

window.openAddModelModal = function() {
    const modal = document.getElementById('addModelModal');
    if (!modal) return;
    modal.style.display = 'flex';
    modal.scrollTop = 0;

    // Populate existing models dropdown
    const aliasSelect = document.getElementById('aliasSourceSelect');
    if (aliasSelect) {
        aliasSelect.innerHTML = '';
        if (window.chatModels && window.chatModels.length > 0) {
            window.chatModels.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m.name;
                opt.textContent = `${m.name} (${m.parameter_size} • ${m.size_gb} GB)`;
                aliasSelect.appendChild(opt);
            });
        } else {
            aliasSelect.innerHTML = '<option value="">No downloaded models detected</option>';
        }
    }

    const aliasCustomInput = document.getElementById('aliasCustomName');
    if (aliasCustomInput) aliasCustomInput.value = '';

    const importName = document.getElementById('importGgufName');
    const importPath = document.getElementById('importGgufPath');
    if (importName) importName.value = '';
    if (importPath) importPath.value = '';

    const customNameInput = document.getElementById('addModelCustomName');
    const tagInput = document.getElementById('addModelTag');
    const progressBox = document.getElementById('addModelProgressBox');
    const progressBar = document.getElementById('addModelProgressBar');
    const submitBtn = document.getElementById('btnAddModelSubmit');
    const cancelBtn = document.getElementById('btnAddModelCancel');

    if (customNameInput) customNameInput.value = '';
    if (tagInput) tagInput.value = '';
    if (progressBox) progressBox.style.display = 'none';
    if (progressBar) {
        progressBar.style.width = '0%';
        progressBar.style.background = 'var(--accent)';
    }
    if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span>Download & Register</span>';
    }
    if (cancelBtn) cancelBtn.disabled = false;

    // Default to existing model naming tab
    window.switchAddModelTab('tab-existing');
};

window.submitAliasExistingModel = async function() {
    const select = document.getElementById('aliasSourceSelect');
    const input = document.getElementById('aliasCustomName');
    const btn = document.getElementById('btnAliasSubmit');

    const sourceModel = select ? select.value : '';
    const customName = input ? input.value.trim() : '';

    if (!sourceModel) {
        alert("Please select a downloaded model.");
        return;
    }
    if (!customName) {
        alert("Please enter a custom name for this model.");
        if (input) input.focus();
        return;
    }

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span>Creating Model Alias...</span>';
    }

    try {
        const res = await fetch('/api/chat/alias_existing', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                source_model: sourceModel,
                custom_name: customName
            })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Failed to create custom model');

        closeAddModelModal();
        await refreshChatModels(data.final_name);
        alert(`Success! Created custom model "${data.final_name}" from "${sourceModel}". Selected in Chat Arena!`);
    } catch (err) {
        alert("Error: " + err.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<span>Register Custom Name & Load</span>';
        }
    }
};

window.triggerGgufBrowserPicker = function() {
    const input = document.getElementById('ggufWebFileInput');
    if (input) {
        input.click();
    }
};

window.browseGgufNativeFile = async function() {
    window.triggerGgufBrowserPicker();
};

window.onGgufWebFileSelected = async function(input) {
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    const pathInput = document.getElementById('importGgufPath');
    const nameInput = document.getElementById('importGgufName');
    const dropBoxText = document.getElementById('ggufDropBoxText');
    const statusBox = document.getElementById('importGgufStatusBox');
    const statusText = document.getElementById('importGgufStatusText');
    const btnSubmit = document.getElementById('btnGgufSubmit');

    const isZip = file.name.toLowerCase().endsWith('.zip');
    let cleanName = file.name.replace(/\.(zip|tar|gguf|bin)$/i, '')
                             .replace(/\.q[0-9]_[a-z0-9_]+/i, '')
                             .replace(/^cloud_trainer_/i, '')
                             .replace(/_[a-f0-9]{8}$/i, '')
                             .toLowerCase()
                             .replace(/[^a-z0-9_\-\.:]/g, '-')
                             .replace(/-+/g, '-')
                             .replace(/^-|-$/g, '');

    if (nameInput && (!nameInput.value || nameInput.value.trim() === '')) {
        nameInput.value = cleanName;
    }

    if (dropBoxText) {
        dropBoxText.innerHTML = isZip 
            ? `Unpacking & Preparing: <strong>${file.name}</strong> (${(file.size / (1024*1024)).toFixed(1)} MB)...` 
            : `Preparing: <strong>${file.name}</strong> (${(file.size / (1024*1024)).toFixed(1)} MB)...`;
    }
    if (statusBox) statusBox.style.display = 'block';
    if (statusText) statusText.textContent = isZip ? `Extracting trained weights from ${file.name}...` : `Preparing local file: ${file.name}...`;

    try {
        const formData = new FormData();
        formData.append('file', file);

        const res = await fetch('/api/chat/upload_gguf', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();

        if (!res.ok) throw new Error(data.detail || 'File preparation failed');

        if (pathInput) pathInput.value = data.path;
        if (dropBoxText) {
            dropBoxText.innerHTML = isZip 
                ? `Extracted & Ready: <strong>${data.filename}</strong> (${data.size_mb} MB)` 
                : `Ready: <strong>${data.filename}</strong> (${data.size_mb} MB)`;
        }
        if (statusText) statusText.textContent = `Weights ready at: ${data.path}`;
    } catch (err) {
        console.error("File upload error:", err);
        if (dropBoxText) dropBoxText.textContent = `Failed: ${err.message}`;
        if (statusText) statusText.textContent = `Failed: ${err.message}`;
    }
};

window.scanLocalGgufs = async function() {
    const container = document.getElementById('detectedGgufContainer');
    const list = document.getElementById('detectedGgufList');
    if (!container || !list) return;

    try {
        const res = await fetch('/api/chat/scan_local_ggufs');
        const data = await res.json();

        if (data.status === 'success' && data.files && data.files.length > 0) {
            container.style.display = 'block';
            list.innerHTML = '';
            data.files.forEach(f => {
                const btn = document.createElement('button');
                btn.type = 'button';
                const isZip = f.type === 'zip';
                const isModel = f.type === 'modelfile';
                const isStarter = f.type === 'starter_pack';

                let colorBg = isZip ? 'var(--accent-subtle)' : (isModel ? 'rgba(16, 185, 129, 0.15)' : 'rgba(56, 189, 248, 0.15)');
                let colorBorder = isZip ? 'var(--border-medium)' : (isModel ? 'rgba(16, 185, 129, 0.4)' : 'rgba(56, 189, 248, 0.35)');
                let colorText = isZip ? 'var(--accent-text)' : (isModel ? '#10b981' : '#38bdf8');

                if (isStarter) {
                    colorBg = 'rgba(245, 158, 11, 0.12)';
                    colorBorder = 'rgba(245, 158, 11, 0.35)';
                    colorText = '#fbbf24';
                }
                
                btn.style.cssText = `background: ${colorBg}; border: 1px solid ${colorBorder}; color: ${colorText}; font-size: 0.72rem; padding: 5px 9px; border-radius: 6px; cursor: pointer; text-align: left; font-family: var(--font-mono);`;
                btn.textContent = isStarter ? `${f.name} (${f.size_mb} MB • Colab Starter Kit)` : `${f.name} (${f.size_mb} MB)`;
                
                let cleanName = f.name.replace(/\.(zip|tar|gguf|bin)$/i, '')
                                     .replace(/\.q[0-9]_[a-z0-9_]+/i, '')
                                     .replace(/^cloud_trainer_/i, '')
                                     .replace(/_[a-f0-9]{8}$/i, '')
                                     .toLowerCase()
                                     .replace(/[^a-z0-9_\-\.:]/g, '-')
                                     .replace(/-+/g, '-')
                                     .replace(/^-|-$/g, '');

                btn.onclick = () => {
                    if (isStarter) {
                        const switchChoice = confirm(
                            `"${f.name}" (${f.size_mb} MB) is a Cloud Training Starter Kit (dataset & Colab notebook), NOT the trained .GGUF model weights.\n\n` +
                            `To turn it into a trained model:\n` +
                            `1. Upload this file to Google Colab and run the training notebook.\n` +
                            `2. Colab will train and export the .GGUF file (~1.2 GB).\n` +
                            `3. Download that .GGUF and import it here!\n\n` +
                            `Want to chat with "${cleanName}" right now? Would you like to switch to "Name Existing Model" and alias one of your downloaded models (e.g. Dolphin 3 or Llama 3) instantly?`
                        );
                        if (switchChoice) {
                            window.switchAddModelTab('tab-existing');
                            const aliasInput = document.getElementById('aliasCustomName');
                            if (aliasInput) {
                                aliasInput.value = cleanName;
                                aliasInput.focus();
                            }
                        }
                        return;
                    }

                    const pathInput = document.getElementById('importGgufPath');
                    const nameInput = document.getElementById('importGgufName');
                    const dropBoxText = document.getElementById('ggufDropBoxText');
                    if (pathInput) pathInput.value = f.path;
                    if (nameInput) nameInput.value = cleanName;
                    if (dropBoxText) dropBoxText.innerHTML = `Selected from PC: <strong>${f.name}</strong>`;
                };
                list.appendChild(btn);
            });
        }
    } catch (err) {
        console.error("Scan error:", err);
    }
};

window.submitImportGgufModel = async function() {
    const nameInput = document.getElementById('importGgufName');
    const pathInput = document.getElementById('importGgufPath');
    const btn = document.getElementById('btnGgufSubmit');
    const statusBox = document.getElementById('importGgufStatusBox');
    const statusText = document.getElementById('importGgufStatusText');

    const modelName = nameInput ? nameInput.value.trim() : '';
    const ggufPath = pathInput ? pathInput.value.trim() : '';

    if (!modelName) {
        alert("Please enter a name for the imported model.");
        if (nameInput) nameInput.focus();
        return;
    }
    if (!ggufPath) {
        alert("Please click 'Browse Files...' or select a .gguf file.");
        if (pathInput) pathInput.focus();
        return;
    }

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span>Registering Weights...</span>';
    }
    if (statusBox) statusBox.style.display = 'block';
    if (statusText) statusText.textContent = `Registering "${modelName}" in Ollama local engine...`;

    try {
        const res = await fetch('/api/chat/import_gguf', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                model_name: modelName,
                gguf_path: ggufPath
            })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Failed to import GGUF');

        if (statusText) statusText.textContent = `Successfully imported "${data.final_name}"!`;
        setTimeout(async () => {
            closeAddModelModal();
            await refreshChatModels(data.final_name);
            alert(`Success! Imported model "${data.final_name}" into local Ollama! Selected in Chat Arena.`);
        }, 800);
    } catch (err) {
        if (statusText) statusText.textContent = `Error: ${err.message}`;
        alert("Error: " + err.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<span>Register Local Model & Load</span>';
        }
    }
};

window.closeAddModelModal = function() {
    if (addModelPollInterval) {
        clearInterval(addModelPollInterval);
        addModelPollInterval = null;
    }
    const modal = document.getElementById('addModelModal');
    if (modal) modal.style.display = 'none';
};

window.selectModelPreset = function(tag, defaultCustomName) {
    const tagInput = document.getElementById('addModelTag');
    const customNameInput = document.getElementById('addModelCustomName');
    if (tagInput) tagInput.value = tag;
    if (customNameInput && (!customNameInput.value || customNameInput.value.trim() === '')) {
        customNameInput.value = defaultCustomName;
    }
};

window.submitAddLocalModel = async function() {
    const tagInput = document.getElementById('addModelTag');
    const customNameInput = document.getElementById('addModelCustomName');
    const progressBox = document.getElementById('addModelProgressBox');
    const progressBar = document.getElementById('addModelProgressBar');
    const progressPct = document.getElementById('addModelProgressPct');
    const statusText = document.getElementById('addModelStatusText');
    const progressDetail = document.getElementById('addModelProgressDetail');
    const submitBtn = document.getElementById('btnAddModelSubmit');
    const cancelBtn = document.getElementById('btnAddModelCancel');

    const modelTag = tagInput ? tagInput.value.trim() : '';
    const customName = customNameInput ? customNameInput.value.trim() : '';

    if (!modelTag) {
        alert("Please enter an Ollama model tag or choose one of the quick presets below.");
        if (tagInput) tagInput.focus();
        return;
    }

    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span>Downloading...</span>';
    }
    if (cancelBtn) cancelBtn.disabled = true;
    if (progressBox) progressBox.style.display = 'block';
    if (progressBar) {
        progressBar.style.width = '0%';
        progressBar.style.background = 'var(--accent)';
    }
    if (progressPct) progressPct.textContent = '0%';
    if (statusText) statusText.textContent = 'Initiating download...';
    if (progressDetail) progressDetail.textContent = 'Connecting to Ollama library...';

    try {
        const res = await fetch('/api/chat/pull', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                model_tag: modelTag,
                custom_name: customName || null
            })
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || 'Failed to start download');
        }

        // Start polling progress
        if (addModelPollInterval) clearInterval(addModelPollInterval);

        addModelPollInterval = setInterval(async () => {
            try {
                const statusRes = await fetch('/api/chat/pull/status');
                if (!statusRes.ok) return;
                const state = await statusRes.json();

                if (state.status === 'downloading' || state.status === 'starting') {
                    const pct = Math.round(state.progress || 0);
                    if (progressBar) progressBar.style.width = pct + '%';
                    if (progressPct) progressPct.textContent = pct + '%';
                    if (statusText) statusText.textContent = state.detail || 'Downloading model layers...';
                    if (progressDetail) {
                        if (state.total_mb > 0) {
                            progressDetail.textContent = `${state.completed_mb} MB / ${state.total_mb} MB (${pct}%)`;
                        } else {
                            progressDetail.textContent = state.detail || 'Pulling layers...';
                        }
                    }
                } else if (state.status === 'aliasing') {
                    if (progressBar) progressBar.style.width = '95%';
                    if (progressPct) progressPct.textContent = '95%';
                    if (statusText) statusText.textContent = `Naming model "${state.final_name || customName}"...`;
                    if (progressDetail) progressDetail.textContent = 'Creating local alias in Ollama runtime...';
                } else if (state.status === 'completed') {
                    clearInterval(addModelPollInterval);
                    addModelPollInterval = null;

                    if (progressBar) {
                        progressBar.style.width = '100%';
                        progressBar.style.background = '#10b981';
                    }
                    if (progressPct) progressPct.textContent = '100%';
                    if (statusText) statusText.textContent = `Ready! Model registered.`;
                    if (progressDetail) progressDetail.textContent = `Model "${state.final_name}" added to local library.`;

                    // Wait 1.2s then close modal and select new model
                    setTimeout(async () => {
                        closeAddModelModal();
                        await refreshChatModels(state.final_name);
                    }, 1200);
                } else if (state.status === 'error') {
                    clearInterval(addModelPollInterval);
                    addModelPollInterval = null;
                    if (statusText) statusText.textContent = 'Download Failed';
                    if (progressDetail) progressDetail.textContent = state.error || state.detail || 'Unknown error occurred.';
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = '<span>Retry Download</span>';
                    }
                    if (cancelBtn) cancelBtn.disabled = false;
                }
            } catch (pollErr) {
                console.error("Error polling pull status:", pollErr);
            }
        }, 800);

    } catch (err) {
        if (addModelPollInterval) {
            clearInterval(addModelPollInterval);
            addModelPollInterval = null;
        }
        if (statusText) statusText.textContent = 'Failed to initiate';
        if (progressDetail) progressDetail.textContent = err.message;
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<span>Download & Register</span>';
        }
        if (cancelBtn) cancelBtn.disabled = false;
        alert("Failed to download model: " + err.message);
    }
};

window.refreshChatModels = async function(modelToSelect = null) {
    const select = document.getElementById('chatModelSelect');
    if (!select) return;
    select.innerHTML = '<option value="">Scanning local models...</option>';
    
    try {
        const res = await fetch('/api/chat/models');
        const data = await res.json();
        
        if (data.status !== 'online' || !data.models || data.models.length === 0) {
            select.innerHTML = '<option value="">No local models detected in Ollama</option>';
            return;
        }

        window.chatModels = data.models;
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
        renderChatSessionsSidebar();
    } catch (err) {
        console.error("Failed to load models:", err);
        select.innerHTML = '<option value="">Error loading models</option>';
    }
};

window.onChatModelChange = function(triggeredBySessionSwitch = false) {
    const select = document.getElementById('chatModelSelect');
    const badge = document.getElementById('chatModelDetailsBadge');
    if (!select || !select.value) return;

    const selectedName = select.value;

    const modelObj = (window.chatModels || []).find(m => m.name === selectedName);
    if (modelObj && badge) {
        badge.textContent = `${modelObj.parameter_size} • ${modelObj.quantization} • ${modelObj.size_gb} GB`;
    }

    // If this change was caused by user clicking a session that had this model, just update sidebar count
    if (triggeredBySessionSwitch) {
        renderChatSessionsSidebar();
        return;
    }

    // User explicitly changed the model dropdown:
    // Check if the current active session belongs to this model
    const active = getActiveSession();
    if (active && active.model === selectedName) {
        renderChatSessionsSidebar();
        return;
    }

    // Look for the most recent conversation associated with this selected model
    const matchingSession = (window.chatSessions || []).find(s => s.model === selectedName);
    if (matchingSession) {
        window.activeSessionId = matchingSession.id;
        renderChatSessionsSidebar();
        renderActiveThread(true);
    } else {
        // No conversation yet for this model: create a new blank one
        createNewChatSession(true, selectedName);
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
    let message = input ? input.value.trim() : '';
    
    const hasImages = window.attachedChatImages && window.attachedChatImages.length > 0;
    if (!message && !hasImages) return;

    if (!message && hasImages) {
        message = "Please analyze this image/screenshot and diagnose what you see.";
    }

    const currentImages = hasImages ? [...window.attachedChatImages] : [];
    window.clearAttachedChatImage();

    let session = getActiveSession();
    if (!session) {
        createNewChatSession(false);
        session = getActiveSession();
    }

    const model = window.activeChatModel || document.getElementById('chatModelSelect')?.value || 'dolphin3:latest';
    session.model = model;
    const systemPrompt = document.getElementById('chatSystemPrompt').value.trim();
    const temperature = parseFloat(document.getElementById('chatTempSlider').value) || 0.7;
    const contextWindow = parseInt(document.getElementById('chatContextWindow')?.value) || session.contextWindow || 4096;
    session.contextWindow = contextWindow;

    // Clear empty hero
    const hero = document.getElementById('chatEmptyHero');
    if (hero) hero.remove();

    if (input) input.value = '';

    // If first message, auto-title the session
    if (session.messages.length === 0) {
        session.title = message.length > 35 ? message.substring(0, 35) + '...' : message;
        const titleEl = document.getElementById('chatActiveTitle');
        if (titleEl) titleEl.textContent = session.title;
    }

    // Add user message to session
    const imgBase64List = currentImages.map(img => img.base64);
    const userMsg = {
        role: 'user',
        content: message,
        images: imgBase64List.length > 0 ? imgBase64List : undefined
    };
    session.messages.push(userMsg);
    saveChatSessions();
    renderChatSessionsSidebar();
    appendMessageElement('user', message, null, true, userMsg.images);

    const activeSkillIds = (session && Array.isArray(session.activeSkills)) ? session.activeSkills : [];
    const isAgentic = window.agenticModeEnabled === true;
    const projectName = session.projectName || ('proj_' + (session.id || 'default').replace(/[^a-zA-Z0-9]/g, '_').substring(0, 16));
    session.projectName = projectName;

    // Show typing bubble with live Antigravity progress telemetry
    const typingId = appendTypingIndicator(model, isAgentic ? projectName : null);

    window.isChatGenerating = true;
    window.activeGeneratingProject = projectName;
    const sendBtn = document.getElementById('btnSendChat');
    const execControls = document.getElementById('activeExecutionControls');
    if (sendBtn) sendBtn.style.display = 'none';
    if (execControls) {
        execControls.style.display = 'inline-flex';
        const pauseLbl = document.getElementById('btnPauseExecutionLabel');
        const pauseIcon = document.getElementById('btnPauseExecutionIcon');
        const pauseBtn = document.getElementById('btnPauseExecution');
        if (pauseLbl) pauseLbl.textContent = 'Pause';
        if (pauseIcon) pauseIcon.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>';
        if (pauseBtn) {
            pauseBtn.style.color = '#f59e0b';
            pauseBtn.style.borderColor = 'rgba(245, 158, 11, 0.4)';
            pauseBtn.style.background = 'rgba(245, 158, 11, 0.1)';
        }
    }

    try {
        const historyPayload = session.messages.map(m => ({
            role: m.role,
            content: m.content,
            images: m.images && m.images.length > 0 ? m.images : undefined
        }));

        const res = await fetch('/api/chat/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                model: model,
                messages: historyPayload,
                system_prompt: systemPrompt,
                temperature: temperature,
                context_window: contextWindow,
                use_rag: window.cyberRAGEnabled !== false,
                skill_ids: activeSkillIds,
                agentic: isAgentic,
                project_name: projectName
            })
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || `Server returned ${res.status}`);
        }

        const data = await res.json();
        removeTypingIndicator(typingId);

        // Add assistant reply to session
        const agenticData = data.agentic ? {
            steps: data.steps,
            created_files: data.created_files,
            project_name: data.project_name,
            gateway_grounding: data.gateway_grounding
        } : null;

        const assistantMsg = {
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

        appendMessageElement('assistant', data.reply, data.telemetry, true, null, data.rag_sources, data.active_skills, agenticData, model, data.bake_recommendation);

        // Auto-Execute in sandbox if user enabled Auto-Run
        if (window.autoExecuteSandbox) {
            setTimeout(() => {
                const thread = document.getElementById('chatMessagesThread');
                if (thread && thread.lastElementChild) {
                    const runBtn = thread.lastElementChild.querySelector('.code-run-btn');
                    if (runBtn) {
                        console.log("Auto-executing generated code block in sandbox...");
                        runBtn.click();
                    }
                }
            }, 150);
        }

        const telSpan = document.getElementById('chatLastTelemetry');
        if (telSpan && data.telemetry) {
            telSpan.textContent = `${data.telemetry.tokens_per_second} tok/s (${data.telemetry.eval_tokens} tokens in ${data.telemetry.eval_duration_sec}s)`;
        }

        // Check for Compute Boundary Reached or Pause checkpoint
        if (data.status === 'boundary_reached' || (data.reply && data.reply.includes('[COMPUTE_BOUNDARY_REACHED:'))) {
            if (window.openComputeBoundaryModal) window.openComputeBoundaryModal(data.boundary_data);
        }
    } catch (err) {
        removeTypingIndicator(typingId);
        appendMessageElement('assistant', `**Local Engine Error:** ${err.message}\n\nPlease verify that Ollama is online.`);
    } finally {
        window.isChatGenerating = false;
        window.activeGeneratingProject = null;
        const sendBtn = document.getElementById('btnSendChat');
        const execControls = document.getElementById('activeExecutionControls');
        if (execControls) execControls.style.display = 'none';
        if (sendBtn) {
            sendBtn.style.display = 'inline-flex';
            sendBtn.disabled = false;
            sendBtn.innerHTML = '<span>Send</span> <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-left:4px;"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>';
        }
    }
};

function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
window.escapeHtml = escapeHtml;

function appendMessageElement(role, content, telemetry = null, autoScroll = true, images = null, ragSources = null, activeSkills = null, agenticData = null, modelUsed = null, bakeRec = null) {
    const thread = document.getElementById('chatMessagesThread');
    if (!thread) return;

    const msgDiv = document.createElement('div');
    msgDiv.style.display = 'flex';
    msgDiv.style.gap = '14px';
    msgDiv.style.marginBottom = '6px';

    const isUser = role === 'user';
    msgDiv.style.flexDirection = isUser ? 'row-reverse' : 'row';

    const avatar = document.createElement('div');
    avatar.style.width = '34px';
    avatar.style.height = '34px';
    avatar.style.borderRadius = '8px';
    avatar.style.display = 'flex';
    avatar.style.alignItems = 'center';
    avatar.style.justifyContent = 'center';
    avatar.style.flexShrink = '0';
    avatar.style.background = isUser ? 'var(--accent)' : 'var(--bg-surface-elevated)';
    avatar.style.border = isUser ? 'none' : '1px solid var(--border-medium)';
    avatar.style.color = isUser ? '#ffffff' : 'var(--text-secondary)';
    avatar.innerHTML = isUser
        ? `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`
        : `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 9h.01"/><path d="M15 9h.01"/><path d="M9 15h6"/></svg>`;

    const bubble = document.createElement('div');
    bubble.style.maxWidth = '80%';
    bubble.style.padding = '14px 18px';
    bubble.style.borderRadius = isUser ? '16px 16px 2px 16px' : '16px 16px 16px 2px';
    bubble.style.background = isUser ? 'var(--chat-bubble-user)' : 'var(--chat-bubble-bot)';
    bubble.style.border = isUser ? '1px solid var(--chat-bubble-user-border)' : '1px solid var(--chat-bubble-bot-border)';
    bubble.style.color = isUser ? 'var(--chat-bubble-user-text)' : 'var(--chat-bubble-bot-text)';
    bubble.style.lineHeight = '1.6';
    bubble.style.fontSize = '0.92rem';
    bubble.style.whiteSpace = 'pre-wrap';
    bubble.style.wordBreak = 'break-word';

    // Render subtle Model Identity Tag if provided
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
    if (images && images.length > 0) {
        const imgGallery = document.createElement('div');
        imgGallery.style.display = 'flex';
        imgGallery.style.flexWrap = 'wrap';
        imgGallery.style.gap = '8px';
        imgGallery.style.marginBottom = '10px';
        images.forEach(b64 => {
            if (!b64) return;
            const img = document.createElement('img');
            let src = b64;
            if (!src.startsWith('data:')) {
                const mime = src.startsWith('/9j/') ? 'image/jpeg' : (src.startsWith('R0lGOD') ? 'image/gif' : 'image/png');
                src = `data:${mime};base64,${b64}`;
            }
            img.src = src;
            img.style.maxHeight = '220px';
            img.style.maxWidth = '100%';
            img.style.borderRadius = '8px';
            img.style.border = '1px solid var(--border-medium)';
            img.style.cursor = 'pointer';
            img.title = 'Click to open full size';
            img.onclick = () => window.open(img.src, '_blank');
            imgGallery.appendChild(img);
        });
        bubble.appendChild(imgGallery);
    }

    // Render RAG grounded sources banner if available
    if (!isUser && ragSources && ragSources.length > 0) {
        const ragBanner = document.createElement('div');
        ragBanner.className = 'rag-sources-banner';
        let chipsHtml = `<span style="color:var(--text-muted);font-weight:600;display:inline-flex;align-items:center;gap:4px;">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
            Grounded via Cyber RAG:
        </span>`;

        ragSources.forEach(s => {
            let catClass = '';
            const cat = (s.category || '').toLowerCase();
            if (cat.includes('cve')) catClass = 'cve';
            else if (cat.includes('mitre') || cat.includes('attack')) catClass = 'mitre';
            else if (cat.includes('owasp') || cat.includes('cwe')) catClass = 'owasp';

            const scorePct = s.score ? Math.round(s.score * 100) : 100;
            const badgeLabel = s.external_id || (s.category ? s.category.toUpperCase() : 'INTEL');
            chipsHtml += `<span class="rag-source-chip ${catClass}" title="${s.title || ''} • Severity: ${s.severity || 'MEDIUM'}">
                <span>${badgeLabel}</span>
                <span style="opacity:0.8;font-size:0.62rem;">${scorePct}% match</span>
            </span>`;
        });
        ragBanner.innerHTML = chipsHtml;
        bubble.appendChild(ragBanner);
    }

    // Render Active Skills Banner if model used attached skills
    if (!isUser && activeSkills && activeSkills.length > 0) {
        const skillsBanner = document.createElement('div');
        skillsBanner.style.display = 'flex';
        skillsBanner.style.alignItems = 'center';
        skillsBanner.style.gap = '6px';
        skillsBanner.style.flexWrap = 'wrap';
        skillsBanner.style.marginBottom = '8px';
        skillsBanner.style.padding = '4px 10px';
        skillsBanner.style.background = 'rgba(59, 130, 246, 0.08)';
        skillsBanner.style.border = '1px solid rgba(59, 130, 246, 0.22)';
        skillsBanner.style.borderRadius = '6px';
        skillsBanner.style.fontSize = '0.72rem';

        let sHtml = `<span style="color:#60a5fa; font-weight:600; display:inline-flex; align-items:center; gap:4px;">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m8 3 4 8 5-5 5 15H2L8 3z"/></svg>
            Active Skills:
        </span>`;

        activeSkills.forEach(sn => {
            sHtml += `<span style="background:rgba(59,130,246,0.18); color:#93c5fd; padding:1px 6px; border-radius:4px; font-weight:600; font-size:0.68rem; border:1px solid rgba(59,130,246,0.3);">${sn}</span>`;
        });
        skillsBanner.innerHTML = sHtml;
        bubble.appendChild(skillsBanner);
    }

    // Render Bake Recommendation Card if multiple skills cause cognitive overload / efficiency drop
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

    // Detect Human-In-The-Loop Installation Proposal
    let cleanText = content;
    const installMatch = content.match(/\[INSTALL_PROPOSAL:([a-zA-Z0-9_\-]+):([a-zA-Z0-9_\-\.\:\@\/]+):([^\]]+)\]/);

    const textSpan = document.createElement('div');
    if (installMatch) {
        cleanText = content.replace(installMatch[0], '').trim();
        const pType = installMatch[1];
        const pName = installMatch[2];
        const pReason = installMatch[3];

        const installCard = document.createElement('div');
        installCard.style.margin = '10px 0';
        installCard.style.padding = '12px 14px';
        installCard.style.background = 'var(--bg-surface-elevated)';
        installCard.style.border = '1px solid var(--border-medium)';
        installCard.style.borderRadius = '8px';
        installCard.style.display = 'flex';
        installCard.style.flexDirection = 'column';
        installCard.style.gap = '8px';

        installCard.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 0.78rem; font-weight: 600; color: var(--text-primary); display: inline-flex; align-items: center; gap: 6px;">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>
                    Permission Request: Dependency Required
                </span>
                <span style="font-size: 0.68rem; font-family: var(--font-mono); color: var(--text-muted); background: var(--bg-base); padding: 1px 6px; border-radius: 4px; border: 1px solid var(--border-subtle);">${pType.toUpperCase()}</span>
            </div>
            <div style="font-size: 0.78rem; color: var(--text-secondary); line-height: 1.45;">
                The agent requires <strong style="color: var(--text-primary); font-family: var(--font-mono);">${escapeHtml(pName)}</strong> to continue: <em>${escapeHtml(pReason)}</em>
            </div>
            <div style="display: flex; gap: 8px; align-items: center; margin-top: 4px;">
                <button type="button" onclick="executeAgentInstall(this, '${pType}', '${pName}')" class="btn-quiet" style="font-size: 0.75rem; padding: 5px 14px; font-weight: 600; cursor: pointer; background: var(--bg-surface); border: 1px solid var(--border-strong); color: var(--text-primary); border-radius: 6px;">
                    ✓ Approve & Install (${pName})
                </button>
            </div>
        `;
        bubble.appendChild(installCard);
    }

    // Detect Agentic Mode Required Proposal (When tool is requested but Agentic is OFF)
    const agenticProposalMatch = cleanText.match(/\[AGENTIC_MODE_PROPOSAL:([^\]]+)\]/);
    if (agenticProposalMatch) {
        cleanText = cleanText.replace(agenticProposalMatch[0], '').trim();
        const aReason = agenticProposalMatch[1];

        const propCard = document.createElement('div');
        propCard.style.margin = '12px 0';
        propCard.style.padding = '14px 16px';
        propCard.style.background = 'var(--bg-surface)';
        propCard.style.border = '1px solid var(--border-medium)';
        propCard.style.borderRadius = '8px';
        propCard.style.display = 'flex';
        propCard.style.flexDirection = 'column';
        propCard.style.gap = '10px';

        propCard.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-subtle); padding-bottom: 8px;">
                <span style="font-size: 0.8rem; font-weight: 600; color: var(--text-primary); display: inline-flex; align-items: center; gap: 6px;">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                    Tool Execution Requested (Agentic Mode is OFF)
                </span>
                <span style="font-size: 0.68rem; font-family: var(--font-mono); color: var(--text-muted); background: var(--bg-surface-elevated); padding: 2px 7px; border-radius: 4px; border: 1px solid var(--border-subtle);">Action Required</span>
            </div>
            <div style="font-size: 0.76rem; color: var(--text-secondary); line-height: 1.45;">
                ${escapeHtml(aReason)} To write files on disk and launch the <strong>Live Preview</strong>, turn on Agentic Mode.
            </div>
            <div style="display: flex; gap: 8px; align-items: center; margin-top: 4px;">
                <button type="button" onclick="confirmEnableAgenticAndRetry(this)" class="btn-quiet" style="font-size: 0.74rem; padding: 6px 14px; font-weight: 600; cursor: pointer; background: var(--bg-surface-elevated); border: 1px solid var(--border-strong); color: var(--text-primary); border-radius: 6px; display: inline-flex; align-items: center; gap: 5px;">
                    <span>⚡ Turn ON & Continue</span>
                </button>
                <button type="button" onclick="dismissAgenticProposal(this)" class="btn-quiet" style="font-size: 0.74rem; padding: 6px 12px; cursor: pointer; border: 1px solid var(--border-subtle); color: var(--text-muted); border-radius: 6px;">
                    Skip (Keep OFF)
                </button>
            </div>
        `;
        bubble.appendChild(propCard);
    }

    // Detect Autonomous Knowledge Acquisition Proposal
    const knowledgeMatch = cleanText.match(/\[KNOWLEDGE_ACQUIRE_PROPOSAL:([^:]+):([^:]+):([^:]+):([^\]]+)\]/);
    if (knowledgeMatch) {
        cleanText = cleanText.replace(knowledgeMatch[0], '').trim();
        const kDomain = knowledgeMatch[1];
        const kDbName = knowledgeMatch[2];
        const kDesc = knowledgeMatch[3];
        const kUrl = knowledgeMatch[4];

        const kCard = document.createElement('div');
        kCard.style.margin = '12px 0';
        kCard.style.padding = '14px 16px';
        kCard.style.background = 'var(--bg-surface)';
        kCard.style.border = '1px solid var(--border-subtle)';
        kCard.style.borderRadius = '8px';
        kCard.style.display = 'flex';
        kCard.style.flexDirection = 'column';
        kCard.style.gap = '10px';
        kCard.style.color = 'var(--text-primary)';

        kCard.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-subtle); padding-bottom: 8px;">
                <div style="display: flex; align-items: center; gap: 8px; font-size: 0.82rem; font-weight: 600; color: var(--text-secondary);">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
                    <span>Knowledge Gap: ${escapeHtml(kDomain.toUpperCase())}</span>
                </div>
                <span style="font-size: 0.68rem; font-family: var(--font-mono); color: var(--text-muted); background: var(--bg-surface-elevated); padding: 2px 7px; border-radius: 4px; border: 1px solid var(--border-subtle);">Ungrounded Domain</span>
            </div>
            <div style="font-size: 0.77rem; color: var(--text-secondary); line-height: 1.45;">
                The model recognizes its base weights lack verified ground truth for this entity. It has identified the premier authoritative database:
            </div>
            <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 10px 12px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                    <strong style="color: var(--text-primary); font-size: 0.82rem;">${escapeHtml(kDbName)}</strong>
                    <a href="${escapeHtml(kUrl)}" target="_blank" style="color: var(--text-secondary); font-size: 0.7rem; text-decoration: underline;">Official Source ↗</a>
                </div>
                <div style="font-size: 0.73rem; color: var(--text-muted); line-height: 1.4;">
                    ${escapeHtml(kDesc)}
                </div>
            </div>
            <div style="display: flex; gap: 8px; align-items: center; margin-top: 4px;">
                <button type="button" onclick="executeKnowledgeAcquire(this, '${escapeHtml(kDomain)}', '${escapeHtml(kDbName)}')" class="btn-quiet" style="font-size: 0.76rem; padding: 6px 16px; font-weight: 600; cursor: pointer; background: var(--bg-surface-elevated); border: 1px solid var(--border-medium); color: var(--text-primary); border-radius: 6px; display: inline-flex; align-items: center; gap: 6px;">
                    <span>⚡ Download & Setup into Model (1-Click)</span>
                </button>
            </div>
        `;
        bubble.appendChild(kCard);
    }

    // 1. Output Text FIRST (clean, uncluttered presentation)
    textSpan.innerHTML = formatMarkdown(cleanText);
    bubble.appendChild(textSpan);

    // 2. Render Created Project Files Artifact Card directly beneath message
    if (!isUser && agenticData && agenticData.project_name) {
        let files = (agenticData.created_files && agenticData.created_files.length > 0) ? agenticData.created_files : ['index.html', 'styles.css', 'app.js'];
        const projCard = document.createElement('div');
        projCard.style.marginTop = '12px';
        projCard.style.padding = '12px 14px';
        projCard.style.background = 'var(--bg-surface)';
        projCard.style.border = '1px solid var(--border-subtle)';
        projCard.style.borderRadius = '8px';

        const hasHtml = files.some(f => f.toLowerCase().endsWith('.html'));
        const chips = files.map(f => {
            return `<button type="button" onclick="openAgentProjectModal('${agenticData.project_name}', '${f}', 'code')" class="btn-quiet" style="font-size:0.72rem;font-family:var(--font-mono);color:var(--text-muted);border-color:var(--border-subtle);background:var(--bg-surface-elevated);padding:2px 8px;display:inline-flex;align-items:center;gap:4px;border-radius:4px;">
                <span>📄 ${f}</span>
            </button>`;
        }).join(' ');

        projCard.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;flex-wrap:wrap;gap:8px;">
                <span style="font-size:0.78rem;font-weight:600;color:var(--text-primary);display:inline-flex;align-items:center;gap:6px;">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                    Workspace (${files.length} Files):
                </span>
                <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
                    ${hasHtml ? `
                        <button type="button" onclick="openAgentProjectModal('${agenticData.project_name}', null, 'preview')" class="btn-quiet" style="font-size:0.73rem;padding:3px 11px;color:var(--text-primary);border:1px solid var(--border-strong);background:var(--bg-surface-elevated);display:inline-flex;align-items:center;gap:4px;font-weight:600;border-radius:4px;" title="Live Interactive Browser Preview">
                            <span>🖥️ Live Preview</span>
                        </button>
                    ` : ''}
                    <button type="button" onclick="openProjectInVSCode('${agenticData.project_name}')" class="btn-quiet" style="font-size:0.73rem;padding:3px 10px;color:var(--text-secondary);border:1px solid var(--border-subtle);background:transparent;display:inline-flex;align-items:center;gap:4px;border-radius:4px;" title="Open workspace folder in VS Code">
                        <span>💙 VS Code</span>
                    </button>
                    <button type="button" onclick="openAgentProjectModal('${agenticData.project_name}', null, 'code')" class="btn-quiet" style="font-size:0.73rem;padding:3px 9px;color:var(--text-muted);border:1px solid var(--border-subtle);background:transparent;border-radius:4px;" title="View file tree and code">
                        <span>Code ↗</span>
                    </button>
                </div>
            </div>
            <div style="display:flex;flex-wrap:wrap;gap:6px;">${chips}</div>
        `;
        bubble.appendChild(projCard);
    }

    // 3. Render Antigravity ReAct Steps Trace as sleek, collapsed developer accordion at bottom
    if (!isUser && agenticData && agenticData.steps && agenticData.steps.length > 0) {
        const reactBox = document.createElement('details');
        reactBox.style.marginTop = '10px';
        reactBox.style.background = 'var(--bg-surface)';
        reactBox.style.border = '1px solid var(--border-subtle)';
        reactBox.style.borderRadius = '6px';
        reactBox.style.padding = '6px 12px';
        reactBox.open = false; // Collapsed by default so conversation remains clean and uncluttered!

        const summary = document.createElement('summary');
        summary.style.cursor = 'pointer';
        summary.style.fontSize = '0.74rem';
        summary.style.fontWeight = '500';
        summary.style.color = 'var(--text-secondary)';
        summary.style.display = 'flex';
        summary.style.alignItems = 'center';
        summary.style.justifyContent = 'space-between';
        summary.style.userSelect = 'none';
        summary.innerHTML = `
            <span style="display:inline-flex;align-items:center;gap:6px;">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                ReAct Execution Trace (${agenticData.steps.length} Step${agenticData.steps.length === 1 ? '' : 's'})
            </span>
            <span style="font-size:0.66rem;color:var(--text-muted);font-family:var(--font-mono);">Workspace: ${agenticData.project_name || 'default'}</span>
        `;
        reactBox.appendChild(summary);

        if (agenticData.gateway_grounding && agenticData.gateway_grounding.matched) {
            const gw = agenticData.gateway_grounding;
            const gwBadge = document.createElement('div');
            gwBadge.style.marginTop = '8px';
            gwBadge.style.marginBottom = '6px';
            gwBadge.style.padding = '6px 10px';
            gwBadge.style.borderRadius = '5px';
            gwBadge.style.background = 'var(--bg-surface-elevated)';
            gwBadge.style.border = '1px solid var(--border-subtle)';
            gwBadge.style.fontSize = '0.72rem';
            gwBadge.style.color = 'var(--text-secondary)';
            gwBadge.style.display = 'flex';
            gwBadge.style.alignItems = 'center';
            gwBadge.style.justifyContent = 'space-between';
            gwBadge.innerHTML = `
                <span style="display:inline-flex;align-items:center;gap:6px;">
                    <span>⚡ <strong>Gateway Grounded:</strong> <em>${escapeHtml(gw.dataset_name)}</em></span>
                </span>
                <span style="font-family:var(--font-mono);font-size:0.66rem;color:var(--text-muted);">${gw.latency_ms || 0.5}ms · Zero Fine-Tuning</span>
            `;
            reactBox.appendChild(gwBadge);
        }

        const stepsList = document.createElement('div');
        stepsList.style.marginTop = '8px';
        stepsList.style.display = 'flex';
        stepsList.style.flexDirection = 'column';
        stepsList.style.gap = '6px';

        agenticData.steps.forEach(st => {
            const stepItem = document.createElement('div');
            stepItem.style.background = 'var(--bg-base)';
            stepItem.style.border = '1px solid var(--border-subtle)';
            stepItem.style.borderRadius = '5px';
            stepItem.style.padding = '7px 9px';
            stepItem.style.fontSize = '0.74rem';

            let actionHtml = '';
            if (st.action) {
                const argsSnippet = st.args ? JSON.stringify(st.args).substring(0, 80) : '';
                actionHtml = `
                    <div style="margin-top: 4px; display: flex; align-items: center; gap: 6px; font-family: var(--font-mono);">
                        <span style="color: var(--text-muted); font-weight: 500;">⚡ Action:</span>
                        <code style="background: var(--bg-surface-elevated); padding: 1px 5px; border-radius: 4px; color: var(--text-primary); border: 1px solid var(--border-subtle);">${st.action}</code>
                        <span style="color: var(--text-muted); font-size: 0.67rem;">${argsSnippet}</span>
                    </div>
                `;
            }

            let obsHtml = '';
            if (st.action === 'run_terminal_command' && typeof st.observation === 'object') {
                const termObs = st.observation;
                const modeLabel = termObs.mode === 'docker_isolated_container' ? '🐳 Docker (--network none)' : '🛡️ Safe Sandbox';
                const outputContent = (termObs.stdout || termObs.stderr || termObs.error || '(no output)').trim();
                obsHtml = `
                    <div style="margin-top: 6px; background: var(--bg-base); border: 1px solid var(--border-subtle); border-radius: 5px; overflow: hidden; font-family: var(--font-mono); font-size: 0.71rem;">
                        <div style="background: var(--bg-surface-elevated); padding: 4px 8px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-subtle); color: var(--text-muted); font-size: 0.67rem;">
                            <span>>_ Terminal Output [${escapeHtml(modeLabel)}]</span>
                            <span style="color: ${termObs.exit_code === 0 ? 'var(--text-secondary)' : '#f87171'};">Exit: ${termObs.exit_code ?? 0}</span>
                        </div>
                        <pre style="margin: 0; padding: 7px; max-height: 120px; overflow-y: auto; color: var(--text-primary); white-space: pre-wrap; line-height: 1.4;">${escapeHtml(outputContent)}</pre>
                    </div>
                `;
            } else if (st.observation) {
                const obsText = typeof st.observation === 'object' ? JSON.stringify(st.observation) : String(st.observation);
                obsHtml = `
                    <div style="margin-top: 4px; color: var(--text-muted); font-family: var(--font-mono); font-size: 0.69rem; background: var(--bg-surface-elevated); padding: 3px 6px; border-radius: 4px; border: 1px solid var(--border-subtle); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                        ✓ Observation: ${escapeHtml(obsText.substring(0, 140))}
                    </div>
                `;
            }

            stepItem.innerHTML = `
                <div style="color: var(--text-secondary); line-height: 1.4;">
                    <strong style="color: var(--text-primary);">Step ${st.step}:</strong> ${escapeHtml(st.thought || 'Executing step...')}
                </div>
                ${actionHtml}
                ${obsHtml}
            `;
            stepsList.appendChild(stepItem);
        });

        reactBox.appendChild(stepsList);
        bubble.appendChild(reactBox);
    }

    if (!isUser && telemetry && telemetry.tokens_per_second) {
        const telBadge = document.createElement('div');
        telBadge.style.marginTop = '10px';
        telBadge.style.fontSize = '0.72rem';
        telBadge.style.color = 'var(--accent-text)';
        telBadge.style.display = 'inline-flex';
        telBadge.style.alignItems = 'center';
        telBadge.style.gap = '6px';
        telBadge.style.padding = '3px 8px';
        telBadge.style.borderRadius = '10px';
        telBadge.style.background = 'var(--accent-subtle)';
        telBadge.style.border = '1px solid var(--border-subtle)';
        telBadge.innerHTML = `<span>${telemetry.tokens_per_second} tok/s</span> • <span>${telemetry.eval_tokens} tokens</span> • <span>${telemetry.eval_duration_sec}s</span>`;
        bubble.appendChild(telBadge);
    }

    msgDiv.appendChild(avatar);
    msgDiv.appendChild(bubble);
    thread.appendChild(msgDiv);

    if (autoScroll) {
        thread.scrollTop = thread.scrollHeight;
    }
}

function highlightCodeSyntax(code) {
    if (!code) return '';
    // Single regex token matching in a single pass ensures injected HTML span tags are NEVER re-matched or corrupted.
    const tokenRegex = /(\/\/[^\n]*|#[^\n]*)|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`)|(\b(?:def|class|return|import|from|as|if|elif|else|for|while|try|except|finally|with|async|await|lambda|yield|const|let|var|function|new|switch|case|break|continue|default|throw|catch|public|private|protected|static|void|int|float|double|bool|string|null|undefined|None|True|False)\b)|(\b\d+(?:\.\d+)?\b)|(\b[a-zA-Z_]\w*(?=\s*\())/g;
    return code.replace(tokenRegex, (match, comment, str, kwd, num, fn) => {
        if (comment) return `<span class="syn-com">${comment}</span>`;
        if (str) return `<span class="syn-str">${str}</span>`;
        if (kwd) return `<span class="syn-kwd">${kwd}</span>`;
        if (num) return `<span class="syn-num">${num}</span>`;
        if (fn) return `<span class="syn-fn">${fn}</span>`;
        return match;
    });
}

function formatMarkdown(text) {
    if (!text) return '';
    let escaped = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    
    // Code blocks with syntax copy button and 1-Click Sandbox Execution
    escaped = escaped.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, function(match, lang, code) {
        const safeLang = (lang || 'code').toLowerCase();
        const rawCode = code.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
        const b64 = btoa(unescape(encodeURIComponent(rawCode)));
        const highlighted = highlightCodeSyntax(code);
        const blockId = 'code_' + Math.random().toString(36).substring(2, 9);
        const canRunInSandbox = ['python', 'py', 'javascript', 'js', 'node', 'batch', 'bat', 'cmd', 'powershell', 'ps1', 'sh', 'bash'].includes(safeLang) || safeLang === 'code';

        const runButtonHtml = canRunInSandbox ? `
            <button type="button" class="code-run-btn" title="Execute in secure isolated sandbox" onclick="runSandboxFromCode('${blockId}', '${b64}', '${safeLang}', this)">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                <span>Run in Sandbox</span>
            </button>
        ` : '';

        return `<div class="code-container" id="${blockId}">
            <div class="code-header">
                <span class="code-lang-label">${safeLang}</span>
                <div class="code-actions">
                    ${runButtonHtml}
                    <button type="button" class="code-copy-btn" onclick="copyCodeFromBase64('${b64}', this)">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
                        <span>Copy</span>
                    </button>
                </div>
            </div>
            <pre class="code-pre"><code>${highlighted}</code></pre>
            <div id="${blockId}_drawer" class="sandbox-drawer">
                <div class="sandbox-header">
                    <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                        <span id="${blockId}_badge" class="sandbox-badge">SANDBOX</span>
                        <span id="${blockId}_meta" style="color:var(--text-muted);font-size:0.72rem;"></span>
                        <span id="${blockId}_engine" class="sandbox-engine-pill" style="display:none;"></span>
                    </div>
                    <button type="button" onclick="closeSandboxDrawer('${blockId}')" style="background:transparent;border:none;color:var(--text-muted);cursor:pointer;font-size:1rem;line-height:1;" title="Close Output">&times;</button>
                </div>
                <pre id="${blockId}_term" class="sandbox-terminal"></pre>
            </div>
        </div>`;
    });

    escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    escaped = escaped.replace(/`([^`]+)`/g, '<code class="code-inline">$1</code>');

    // Convert markdown links [Label](url) into blue clickable links
    escaped = escaped.replace(/\[([^\]]+)\]\((https?:\/\/[^\s\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="chat-link">$1</a>');

    // Auto-link bare URLs not inside tags
    escaped = escaped.replace(/(^|[^"'=])(https?:\/\/[a-zA-Z0-9_\-\.:\/?#\[\]@!$&*+,;=%]+)/g, function(match, prefix, url) {
        return prefix + '<a href="' + url + '" target="_blank" rel="noopener noreferrer" class="chat-link">' + url + '</a>';
    });

    return escaped;
}

window.runSandboxFromCode = async function(blockId, b64, lang, btn) {
    const drawer = document.getElementById(`${blockId}_drawer`);
    const badge = document.getElementById(`${blockId}_badge`);
    const meta = document.getElementById(`${blockId}_meta`);
    const enginePill = document.getElementById(`${blockId}_engine`);
    const term = document.getElementById(`${blockId}_term`);
    if (!drawer || !term) return;

    let code = "";
    try {
        code = decodeURIComponent(escape(atob(b64)));
    } catch (e) {
        console.error("Base64 decode error", e);
        return;
    }

    // Open drawer and set state to executing
    drawer.style.display = 'block';
    if (badge) {
        badge.className = 'sandbox-badge';
        badge.style.background = 'rgba(56, 189, 248, 0.15)';
        badge.style.color = '#38bdf8';
        badge.style.border = '1px solid rgba(56, 189, 248, 0.3)';
        badge.textContent = 'EXECUTING...';
    }
    if (meta) meta.textContent = 'Sandboxed subprocess initialized...';
    if (enginePill) enginePill.style.display = 'none';
    term.textContent = 'Spawning isolated execution scratchpad with security constraints...\n';

    if (btn) {
        btn.classList.add('running');
        btn.innerHTML = `<span class="status-dot" style="width:6px;height:6px;background:#38bdf8;"></span><span>Running...</span>`;
    }

    try {
        const res = await fetch('/api/chat/sandbox/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                code: code,
                language: lang || 'python',
                timeout_seconds: 5.0
            })
        });

        const data = await res.json();

        // Display active isolation engine
        if (enginePill && data.engine_detail) {
            enginePill.textContent = data.engine_detail;
            enginePill.style.display = 'inline-block';
        }

        // Render result according to sandbox status
        if (data.status === 'success') {
            if (badge) {
                badge.className = 'sandbox-badge success';
                badge.textContent = `EXIT ${data.exit_code}`;
            }
            if (meta) meta.textContent = `${data.execution_time_ms}ms`;

            let output = data.stdout || '[Program executed with returncode 0. No stdout output.]';
            if (data.created_files && data.created_files.length > 0) {
                output += '\n\n-- Created Files in Scratchpad --\n' + data.created_files.map(f => `* ${f.name} (${f.size_bytes} bytes)`).join('\n');
            }
            term.textContent = output;
        } else if (data.status === 'blocked') {
            if (badge) {
                badge.className = 'sandbox-badge blocked';
                badge.textContent = 'BLOCKED BY POLICY';
            }
            if (meta) meta.textContent = `Risk: ${data.risk_level || 'CRITICAL'}`;
            term.innerHTML = `<span class="term-err">${data.stderr || 'Destructive system command intercepted.'}</span>`;
        } else if (data.status === 'timeout') {
            if (badge) {
                badge.className = 'sandbox-badge timeout';
                badge.textContent = 'TIMEOUT';
            }
            if (meta) meta.textContent = `${data.execution_time_ms || 5000}ms (Hard Timeout)`;
            term.innerHTML = `<span class="term-err">${data.stderr}</span>`;
        } else {
            // Error exit
            if (badge) {
                badge.className = 'sandbox-badge error';
                badge.textContent = `EXIT ${data.exit_code !== undefined ? data.exit_code : 1}`;
            }
            if (meta) meta.textContent = `${data.execution_time_ms}ms • Exit code ${data.exit_code}`;
            
            let errOut = "";
            if (data.stdout) errOut += data.stdout + "\n";
            if (data.stderr) errOut += `<span class="term-err">${data.stderr}</span>`;
            term.innerHTML = errOut || '<span class="term-err">Unknown execution failure.</span>';
        }
    } catch (err) {
        if (badge) {
            badge.className = 'sandbox-badge error';
            badge.textContent = 'NETWORK ERROR';
        }
        if (meta) meta.textContent = 'Failed to connect to sandbox backend';
        term.innerHTML = `<span class="term-err">${err.message}</span>`;
    } finally {
        if (btn) {
            btn.classList.remove('running');
            btn.innerHTML = `<svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg><span>Run in Sandbox</span>`;
        }
    }
};

window.closeSandboxDrawer = function(blockId) {
    const drawer = document.getElementById(`${blockId}_drawer`);
    if (drawer) drawer.style.display = 'none';
};

window.copyCodeFromBase64 = function(b64, btn) {
    try {
        const text = decodeURIComponent(escape(atob(b64)));
        navigator.clipboard.writeText(text);
        if (btn) {
            const originalHtml = btn.innerHTML;
            btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg><span style="color:#10b981;font-weight:600;">Copied!</span>`;
            setTimeout(() => { btn.innerHTML = originalHtml; }, 2000);
        }
    } catch (e) {
        console.error("Copy failed", e);
    }
};

function appendTypingIndicator(modelName, projectName) {
    const thread = document.getElementById('chatMessagesThread');
    if (!thread) return null;

    const id = 'typing_' + Date.now();
    const div = document.createElement('div');
    div.id = id;
    div.style.display = 'flex';
    div.style.gap = '14px';
    div.style.marginBottom = '8px';
    div.style.animation = 'fadeIn 0.2s ease';

    const isAgentic = !!projectName;

    if (!isAgentic) {
        div.innerHTML = `
            <div style="width: 34px; height: 34px; border-radius: 8px; display: flex; align-items: center; justify-content: center; background: var(--bg-surface-elevated); border: 1px solid var(--border-medium); color: var(--text-secondary); flex-shrink: 0;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 9h.01"/><path d="M15 9h.01"/><path d="M9 15h6"/></svg>
            </div>
            <div style="padding: 11px 16px; border-radius: 14px 14px 14px 2px; background: var(--chat-bubble-bot); border: 1px solid var(--chat-bubble-bot-border); color: var(--text-secondary); font-size: 0.85rem; display: flex; align-items: center; gap: 8px;">
                <span class="status-dot" style="background: var(--accent); width: 7px; height: 7px;"></span>
                <span><strong>${modelName}</strong> is thinking...</span>
            </div>
        `;
    } else {
        // Antigravity Live Agentic Execution Telemetry Indicator
        div.innerHTML = `
            <div style="width: 34px; height: 34px; border-radius: 8px; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(168, 85, 247, 0.15)); border: 1px solid rgba(129, 140, 248, 0.4); color: #818cf8; flex-shrink: 0;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
            </div>
            <div style="min-width: 280px; max-width: 520px; padding: 10px 14px; border-radius: 12px 12px 12px 2px; background: var(--bg-surface-elevated); border: 1px solid var(--border-medium); box-shadow: 0 4px 14px rgba(0,0,0,0.15); display: flex; flex-direction: column; gap: 6px;">
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
                    <div style="display: flex; align-items: center; gap: 7px;">
                        <span id="${id}_dot" class="status-dot agent-status-pulse" style="background: #3b82f6; width: 8px; height: 8px; border-radius: 50%; box-shadow: 0 0 8px #3b82f6; display: inline-block;"></span>
                        <span id="${id}_phase" style="font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; padding: 2px 6px; border-radius: 4px; background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3);">SCOUTING</span>
                        <span style="font-size: 0.72rem; color: var(--text-muted); font-family: var(--font-mono);">${modelName}</span>
                    </div>
                    <span id="${id}_timer" style="font-size: 0.70rem; color: var(--text-muted); font-family: var(--font-mono);">0.0s</span>
                </div>
                <div style="display: flex; flex-direction: column; gap: 2px;">
                    <div id="${id}_headline" style="font-size: 0.82rem; font-weight: 600; color: var(--text-primary); display: flex; align-items: center; gap: 6px;">
                        <span>Scouting project architecture & requirements...</span>
                    </div>
                    <div id="${id}_detail" style="font-size: 0.73rem; color: var(--text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                        Pre-flight prompt analysis & dataset discovery
                    </div>
                </div>
            </div>
        `;

        const pollUrl = `/api/chat/agent/projects/${encodeURIComponent(projectName)}/progress`;
        const startTime = Date.now();

        const intervalId = setInterval(async () => {
            try {
                const pRes = await fetch(pollUrl);
                if (!pRes.ok) return;
                const pData = await pRes.json();
                if (!pData || pData.phase === 'idle') return;

                const dotEl = document.getElementById(`${id}_dot`);
                const phaseEl = document.getElementById(`${id}_phase`);
                const timerEl = document.getElementById(`${id}_timer`);
                const headEl = document.getElementById(`${id}_headline`);
                const detailEl = document.getElementById(`${id}_detail`);

                const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
                if (timerEl) timerEl.textContent = `${elapsed}s`;

                if (headEl && pData.headline) {
                    headEl.textContent = pData.headline;
                }
                if (detailEl && (pData.detail || pData.file)) {
                    detailEl.textContent = pData.file ? `Target: ${pData.file} — ${pData.detail || ''}` : pData.detail;
                }

                if (phaseEl && pData.phase) {
                    const phase = pData.phase.toLowerCase();
                    phaseEl.textContent = phase.toUpperCase();

                    let color = '#3b82f6';
                    let bg = 'rgba(59, 130, 246, 0.15)';
                    let border = 'rgba(59, 130, 246, 0.3)';

                    if (phase === 'coding' || phase === 'styling' || phase === 'scripting') {
                        color = '#a855f7';
                        bg = 'rgba(168, 85, 247, 0.15)';
                        border = 'rgba(168, 85, 247, 0.3)';
                    } else if (phase === 'validating') {
                        color = '#eab308';
                        bg = 'rgba(234, 179, 8, 0.15)';
                        border = 'rgba(234, 179, 8, 0.3)';
                    } else if (phase === 'self_repairing') {
                        color = '#f97316';
                        bg = 'rgba(249, 115, 22, 0.15)';
                        border = 'rgba(249, 115, 22, 0.3)';
                    } else if (phase === 'completed') {
                        color = '#10b981';
                        bg = 'rgba(16, 185, 129, 0.15)';
                        border = 'rgba(16, 185, 129, 0.3)';
                    }

                    phaseEl.style.color = color;
                    phaseEl.style.background = bg;
                    phaseEl.style.borderColor = border;
                    if (dotEl) {
                        dotEl.style.background = color;
                        dotEl.style.boxShadow = `0 0 8px ${color}`;
                    }
                }
            } catch (e) {
                // Ignore transient network hiccups during polling
            }
        }, 400);

        div._pollInterval = intervalId;
    }

    thread.appendChild(div);
    thread.scrollTop = thread.scrollHeight;
    return id;
}

function removeTypingIndicator(id) {
    if (!id) return;
    const el = document.getElementById(id);
    if (el) {
        if (el._pollInterval) {
            clearInterval(el._pollInterval);
        }
        el.remove();
    }
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

// ========================================================
// CYBERSECURITY KNOWLEDGE BASE VAULT MODAL (TRACK 1 RAG)
// ========================================================

window.openKnowledgeBaseModal = async function() {
    const modal = document.getElementById('knowledgeBaseModal');
    if (!modal) return;
    modal.style.display = 'flex';

    // Sync model filter & model scope options with available models
    const filterSel = document.getElementById('kbModelFilterSelect');
    const newScopeSel = document.getElementById('kbNewModelScope');
    const curChatModel = document.getElementById('chatModelSelect')?.value || '';

    if (filterSel) {
        filterSel.innerHTML = '<option value="all">All Models (Combined Vault)</option>';
        if (window.chatModels && window.chatModels.length > 0) {
            window.chatModels.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m.name;
                opt.textContent = m.name + ' (Exclusive + Global)';
                if (curChatModel && m.name === curChatModel) {
                    opt.selected = true;
                }
                filterSel.appendChild(opt);
            });
        }
    }

    if (newScopeSel) {
        newScopeSel.innerHTML = '<option value="global">Assign: Global (All Models)</option>';
        if (window.chatModels && window.chatModels.length > 0) {
            window.chatModels.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m.name;
                opt.textContent = 'Assign to ' + m.name;
                if (curChatModel && m.name === curChatModel) {
                    opt.selected = true;
                }
                newScopeSel.appendChild(opt);
            });
        }
    }

    // Fetch live status
    try {
        const res = await fetch('/api/chat/rag/status');
        if (res.ok) {
            const data = await res.json();
            const label = document.getElementById('kbEmbeddingModelLabel');
            if (label && data.embedding_model) {
                label.textContent = `${data.embedding_model} • ${data.total_documents} Indexed Records`;
            }
        }
    } catch (e) {
        console.warn("Could not fetch RAG status:", e);
    }

    // Load initial documents
    window.searchKnowledgeBase('');
};

window.closeKnowledgeBaseModal = function() {
    const modal = document.getElementById('knowledgeBaseModal');
    if (modal) modal.style.display = 'none';
};

window.searchKnowledgeBase = async function(queryOverride = null) {
    const input = document.getElementById('kbSearchInput');
    const query = (queryOverride !== null) ? queryOverride : (input ? input.value.trim() : '');
    const modelScope = document.getElementById('kbModelFilterSelect')?.value || 'all';
    const list = document.getElementById('kbDocumentList');
    const countSummary = document.getElementById('kbDocCountSummary');
    if (!list) return;

    list.innerHTML = `<div style="text-align:center;color:var(--text-muted);font-size:0.8rem;padding:20px;">Searching vector knowledge vault...</div>`;

    try {
        const url = `/api/chat/rag/search?query=${encodeURIComponent(query)}&top_k=35&model_scope=${encodeURIComponent(modelScope)}`;
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const results = data.results || [];
        if (countSummary) {
            countSummary.textContent = `${results.length} record${results.length === 1 ? '' : 's'} available`;
        }
        window.renderKBDocuments(results);
    } catch (err) {
        list.innerHTML = `<div style="text-align:center;color:#f43f5e;font-size:0.8rem;padding:20px;">Error searching vault: ${err.message}</div>`;
    }
};

window.renderKBDocuments = function(docs) {
    const list = document.getElementById('kbDocumentList');
    if (!list) return;

    if (!docs || docs.length === 0) {
        list.innerHTML = `<div style="text-align:center;color:var(--text-muted);font-size:0.8rem;padding:25px;">No matching cybersecurity records found. Try a different search term or ingest a new CVE below.</div>`;
        return;
    }

    list.innerHTML = '';
    docs.forEach(d => {
        const card = document.createElement('div');
        card.className = 'kb-doc-card';

        let catClass = '';
        const cat = (d.category || '').toLowerCase();
        if (cat.includes('cve')) catClass = 'cve';
        else if (cat.includes('mitre') || cat.includes('attack')) catClass = 'mitre';
        else if (cat.includes('owasp') || cat.includes('cwe')) catClass = 'owasp';

        const matchBadge = (d.score && d.score < 1.0)
            ? `<span style="font-size:0.68rem;padding:2px 6px;border-radius:4px;background:var(--accent-subtle);color:var(--accent-text);font-family:var(--font-mono);">${Math.round(d.score * 100)}% match</span>`
            : '';

        let sevColor = '#38bdf8';
        const sev = (d.severity || 'MEDIUM').toUpperCase();
        if (sev === 'CRITICAL') sevColor = '#f43f5e';
        else if (sev === 'HIGH') sevColor = '#f97316';
        else if (sev === 'LOW') sevColor = '#10b981';

        card.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;flex-wrap:wrap;gap:6px;">
                <div style="display:flex;align-items:center;gap:6px;">
                    <span class="rag-source-chip ${catClass}">${d.external_id || d.category.toUpperCase()}</span>
                    <strong style="font-size:0.84rem;color:var(--text-primary);">${d.title}</strong>
                </div>
                <div style="display:flex;align-items:center;gap:6px;">
                    <span style="font-size:0.68rem;font-weight:700;color:${sevColor};border:1px solid ${sevColor}40;padding:1px 6px;border-radius:4px;">${sev}</span>
                    ${matchBadge}
                </div>
            </div>
            <div style="font-size:0.77rem;color:var(--text-secondary);line-height:1.45;margin-bottom:6px;">
                ${d.content}
            </div>
            ${d.mitigation ? `<div style="font-size:0.72rem;color:var(--success);background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.2);padding:4px 8px;border-radius:4px;margin-top:4px;"><strong>Mitigation / Defense:</strong> ${d.mitigation}</div>` : ''}
            ${d.detection ? `<div style="font-size:0.72rem;color:#38bdf8;background:rgba(56,189,248,0.08);border:1px solid rgba(56,189,248,0.2);padding:4px 8px;border-radius:4px;margin-top:4px;"><strong>Detection / Rule:</strong> ${d.detection}</div>` : ''}
        `;
        list.appendChild(card);
    });
};

window.submitCustomKnowledgeDoc = async function() {
    const categoryEl = document.getElementById('kbNewCategory');
    const extIdEl = document.getElementById('kbNewExtId');
    const titleEl = document.getElementById('kbNewTitle');
    const contentEl = document.getElementById('kbNewContent');
    const mitigationEl = document.getElementById('kbNewMitigation');

    const category = categoryEl ? categoryEl.value : 'cve';
    const external_id = extIdEl ? extIdEl.value.trim() : '';
    const title = titleEl ? titleEl.value.trim() : '';
    const content = contentEl ? contentEl.value.trim() : '';
    const mitigation = mitigationEl ? mitigationEl.value.trim() : '';

    if (!title) {
        alert("Please enter a document title.");
        if (titleEl) titleEl.focus();
        return;
    }
    if (!content) {
        alert("Please enter the technical breakdown or vulnerability content.");
        if (contentEl) contentEl.focus();
        return;
    }

    try {
        const payload = {
            category: category,
            title: title,
            content: content,
            external_id: external_id || null,
            severity: 'HIGH',
            mitigation: mitigation || null
        };

        const res = await fetch('/api/chat/rag/ingest', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Ingestion failed');

        alert(`Successfully ingested & vectorized "${data.title}" into local knowledge vault!`);

        // Clear fields
        if (extIdEl) extIdEl.value = '';
        if (titleEl) titleEl.value = '';
        if (contentEl) contentEl.value = '';
        if (mitigationEl) mitigationEl.value = '';

        // Refresh list
        window.searchKnowledgeBase('');
    } catch (err) {
        alert("Failed to ingest document: " + err.message);
    }
};

// ============================================================================
// SYNTHETIC DATASET STUDIO & SANDBOX VERIFICATION CONTROLLER
// ============================================================================
let activeSynthJobId = null;
let synthPollTimer = null;
let cachedSynthTelemetry = null;

window.initSyntheticStudio = async function() {
    console.log("Initializing Synthetic Dataset Studio...");
    await refreshSynthTelemetry();
    await loadSavedDatasetsList();
};

window.refreshSynthTelemetry = async function() {
    try {
        const res = await fetch('/api/llm/synthetic/telemetry');
        const data = await res.json();
        cachedSynthTelemetry = data;

        // 1. Docker Pill & Status
        const dStat = data.docker_status || {};
        const dPill = document.getElementById('synthDockerPill');
        const dDot = document.getElementById('synthDockerDot');
        const dTxt = document.getElementById('synthDockerText');
        const noticeTxt = document.getElementById('synthNoticeText');
        const noticeIcon = document.getElementById('synthNoticeIcon');

        if (dStat.docker_daemon_running) {
            if (dPill) dPill.style.borderColor = 'rgba(16, 185, 129, 0.4)';
            if (dDot) dDot.style.background = '#10b981';
            if (dTxt) dTxt.textContent = dStat.cyber_image_built ? 'Docker: cyber-sandbox Ready' : 'Docker: Online';
            if (noticeIcon) noticeIcon.textContent = '🟢';
            if (noticeTxt) noticeTxt.textContent = 'Ready to generate. Docker air-gapped micro-container online.';
        } else {
            if (dPill) dPill.style.borderColor = 'rgba(244, 63, 94, 0.4)';
            if (dDot) dDot.style.background = '#f43f5e';
            if (dTxt) dTxt.textContent = 'Docker: Offline (RAM Saved)';
            if (noticeIcon) noticeIcon.textContent = '🟡';
            if (noticeTxt) noticeTxt.textContent = 'Docker offline. Will ask permission to start or fallback to Windows Jail.';
        }

        // 2. Populate Models in Dropdowns
        const genSelect = document.getElementById('synthGenModel');
        const refSelect = document.getElementById('synthRefModel');
        const mTxt = document.getElementById('synthModelsText');
        
        let modelOptions = [];
        if (data.gemini_available) {
            modelOptions.push({ id: 'gemini-flash-latest', label: 'Gemini 2.0 Flash (Fast Cloud SOTA)' });
        }
        if (data.ollama_models && data.ollama_models.length > 0) {
            data.ollama_models.forEach(m => {
                modelOptions.push({ id: m.name, label: `${m.name} (Local GPU • ${m.param_size})` });
            });
            if (mTxt) mTxt.textContent = `${data.ollama_models.length} Local Models Ready`;
        } else {
            if (mTxt) mTxt.textContent = data.gemini_available ? 'Gemini Cloud Ready' : 'No Models Found';
        }

        if (genSelect && modelOptions.length > 0) {
            const curVal = genSelect.value;
            genSelect.innerHTML = modelOptions.map(o => `<option value="${o.id}">${o.label}</option>`).join('');
            if (curVal && modelOptions.some(o => o.id === curVal)) genSelect.value = curVal;
        }

        if (refSelect && modelOptions.length > 0) {
            const curVal = refSelect.value;
            refSelect.innerHTML = modelOptions.map(o => `<option value="${o.id}">${o.label}</option>`).join('');
            if (curVal && modelOptions.some(o => o.id === curVal)) refSelect.value = curVal;
        }

    } catch (e) {
        console.error("Failed to refresh synthetic telemetry:", e);
    }
};

window.setSynthPreset = function(presetText) {
    const input = document.getElementById('synthTopicInput');
    if (input) {
        input.value = presetText;
        input.focus();
    }
};

window.checkSynthDockerPermission = function() {
    const isDockerOn = cachedSynthTelemetry?.docker_status?.docker_daemon_running;
    if (!isDockerOn) {
        const modal = document.getElementById('synthDockerPermissionModal');
        if (modal) modal.style.display = 'flex';
    } else {
        alert("Docker Micro-Container is online and ready for air-gapped execution!");
    }
};

window.dismissDockerPermissionModal = function(proceedWithWindowsJail) {
    const modal = document.getElementById('synthDockerPermissionModal');
    if (modal) modal.style.display = 'none';
    if (proceedWithWindowsJail) {
        const chk = document.getElementById('chkSynthRequireDocker');
        if (chk) chk.checked = false;
        executeSyntheticJobSubmission(false);
    }
};

window.confirmStartDockerAndProceed = async function() {
    const modal = document.getElementById('synthDockerPermissionModal');
    if (modal) modal.style.display = 'none';

    const noticeTxt = document.getElementById('synthNoticeText');
    const noticeIcon = document.getElementById('synthNoticeIcon');
    if (noticeIcon) noticeIcon.textContent = '⏳';
    if (noticeTxt) noticeTxt.textContent = 'Starting Docker Desktop in background... (~15s)';

    try {
        await fetch('/api/chat/sandbox/docker/start', { method: 'POST' });
        // Poll for 20s
        for (let i = 0; i < 8; i++) {
            await new Promise(r => setTimeout(r, 2500));
            const check = await fetch('/api/llm/synthetic/telemetry');
            const data = await check.json();
            if (data.docker_status?.docker_daemon_running) {
                cachedSynthTelemetry = data;
                await refreshSynthTelemetry();
                executeSyntheticJobSubmission(true);
                return;
            }
        }
    } catch (e) {
        console.error("Error starting Docker:", e);
    }

    // If still not online, proceed with Windows Jail
    alert("Docker Desktop launch initiated. Proceeding with execution sandbox...");
    executeSyntheticJobSubmission(false);
};

window.triggerStartSynthJob = function() {
    const topic = document.getElementById('synthTopicInput')?.value.trim();
    if (!topic) {
        alert("Please enter a domain or task topic for dataset generation.");
        document.getElementById('synthTopicInput')?.focus();
        return;
    }

    const requireDocker = document.getElementById('chkSynthRequireDocker')?.checked;
    const isDockerOn = cachedSynthTelemetry?.docker_status?.docker_daemon_running;

    // Check if user specifically requested Docker, but it's offline -> Ask Permission!
    if (requireDocker && !isDockerOn) {
        const modal = document.getElementById('synthDockerPermissionModal');
        if (modal) modal.style.display = 'flex';
        return;
    }

    executeSyntheticJobSubmission(requireDocker);
};

async function executeSyntheticJobSubmission(requireDocker) {
    const topic = document.getElementById('synthTopicInput')?.value.trim();
    const targetCount = parseInt(document.getElementById('synthTargetCount')?.value || '10', 10);
    const genModel = document.getElementById('synthGenModel')?.value;
    const refModel = document.getElementById('synthRefModel')?.value;
    const enableCot = document.getElementById('chkSynthEnableCoT')?.checked ?? true;
    const enableEvol = document.getElementById('chkSynthEnableEvol')?.checked ?? true;
    const candCount = parseInt(document.getElementById('synthCandidateCount')?.value || '1', 10);
    const useCouncil = document.getElementById('chkSynthEnableCouncil')?.checked ?? false;

    const payload = {
        topic: topic,
        target_count: targetCount,
        generator_model: genModel,
        refiner_model: refModel,
        require_docker: requireDocker,
        enable_cot: enableCot,
        enable_evol: enableEvol,
        candidates_per_sample: candCount,
        use_council: useCouncil
    };

    // UI state
    document.getElementById('btnStartSynth').style.display = 'none';
    document.getElementById('btnStopSynth').style.display = 'inline-block';
    const monitor = document.getElementById('synthLiveMonitorCard');
    if (monitor) monitor.style.display = 'block';

    try {
        const res = await fetch('/api/llm/synthetic/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        activeSynthJobId = data.job_id;

        // Reset counters
        updateSynthMonitorUI({
            stats: { total_attempts: 0, verified_first_pass: 0, verified_after_repair: 0, docker_used: 0, progress_percent: 0, current_step: 'Starting pipeline...' },
            sample_count: 0,
            target_count: targetCount,
            logs: [{ time: new Date().toLocaleTimeString(), level: 'info', message: 'Pipeline initialized with CoT & Evol-Instruct.' }]
        });

        startSynthPolling(activeSynthJobId);
    } catch (e) {
        alert("Failed to start synthetic generation job: " + e.message);
        document.getElementById('btnStartSynth').style.display = 'inline-flex';
        document.getElementById('btnStopSynth').style.display = 'none';
    }
}

function startSynthPolling(jobId) {
    if (synthPollTimer) clearInterval(synthPollTimer);
    synthPollTimer = setInterval(async () => {
        try {
            const res = await fetch(`/api/llm/synthetic/status/${jobId}`);
            if (!res.ok) return;
            const data = await res.json();
            updateSynthMonitorUI(data);

            if (!data.is_running || data.is_stopped) {
                clearInterval(synthPollTimer);
                document.getElementById('btnStartSynth').style.display = 'inline-flex';
                document.getElementById('btnStopSynth').style.display = 'none';
                await loadSavedDatasetsList();
            }
        } catch (e) {
            console.error("Polling error:", e);
        }
    }, 1500);
}

function updateSynthMonitorUI(data) {
    const stats = data.stats || {};
    const sampleCount = data.sample_count || 0;
    const targetCount = data.target_count || 10;
    const progressPct = stats.progress_percent || 0;

    // Headers & Progress
    const countEl = document.getElementById('synthProgressCount');
    const pctEl = document.getElementById('synthProgressPct');
    const barEl = document.getElementById('synthProgressBar');
    const stepEl = document.getElementById('synthCurrentStepText');

    if (countEl) countEl.textContent = `${sampleCount} / ${targetCount}`;
    if (pctEl) pctEl.textContent = `${progressPct}%`;
    if (barEl) barEl.style.width = `${progressPct}%`;
    if (stepEl) stepEl.textContent = stats.current_step || 'Processing...';

    // Stat Boxes
    const atEl = document.getElementById('statSynthAttempts');
    const fpEl = document.getElementById('statSynthFirstPass');
    const repEl = document.getElementById('statSynthRepaired');
    const docEl = document.getElementById('statSynthDocker');

    if (atEl) atEl.textContent = stats.total_attempts || 0;
    if (fpEl) fpEl.textContent = stats.verified_first_pass || 0;
    if (repEl) repEl.textContent = stats.verified_after_repair || 0;
    if (docEl) docEl.textContent = stats.docker_used || 0;

    // Logs Console
    const logsEl = document.getElementById('synthConsoleLogs');
    if (logsEl && data.logs) {
        logsEl.innerHTML = data.logs.map(l => {
            const col = l.level === 'error' ? '#f43f5e' : (l.level === 'success' ? '#10b981' : (l.level === 'warning' ? '#fbbf24' : '#93c5fd'));
            return `<div style="margin-bottom: 3px;"><span style="color: var(--text-muted);">[${l.time}]</span> <span style="color: ${col}; font-weight: 600;">${l.message}</span></div>`;
        }).join('');
        logsEl.scrollTop = logsEl.scrollHeight;
    }

    // Latest Verified Sample with CoT formatting
    const codeEl = document.getElementById('synthLatestSampleCode');
    const badgeEl = document.getElementById('synthSampleBadge');
    if (data.recent_samples && data.recent_samples.length > 0) {
        const last = data.recent_samples[data.recent_samples.length - 1];
        if (codeEl) {
            if (last.thought) {
                codeEl.textContent = `// 🧠 DeepSeek-R1 CoT Reasoning Trace:\n/*\n${last.thought}\n*/\n\n# 💻 Verified Code Solution:\n${last.output || ''}`;
            } else {
                codeEl.textContent = last.output || '';
            }
        }
        if (badgeEl) badgeEl.textContent = `✔ Verified in ${last.metadata?.engine || 'Sandbox'} (${last.metadata?.execution_time_ms || 0}ms)`;
    }
}

window.stopActiveSynthJob = async function() {
    if (!activeSynthJobId) return;
    try {
        await fetch(`/api/llm/synthetic/stop/${activeSynthJobId}`, { method: 'POST' });
        const stepEl = document.getElementById('synthCurrentStepText');
        if (stepEl) stepEl.textContent = 'Stopping job...';
    } catch (e) {
        console.error("Failed to stop job:", e);
    }
};

window.loadSavedDatasetsList = async function() {
    const tbody = document.getElementById('synthDatasetsTbody');
    if (!tbody) return;

    try {
        const res = await fetch('/api/llm/synthetic/datasets');
        const data = await res.json();
        const datasets = data.datasets || [];

        if (datasets.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 24px;">No synthetic datasets compiled yet. Run your first autonomous synthesis batch above!</td></tr>`;
            return;
        }

        tbody.innerHTML = datasets.map(d => `
            <tr>
                <td style="font-family: monospace; font-size: 0.8rem; font-weight: 600; color: var(--text-primary);">
                    ${d.filename}
                </td>
                <td style="font-weight: 700; color: var(--success); font-size: 0.82rem;">
                    ✔ ${d.sample_count} Samples
                </td>
                <td style="font-size: 0.75rem;">
                    ${d.has_cot ? '<span style="color:#818cf8; font-weight:700; background:rgba(99, 102, 241,0.15); border:1px solid rgba(99, 102, 241,0.3); padding:2px 8px; border-radius:10px;">🧠 CoT Active</span>' : '<span style="color:var(--text-muted);">Standard</span>'}
                </td>
                <td style="color: var(--text-muted); font-size: 0.78rem;">
                    ${d.size_kb} KB
                </td>
                <td style="text-align: center; display: flex; gap: 6px; justify-content: center; align-items: center;">
                    <a href="/api/llm/synthetic/datasets/download/${d.filename}" download class="btn secondary" style="font-size: 0.72rem; padding: 4px 8px; border-radius: 4px; display: inline-flex; align-items: center; gap: 3px; text-decoration: none;">
                        ⬇ Download
                    </a>
                    <button type="button" onclick="exportSynthDatasetToStudio('${d.filename}')" class="btn primary" style="font-size: 0.72rem; padding: 4px 10px; border-radius: 4px; display: inline-flex; align-items: center; gap: 4px; font-weight: 600;">
                        🚀 Train in Studio
                    </button>
                </td>
            </tr>
        `).join('');
    } catch (e) {
        console.error("Failed to load saved datasets:", e);
    }
};

window.exportSynthDatasetToStudio = async function(filename) {
    try {
        const btn = window.event?.currentTarget;
        const origText = btn ? btn.innerHTML : '';
        if (btn) {
            btn.innerHTML = '⏳ Importing...';
            btn.disabled = true;
        }

        const res = await fetch(`/api/llm/synthetic/export/${encodeURIComponent(filename)}`, {
            method: 'POST'
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Export to studio failed");
        }

        const data = await res.json();
        window.llmSessionId = data.session_id;
        window.llmSamples = data.samples || [];

        // Prepopulate LLM Studio Inputs
        const promptInput = document.getElementById("llmPromptInput");
        if (promptInput) {
            promptInput.value = `Synthetic Fine-Tuning: ${data.topic || filename.replace('.jsonl', '')}`;
        }
        const targetInput = document.getElementById("llmTargetCount");
        if (targetInput) {
            targetInput.value = data.sample_count || 10;
        }

        // Show curation & training sections in LLM Studio
        const curSec = document.getElementById("llmCurationSection");
        const trainSec = document.getElementById("llmTrainingConfigSection");
        if (curSec) curSec.style.display = "block";
        if (trainSec) trainSec.style.display = "block";

        if (typeof renderLLMData === 'function') {
            renderLLMData(data.samples, data.stats);
        }

        if (typeof window.updateSituationRecommendations === 'function') {
            await window.updateSituationRecommendations();
        }

        // Switch tab to LLM Studio
        if (typeof window.switchAppTab === 'function') {
            window.switchAppTab('llm-section');
        }

        alert(`🚀 Successfully bridged "${filename}" (${data.sample_count} verified samples) into LLM Fine-Tuning Studio!\n\nYour curated dataset is loaded and hyper-parameters are auto-calibrated.`);
        
        if (btn) {
            btn.innerHTML = origText;
            btn.disabled = false;
        }
    } catch (e) {
        alert("Failed to export dataset to studio: " + e.message);
    }
};

// ==========================================
// DECENTRALIZED AI COUNCIL CHAMBER MODULE
// ==========================================
window.activeCouncilChampionData = null;

window.openCouncilChamberModal = function() {
    const modal = document.getElementById('aiCouncilModal');
    if (!modal) return;
    const synthTopic = document.getElementById('synthTopicInput')?.value.trim();
    const promptArea = document.getElementById('councilTaskPrompt');
    if (promptArea && synthTopic && !promptArea.value.trim()) {
        promptArea.value = synthTopic;
    }
    modal.style.display = 'flex';
};

window.closeCouncilModal = function() {
    const modal = document.getElementById('aiCouncilModal');
    if (modal) modal.style.display = 'none';
};

window.triggerCouncilDeliberation = async function() {
    const prompt = document.getElementById('councilTaskPrompt')?.value.trim();
    if (!prompt) {
        alert("Please enter a task or coding problem for the Council to deliberate.");
        document.getElementById('councilTaskPrompt')?.focus();
        return;
    }

    const requireDocker = document.getElementById('chkCouncilRequireDocker')?.checked ?? true;
    const btn = document.getElementById('btnExecuteCouncil');
    const statusArea = document.getElementById('councilStatusArea');
    const resultsArea = document.getElementById('councilResultsArea');
    const phaseText = document.getElementById('councilCurrentPhaseText');
    const logsList = document.getElementById('councilLogsList');

    function updateCouncilRelayStage(step) {
        for (let i = 1; i <= 5; i++) {
            const node = document.getElementById(`relayStep${i}`);
            const line = document.getElementById(`relayLine${i}`);
            if (node) {
                node.classList.remove('active', 'completed');
                const badge = node.querySelector('.relay-step-badge');
                if (i < step) {
                    node.classList.add('completed');
                    if (badge) badge.textContent = '✓';
                } else if (i === step) {
                    node.classList.add('active');
                    if (badge) badge.textContent = `0${i}`;
                } else {
                    if (badge) badge.textContent = `0${i}`;
                }
            }
            if (line) {
                if (i < step) {
                    line.classList.add('completed');
                } else {
                    line.classList.remove('completed');
                }
            }
        }
    }

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span>Deliberating...</span>';
    }
    if (statusArea) statusArea.style.display = 'block';
    if (resultsArea) resultsArea.style.display = 'none';
    if (logsList) logsList.innerHTML = '';
    if (phaseText) phaseText.textContent = 'Drafting independent solutions in parallel...';
    updateCouncilRelayStage(1);

    const startCouncilTime = performance.now();
    const elapsedInterval = setInterval(() => {
        const el = document.getElementById('councilElapsedTicker');
        if (el) {
            const sec = ((performance.now() - startCouncilTime) / 1000).toFixed(1);
            el.textContent = `${sec}s`;
        }
    }, 100);

    const hudVal = document.getElementById('hudStatusVal');
    if (hudVal) hudVal.textContent = 'Council Deliberating...';

    // Progress updates while waiting for multi-model consensus API
    const stages = [
        { text: 'Drafting independent solutions in parallel...', step: 1 },
        { text: 'Code canonicalization & double-blind anonymization...', step: 2 },
        { text: 'Docker Sandbox Reality Gate execution (--network none)...', step: 3 },
        { text: 'Double-blind cross peer-review matrix scoring...', step: 4 },
        { text: 'Synthesizing Borda count consensus verdict...', step: 5 }
    ];
    let sIdx = 0;
    const progressTimer = setInterval(() => {
        sIdx = (sIdx + 1) % stages.length;
        if (phaseText) phaseText.textContent = stages[sIdx].text;
        updateCouncilRelayStage(stages[sIdx].step);
    }, 4500);

    try {
        const payload = {
            task_prompt: prompt,
            council_models: ["gemini-flash-latest", "dolphin3:latest", "llama3:latest"],
            require_docker: requireDocker
        };

        const res = await fetch('/api/llm/council/deliberate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        clearInterval(progressTimer);

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Council deliberation failed");
        }

        const data = await res.json();
        window.activeCouncilChampionData = data.champion;

        // Populate Champion Card
        const c = data.champion;
        document.getElementById('councilChampTitle').textContent = `👑 ${c.moniker} Crowned Council Champion`;
        document.getElementById('councilChampAuthor').textContent = `Author Model: ${c.author_model} (Unmasked)`;
        document.getElementById('councilChampScore').textContent = `${c.composite_score} / 10`;
        document.getElementById('councilChampLatency').textContent = `✔ ${c.duration_ms}ms in Container`;
        document.getElementById('councilChampPeerScore').textContent = `${c.peer_score} / 10`;
        
        const codeView = document.getElementById('councilChampCodeView');
        if (codeView) {
            if (c.thought) {
                codeView.textContent = `// 🧠 DeepSeek-R1 Style Reasoning Trace:\n/*\n${c.thought}\n*/\n\n# 💻 Verified Code Champion:\n${c.code}`;
            } else {
                codeView.textContent = c.code;
            }
        }

        // Populate Standings Table
        const tbody = document.getElementById('councilStandingsTbody');
        if (tbody && data.standings) {
            tbody.innerHTML = data.standings.map((s, idx) => {
                const isWinner = idx === 0 && s.passed_sandbox;
                const statusBadge = s.passed_sandbox 
                    ? `<span style="color:#10b981; font-weight:700; background:rgba(16, 185, 129,0.15); padding:2px 8px; border-radius:10px;">✔ PASSED (${s.duration_ms}ms)</span>`
                    : `<span style="color:#f43f5e; font-weight:700; background:rgba(244, 63, 94,0.15); padding:2px 8px; border-radius:10px;">✘ VETOED (Crash/Fail)</span>`;
                
                const rankBadge = isWinner 
                    ? `<span style="color:#fbbf24; font-weight:800;">👑 WINNER</span>`
                    : `<span style="color:var(--text-muted);">Rank #${idx + 1}</span>`;

                return `
                    <tr style="${isWinner ? 'background: rgba(16,185,129,0.06); font-weight: 600;' : ''}">
                        <td style="color: #60a5fa; font-weight: 700;">${s.moniker}</td>
                        <td style="font-family: monospace; font-size: 0.78rem;">${s.author_model}</td>
                        <td style="font-size: 0.75rem;">${statusBadge}</td>
                        <td style="font-size: 0.8rem; color: #818cf8; font-weight: 700;">${s.peer_score} / 10</td>
                        <td style="font-size: 0.9rem; color: var(--success); font-weight: 800;">${s.composite_score}</td>
                        <td style="text-align: center;">${rankBadge}</td>
                    </tr>
                `;
            }).join('');
        }

        // Populate Peer Reviews Breakdown
        const reviewsBox = document.getElementById('councilReviewsContainer');
        if (reviewsBox && data.standings) {
            let revHtml = '';
            data.standings.forEach(s => {
                const reviews = s.peer_reviews || [];
                revHtml += `
                    <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 10px; font-size: 0.75rem;">
                        <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
                            <strong style="color:var(--text-primary);">${s.moniker} (${s.author_model})</strong>
                            <span style="color:var(--accent-text);">Composite: ${s.composite_score}/10</span>
                        </div>
                        ${reviews.map(r => `
                            <div style="margin-top: 4px; padding-top: 4px; border-top: 1px dashed var(--border-subtle); color: var(--text-secondary); line-height: 1.3;">
                                <div><span style="color:#60a5fa; font-weight:600;">Peer Reviewer (${r.reviewer_moniker}):</span> Score <strong style="color:#10b981;">${r.overall_score}/10</strong></div>
                                <div style="font-style: italic; color: var(--text-muted); margin-top:2px;">"${r.critique}"</div>
                            </div>
                        `).join('')}
                    </div>
                `;
            });
            reviewsBox.innerHTML = revHtml;
        }

        clearInterval(progressTimer);
        clearInterval(elapsedInterval);
        if (statusArea) statusArea.style.display = 'none';
        if (resultsArea) resultsArea.style.display = 'block';
        if (hudVal) hudVal.textContent = 'Council Verdict Crowned';

    } catch (e) {
        clearInterval(progressTimer);
        clearInterval(elapsedInterval);
        alert("Council Deliberation error: " + e.message);
        if (statusArea) statusArea.style.display = 'none';
        if (hudVal) hudVal.textContent = 'Ready';
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<span>Deliberate →</span>';
        }
    }
};

window.copyCouncilChampCode = function() {
    if (!window.activeCouncilChampionData?.code) return;
    navigator.clipboard.writeText(window.activeCouncilChampionData.code).then(() => {
        alert("Council Champion code copied to clipboard!");
    });
};

window.bridgeCouncilChampToStudio = function() {
    if (!window.activeCouncilChampionData) return;
    const c = window.activeCouncilChampionData;
    const sample = {
        id: `council_${Date.now()}`,
        instruction: document.getElementById('councilTaskPrompt')?.value.trim() || 'Council Verified Task',
        input: '',
        output: c.thought ? `<thought>\n${c.thought}\n</thought>\n\n\`\`\`python\n${c.code}\n\`\`\`` : c.code,
        source: `Council Champion (${c.author_model})`,
        quality_score: 1.0,
        token_count: Math.round((c.code.length + (c.thought?.length || 0)) / 4)
    };

    window.llmSessionId = `council_${Date.now()}`;
    window.llmSamples = [sample];

    const curSec = document.getElementById("llmCurationSection");
    const trainSec = document.getElementById("llmTrainingConfigSection");
    if (curSec) curSec.style.display = "block";
    if (trainSec) trainSec.style.display = "block";

    if (typeof renderLLMData === 'function') {
        renderLLMData([sample], {
            initial_samples: 1,
            retained_samples: 1,
            retention_rate: 100,
            avg_tokens: sample.token_count
        });
    }

    window.closeCouncilModal();
    if (typeof window.switchAppTab === 'function') {
        window.switchAppTab('llm-section');
    }
    alert(`🚀 Council Champion code (${c.author_model}) bridged directly into LLM Fine-Tuning Studio for training!`);
};

/* ========================================================
   COMMAND PALETTE SYSTEM (CTRL+K)
   Zero-Neon Tactile Workstation Controls
   ======================================================== */
const COMMAND_REGISTRY = [
    {
        id: 'nav-train',
        title: 'Train AI (Classical Machine Learning)',
        category: 'Navigation',
        shortcut: 'T',
        action: () => window.switchAppTab('train-section')
    },
    {
        id: 'nav-lab',
        title: 'Model Lab (Surgery, Retraining & Version Lineage)',
        category: 'Navigation',
        shortcut: 'M',
        action: () => window.switchAppTab('lab-section')
    },
    {
        id: 'nav-llm',
        title: 'LLM Fine-Tuning Studio (DoRA, QLoRA & GaLore)',
        category: 'Navigation',
        shortcut: 'L',
        action: () => window.switchAppTab('llm-section')
    },
    {
        id: 'nav-synth',
        title: 'Synthetic Dataset Studio (Generator & Evol-Instruct)',
        category: 'Navigation',
        shortcut: 'S',
        action: () => window.switchAppTab('synth-section')
    },
    {
        id: 'nav-chat',
        title: 'Local Chat Arena (Air-Gapped Offline Ollama)',
        category: 'Navigation',
        shortcut: 'C',
        action: () => window.switchAppTab('chat-section')
    },
    {
        id: 'act-council',
        title: 'Decentralized AI Council Chamber (Multi-Model Consensus)',
        category: 'Laboratories',
        shortcut: '↵',
        action: () => {
            if (typeof window.openCouncilModal === 'function') {
                window.openCouncilModal();
            } else {
                const m = document.getElementById('aiCouncilModal');
                if (m) m.style.display = 'flex';
            }
        }
    },
    {
        id: 'act-docker',
        title: 'Linux Micro-Container Sandbox (Docker Settings)',
        category: 'System',
        shortcut: '',
        action: () => {
            const m = document.getElementById('dockerSetupModal');
            if (m) m.style.display = 'flex';
        }
    },
    {
        id: 'act-cve',
        title: 'Cybersecurity RAG Knowledge Base & CVE Ingestion',
        category: 'Laboratories',
        shortcut: '',
        action: () => {
            const kbSec = document.getElementById('cyberRAGKnowledgeModal');
            if (kbSec) kbSec.style.display = 'flex';
        }
    },
    {
        id: 'act-theme',
        title: 'Toggle Light / Dark Mode',
        category: 'Interface',
        shortcut: '⌘D',
        action: () => {
            if (typeof window.toggleTheme === 'function') window.toggleTheme();
        }
    },
    {
        id: 'act-interpret',
        title: 'Analyze Objective & Synthesize Architecture',
        category: 'Actions',
        shortcut: '↵',
        action: () => {
            window.switchAppTab('train-section');
            if (typeof window.interpret === 'function') window.interpret();
        }
    }
];

let selectedCmdIndex = 0;
let filteredCommands = [...COMMAND_REGISTRY];

window.openCommandPalette = function() {
    const modal = document.getElementById('cmdPaletteModal');
    const input = document.getElementById('cmdPaletteInput');
    if (!modal) return;
    modal.style.display = 'flex';
    if (input) {
        input.value = '';
        input.focus();
    }
    filterCommandPalette('');
};

window.closeCommandPalette = function() {
    const modal = document.getElementById('cmdPaletteModal');
    if (modal) modal.style.display = 'none';
};

window.handleCmdBackdropClick = function(e) {
    if (e.target.id === 'cmdPaletteModal') {
        window.closeCommandPalette();
    }
};

window.filterCommandPalette = function(query) {
    const q = (query || '').toLowerCase().trim();
    if (!q) {
        filteredCommands = [...COMMAND_REGISTRY];
    } else {
        filteredCommands = COMMAND_REGISTRY.filter(cmd => 
            cmd.title.toLowerCase().includes(q) || 
            cmd.category.toLowerCase().includes(q) ||
            cmd.id.toLowerCase().includes(q)
        );
    }
    selectedCmdIndex = 0;
    renderCommandPaletteList();
};

function renderCommandPaletteList() {
    const list = document.getElementById('cmdPaletteResults');
    if (!list) return;

    if (filteredCommands.length === 0) {
        list.innerHTML = `<div style="padding: 16px; text-align: center; color: var(--text-muted); font-size: 0.8rem; font-family: var(--font-mono);">No matching commands found</div>`;
        return;
    }

    list.innerHTML = filteredCommands.map((cmd, idx) => `
        <div class="cmd-palette-item ${idx === selectedCmdIndex ? 'selected' : ''}" onclick="executePaletteCommand(${idx})" onmouseenter="selectPaletteItem(${idx})">
            <div class="cmd-palette-item-left">
                <span class="cmd-palette-item-category">${cmd.category}</span>
                <span style="font-weight: 500;">${cmd.title}</span>
            </div>
            ${cmd.shortcut ? `<kbd class="kbd-badge">${cmd.shortcut}</kbd>` : ''}
        </div>
    `).join('');
}

window.selectPaletteItem = function(idx) {
    selectedCmdIndex = idx;
    const items = document.querySelectorAll('.cmd-palette-item');
    items.forEach((it, i) => {
        if (i === idx) it.classList.add('selected');
        else it.classList.remove('selected');
    });
};

window.executePaletteCommand = function(idx) {
    const cmd = filteredCommands[idx];
    if (cmd && typeof cmd.action === 'function') {
        window.closeCommandPalette();
        cmd.action();
    }
};

window.handleCmdPaletteKey = function(e) {
    if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (filteredCommands.length > 0) {
            selectedCmdIndex = (selectedCmdIndex + 1) % filteredCommands.length;
            renderCommandPaletteList();
        }
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (filteredCommands.length > 0) {
            selectedCmdIndex = (selectedCmdIndex - 1 + filteredCommands.length) % filteredCommands.length;
            renderCommandPaletteList();
        }
    } else if (e.key === 'Enter') {
        e.preventDefault();
        if (filteredCommands[selectedCmdIndex]) {
            executePaletteCommand(selectedCmdIndex);
        }
    } else if (e.key === 'Escape') {
        e.preventDefault();
        window.closeCommandPalette();
    }
};

// Global Hotkey Listener: Ctrl+K or Cmd+K
document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        const modal = document.getElementById('cmdPaletteModal');
        if (modal && modal.style.display !== 'none') {
            window.closeCommandPalette();
        } else {
            window.openCommandPalette();
        }
    } else if (e.key === 'Escape') {
        const modal = document.getElementById('cmdPaletteModal');
        if (modal && modal.style.display !== 'none') {
            window.closeCommandPalette();
        }
    }
});





// ============================================================================
// SKILLS & MCP MARKETPLACE STUDIO CLIENT LOGIC
// ============================================================================

window.currentSkillsData = { installed: [], catalog: [], active_ids: [] };

window.initSkillsStudio = async function() {
    console.log("Initializing Skills Studio...");
    await window.loadSkillsData();
};

window.loadSkillsData = async function() {
    try {
        const res = await fetch('/api/skills/list');
        if (!res.ok) throw new Error("Failed to load skills");
        const data = await res.json();
        window.currentSkillsData = data;

        // Render Installed & Catalog Lists
        window.renderInstalledSkills();
        window.renderCatalogSkills();
        window.updateSkillsHeaderBadges();
    } catch (err) {
        console.error("Error loading skills:", err);
    }
};

window.updateSkillsHeaderBadges = function() {
    const activeCount = window.currentSkillsData.active_ids ? window.currentSkillsData.active_ids.length : 0;
    const installedCount = window.currentSkillsData.installed ? window.currentSkillsData.installed.length : 0;

    const countBadge = document.getElementById('installedSkillsCountBadge');
    if (countBadge) countBadge.textContent = installedCount;

    const summaryLabel = document.getElementById('skillsActiveCountLabel');
    if (summaryLabel) {
        summaryLabel.textContent = installedCount + " Skills Installed and Available";
    }

    if (typeof window.updateSessionSkillsUI === 'function') {
        window.updateSessionSkillsUI();
    }
};

window.renderInstalledSkills = function() {
    const container = document.getElementById('installedSkillsList');
    if (!container) return;

    const installed = window.currentSkillsData.installed || [];
    if (installed.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; color: var(--text-muted); padding: 30px 10px; font-size: 0.82rem;">
                No skills installed yet. Browse the catalog on the right or import one from GitHub.
            </div>
        `;
        return;
    }

    container.innerHTML = installed.map(s => {
        const borderStyle = 'border-color: var(--border-subtle); background: var(--bg-surface-elevated);';
        const statusBadge = `<span style="font-size: 0.68rem; font-weight: 600; color: #10b981; background: rgba(16, 185, 129, 0.1); padding: 2px 7px; border-radius: 4px; border: 1px solid rgba(16, 185, 129, 0.25);">INSTALLED</span>`;

        const toolChips = (s.tools || []).map(t => `<span style="font-size: 0.64rem; font-family: var(--font-mono); color: var(--text-secondary); background: var(--bg-base); padding: 1px 6px; border-radius: 4px; border: 1px solid var(--border-subtle);">${t}</span>`).join(' ');

        return `
            <div style="border: 1px solid transparent; border-radius: var(--radius-md); padding: 14px; transition: all 0.2s ease; ${borderStyle}">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; margin-bottom: 6px;">
                    <div>
                        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                            <strong style="font-size: 0.88rem; color: var(--text-primary);">${s.name}</strong>
                            <span style="font-size: 0.68rem; font-family: var(--font-mono); color: var(--text-muted);">v${s.version || '1.0'}</span>
                            ${statusBadge}
                        </div>
                        <div style="font-size: 0.72rem; color: var(--text-muted); margin-top: 2px;">
                            Author: <strong>${s.author || 'Community'}</strong> ${s.github_url ? `• <a href="${s.github_url}" target="_blank" style="color: #60a5fa; text-decoration: none;">GitHub ↗</a>` : ''}
                        </div>
                    </div>

                    <!-- Manage in Chat button -->
                    <button type="button" onclick="openChatWithSkill('${s.id}')" class="btn-quiet" style="font-size: 0.74rem; padding: 5px 12px; font-weight: 500; white-space: nowrap; color: #60a5fa; border-color: rgba(59, 130, 246, 0.3);">
                        Attach in Chat ↗
                    </button>
                </div>

                <p style="font-size: 0.78rem; color: var(--text-secondary); margin: 0 0 10px 0; line-height: 1.45;">
                    ${s.description}
                </p>

                <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border-subtle); padding-top: 8px;">
                    <div style="display: flex; gap: 4px; flex-wrap: wrap; align-items: center;">
                        <span style="font-size: 0.64rem; text-transform: uppercase; color: var(--text-muted);">Tools:</span>
                        ${toolChips || '<span style="font-size: 0.64rem; color: var(--text-muted);">Prompt persona</span>'}
                    </div>

                    <button type="button" onclick="uninstallSkill('${s.id}')" style="background: transparent; border: none; font-size: 0.7rem; color: var(--danger); cursor: pointer; padding: 0;">
                        Uninstall
                    </button>
                </div>
            </div>
        `;
    }).join('');
};

window.renderCatalogSkills = function(filterQuery = '') {
    const container = document.getElementById('catalogSkillsList');
    if (!container) return;

    let catalog = window.currentSkillsData.catalog || [];
    if (filterQuery.trim()) {
        const q = filterQuery.toLowerCase();
        catalog = catalog.filter(s => s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q) || s.category.toLowerCase().includes(q));
    }

    if (catalog.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; color: var(--text-muted); padding: 30px 10px; font-size: 0.82rem;">
                No skills match '${filterQuery}'. You can import any GitHub repo with the button above.
            </div>
        `;
        return;
    }

    container.innerHTML = catalog.map(s => {
        const toolChips = (s.tools || []).map(t => `<span style="font-size: 0.64rem; font-family: var(--font-mono); color: var(--text-secondary); background: var(--bg-base); padding: 1px 6px; border-radius: 4px; border: 1px solid var(--border-subtle);">${t}</span>`).join(' ');

        return `
            <div style="border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 14px; background: var(--bg-surface-elevated);">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; margin-bottom: 6px;">
                    <div>
                        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                            <strong style="font-size: 0.88rem; color: var(--text-primary);">${s.name}</strong>
                            <span style="font-size: 0.68rem; font-family: var(--font-mono); color: var(--text-muted);">v${s.version || '1.0'}</span>
                            <span style="font-size: 0.64rem; text-transform: uppercase; color: var(--text-muted); background: var(--bg-surface); padding: 1px 5px; border-radius: 3px; border: 1px solid var(--border-subtle);">${s.category}</span>
                        </div>
                        <div style="font-size: 0.72rem; color: var(--text-muted); margin-top: 2px;">
                            By ${s.author || 'Community'} ${s.github_url ? `• <a href="${s.github_url}" target="_blank" style="color: #60a5fa; text-decoration: none;">GitHub ↗</a>` : ''}
                        </div>
                    </div>

                    <button type="button" onclick="installCatalogSkill('${s.id}')" class="primary" style="font-size: 0.74rem; padding: 5px 12px; font-weight: 600; white-space: nowrap;">
                        Install Skill
                    </button>
                </div>

                <p style="font-size: 0.78rem; color: var(--text-secondary); margin: 0 0 10px 0; line-height: 1.45;">
                    ${s.description}
                </p>

                <div style="display: flex; gap: 4px; flex-wrap: wrap; align-items: center; border-top: 1px solid var(--border-subtle); padding-top: 8px;">
                    <span style="font-size: 0.64rem; text-transform: uppercase; color: var(--text-muted);">Capabilities:</span>
                    ${toolChips || '<span style="font-size: 0.64rem; color: var(--text-muted);">Prompt persona</span>'}
                </div>
            </div>
        `;
    }).join('');
};

window.filterSkillsCatalog = function(query) {
    window.renderCatalogSkills(query);
};

window.toggleSkillActive = async function(skillId) {
    try {
        const res = await fetch(`/api/skills/toggle/${skillId}`, { method: 'POST' });
        if (!res.ok) throw new Error("Toggle failed");
        await window.loadSkillsData();
        // If quick modal is open, re-render it
        if (document.getElementById('chatSkillsQuickModal')?.style.display === 'flex') {
            window.renderQuickSkillsList();
        }
    } catch (e) {
        alert("Could not toggle skill: " + e.message);
    }
};

window.installCatalogSkill = async function(skillId) {
    try {
        const res = await fetch('/api/skills/install', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ skill_id: skillId })
        });
        if (!res.ok) throw new Error("Installation failed");
        await window.loadSkillsData();
    } catch (e) {
        alert("Failed to install skill: " + e.message);
    }
};

window.uninstallSkill = async function(skillId) {
    if (!confirm("Are you sure you want to uninstall this skill?")) return;
    try {
        const res = await fetch(`/api/skills/uninstall/${skillId}`, { method: 'POST' });
        if (!res.ok) throw new Error("Uninstall failed");
        await window.loadSkillsData();
    } catch (e) {
        alert("Failed to uninstall: " + e.message);
    }
};

// Quick Modal in Chat
window.openChatSkillsQuickModal = async function() {
    const modal = document.getElementById('chatSkillsQuickModal');
    if (!modal) return;
    modal.style.display = 'flex';

    const targetLabel = document.getElementById('quickSkillTargetModelName');
    const curModel = document.getElementById('chatModelSelect')?.value || 'Active Model';
    if (targetLabel) targetLabel.textContent = curModel;

    await window.loadSkillsData();
    window.renderQuickSkillsList();
};

window.closeChatSkillsQuickModal = function() {
    const modal = document.getElementById('chatSkillsQuickModal');
    if (modal) modal.style.display = 'none';
};

window.renderQuickSkillsList = function() {
    const container = document.getElementById('quickSkillsListContainer');
    if (!container) return;

    const installed = window.currentSkillsData.installed || [];
    if (installed.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; color: var(--text-muted); padding: 20px; font-size: 0.8rem;">
                No skills installed. Open the Skills & MCP tab to browse and install skills.
            </div>
        `;
        return;
    }

    container.innerHTML = installed.map(s => {
        const isActive = s.is_active;
        return `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border-radius: 8px; border: 1px solid ${isActive ? 'rgba(59, 130, 246, 0.45)' : 'var(--border-subtle)'}; background: ${isActive ? 'rgba(59, 130, 246, 0.08)' : 'var(--bg-surface-elevated)'};">
                <div>
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <strong style="font-size: 0.84rem; color: var(--text-primary);">${s.name}</strong>
                        ${isActive ? '<span style="font-size: 0.65rem; color: #60a5fa; font-weight: 700;">• ACTIVE</span>' : ''}
                    </div>
                    <div style="font-size: 0.72rem; color: var(--text-secondary); max-width: 340px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        ${s.description}
                    </div>
                </div>

                <button type="button" onclick="toggleSkillActive('${s.id}')" class="${isActive ? 'primary' : 'btn-quiet'}" style="font-size: 0.74rem; padding: 4px 10px; font-weight: 600;">
                    ${isActive ? '✓ Attached' : '+ Attach'}
                </button>
            </div>
        `;
    }).join('');
};

// Modal: Bake Skills into Model (Supports both In-Place & New Model)
window.currentBakeMode = 'inplace';

window.setBakeMode = function(mode) {
    window.currentBakeMode = mode;
    const inPlaceBtn = document.getElementById('bakeModeInPlaceBtn');
    const newBtn = document.getElementById('bakeModeNewBtn');
    const nameGroup = document.getElementById('bakeNewNameGroup');
    const execBtn = document.getElementById('btnExecuteBake');
    const targetNotice = document.getElementById('bakeTargetNotice');
    const selVal = document.getElementById('bakeBaseModelSelect')?.value || 'active model';

    if (mode === 'inplace') {
        if (inPlaceBtn) {
            inPlaceBtn.style.background = '#60a5fa';
            inPlaceBtn.style.color = '#fff';
        }
        if (newBtn) {
            newBtn.style.background = 'transparent';
            newBtn.style.color = 'var(--text-muted)';
        }
        if (nameGroup) nameGroup.style.display = 'none';
        if (targetNotice) targetNotice.style.display = 'block';
        if (execBtn) execBtn.textContent = 'Bake into Existing Model';
    } else {
        if (newBtn) {
            newBtn.style.background = '#60a5fa';
            newBtn.style.color = '#fff';
        }
        if (inPlaceBtn) {
            inPlaceBtn.style.background = 'transparent';
            inPlaceBtn.style.color = 'var(--text-muted)';
        }
        if (nameGroup) nameGroup.style.display = 'block';
        if (targetNotice) targetNotice.style.display = 'none';
        if (execBtn) execBtn.textContent = 'Compile New Standalone Model';
    }
};

window.onBakeTargetChange = function() {
    const selVal = document.getElementById('bakeBaseModelSelect')?.value || 'model';
    const boldEl = document.getElementById('bakeTargetNameBold');
    if (boldEl) boldEl.textContent = selVal;

    const nameInput = document.getElementById('bakeNewModelNameInput');
    if (nameInput) {
        nameInput.value = `${selVal.split(':')[0]}-skilled`;
    }
};

window.triggerBakeRecommendation = function(baseModel, suggestedName, skillIds) {
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
};

window.closeBakeSkillsModal = function() {
    const modal = document.getElementById('bakeSkillsModal');
    if (modal) modal.style.display = 'none';
};

window.executeBakeSkillsIntoModel = async function() {
    const baseModel = document.getElementById('bakeBaseModelSelect')?.value || 'dolphin3:latest';
    const isOverwriting = window.currentBakeMode === 'inplace';
    const newName = isOverwriting ? baseModel : (document.getElementById('bakeNewModelNameInput')?.value.trim() || `${baseModel.split(':')[0]}-skilled`);
    const selectedIds = Array.from(document.querySelectorAll('.bake-skill-cb:checked')).map(cb => cb.value);

    if (selectedIds.length === 0) {
        alert("Please select at least 1 skill to bake into the model.");
        return;
    }

    const btn = document.getElementById('btnExecuteBake');
    const feedback = document.getElementById('bakeStatusFeedback');

    if (btn) {
        btn.disabled = true;
        btn.textContent = isOverwriting ? "Baking Skills into Existing Model..." : "Compiling New Model via Ollama...";
    }
    if (feedback) {
        feedback.style.display = 'block';
        feedback.style.background = 'rgba(59, 130, 246, 0.15)';
        feedback.style.color = '#60a5fa';
        feedback.textContent = isOverwriting 
            ? `Baking ${selectedIds.length} skill(s) directly into existing '${baseModel}' on local GPU...`
            : `Compiling new model '${newName}' with ${selectedIds.length} skill(s)...`;
    }

    try {
        const res = await fetch('/api/skills/bake_into_model', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                base_model: baseModel,
                new_model_name: newName,
                overwrite_existing: isOverwriting,
                skill_ids: selectedIds
            })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Bake compilation failed");

        if (feedback) {
            feedback.style.background = 'rgba(16, 185, 129, 0.15)';
            feedback.style.color = '#10b981';
            feedback.innerHTML = isOverwriting
                ? `<strong>✓ Success!</strong> Skills successfully baked directly into <code>${data.model_name}</code>!`
                : `<strong>✓ Success!</strong> Created and compiled model <code>${data.model_name}</code> into Ollama!`;
        }

        setTimeout(async () => {
            window.closeBakeSkillsModal();
            if (window.refreshChatModels) await window.refreshChatModels(data.model_name);
            window.switchAppTab('chat-section');
        }, 1500);

    } catch (err) {
        if (feedback) {
            feedback.style.background = 'rgba(244, 63, 94, 0.15)';
            feedback.style.color = '#f43f5e';
            feedback.textContent = `Error: ${err.message}`;
        }
        alert("Compilation failed: " + err.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = isOverwriting ? "Bake into Existing Model" : "Compile New Standalone Model";
        }
    }
};

// Modal: Import Skill
window.openImportSkillModal = function() {
    const modal = document.getElementById('importSkillModal');
    if (modal) modal.style.display = 'flex';
};

window.closeImportSkillModal = function() {
    const modal = document.getElementById('importSkillModal');
    if (modal) modal.style.display = 'none';
};

window.executeImportSkill = async function() {
    const githubUrl = document.getElementById('importSkillGithubUrl')?.value.trim();
    const name = document.getElementById('importSkillName')?.value.trim();
    const category = document.getElementById('importSkillCategory')?.value;
    const instructions = document.getElementById('importSkillInstructions')?.value.trim();

    if (!name && !githubUrl) {
        alert("Please provide at least a Skill Name or GitHub URL.");
        return;
    }

    try {
        const res = await fetch('/api/skills/install', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                github_url: githubUrl || null,
                name: name || null,
                category: category || 'custom',
                system_instructions: instructions || null
            })
        });

        if (!res.ok) throw new Error("Import failed");
        window.closeImportSkillModal();
        await window.loadSkillsData();
    } catch (e) {
        alert("Could not import skill: " + e.message);
    }
};

// Initial trigger to load skill badges on boot
setTimeout(() => {
    if (window.loadSkillsData) window.loadSkillsData();
}, 1000);


// =============================================================
// PER-CHAT SKILL INJECTION & IMPORT CHATS MODAL
// =============================================================

window.updateSessionSkillsUI = function(session) {
    if (!session) session = getActiveSession();
    const count = session && Array.isArray(session.activeSkills) ? session.activeSkills.length : 0;
    const pill = document.getElementById('chatActiveSkillsCountPill');
    if (pill) {
        pill.textContent = count > 0 ? count : 'Auto';
    }
};

window.clearChatPinnedSkills = function() {
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
};

window.renderQuickSkillsList = function() {
    const container = document.getElementById('quickSkillsListContainer');
    if (!container) return;

    const installed = (window.currentSkillsData && window.currentSkillsData.installed) || [];
    if (installed.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; color: var(--text-muted); padding: 20px; font-size: 0.8rem;">
                No skills installed. Open the Skills & MCP tab to browse and install skills.
            </div>
        `;
        return;
    }

    const session = getActiveSession();
    const sessionSkills = (session && Array.isArray(session.activeSkills)) ? session.activeSkills : [];

    container.innerHTML = installed.map(s => {
        const isActive = sessionSkills.includes(s.id);
        return `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border-radius: 8px; border: 1px solid ${isActive ? 'rgba(59, 130, 246, 0.45)' : 'var(--border-subtle)'}; background: ${isActive ? 'rgba(59, 130, 246, 0.08)' : 'var(--bg-surface-elevated)'};">
                <div>
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <strong style="font-size: 0.84rem; color: var(--text-primary);">${s.name}</strong>
                        ${isActive ? '<span style="font-size: 0.65rem; color: #60a5fa; font-weight: 700;">• ACTIVE IN THIS CHAT</span>' : ''}
                    </div>
                    <div style="font-size: 0.72rem; color: var(--text-secondary); max-width: 340px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        ${s.description}
                    </div>
                </div>

                <button type="button" onclick="toggleSkillForCurrentChat('${s.id}')" class="${isActive ? 'primary' : 'btn-quiet'}" style="font-size: 0.74rem; padding: 4px 10px; font-weight: 600;">
                    ${isActive ? '✓ Attached' : '+ Attach'}
                </button>
            </div>
        `;
    }).join('');
};

window.openImportChatsModal = function() {
    const modal = document.getElementById('importChatsModal');
    if (!modal) return;
    
    const curModel = document.getElementById('chatModelSelect')?.value || (window.chatModels && window.chatModels.length > 0 ? window.chatModels[0].name : 'current model');
    const targetLabel = document.getElementById('importChatsTargetModelName');
    if (targetLabel) targetLabel.textContent = curModel;

    const sourceSelect = document.getElementById('importChatsSourceModelSelect');
    if (sourceSelect) {
        sourceSelect.innerHTML = '';
        
        const allSessions = window.chatSessions || [];
        const modelSet = new Set();
        allSessions.forEach(s => {
            if (s.model && s.model !== curModel) {
                modelSet.add(s.model);
            }
        });

        const availableModels = Array.from(modelSet);

        if (availableModels.length === 0) {
            sourceSelect.innerHTML = '<option value="">No other models have chat history</option>';
        } else {
            availableModels.forEach(m => {
                const count = allSessions.filter(s => s.model === m).length;
                const opt = document.createElement('option');
                opt.value = m;
                opt.textContent = `${m} (${count} conversation${count === 1 ? '' : 's'})`;
                sourceSelect.appendChild(opt);
            });
        }
    }

    const feedback = document.getElementById('importChatsFeedback');
    if (feedback) feedback.style.display = 'none';

    onImportChatsSourceChange();
    modal.style.display = 'flex';
};

window.closeImportChatsModal = function() {
    const modal = document.getElementById('importChatsModal');
    if (modal) modal.style.display = 'none';
};

window.onImportChatsSourceChange = function() {
    const sourceSelect = document.getElementById('importChatsSourceModelSelect');
    const container = document.getElementById('importChatsCheckboxesList');
    if (!container || !sourceSelect) return;

    const sourceModel = sourceSelect.value;
    if (!sourceModel) {
        container.innerHTML = '<div style="color: var(--text-muted); font-size: 0.78rem; text-align: center; padding: 14px;">No source model available.</div>';
        return;
    }

    const matchingSessions = (window.chatSessions || []).filter(s => s.model === sourceModel);
    if (matchingSessions.length === 0) {
        container.innerHTML = '<div style="color: var(--text-muted); font-size: 0.78rem; text-align: center; padding: 14px;">No chats found for this source model.</div>';
        return;
    }

    container.innerHTML = matchingSessions.map(s => {
        const msgCount = (s.messages || []).length;
        const dateStr = s.createdAt ? new Date(s.createdAt).toLocaleDateString() : '';
        return `
            <label style="display: flex; align-items: flex-start; gap: 10px; padding: 8px 10px; border-radius: 6px; background: var(--bg-surface); border: 1px solid var(--border-subtle); cursor: pointer;">
                <input type="checkbox" class="import-chat-checkbox" value="${s.id}" checked style="margin-top: 3px; width: 14px; height: 14px;">
                <div style="flex: 1; min-width: 0;">
                    <div style="font-size: 0.82rem; font-weight: 500; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        ${s.title || 'Untitled Conversation'}
                    </div>
                    <div style="font-size: 0.7rem; color: var(--text-muted); margin-top: 2px;">
                        ${msgCount} messages ${dateStr ? '• ' + dateStr : ''}
                    </div>
                </div>
            </label>
        `;
    }).join('');
};

window.toggleSelectAllImportChats = function() {
    const checkboxes = document.querySelectorAll('.import-chat-checkbox');
    if (checkboxes.length === 0) return;
    const shouldCheck = Array.from(checkboxes).some(cb => !cb.checked);
    checkboxes.forEach(cb => cb.checked = shouldCheck);
};

window.executeImportChats = function() {
    const targetModel = document.getElementById('chatModelSelect')?.value;
    if (!targetModel) {
        alert("Please select a target model in the chat header first.");
        return;
    }

    const checkedBoxes = Array.from(document.querySelectorAll('.import-chat-checkbox:checked'));
    if (checkedBoxes.length === 0) {
        alert("Please select at least one conversation to import.");
        return;
    }

    const keepCopy = document.getElementById('importChatsKeepCopyToggle')?.checked !== false;
    const selectedIds = checkedBoxes.map(cb => cb.value);

    let importedCount = 0;
    const newSessions = [];

    window.chatSessions = (window.chatSessions || []).map(s => {
        if (selectedIds.includes(s.id)) {
            importedCount++;
            if (keepCopy) {
                const cloned = JSON.parse(JSON.stringify(s));
                cloned.id = 'chat_' + Date.now() + '_' + Math.random().toString(36).substring(2, 6);
                cloned.model = targetModel;
                cloned.title = (cloned.title || 'Conversation') + ' (Imported)';
                newSessions.push(cloned);
                return s;
            } else {
                s.model = targetModel;
                return s;
            }
        }
        return s;
    });

    if (newSessions.length > 0) {
        window.chatSessions = [...newSessions, ...window.chatSessions];
    }

    saveChatSessions();
    renderChatSessionsSidebar();

    const firstImported = newSessions.length > 0 ? newSessions[0].id : selectedIds[0];
    if (firstImported) {
        switchChatSession(firstImported);
    }

    const feedback = document.getElementById('importChatsFeedback');
    if (feedback) {
        feedback.style.display = 'block';
        feedback.style.background = 'rgba(16, 185, 129, 0.15)';
        feedback.style.color = '#10b981';
        feedback.style.border = '1px solid rgba(16, 185, 129, 0.3)';
        feedback.textContent = `✓ Successfully imported ${importedCount} chat${importedCount === 1 ? '' : 's'} into ${targetModel}.`;
    }

    setTimeout(() => {
        closeImportChatsModal();
    }, 1100);
};


// Opens Chat Arena preserving the last used model and attaches the given skill
window.openChatWithSkill = async function(skillId = null) {
    if (typeof switchAppTab === 'function') {
        switchAppTab('chat-section');
    }

    const select = document.getElementById('chatModelSelect');
    const lastUsedModel = localStorage.getItem('chat_arena_last_model') || (window.chatModels && window.chatModels[0]?.name) || (select ? select.value : '');

    // Ensure model dropdown is set to last used model
    if (select && lastUsedModel && select.value !== lastUsedModel) {
        select.value = lastUsedModel;
        if (typeof onChatModelChange === 'function') {
            onChatModelChange();
        }
    }

    // Open the Quick Skills modal for this model's active conversation
    if (typeof openChatSkillsQuickModal === 'function') {
        await openChatSkillsQuickModal();
    }

    // If a specific skillId was passed, automatically attach it if not already attached
    if (skillId) {
        const session = typeof getActiveSession === 'function' ? getActiveSession() : null;
        if (session) {
            if (!Array.isArray(session.activeSkills)) {
                session.activeSkills = [];
            }
            if (!session.activeSkills.includes(skillId)) {
                session.activeSkills.push(skillId);
                if (typeof saveChatSessions === 'function') saveChatSessions();
                if (typeof updateSessionSkillsUI === 'function') updateSessionSkillsUI(session);
                if (typeof renderQuickSkillsList === 'function') renderQuickSkillsList();
                if (typeof renderChatSessionsSidebar === 'function') renderChatSessionsSidebar();
            }
        }
    }
};


// =============================================================
// ANTIGRAVITY REACT AGENT CONTROLLER & MODALS
// =============================================================
// Default agenticModeEnabled to true so code/game generation always builds files and triggers Live Preview
const savedAgentic = localStorage.getItem('agentic_mode_enabled');
window.agenticModeEnabled = savedAgentic !== null ? savedAgentic === 'true' : true;

window.updateAgenticModeUI = function() {
    const btns = document.querySelectorAll('#btnAgenticModeToggle');
    const labels = document.querySelectorAll('#agenticStatusLabel');

    labels.forEach(l => {
        l.textContent = window.agenticModeEnabled ? 'ON' : 'OFF';
        l.style.color = window.agenticModeEnabled ? 'var(--text-primary)' : 'var(--text-muted)';
    });

    btns.forEach(b => {
        if (window.agenticModeEnabled) {
            b.style.color = 'var(--text-primary)';
            b.style.borderColor = 'var(--border-strong)';
            b.style.background = 'var(--bg-surface-elevated)';
            b.title = 'Autonomous ReAct Agent Active: Multi-Step Tool Calling & Project File Creation Enabled';
        } else {
            b.style.color = 'var(--text-muted)';
            b.style.borderColor = 'var(--border-subtle)';
            b.style.background = 'transparent';
            b.title = 'Standard Chat Mode (Click to enable ReAct Agent)';
        }
    });
};

window.toggleAgenticMode = function() {
    window.agenticModeEnabled = !window.agenticModeEnabled;
    try {
        localStorage.setItem('agentic_mode_enabled', window.agenticModeEnabled ? 'true' : 'false');
    } catch (e) {}
    window.updateAgenticModeUI();
};

window.openProjectInVSCode = async function(projectName) {
    try {
        const res = await fetch(`/api/chat/agent/projects/${encodeURIComponent(projectName)}/open_vscode`, { method: 'POST' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Could not open VS Code');
        // Flash subtle confirmation
        const note = document.createElement('div');
        note.style.position = 'fixed';
        note.style.bottom = '24px';
        note.style.right = '24px';
        note.style.background = 'var(--bg-surface-elevated)';
        note.style.border = '1px solid var(--border-medium)';
        note.style.color = 'var(--text-primary)';
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
                            📄 Code
                        </button>
                        <button type="button" onclick="window._setWorkspaceView('audit')" style="font-size: 0.74rem; font-weight: 600; padding: 3px 10px; border: none; border-radius: 4px; cursor: pointer; background: ${currentView === 'audit' ? 'var(--accent)' : 'transparent'}; color: ${currentView === 'audit' ? '#ffffff' : 'var(--text-secondary)'};" title="Explainability Timeline & Decision Tracer">
                            🔍 Audit Trail
                        </button>
                        <button type="button" onclick="window._setWorkspaceView('snapshots')" style="font-size: 0.74rem; font-weight: 600; padding: 3px 10px; border: none; border-radius: 4px; cursor: pointer; background: ${currentView === 'snapshots' ? 'var(--accent)' : 'transparent'}; color: ${currentView === 'snapshots' ? '#ffffff' : 'var(--text-secondary)'};" title="Workspace Snapshots & History">
                            🕒 Snapshots
                        </button>
                    </div>

                    <button type="button" onclick="window.undoProjectStep('${projectName}')" class="btn-quiet" style="font-size: 0.72rem; padding: 4px 10px; color: var(--text-primary); border: 1px solid var(--border-subtle); display: inline-flex; align-items: center; gap: 4px; background: rgba(239, 68, 68, 0.08);" title="1-Click Undo: Revert workspace to state before last agent turn">
                        <span>↩ Undo Step</span>
                    </button>

                    ${hasHtml ? `
                        <a href="/api/chat/agent/projects/${encodeURIComponent(projectName)}/preview/" target="_blank" class="btn-quiet" style="font-size: 0.72rem; padding: 4px 10px; text-decoration: none; color: var(--text-primary); border: 1px solid var(--border-subtle); display: inline-flex; align-items: center; gap: 4px;" title="Open live website in full browser tab">
                            <span>↗ Open in Tab</span>
                        </a>
                    ` : ''}

                    <button type="button" onclick="openProjectInVSCode('${projectName}')" class="btn-quiet" style="font-size: 0.72rem; padding: 4px 10px; color: var(--text-secondary); border: 1px solid var(--border-subtle); display: inline-flex; align-items: center; gap: 4px;" title="Open this workspace in VS Code">
                        <span>💙 VS Code</span>
                    </button>

                    <button type="button" onclick="openProjectFolder('${projectName}')" class="btn-quiet" style="font-size: 0.72rem; padding: 4px 10px; color: var(--text-secondary); display: inline-flex; align-items: center; gap: 4px;" title="Open directory in Windows Explorer">
                        <span>📁 Folder</span>
                    </button>
                `;
            }

            if (currentView === 'preview' && hasHtml) {
                // Live Browser Rendering View (Antigravity-style)
                const previewUrl = `/api/chat/agent/projects/${encodeURIComponent(projectName)}/preview/`;
                bodyEl.innerHTML = `
                    <div style="display: flex; flex-direction: column; flex: 1; border-radius: 8px; overflow: hidden; border: 1px solid var(--border-subtle); background: #ffffff;">
                        <!-- Browser Header Strip -->
                        <div style="background: var(--bg-surface); padding: 8px 12px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--border-subtle);">
                            <div style="display: flex; align-items: center; gap: 6px;">
                                <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: #ef4444; opacity: 0.8;"></span>
                                <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: #f59e0b; opacity: 0.8;"></span>
                                <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: #10b981; opacity: 0.8;"></span>
                                <div style="margin-left: 10px; background: var(--bg-base); border: 1px solid var(--border-subtle); padding: 2px 12px; border-radius: 4px; font-family: var(--font-mono); font-size: 0.72rem; color: var(--text-secondary); display: inline-flex; align-items: center; gap: 6px;">
                                    <span style="color: var(--text-muted);">🔒</span>
                                    <span>http://127.0.0.1:8001${previewUrl}</span>
                                </div>
                            </div>
                            <div style="display: flex; align-items: center; gap: 6px;">
                                <button type="button" onclick="const f = document.getElementById('projectPreviewIframe'); if (f) f.src = f.src;" class="btn-quiet" style="font-size: 0.7rem; padding: 2px 8px; color: var(--text-secondary);" title="Reload preview">
                                    ⟳ Refresh
                                </button>
                                <a href="${previewUrl}" target="_blank" class="btn-quiet" style="font-size: 0.7rem; padding: 2px 8px; text-decoration: none; color: var(--text-primary); border: 1px solid var(--border-subtle);">
                                    ↗ Full Screen
                                </a>
                            </div>
                        </div>

                        <!-- Live Iframe View -->
                        <iframe id="projectPreviewIframe" src="${previewUrl}" style="flex: 1; width: 100%; border: none; background: #ffffff;" sandbox="allow-scripts allow-forms allow-same-origin allow-modals"></iframe>
                    </div>
                `;
            } else if (currentView === 'audit') {
                // Decision Audit Trail & Explainability Timeline View (Elena Vance & Clara Higgins)
                bodyEl.innerHTML = '<div style="padding: 40px; text-align: center; color: var(--text-muted);">Loading explainability audit trail...</div>';
                try {
                    const [aRes, sRes] = await Promise.all([
                        fetch(`/api/chat/agent/projects/${encodeURIComponent(projectName)}/audit-trail`),
                        fetch(`/api/chat/agent/projects/${encodeURIComponent(projectName)}/security-audit`)
                    ]);
                    const auditEvents = aRes.ok ? await aRes.json() : [];
                    const secAudit = sRes.ok ? await sRes.json() : { valid: true, critical_count: 0 };

                    bodyEl.innerHTML = `
                        <div style="flex: 1; display: flex; flex-direction: column; overflow: hidden; gap: 12px; padding: 6px 4px;">
                            <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: 8px; padding: 10px 16px; display: flex; justify-content: space-between; align-items: center;">
                                <div style="display: flex; align-items: center; gap: 10px;">
                                    <span style="font-size: 0.82rem; font-weight: 600; color: var(--text-primary);">AppSec & Gate Status:</span>
                                    <span style="font-size: 0.74rem; padding: 2px 8px; border-radius: 4px; font-weight: 600; background: ${secAudit.valid ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)'}; color: ${secAudit.valid ? '#10b981' : '#ef4444'};">
                                        ${secAudit.valid ? 'Verified Clean (0 Defects)' : `${secAudit.critical_count} Critical Issues`}
                                    </span>
                                </div>
                                <span style="font-size: 0.74rem; color: var(--text-muted); font-family: var(--font-mono);">${auditEvents.length} Recorded Decision Events</span>
                            </div>

                            <div style="flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; padding-right: 6px;">
                                ${auditEvents.length === 0 ? '<div style="text-align: center; color: var(--text-muted); padding: 40px;">No decision events recorded for this project yet.</div>' : ''}
                                ${auditEvents.map(ev => {
                                    const typeColors = {
                                        intent_analysis: '#3b82f6',
                                        milestone_plan: '#8b5cf6',
                                        action_execution: '#10b981',
                                        gate_audit: '#f59e0b',
                                        provenance_routed: '#ec4899',
                                        security_check: '#ef4444'
                                    };
                                    const color = typeColors[ev.type] || '#60a5fa';
                                    return `
                                        <div style="background: var(--bg-base); border: 1px solid var(--border-subtle); border-left: 3px solid ${color}; border-radius: 6px; padding: 12px 14px;">
                                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                                                <div style="display: flex; align-items: center; gap: 8px;">
                                                    <span style="font-size: 0.68rem; font-weight: 700; text-transform: uppercase; padding: 1px 6px; border-radius: 3px; background: rgba(255,255,255,0.06); color: ${color}; font-family: var(--font-mono);">${ev.type}</span>
                                                    <span style="font-size: 0.82rem; font-weight: 600; color: var(--text-primary);">${escapeHtml(ev.title)}</span>
                                                </div>
                                                <span style="font-size: 0.7rem; color: var(--text-muted); font-family: var(--font-mono);">${ev.timestamp || ''}</span>
                                            </div>
                                            <div style="font-size: 0.78rem; color: var(--text-secondary); line-height: 1.4; margin-bottom: ${ev.metadata && Object.keys(ev.metadata).length ? '8px' : '0'};">
                                                ${escapeHtml(ev.rationale)}
                                            </div>
                                            ${ev.metadata && Object.keys(ev.metadata).length ? `
                                                <pre style="margin: 0; background: rgba(0,0,0,0.25); border: 1px solid var(--border-subtle); border-radius: 4px; padding: 6px 10px; font-size: 0.7rem; font-family: var(--font-mono); color: var(--text-muted); overflow-x: auto;">${escapeHtml(JSON.stringify(ev.metadata, null, 2))}</pre>
                                            ` : ''}
                                        </div>
                                    `;
                                }).join('')}
                            </div>
                        </div>
                    `;
                } catch (err) {
                    bodyEl.innerHTML = `<div style="padding: 30px; text-align: center; color: var(--danger);">Failed to load audit trail: ${err.message}</div>`;
                }
            } else if (currentView === 'snapshots') {
                // Workspace Snapshots & 1-Click Rollback History View (Priya Patel & Clara Higgins)
                bodyEl.innerHTML = '<div style="padding: 40px; text-align: center; color: var(--text-muted);">Loading snapshots...</div>';
                try {
                    const sRes = await fetch(`/api/chat/agent/projects/${encodeURIComponent(projectName)}/snapshots`);
                    const snapshots = sRes.ok ? await sRes.json() : [];

                    bodyEl.innerHTML = `
                        <div style="flex: 1; display: flex; flex-direction: column; overflow: hidden; gap: 12px; padding: 6px 4px;">
                            <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); border-radius: 8px; padding: 10px 16px; display: flex; justify-content: space-between; align-items: center;">
                                <span style="font-size: 0.82rem; font-weight: 600; color: var(--text-primary);">Workspace Checkpoints (${snapshots.length})</span>
                                <span style="font-size: 0.72rem; color: var(--text-muted);">Auto-created before each turn & self-repair attempt</span>
                            </div>
                            <div style="flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; padding-right: 6px;">
                                ${snapshots.length === 0 ? '<div style="text-align: center; color: var(--text-muted); padding: 40px;">No snapshots captured yet for this workspace.</div>' : ''}
                                ${snapshots.map(s => `
                                    <div style="background: var(--bg-base); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 12px 14px; display: flex; justify-content: space-between; align-items: center;">
                                        <div>
                                            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                                                <span style="font-size: 0.72rem; font-weight: 700; font-family: var(--font-mono); color: var(--accent);">${s.snapshot_id}</span>
                                                <span style="font-size: 0.76rem; font-weight: 600; color: var(--text-primary);">${escapeHtml(s.label || s.turn_id || '')}</span>
                                            </div>
                                            <div style="font-size: 0.72rem; color: var(--text-muted); font-family: var(--font-mono);">
                                                ${s.created_at || ''} &bull; ${s.file_count || 0} files (${Math.round((s.total_bytes || 0) / 1024 * 10) / 10} KB)
                                            </div>
                                        </div>
                                        <button type="button" onclick="window.rollbackProjectSnapshot('${projectName}', '${s.snapshot_id}')" class="btn-quiet" style="font-size: 0.72rem; padding: 5px 12px; color: var(--text-primary); border: 1px solid var(--border-subtle); background: rgba(59, 130, 246, 0.1);">
                                            ⏪ Rollback
                                        </button>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    `;
                } catch (err) {
                    bodyEl.innerHTML = `<div style="padding: 30px; text-align: center; color: var(--danger);">Failed to load snapshots: ${err.message}</div>`;
                }
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
                                    <div onclick="window._onProjectFileSelect('${projectName}', '${f.path}')" style="cursor: pointer; padding: 6px 10px; border-radius: 6px; font-size: 0.78rem; font-family: var(--font-mono); display: flex; justify-content: space-between; align-items: center; background: ${isSel ? 'var(--bg-surface-elevated)' : 'transparent'}; color: ${isSel ? 'var(--text-primary)' : 'var(--text-secondary)'}; border: 1px solid ${isSel ? 'var(--border-strong)' : 'transparent'}; transition: 0.15s;">
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
};

window.undoProjectStep = async function(projectName) {
    if (!confirm(`Are you sure you want to undo the last turn in '${projectName}'? The workspace will revert to its previous checkpoint.`)) return;
    try {
        const res = await fetch(`/api/chat/agent/projects/${encodeURIComponent(projectName)}/undo`, { method: 'POST' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || data.message || 'Undo failed');
        alert(`Undone successfully: Reverted to checkpoint '${data.restored_snapshot_id || ''}'`);
        window.openAgentProjectModal(projectName);
    } catch (err) {
        alert("Undo Error: " + err.message);
    }
};

window.rollbackProjectSnapshot = async function(projectName, snapshotId) {
    if (!confirm(`Rollback workspace '${projectName}' to snapshot '${snapshotId}'? Current files will be replaced with this checkpoint.`)) return;
    try {
        const res = await fetch(`/api/chat/agent/projects/${encodeURIComponent(projectName)}/rollback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ snapshot_id: snapshotId })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || data.message || 'Rollback failed');
        alert(`Successfully rolled back to snapshot: ${snapshotId}`);
        window.openAgentProjectModal(projectName);
    } catch (err) {
        alert("Rollback Error: " + err.message);
    }
};


// Autonomous Knowledge Acquisition & Model Grounding Action
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

// Human-In-The-Loop Package Installer Action
window.executeAgentInstall = async function(btn, pkgType, pkgName) {
    if (!btn) return;
    const parent = btn.parentElement;
    btn.disabled = true;
    btn.innerHTML = '<span>Installing...</span>';

    try {
        const res = await fetch('/api/chat/agent/install_package', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ package: pkgName, install_type: pkgType })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Install failed');

        btn.className = 'btn-quiet';
        btn.style.color = '#10b981';
        btn.style.borderColor = 'rgba(16, 185, 129, 0.4)';
        btn.innerHTML = '✓ Installed';

        if (parent) {
            const notice = document.createElement('div');
            notice.style.fontSize = '0.72rem';
            notice.style.color = '#10b981';
            notice.style.marginTop = '6px';
            notice.style.fontFamily = 'var(--font-mono)';
            notice.textContent = `Successfully configured ${pkgName}. Ready to resume.`;
            parent.appendChild(notice);
        }
    } catch (err) {
        btn.disabled = false;
        btn.innerHTML = 'Retry Install';
        alert("Installation failed: " + err.message);
    }
};

// 1-Click Turn ON Agentic Mode & Retry Prompt
window.confirmEnableAgenticAndRetry = async function(btn) {
    window.agenticModeEnabled = true;
    try {
        localStorage.setItem('agentic_mode_enabled', 'true');
    } catch (e) {}
    window.updateAgenticModeUI();

    const card = btn ? btn.closest('div[style*="border"]') : null;
    if (card) {
        card.innerHTML = `
            <div style="display:flex;align-items:center;gap:8px;color:var(--text-primary);font-size:0.78rem;">
                <span class="status-dot" style="width:7px;height:7px;background:var(--text-primary);"></span>
                <span>Agentic Mode enabled. Retrying prompt with autonomous tools...</span>
            </div>
        `;
    }

    const session = window.chatSessions?.find(s => s.id === window.currentChatSessionId);
    if (!session || !session.messages || session.messages.length === 0) return;

    if (session.messages[session.messages.length - 1].role === 'assistant') {
        session.messages.pop();
    }

    let lastUserMsg = null;
    for (let i = session.messages.length - 1; i >= 0; i--) {
        if (session.messages[i].role === 'user') {
            lastUserMsg = session.messages[i];
            break;
        }
    }
    if (!lastUserMsg) return;

    const model = session.model || document.getElementById('chatModelSelect')?.value || 'cyber-specialist:latest';
    const isAgentic = window.agenticModeEnabled === true;
    const projectName = session.projectName || ('proj_' + (session.id || 'default').replace(/[^a-zA-Z0-9]/g, '_').substring(0, 16));
    session.projectName = projectName;
    const typingId = appendTypingIndicator(model, isAgentic ? projectName : null);

    window.isChatGenerating = true;
    const sendBtn = document.getElementById('btnSendChat');
    if (sendBtn) {
        sendBtn.disabled = true;
        sendBtn.innerHTML = '<span>Thinking...</span>';
    }

    try {
        const historyPayload = session.messages.map(m => ({
            role: m.role,
            content: m.content,
            images: m.images && m.images.length > 0 ? m.images : undefined
        }));
        const activeSkillIds = (session && Array.isArray(session.activeSkills)) ? session.activeSkills : [];

        const res = await fetch('/api/chat/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                model: model,
                messages: historyPayload,
                system_prompt: document.getElementById('chatSystemPromptInput')?.value || '',
                temperature: parseFloat(document.getElementById('chatTempSlider')?.value || '0.7'),
                context_window: parseInt(document.getElementById('chatCtxSlider')?.value || '8192', 10),
                use_rag: window.cyberRAGEnabled !== false,
                skill_ids: activeSkillIds,
                agentic: true,
                project_name: projectName
            })
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || `Server returned ${res.status}`);
        }

        const data = await res.json();
        removeTypingIndicator(typingId);

        const agenticData = data.agentic ? {
            steps: data.steps,
            created_files: data.created_files,
            project_name: data.project_name,
            gateway_grounding: data.gateway_grounding
        } : null;

        const assistantMsg = {
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

        appendMessageElement('assistant', data.reply, data.telemetry, true, null, data.rag_sources, data.active_skills, agenticData, model, data.bake_recommendation);
    } catch (err) {
        removeTypingIndicator(typingId);
        appendMessageElement('assistant', `**Local Engine Error:** ${err.message}\n\nPlease verify that Ollama is online.`);
    } finally {
        window.isChatGenerating = false;
        if (sendBtn) {
            sendBtn.disabled = false;
            sendBtn.innerHTML = '<span>Send</span> <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-left:4px;"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>';
        }
    }
};

// Dismiss Proposal and Continue in Pure Text Mode
window.dismissAgenticProposal = async function(btn) {
    const card = btn ? btn.closest('div[style*="border"]') : null;
    if (card) {
        card.innerHTML = `
            <div style="font-size:0.74rem;color:var(--text-muted);">
                Skipped. Continuing in pure text chat mode without writing files.
            </div>
        `;
    }

    const session = window.chatSessions?.find(s => s.id === window.currentChatSessionId);
    if (!session || !session.messages || session.messages.length === 0) return;

    if (session.messages[session.messages.length - 1].role === 'assistant') {
        session.messages.pop();
    }

    const model = session.model || document.getElementById('chatModelSelect')?.value || 'cyber-specialist:latest';
    const isAgentic = window.agenticModeEnabled === true;
    const projectName = session.projectName || ('proj_' + (session.id || 'default').replace(/[^a-zA-Z0-9]/g, '_').substring(0, 16));
    session.projectName = projectName;
    const typingId = appendTypingIndicator(model, isAgentic ? projectName : null);

    window.isChatGenerating = true;
    const sendBtn = document.getElementById('btnSendChat');
    if (sendBtn) {
        sendBtn.disabled = true;
        sendBtn.innerHTML = '<span>Thinking...</span>';
    }

    try {
        const historyPayload = session.messages.map(m => ({
            role: m.role,
            content: m.content,
            images: m.images && m.images.length > 0 ? m.images : undefined
        }));
        const activeSkillIds = (session && Array.isArray(session.activeSkills)) ? session.activeSkills : [];

        const res = await fetch('/api/chat/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                model: model,
                messages: historyPayload,
                system_prompt: document.getElementById('chatSystemPromptInput')?.value || '',
                temperature: parseFloat(document.getElementById('chatTempSlider')?.value || '0.7'),
                context_window: parseInt(document.getElementById('chatCtxSlider')?.value || '8192', 10),
                use_rag: window.cyberRAGEnabled !== false,
                skill_ids: activeSkillIds,
                agentic: false,
                skip_agentic_prompt: true,
                project_name: projectName
            })
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || `Server returned ${res.status}`);
        }

        const data = await res.json();
        removeTypingIndicator(typingId);

        const assistantMsg = {
            role: 'assistant',
            content: data.reply,
            model_used: model,
            telemetry: data.telemetry,
            rag_sources: data.rag_sources,
            active_skills: data.active_skills,
            bake_recommendation: data.bake_recommendation,
            agentic_data: null
        };
        session.messages.push(assistantMsg);
        saveChatSessions();
        renderChatSessionsSidebar();

        appendMessageElement('assistant', data.reply, data.telemetry, true, null, data.rag_sources, data.active_skills, null, model, data.bake_recommendation);
    } catch (err) {
        removeTypingIndicator(typingId);
        appendMessageElement('assistant', `**Local Engine Error:** ${err.message}\n\nPlease verify that Ollama is online.`);
    } finally {
        window.isChatGenerating = false;
        if (sendBtn) {
            sendBtn.disabled = false;
            sendBtn.innerHTML = '<span>Send</span> <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-left:4px;"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>';
        }
    }
};


// =============================================================
// ANTIGRAVITY-STYLE FLOATING MODEL SELECTOR POPOVER
// =============================================================

window.activeChatModel = localStorage.getItem('chat_arena_last_model') || 'dolphin3:latest';

window.toggleModelPickerPopover = async function() {
    const popover = document.getElementById('modelPickerPopover');
    if (!popover) return;
    const isVisible = popover.style.display === 'block';
    popover.style.display = isVisible ? 'none' : 'block';
    if (!isVisible) {
        if (!window.chatModels || window.chatModels.length === 0) {
            await refreshChatModels();
        }
        renderModelPickerPopoverList();
    }
};

window.renderModelPickerPopoverList = function() {
    const list = document.getElementById('modelPickerPopoverList');
    if (!list) return;
    list.innerHTML = '';

    const models = window.chatModels || [];
    if (models.length === 0) {
        list.innerHTML = `
            <div style="padding: 12px 14px; text-align: center; font-size: 0.74rem; color: var(--text-muted);">
                <div style="margin-bottom: 6px;">No local models loaded in memory</div>
                <button type="button" onclick="refreshChatModels().then(() => renderModelPickerPopoverList())" class="btn-quiet" style="font-size: 0.7rem; padding: 2px 8px;">↻ Scan Ollama</button>
            </div>
        `;
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

// ==========================================
// CHAT ARENA SETTINGS MODAL CONTROLLERS
// ==========================================
window.openChatSettingsModal = function() {
    const modal = document.getElementById('chatSettingsModal');
    if (modal) {
        modal.style.display = 'flex';
        // Sync modal controls with active session settings
        const session = (typeof getActiveSession === 'function') ? getActiveSession() : null;
        if (session) {
            const sys = document.getElementById('chatSystemPrompt');
            if (sys && session.systemPrompt) sys.value = session.systemPrompt;
            const temp = document.getElementById('chatTempSlider');
            const tempVal = document.getElementById('chatTempValue');
            if (temp && session.temperature !== undefined) {
                temp.value = session.temperature;
                if (tempVal) tempVal.textContent = session.temperature;
            }
            const ctx = document.getElementById('chatContextWindow');
            if (ctx && session.contextWindow) ctx.value = session.contextWindow;
        }
        if (typeof refreshDockerStatus === 'function') refreshDockerStatus();
        if (typeof refreshChatStatus === 'function') refreshChatStatus();
    }
};

window.closeChatSettingsModal = function() {
    const modal = document.getElementById('chatSettingsModal');
    if (modal) modal.style.display = 'none';

    // Persist any updated settings into active conversation session
    const session = (typeof getActiveSession === 'function') ? getActiveSession() : null;
    if (session) {
        const sys = document.getElementById('chatSystemPrompt');
        if (sys) session.systemPrompt = sys.value.trim();
        const temp = document.getElementById('chatTempSlider');
        if (temp) session.temperature = parseFloat(temp.value) || 0.7;
        const ctx = document.getElementById('chatContextWindow');
        if (ctx) session.contextWindow = parseInt(ctx.value) || 4096;
        if (typeof saveChatSessions === 'function') saveChatSessions();
    }
};

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        const sm = document.getElementById('chatSettingsModal');
        if (sm && sm.style.display !== 'none') {
            closeChatSettingsModal();
        }
    }
});


// ========================================================
// 1-CLICK CLOUD GPU BRIDGE & CREDIT MANAGEMENT
// ========================================================

window.currentSelectedGpuTarget = 'local';

window.openCloudGpuModal = async function() {
    const modal = document.getElementById('cloudGpuModal');
    if (modal) {
        modal.style.display = 'flex';
        await window.refreshCloudGpuStatus();
    }
};

window.closeCloudGpuModal = function() {
    const modal = document.getElementById('cloudGpuModal');
    if (modal) modal.style.display = 'none';
};

window.refreshCloudGpuStatus = async function() {
    try {
        const res = await fetch('/api/chat/cloud_gpu/status');
        if (!res.ok) return;
        const data = await res.json();

        // Update Pill in Chat Header
        const pillLabel = document.getElementById('activeGpuPillLabel');
        const quotaBadge = document.getElementById('activeGpuQuotaBadge');
        if (pillLabel) pillLabel.textContent = data.active_name || 'Local RTX 3050';
        if (quotaBadge) {
            if (data.active_provider === 'local') {
                quotaBadge.textContent = 'Free Unlimited';
                quotaBadge.style.background = 'rgba(56, 189, 248, 0.15)';
                quotaBadge.style.color = '#38bdf8';
            } else if (data.active_provider === 'purchased') {
                quotaBadge.textContent = `$${Number(data.remaining_quota || 0).toFixed(2)} Credits`;
                quotaBadge.style.background = 'rgba(16, 185, 129, 0.15)';
                quotaBadge.style.color = '#10b981';
            } else {
                quotaBadge.textContent = `${Number(data.remaining_quota || 0).toFixed(1)} hrs left`;
                quotaBadge.style.background = 'rgba(245, 158, 11, 0.15)';
                quotaBadge.style.color = '#f59e0b';
            }
        }

        // Update Modal Cards
        const providers = data.providers || {};
        const kaggle = providers.kaggle || {};
        const colab = providers.colab || {};
        const paid = providers.purchased || {};

        const kDisp = document.getElementById('kaggleQuotaDisplay');
        if (kDisp) kDisp.textContent = `${Number(kaggle.remaining_quota || 30.0).toFixed(1)} / 30.0 hrs remaining`;

        const cDisp = document.getElementById('colabQuotaDisplay');
        if (cDisp) cDisp.textContent = `${Number(colab.remaining_quota || 12.0).toFixed(1)} hrs / session`;

        const pDisp = document.getElementById('paidCreditsDisplay');
        if (pDisp) pDisp.textContent = `$${Number(paid.remaining_credits || 0.0).toFixed(2)} Remaining`;

        const pInput = document.getElementById('inputPaidCreditsRemaining');
        if (pInput && paid.remaining_credits !== undefined) {
            pInput.value = Number(paid.remaining_credits).toFixed(2);
        }

        // Highlight active card
        window.selectGpuTarget(data.active_provider || 'local', false);

        const tunnelInput = document.getElementById('cloudTunnelInput');
        if (tunnelInput && data.active_url && data.active_provider !== 'local') {
            tunnelInput.value = data.active_url;
        }
    } catch (err) {
        console.error("Error refreshing Cloud GPU status:", err);
    }
};

window.selectGpuTarget = function(providerKey, updateHelp = true) {
    window.currentSelectedGpuTarget = providerKey;
    const cards = {
        'local': document.getElementById('cardProviderLocal'),
        'kaggle': document.getElementById('cardProviderKaggle'),
        'colab': document.getElementById('cardProviderColab'),
        'purchased': document.getElementById('cardProviderPurchased')
    };

    for (const [k, el] of Object.entries(cards)) {
        if (!el) continue;
        if (k === providerKey) {
            el.style.border = '2px solid #38bdf8';
            el.style.boxShadow = '0 0 12px rgba(56, 189, 248, 0.3)';
        } else {
            el.style.border = '1px solid var(--border-subtle)';
            el.style.boxShadow = 'none';
        }
    }

    if (updateHelp) {
        const helpEl = document.getElementById('cloudHelpText');
        const tunnelInput = document.getElementById('cloudTunnelInput');
        if (providerKey === 'local') {
            if (helpEl) helpEl.textContent = 'Using your offline local GPU (RTX 3050 6GB). 100% free with 0 network latency.';
            if (tunnelInput) tunnelInput.value = 'http://127.0.0.1:11434';
        } else if (providerKey === 'kaggle') {
            if (helpEl) helpEl.textContent = 'Free 30h/week Dual Tesla T4 (30GB VRAM) on Kaggle. Copy the 1-click script into a Kaggle Notebook and paste the generated URL here.';
            if (tunnelInput && !tunnelInput.value.startsWith('http')) tunnelInput.value = '';
        } else if (providerKey === 'colab') {
            if (helpEl) helpEl.textContent = 'Free Tesla T4 (16GB VRAM) on Google Colab. Copy 1-click script, start notebook, and paste URL.';
            if (tunnelInput && !tunnelInput.value.startsWith('http')) tunnelInput.value = '';
        } else if (providerKey === 'purchased') {
            if (helpEl) helpEl.textContent = 'Dedicated On-Demand Cloud (A100/H100 via RunPod/Modal). Enter your serverless endpoint URL.';
        }
    }
};

window.copyCloudOneClickScript = async function() {
    const prov = window.currentSelectedGpuTarget || 'kaggle';
    try {
        const res = await fetch(`/api/chat/cloud_gpu/script/${prov}`);
        const data = await res.json();
        if (data.script) {
            await navigator.clipboard.writeText(data.script);
            alert(`Copied 1-Click Startup Script for ${prov.toUpperCase()} to clipboard!

Paste this in your free ${prov.toUpperCase()} notebook, run it, and paste the generated tunnel URL.`);
        }
    } catch (e) {
        alert("Failed to copy script: " + e.message);
    }
};

window.applyCloudGpuSwitch = async function() {
    const provider = window.currentSelectedGpuTarget || 'local';
    const tunnelInput = document.getElementById('cloudTunnelInput');
    const customUrl = tunnelInput ? tunnelInput.value.trim() : null;

    try {
        const res = await fetch('/api/chat/cloud_gpu/switch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                provider: provider,
                custom_url: customUrl
            })
        });
        const data = await res.json();
        alert(`Successfully switched inference target to: ${data.active_name || provider}!
Online: ${data.is_online ? 'YES' : 'NO'}`);
        await window.refreshCloudGpuStatus();
        window.closeCloudGpuModal();
    } catch (err) {
        alert("Failed to switch GPU target: " + err.message);
    }
};

window.savePurchasedCredits = async function() {
    const input = document.getElementById('inputPaidCreditsRemaining');
    const val = input ? parseFloat(input.value) : 10.0;
    try {
        const res = await fetch('/api/chat/cloud_gpu/credits', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                purchased_usd: val,
                remaining_usd: val
            })
        });
        const data = await res.json();
        alert(`Updated Paid Credits balance to: $${val.toFixed(2)} USD!`);
        await window.refreshCloudGpuStatus();
    } catch (e) {
        alert("Error saving credits: " + e.message);
    }
};

// Auto-refresh Cloud GPU pill on load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.refreshCloudGpuStatus();
        window.refreshComputePolicyStatus();
    });
} else {
    window.refreshCloudGpuStatus();
    window.refreshComputePolicyStatus();
}

// ========================================================
// FREE CLOUD GPU WATERFALL & LIVE EXECUTION CONTROLS
// ========================================================

window.toggleComputePolicyPopover = function(forceState) {
    const pop = document.getElementById('computePolicyPopover');
    if (!pop) return;
    if (typeof forceState === 'boolean') {
        pop.style.display = forceState ? 'block' : 'none';
    } else {
        pop.style.display = pop.style.display === 'block' ? 'none' : 'block';
    }
    if (pop.style.display === 'block') {
        window.refreshComputePolicyStatus();
    }
};

// Close popover when clicking outside
document.addEventListener('click', function(e) {
    const pop = document.getElementById('computePolicyPopover');
    const pill = document.getElementById('btnTurboPill');
    if (pop && pop.style.display === 'block') {
        if (!pop.contains(e.target) && pill && !pill.contains(e.target)) {
            pop.style.display = 'none';
        }
    }
});

window.selectComputeModeUI = async function(mode) {
    try {
        const res = await fetch('/api/chat/compute/policy', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ compute_mode: mode })
        });
        if (res.ok) {
            await window.refreshComputePolicyStatus();
        }
    } catch (e) {
        console.error("Failed to update compute mode:", e);
    }
};

window.selectFallbackPolicyUI = async function(policy) {
    try {
        const res = await fetch('/api/chat/compute/policy', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fallback_policy: policy })
        });
        if (res.ok) {
            await window.refreshComputePolicyStatus();
        }
    } catch (e) {
        console.error("Failed to update fallback policy:", e);
    }
};

window.refreshComputePolicyStatus = async function() {
    try {
        const res = await fetch('/api/chat/compute/policy');
        if (!res.ok) return;
        const data = await res.json();

        const mode = data.compute_mode || 'turbo';
        const policy = data.fallback_policy || 'prompt_first';

        // Update Pill appearance
        const pillLbl = document.getElementById('turboPillLabel');
        const pillIcon = document.getElementById('turboPillIcon');
        const pillBtn = document.getElementById('btnTurboPill');

        if (pillLbl && pillIcon) {
            if (mode === 'turbo') {
                pillLbl.textContent = 'Turbo';
                pillIcon.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>';
                pillIcon.style.color = '#38bdf8';
                if (pillBtn) pillBtn.title = 'Turbo Mode (Cloud GPU: Kaggle/Colab Dual T4)';
            } else if (mode === 'balanced') {
                pillLbl.textContent = 'Balanced';
                pillIcon.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>';
                pillIcon.style.color = '#10b981';
                if (pillBtn) pillBtn.title = 'Balanced Edge (Local GPU: RTX 3050 6GB)';
            } else {
                pillLbl.textContent = 'CPU Safe';
                pillIcon.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="10"/></svg>';
                pillIcon.style.color = '#a3e635';
                if (pillBtn) pillBtn.title = 'CPU Safe Mode (0% VRAM / Zero-Crash RAM)';
            }
        }

        // Sync Radio Buttons
        const rTurbo = document.getElementById('radioTierTurbo');
        const rBal = document.getElementById('radioTierBalanced');
        const rCpu = document.getElementById('radioTierCpuSafe');
        if (rTurbo) rTurbo.checked = (mode === 'turbo');
        if (rBal) rBal.checked = (mode === 'balanced');
        if (rCpu) rCpu.checked = (mode === 'cpu_safe');

        const rPrompt = document.getElementById('radioPolicyPrompt');
        const rCascade = document.getElementById('radioPolicyCascade');
        const rResume = document.getElementById('radioPolicyResume');
        if (rPrompt) rPrompt.checked = (policy === 'prompt_first');
        if (rCascade) rCascade.checked = (policy === 'auto_cascade');
        if (rResume) rResume.checked = (policy === 'auto_resume');
    } catch (e) {
        console.error("Error refreshing compute policy:", e);
    }
};

window.handlePauseExecutionClick = async function() {
    const session = getActiveSession();
    const projName = window.activeGeneratingProject || (session ? session.projectName : 'default_project');
    const pauseLbl = document.getElementById('btnPauseExecutionLabel');
    const pauseIcon = document.getElementById('btnPauseExecutionIcon');
    const pauseBtn = document.getElementById('btnPauseExecution');

    const isCurrentlyPaused = pauseLbl && pauseLbl.textContent.trim().toLowerCase() === 'resume';

    if (isCurrentlyPaused) {
        // RESUME ACTION
        if (pauseLbl) pauseLbl.textContent = 'Resuming...';
        try {
            const res = await fetch('/api/chat/execution/resume', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_name: projName })
            });
            const data = await res.json();
            if (pauseLbl) pauseLbl.textContent = 'Pause';
            if (pauseIcon) pauseIcon.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>';
            if (pauseBtn) {
                pauseBtn.style.color = '#f59e0b';
                pauseBtn.style.borderColor = 'rgba(245, 158, 11, 0.4)';
                pauseBtn.style.background = 'rgba(245, 158, 11, 0.1)';
            }
        } catch (e) {
            alert("Error resuming: " + e.message);
        }
    } else {
        // PAUSE ACTION
        if (pauseLbl) pauseLbl.textContent = 'Pausing...';
        try {
            const res = await fetch('/api/chat/execution/pause', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_name: projName })
            });
            const data = await res.json();
            if (pauseLbl) pauseLbl.textContent = 'Resume';
            if (pauseIcon) pauseIcon.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>';
            if (pauseBtn) {
                pauseBtn.style.color = '#10b981';
                pauseBtn.style.borderColor = 'rgba(16, 185, 129, 0.4)';
                pauseBtn.style.background = 'rgba(16, 185, 129, 0.1)';
            }
        } catch (e) {
            console.error("Pause request error:", e);
        }
    }
};

window.handleCancelExecutionClick = async function() {
    const session = getActiveSession();
    const projName = window.activeGeneratingProject || (session ? session.projectName : 'default_project');
    const confirmed = confirm("Are you sure you want to stop execution? Your workspace files are preserved.");
    if (!confirmed) return;

    try {
        const res = await fetch('/api/chat/execution/cancel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ project_name: projName, rollback: false })
        });
        const data = await res.json();
        const execControls = document.getElementById('activeExecutionControls');
        const sendBtn = document.getElementById('btnSendChat');
        if (execControls) execControls.style.display = 'none';
        if (sendBtn) {
            sendBtn.style.display = 'inline-flex';
            sendBtn.disabled = false;
            sendBtn.innerHTML = '<span>Send</span> <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-left:4px;"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>';
        }
        window.isChatGenerating = false;
        alert("Execution cancelled by user. You can start a new prompt or click Undo to revert workspace files.");
    } catch (e) {
        console.error("Cancel request error:", e);
    }
};

window.openComputeBoundaryModal = function(boundaryData) {
    const modal = document.getElementById('computeBoundaryModal');
    if (modal) modal.style.display = 'flex';
};

window.closeComputeBoundaryModal = function() {
    const modal = document.getElementById('computeBoundaryModal');
    if (modal) modal.style.display = 'none';
};

window.resolveComputeBoundaryChoice = async function(choice) {
    const session = getActiveSession();
    const projName = window.activeGeneratingProject || (session ? session.projectName : 'default_project');
    window.closeComputeBoundaryModal();

    if (choice === 'cancel') {
        try {
            await fetch('/api/chat/execution/cancel', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_name: projName, rollback: true })
            });
            alert("Cancelled execution and rolled back workspace to pre-turn snapshot.");
        } catch (e) {
            alert("Error: " + e.message);
        }
        return;
    }

    // Cascade to balanced or cpu_safe
    try {
        const res = await fetch('/api/chat/execution/resume', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project_name: projName,
                new_tier: choice
            })
        });
        const data = await res.json();
        alert(`Cascaded execution to ${choice === 'balanced' ? 'Local RTX 3050' : 'CPU Safe Mode'}! Continuing task...`);
        await window.refreshComputePolicyStatus();
    } catch (e) {
        alert("Failed to cascade execution: " + e.message);
    }
};

