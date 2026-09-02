const API_BASE = "http://127.0.0.1:9067";
let queue = [];
let currentIndex = -1;
let trimIn = 0;
let trimOut = null;
let isDragging = false;

const elQueueList = document.getElementById('queueList');
const elQueueCount = document.getElementById('queueCount');
const elPlayerArea = document.getElementById('playerArea');
const elEmptyArea = document.getElementById('emptyArea');
const vid = document.getElementById('vidPlayer');

const elTimeCurrent = document.getElementById('timeCurrent');
const elTimeTotal = document.getElementById('timeTotal');
const elTimeTrimIn = document.getElementById('timeTrimIn');
const elTimeTrimOut = document.getElementById('timeTrimOut');

const scrubber = document.getElementById('scrubber');
const playhead = document.getElementById('playhead');
const trimHighlight = document.getElementById('trimHighlight');

async function fetchQueue() {
    try {
        const res = await fetch(`${API_BASE}/api/assets/review`);
        const data = await res.json();
        queue = data.assets;
        renderQueue();
        if (queue.length > 0 && currentIndex === -1) {
            loadAsset(0);
        } else if (queue.length === 0) {
            showEmpty();
        }
    } catch (err) {
        console.error("Failed to fetch queue", err);
    }
}

function renderQueue() {
    elQueueCount.textContent = queue.length;
    elQueueList.innerHTML = "";
    queue.forEach((asset, idx) => {
        const div = document.createElement('div');
        div.className = `queue-item ${idx === currentIndex ? 'active' : ''}`;
        div.onclick = () => loadAsset(idx);
        
        const title = document.createElement('div');
        title.className = 'title';
        title.textContent = asset.source_file_name;
        
        const meta = document.createElement('div');
        meta.className = 'meta';
        meta.textContent = `${asset.brand || 'No Brand'} / ${asset.tier || 'No Tier'}`;
        
        div.appendChild(title);
        div.appendChild(meta);
        elQueueList.appendChild(div);
    });
}

function showEmpty() {
    elPlayerArea.style.display = 'none';
    elEmptyArea.style.display = 'flex';
}

function loadAsset(index) {
    if (index < 0 || index >= queue.length) return;
    currentIndex = index;
    const asset = queue[index];
    
    trimIn = 0;
    trimOut = null;
    
    if (asset.metadata && asset.metadata.start_time !== undefined) {
        trimIn = parseFloat(asset.metadata.start_time);
        if (asset.metadata.duration !== undefined) {
            trimOut = trimIn + parseFloat(asset.metadata.duration);
        }
    }
    
    vid.src = `${API_BASE}/api/media/${asset.asset_id}`;
    vid.load();
    vid.play().catch(e => console.log("Autoplay prevented"));
    
    elPlayerArea.style.display = 'flex';
    elEmptyArea.style.display = 'none';
    
    renderQueue();
    updateTrimVisuals();
}

function formatTime(sec) {
    if (isNaN(sec)) return "00:00.00";
    const m = Math.floor(sec / 60).toString().padStart(2, '0');
    const s = Math.floor(sec % 60).toString().padStart(2, '0');
    const ms = Math.floor((sec % 1) * 100).toString().padStart(2, '0');
    return `${m}:${s}.${ms}`;
}

vid.addEventListener('timeupdate', () => {
    elTimeCurrent.textContent = formatTime(vid.currentTime);
    const pct = (vid.currentTime / vid.duration) * 100;
    playhead.style.left = `${pct}%`;
});

vid.addEventListener('loadedmetadata', () => {
    elTimeTotal.textContent = formatTime(vid.duration);
    if (trimOut === null || trimOut > vid.duration) {
        trimOut = vid.duration;
    }
    updateTrimVisuals();
    
    const asset = queue[currentIndex];
    if (asset && asset.metadata && asset.metadata.gemini_reasoning) {
        appendMessage(`AI Suggestion loaded: ${asset.metadata.gemini_reasoning}`, 'agent');
    }
});

function updatePlayheadFromEvent(e) {
    const rect = scrubber.getBoundingClientRect();
    let pct = (e.clientX - rect.left) / rect.width;
    pct = Math.max(0, Math.min(1, pct));
    vid.currentTime = pct * vid.duration;
}

scrubber.addEventListener('mousedown', (e) => {
    isDragging = true;
    updatePlayheadFromEvent(e);
});

window.addEventListener('mousemove', (e) => {
    if (isDragging) {
        updatePlayheadFromEvent(e);
    }
});

window.addEventListener('mouseup', () => {
    isDragging = false;
});

document.getElementById('btnSetIn').onclick = () => {
    trimIn = vid.currentTime;
    if (trimOut !== null && trimIn >= trimOut) trimOut = vid.duration;
    updateTrimVisuals();
};

document.getElementById('btnSetOut').onclick = () => {
    trimOut = vid.currentTime;
    if (trimIn >= trimOut) trimIn = 0;
    updateTrimVisuals();
};

document.getElementById('btnResetTrim').onclick = () => {
    trimIn = 0;
    trimOut = vid.duration;
    updateTrimVisuals();
};

function updateTrimVisuals() {
    elTimeTrimIn.textContent = formatTime(trimIn);
    elTimeTrimOut.textContent = formatTime(trimOut);
    
    if (vid.duration) {
        const inPct = (trimIn / vid.duration) * 100;
        const outPct = (trimOut / vid.duration) * 100;
        trimHighlight.style.left = `${inPct}%`;
        trimHighlight.style.width = `${outPct - inPct}%`;
    }
}

function triggerQuickAction(promptText) {
    elChatInput.value = promptText;
    sendChat();
}

document.getElementById('btnQuickShort').onclick = () => {
    const dur = (trimOut !== null && trimIn !== null) ? (trimOut - trimIn).toFixed(2) : "full";
    triggerQuickAction(`Format this as a YouTube Short starting at ${trimIn.toFixed(2)}s for ${dur}s`);
};

document.getElementById('btnQuickTrim').onclick = () => {
    const dur = (trimOut !== null && trimIn !== null) ? (trimOut - trimIn).toFixed(2) : "full";
    triggerQuickAction(`Trim the video starting at ${trimIn.toFixed(2)}s with a duration of ${dur}s`);
};

document.getElementById('btnQuickRebuild').onclick = () => triggerQuickAction('Rebuild the timeline');
document.getElementById('btnQuickExport').onclick = () => triggerQuickAction('Export this video');

// Chat Integration
const elChatHistory = document.getElementById('chatHistory');
const elChatInput = document.getElementById('chatInput');
const elBtnSendChat = document.getElementById('btnSendChat');

function appendMessage(text, role) {
    const div = document.createElement('div');
    div.className = `chat-msg ${role === 'user' ? 'chat-user' : 'chat-agent'}`;
    div.textContent = text;
    elChatHistory.appendChild(div);
    elChatHistory.scrollTop = elChatHistory.scrollHeight;
}

async function sendChat() {
    const msg = elChatInput.value.trim();
    if (!msg) return;
    
    appendMessage(msg, 'user');
    elChatInput.value = '';
    
    // Show loading
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'chat-msg chat-agent';
    loadingDiv.textContent = '...';
    loadingDiv.id = 'chatLoading';
    elChatHistory.appendChild(loadingDiv);
    elChatHistory.scrollTop = elChatHistory.scrollHeight;
    
    const currentAssetId = (currentIndex >= 0 && queue[currentIndex]) ? queue[currentIndex].asset_id : null;
    
    try {
        const res = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ message: msg, project_id: currentAssetId })
        });
        const data = await res.json();
        
        document.getElementById('chatLoading')?.remove();
        
        if (data.status === 'success') {
            appendMessage(data.response, 'agent');
        } else {
            appendMessage("Error: " + data.response, 'agent');
        }
    } catch(e) {
        document.getElementById('chatLoading')?.remove();
        appendMessage("Failed to reach AI.", 'agent');
    }
}

async function runCouncilThink() {
    const currentAssetId = (currentIndex >= 0 && queue[currentIndex]) ? queue[currentIndex].asset_id : null;
    if (!currentAssetId) return;
    
    appendMessage("Consulting the Council...", 'user');
    
    // Create a thought bubble
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'chat-msg chat-agent';
    loadingDiv.style.fontStyle = 'italic';
    loadingDiv.style.opacity = '0.8';
    loadingDiv.textContent = 'Thinking...';
    loadingDiv.id = 'chatLoading';
    elChatHistory.appendChild(loadingDiv);
    elChatHistory.scrollTop = elChatHistory.scrollHeight;

    try {
        const response = await fetch(`${API_BASE}/api/council_think`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ message: "Please analyze this.", project_id: currentAssetId })
        });

        const data = await response.json();
        loadingDiv.remove();
        if (data.status === 'success') {
            appendMessage("Polyglot Pipeline: " + data.response, 'agent');
        } else {
            appendMessage("Error: " + data.response, 'agent');
        }
    } catch(e) {
        document.getElementById('chatLoading')?.remove();
        appendMessage("Failed to reach Council.", 'agent');
    }
}

document.getElementById('btnCouncilThink').onclick = runCouncilThink;

elBtnSendChat.onclick = sendChat;
elChatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendChat();
});

// Draft State Polling
async function pollDraftState() {
    try {
        const res = await fetch(`${API_BASE}/api/draft_state`);
        const data = await res.json();
        const panel = document.getElementById('draftPanel');
        
        if (data.status === 'AWAITING_HUMAN_COMMIT') {
            panel.style.display = 'block';
            document.getElementById('draftConcept').innerText = "Concept: " + data.concept;
            document.getElementById('draftSummary').innerText = data.ai_summary;
        } else {
            panel.style.display = 'none';
        }
    } catch(e) {}
    setTimeout(pollDraftState, 3000);
}

document.getElementById('btnCommitRender').addEventListener('click', async () => {
    document.getElementById('btnCommitRender').innerText = "Committing...";
    try {
        const res = await fetch(`${API_BASE}/api/commit_render`, { method: 'POST' });
        const data = await res.json();
        if (data.status === 'success') {
            document.getElementById('btnCommitRender').innerText = "Committed!";
            setTimeout(() => { document.getElementById('draftPanel').style.display = 'none'; }, 2000);
        }
    } catch(e) {
        document.getElementById('btnCommitRender').innerText = "Error committing";
    }
});

// Initial fetch
fetchQueue();
pollDraftState();
