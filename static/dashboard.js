let currentUser = null;
let audioEnabled = false;
let audioContext = null;
// Audio State
const ALARM_DURATION_MS = 60000; // 1 minute
let alarmInterval = null;
let alarmTimeout = null;
let isAlarmPlaying = false;
let lastAlertId = 0;
const playedReplies = new Set();
const airportNames = {}; // Cache for code -> name
const openReplyBoxes = new Set(); // Track open reply box IDs
const replyInputValues = {}; // Store unsent reply text
let lastAlertsData = null; // To avoid unnecessary re-renders
let lastChatData = null; // To avoid unnecessary chat re-renders
let lastChatMsgId = 0; // Track last message to notify only once
let globalLastMsgId = 0; // Track overall latest received message ID


// Init
document.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = '/login';
        return;
    }

    // Decode token to get user info
    const payload = JSON.parse(atob(token.split('.')[1]));
    // We need ID. Let's fetch /users/me or similar.
    // For now, let's just fetch a new endpoint /auth/me
    const meRes = await fetch('/auth/me', {
        headers: { 'Authorization': `Bearer ${token}` }
    });
    if (meRes.ok) {
        currentUser = await meRes.json();
    } else {
        currentUser = { username: payload.sub, role: payload.role, id: payload.id || 0 }; // Fallback
    }

    const displayName = currentUser.full_name || currentUser.username;
    document.getElementById('user-role-display').innerText = `Logged in as: ${displayName} (${currentUser.role})`;

    // UI Setup based on role
    if (currentUser.role === 'regional_airport') {
        document.getElementById('create-alert-section').style.display = 'block';
        // Load chat with Admin (ID 1 usually, but we need to fetch partner ID or just send to Admin)
        // For now, let's assume Admin ID is 1.
        loadChat(1);

        // Initialize Preview and Listeners
        initPreview();

    } else if (currentUser.role === 'mwo_admin') {
        document.getElementById('admin-controls').style.display = 'block';
        if (document.getElementById('history-section')) {
            document.getElementById('history-section').style.display = 'block';
        }
        document.getElementById('chat-partner-select').style.display = 'block';
        // Load list of airports for chat (Mock for now or fetch)
        loadAirportList();

        // Show Admin History Filter
        document.getElementById('admin-history-filter').style.display = 'block';
        // Populate it (re-use loadAirportList logic or separate)
        loadHistoryAirports();

        // Load names for crystal clear audio
        fetchAirportNames();
    }

    // Initial Fetch
    fetchActiveAlerts();

    // Polling
    setInterval(fetchActiveAlerts, 2000); // 2s polling for faster sound response
    setInterval(pollChat, 3000); // 3s polling for chat messages
    setInterval(checkGlobalNotifications, 4000); // 4s polling for global notifications

    if (currentUser.role === 'mwo_admin') {
        // Stop alarm on any click
        document.addEventListener('click', (e) => {
            if (isAlarmPlaying) {
                // If the click was not on the stop button itself (to avoid redundant calls, although stopAlarm is safe)
                if (e.target.id !== 'stop-alarm-btn') {
                    stopAlarm();
                }
            }
        });
    }
});

function initPreview() {
    // We do NOT auto-fill visible fields anymore. User enters HHMM only.

    // Attach event listeners to all inputs in the form
    const form = document.getElementById('alertForm');
    const inputs = form.querySelectorAll('input, select');
    inputs.forEach(input => {
        input.addEventListener('input', updatePreview);
        input.addEventListener('change', updatePreview);
    });

    // Initial update
    updatePreview();
}

function getCurrentDateDD() {
    const now = new Date();
    // Return UTC Day
    return String(now.getUTCDate()).padStart(2, '0');
}

function updatePreview() {
    const formData = new FormData(document.getElementById('alertForm'));

    const airport = formData.get('airport_code') || 'VASD';
    const seq = formData.get('seq_num') || '1';

    // User inputs only Time (HHMM)
    const validFromTime = formData.get('valid_from') || '';
    const validToTime = formData.get('valid_to') || '';

    // Prepend Current Date (DD)
    const day = getCurrentDateDD();

    // Use fallback if empty
    // If empty input, do we show just DD? Or DDHHMM?
    // Let's show DDHHMM as placeholder in preview if empty.

    let validFrom = validFromTime ? (day + validFromTime) : 'DDHHMM';
    let validTo = validToTime ? (day + validToTime) : 'DDHHMM';

    const type = formData.get('type');

    // Header
    // VASD 080615 AD WRNG 1 VALID 080630/081030 

    let text = `${airport} ${validFrom} AD WRNG ${seq} VALID ${validFrom}/${validTo}`;

    if (type === 'Wind') {
        // SFC WSPD 17KT MAX27 FROM 020 DEG FCST NC=
        const speed = formData.get('wind_speed') || '00';
        const gust = formData.get('max_gust') || '00';
        const dir = formData.get('wind_dir') || '000';
        const wType = formData.get('wind_type') || 'FCST';
        const wChange = formData.get('wind_change') || 'NC';

        text += ` SFC WSPD ${speed}KT MAX${gust} FROM ${dir} DEG ${wType} ${wChange}=`;
    } else {
        // TS Format
        const tIntensity = formData.get('ts_intensity') || '';
        const tType = formData.get('ts_type') || '';
        const tChange = formData.get('ts_change') || '';

        // Example: TS FBL OBS NC=
        text += ` TS ${tIntensity} ${tType} ${tChange}=`;
    }

    // Update Textarea Value
    // We update it unless user is typing IN IT? 
    // Requirement is editable preview.
    // For now always overwrite. 
    document.getElementById('alert-preview').value = text.toUpperCase();
}

function toggleAlertFields() {
    const type = document.getElementById('alertType').value;
    if (type === 'Wind') {
        document.getElementById('wind-fields').style.display = 'block';
        document.getElementById('ts-fields').style.display = 'none';
    } else {
        document.getElementById('wind-fields').style.display = 'none';
        document.getElementById('ts-fields').style.display = 'block';
    }
    updatePreview();
}

async function submitAlert(event) {
    event.preventDefault();
    const form = event.target;

    const formData = new FormData(form);
    const type = formData.get('type');

    const generatedText = document.getElementById('alert-preview').value;

    // We must ensure the valid_from/to sent to backend includes the date
    const day = getCurrentDateDD();
    // If user typed 1230, validFrom = DD1230
    const validFrom = day + (formData.get('valid_from') || '');
    const validTo = day + (formData.get('valid_to') || '');

    let content = {};

    if (type === 'Wind') {
        content = {
            speed: formData.get('wind_speed'),
            gust: formData.get('max_gust'),
            direction: formData.get('wind_dir'),
            w_type: formData.get('wind_type'),
            change: formData.get('wind_change'),

            airport: formData.get('airport_code'),
            seq: formData.get('seq_num'),
            valid_from: validFrom,
            valid_to: validTo,
            generated_text: generatedText
        };
    } else {
        content = {
            type: formData.get('ts_type'),
            intensity: formData.get('ts_intensity'),
            change: formData.get('ts_change'),

            airport: formData.get('airport_code'),
            seq: formData.get('seq_num'),
            valid_from: validFrom,
            valid_to: validTo,
            generated_text: generatedText
        };
    }

    content.time = validFrom;

    try {
        const response = await fetch('/alerts/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({ type, content })
        });

        if (response.ok) {
            alert('Alert sent successfully!');
            fetchActiveAlerts();
            form.reset();
            updatePreview();
            // initPreview(); 
        } else {
            alert('Failed to send alert');
        }
    } catch (e) {
        console.error(e);
    }
}

async function fetchActiveAlerts() {
    try {
        const response = await fetch('/alerts/active', {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` },
            cache: 'no-store'
        });
        if (response.ok) {
            const alerts = await response.json();

            // Optimization: Only re-render if data has changed
            const currentDataStr = JSON.stringify(alerts);
            if (currentDataStr !== lastAlertsData) {
                lastAlertsData = currentDataStr;
                renderAlerts(alerts);
            }

            // Audio Trigger for Admin
            if (currentUser && currentUser.role === 'mwo_admin' && audioEnabled) {
                // Check for new alerts (id > lastAlertId)
                const newAlerts = alerts.filter(a => a.id > lastAlertId);
                // If we have any new alerts, play the warning sound
                if (newAlerts.length > 0) {
                    const latest = newAlerts[0];
                    const airportCode = latest.content.airport || "Aerodrome";
                    const airportDisplayName = airportNames[airportCode] || airportCode;
                    triggerAlarm(airportDisplayName);
                }
            }

            // Audio Trigger for Regional User (Admin Reply)
            if (currentUser && currentUser.role === 'regional_airport' && audioEnabled) {
                alerts.forEach(a => {
                    if (a.admin_reply && !playedReplies.has(a.id)) {
                        speak(`Admin replied: ${a.admin_reply}`);
                        playedReplies.add(a.id);
                    }
                });
            }

            if (alerts.length > 0) {
                lastAlertId = Math.max(...alerts.map(a => a.id));
            }
        }
    } catch (e) {
        console.error(e);
    }
}

function renderAlerts(alerts) {
    const list = document.getElementById('active-alerts-list');
    list.innerHTML = '';
    alerts.forEach(alert => {
        const div = document.createElement('div');
        div.className = 'alert-item alert-active';
        div.style.padding = '10px';
        div.style.marginBottom = '10px';
        div.style.background = '#fff3cd';

        let contentStr = '';

        // Use generated_text if available
        if (alert.content.generated_text) {
            contentStr = `<strong>${alert.content.generated_text}</strong>`;
        } else {
            if (alert.content.airport) {
                contentStr = `<strong>${alert.content.airport} WRNG ${alert.content.seq}</strong><br>`;
            }

            if (alert.type === 'Wind') {
                contentStr += `Wind: ${alert.content.direction}° ${alert.content.speed}KT G${alert.content.gust}KT`;
            } else {
                contentStr += `TS: ${alert.content.intensity} ${alert.content.type} ${alert.content.change}`;
            }
        }

        // Show Admin Reply if exists
        let replyHtml = '';
        if (alert.admin_reply) {
            replyHtml = `<div style="margin-top: 5px; padding: 5px; background: #e0f7fa; border-left: 3px solid #00acc1;">
                <strong>Admin Reply:</strong> ${alert.admin_reply}
            </div>`;
        }

        div.innerHTML = `
            <strong>${alert.type} Alert</strong> <br>
            ${contentStr} <br>
            <small>Valid: ${alert.content.valid_from || alert.content.time} UTC</small>
            ${replyHtml}
            ${currentUser && currentUser.role === 'mwo_admin' ? `<div style="margin-top: 5px;">
                <button onclick="finalizeAlert(${alert.id})">Finalize</button>
                <button onclick="toggleReplyInput(${alert.id})" style="background-color: #008CBA;">Reply</button>
                <div id="reply-container-${alert.id}" class="reply-input-container" style="display: ${openReplyBoxes.has(alert.id) ? 'flex' : 'none'};">
                    <input type="text" id="reply-input-${alert.id}" placeholder="Enter reply..." 
                        value="${replyInputValues[alert.id] || ''}"
                        oninput="saveReplyText(${alert.id}, this.value)">
                    <div class="reply-actions">
                        <button onclick="submitReply(${alert.id})" style="background-color: #28a745;">Send</button>
                        <button onclick="toggleReplyInput(${alert.id})" style="background-color: #6c757d;">Cancel</button>
                    </div>
                </div>
            </div>` : ''}
        `;
        list.appendChild(div);
    });
}

async function finalizeAlert(id) {
    const warning = prompt("Enter Final Warning Text:");
    if (!warning) return;

    try {
        const response = await fetch(`/alerts/${id}/finalize?warning_text=${encodeURIComponent(warning)}`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });

        if (response.ok) {
            fetchActiveAlerts();
        }
    } catch (e) {
        console.error(e);
    }
}

// Chat functions
let currentChatPartnerId = null;

async function loadChat(partnerId) {
    if (currentChatPartnerId !== parseInt(partnerId)) {
        lastChatData = null; // Force re-render for new partner
        lastChatMsgId = 0;   // Reset message tracking
    }
    currentChatPartnerId = parseInt(partnerId);

    // Initial fetch to show immediate results
    console.log(`Loading chat with partner: ${currentChatPartnerId}`);
    fetchChatUpdates(currentChatPartnerId);
}

async function pollChat() {
    if (currentChatPartnerId) {
        fetchChatUpdates(currentChatPartnerId);
    }
}

async function fetchChatUpdates(partnerId) {
    if (!partnerId) return;
    try {
        const response = await fetch(`/chat/${partnerId}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` },
            cache: 'no-store'
        });
        if (response.ok) {
            const chats = await response.json();

            // Optimization: Only re-render if data has changed
            const currentChatDataStr = JSON.stringify(chats);
            if (currentChatDataStr !== lastChatData) {
                lastChatData = currentChatDataStr;
                renderChat(chats);

                // Keep local tracking for consistency, but notification is now global
                if (chats.length > 0) {
                    lastChatMsgId = chats[chats.length - 1].id;
                }
            }
        }
    } catch (e) {
        console.error(e);
    }
}

async function checkGlobalNotifications() {
    try {
        const response = await fetch('/chat/received/latest', {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` },
            cache: 'no-store'
        });
        if (response.ok) {
            const latestChat = await response.json();

            // If it's a new message (ID higher than last seen)
            // and NOT the first load (globalLastMsgId > 0)
            if (globalLastMsgId > 0 && latestChat.id > globalLastMsgId) {
                playNotificationPing();
            }

            // Update last seen ID
            globalLastMsgId = latestChat.id;
        }
    } catch (e) {
        // Handle 404 (no messages yet) or other issues
        if (e.status !== 404) console.debug("Global notification check:", e);
    }
}

function renderChat(chats) {
    const chatBox = document.getElementById('chat-box');
    chatBox.innerHTML = '';
    chats.forEach(chat => {
        const div = document.createElement('div');
        const isMe = chat.sender_id === currentUser.id;

        div.className = 'chat-message';
        div.style.textAlign = isMe ? 'right' : 'left';
        div.style.margin = '5px';
        div.innerHTML = `<span style="background: ${isMe ? '#dcf8c6' : '#fff'}; padding: 5px 10px; border-radius: 10px; display: inline-block;">${chat.message}</span>`;
        chatBox.appendChild(div);
    });
    chatBox.scrollTop = chatBox.scrollHeight;
}

async function sendChat(event) {
    event.preventDefault();
    const input = document.getElementById('chat-message');
    const message = input.value;
    if (!message || !currentChatPartnerId) return;

    try {
        const response = await fetch('/chat/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({ receiver_id: currentChatPartnerId, message: message })
        });

        if (response.ok) {
            input.value = '';
            lastChatData = null; // Force re-render
            fetchChatUpdates(currentChatPartnerId);
            playNotificationPing();
        }
    } catch (e) {
        console.error(e);
    }
}

async function loadHistoryAirports() {
    const select = document.getElementById('history-airport-select');
    // Clear existing, keep 'All'
    select.innerHTML = '<option value="">All Airports</option>';

    try {
        const response = await fetch('/admin/airports', {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        if (response.ok) {
            const airports = await response.json();
            airports.forEach(a => {
                const option = document.createElement('option');
                option.value = a.code;
                option.innerText = `${a.code} - ${a.name}`;
                select.appendChild(option);
            });
        }
    } catch (e) {
        console.error("Failed to load airports", e);
    }
}


async function fetchAirportNames() {
    try {
        const response = await fetch('/admin/airports', {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        if (response.ok) {
            const airports = await response.json();
            airports.forEach(a => {
                airportNames[a.code] = a.name;
            });
        }
    } catch (e) {
        console.error("Failed to load airport names", e);
    }
}

async function loadAirportList() {
    const select = document.getElementById('chat-partner');
    select.innerHTML = '<option value="">Select Airport...</option>';

    try {
        const response = await fetch('/admin/airports', {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        if (response.ok) {
            const airports = await response.json();
            airports.forEach((a, index) => {
                const option = document.createElement('option');
                option.value = a.id;
                option.innerText = `${a.code} - ${a.name}`;
                select.appendChild(option);

                // Set default partner to first airport if any
                if (index === 0) {
                    select.value = a.id;
                    currentChatPartnerId = parseInt(a.id);
                    loadChat(a.id);
                }
            });
        }
    } catch (e) {
        console.error("Failed to load airport list", e);
    }
}

function toggleAudio() {
    audioEnabled = !audioEnabled;
    const btn = document.getElementById('audio-btn');
    btn.innerText = audioEnabled ? "Disable Audio" : "Enable Audio";
    btn.style.backgroundColor = audioEnabled ? "#dc3545" : "#0055a5";

    if (audioEnabled) {
        speak("Audio notifications enabled");
    }
}

function speak(text) {
    if ('speechSynthesis' in window) {
        // Cancel any ongoing speech to ensure current one is heard immediately and clearly
        window.speechSynthesis.cancel();

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.volume = 1.0; // Max volume
        utterance.rate = 0.9;   // Slightly slower for better clarity
        utterance.pitch = 1.0;

        // Try to find a clear English voice if available
        const voices = window.speechSynthesis.getVoices();
        const preferredVoice = voices.find(v => v.lang.includes('en-US') || v.lang.includes('en-GB'));

        if (preferredVoice) utterance.voice = preferredVoice;

        window.speechSynthesis.speak(utterance);
    }
}

function playNotificationPing() {
    if (!audioEnabled) return;

    try {
        if (!audioContext) {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }

        const osc = audioContext.createOscillator();
        const gain = audioContext.createGain();

        osc.type = 'sine';
        osc.frequency.setValueAtTime(880, audioContext.currentTime); // A5

        gain.gain.setValueAtTime(0, audioContext.currentTime);
        gain.gain.linearRampToValueAtTime(0.2, audioContext.currentTime + 0.02);
        gain.gain.linearRampToValueAtTime(0, audioContext.currentTime + 0.2);

        osc.connect(gain);
        gain.connect(audioContext.destination);

        osc.start();
        osc.stop(audioContext.currentTime + 0.2);
    } catch (e) {
        console.error("Audio error", e);
    }
}



function stopAlarm() {
    if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
    }
    if (alarmInterval) clearInterval(alarmInterval);
    if (alarmTimeout) clearTimeout(alarmTimeout);

    isAlarmPlaying = false;
    const stopBtn = document.getElementById('stop-alarm-btn');
    if (stopBtn) stopBtn.style.display = 'none';
}

function triggerAlarm(airportName) {
    if (isAlarmPlaying) return; // Already playing

    isAlarmPlaying = true;
    const stopBtn = document.getElementById('stop-alarm-btn');
    if (stopBtn) {
        stopBtn.style.display = 'inline-block';
    }

    const text = `Attention! Aerodrome Warning. Received alert from ${airportName}. Please check Active Alerts. Repeating, Aerodrome Warning received.`;

    // Play immediately
    speak(text);

    // Loop for 1 minute (every 8 seconds to allow full speech)
    alarmInterval = setInterval(() => {
        speak(text);
    }, 8000);

    // Stop after 1 minute
    alarmTimeout = setTimeout(() => {
        stopAlarm();
    }, ALARM_DURATION_MS);
}

// Duplicate function code removed


function toggleReplyInput(id) {
    const container = document.getElementById(`reply-container-${id}`);
    const isHidden = container.style.display === 'none';

    if (isHidden) {
        container.style.display = 'flex';
        openReplyBoxes.add(id);
        const input = document.getElementById(`reply-input-${id}`);
        input.focus();
        // Add enter key listener
        input.onkeypress = function (e) {
            if (e.key === 'Enter') {
                submitReply(id);
            }
        };
    } else {
        container.style.display = 'none';
        openReplyBoxes.delete(id);
    }
}

function saveReplyText(id, value) {
    replyInputValues[id] = value;
}

async function submitReply(id) {
    const input = document.getElementById(`reply-input-${id}`);
    const reply = input.value;
    if (!reply) return;

    try {
        const response = await fetch(`/alerts/${id}/reply?reply_text=${encodeURIComponent(reply)}`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });

        if (response.ok) {
            // Success: clear state for this box
            openReplyBoxes.delete(id);
            delete replyInputValues[id];

            // Force re-render by clearing lastAlertsData
            lastAlertsData = null;
            fetchActiveAlerts();
        } else {
            alert("Failed to send reply");
        }
    } catch (e) {
        console.error(e);
    }
}

async function replyToAlert(id) {
    // Deprecated for toggleReplyInput but keeping for potential legacy usage or quick fix
    const reply = prompt("Enter Reply:");
    if (!reply) return;

    try {
        const response = await fetch(`/alerts/${id}/reply?reply_text=${encodeURIComponent(reply)}`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });

        if (response.ok) {
            fetchActiveAlerts();
        }
    } catch (e) {
        console.error(e);
    }
}
// Admin Functions
function toggleAdminPanel() {
    const panel = document.getElementById('admin-panel');
    if (panel.style.display === 'none') {
        panel.style.display = 'block';
    } else {
        panel.style.display = 'none';
    }
}

async function addAirport(event) {
    event.preventDefault();
    const code = document.getElementById('new-airport-code').value;
    const name = document.getElementById('new-airport-name').value;
    const password = document.getElementById('new-airport-password').value;
    const msgDiv = document.getElementById('admin-msg');

    try {
        const response = await fetch('/admin/add_airport', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({
                airport_code: code,
                airport_name: name,
                password: password
            })
        });

        if (response.ok) {
            const data = await response.json();
            msgDiv.innerText = `Success: ${data.message} (User: ${data.username})`;
            msgDiv.style.color = 'green';
            document.getElementById('new-airport-code').value = '';
            document.getElementById('new-airport-name').value = '';
            document.getElementById('new-airport-password').value = '';
            // Refresh airport list if chat uses it
            loadAirportList();
        } else {
            const err = await response.json();
            msgDiv.innerText = `Error: ${err.detail}`;
            msgDiv.style.color = 'red';
        }
    } catch (e) {
        console.error(e);
        msgDiv.innerText = "Network error";
        msgDiv.style.color = 'red';
    }
}

// History Functions
async function searchHistory() {
    const date = document.getElementById('history-date').value;
    const month = document.getElementById('history-month').value;
    const airport = document.getElementById('history-airport-select').value;

    let url = '/alerts/history?';
    if (date) url += `date=${date}&`;
    if (month) url += `month=${month}&`; // Fixed bug: else if prevented both (though technically UI might only allow one or backend handles priority)
    // Actually typically one or the other. Backend handles date priority. Using Query Params is fine.

    if (airport) url += `airport_code=${airport}`;

    // Clear previous
    const list = document.getElementById('history-list');
    list.innerHTML = '<p>Loading...</p>';

    try {
        const response = await fetch(url, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });

        if (response.ok) {
            const alerts = await response.json();
            renderHistory(alerts);
        } else {
            const err = await response.json();
            list.innerHTML = `<p style="color: red;">Error: ${err.detail || 'Failed'}</p>`;
        }
    } catch (e) {
        console.error(e)
        list.innerHTML = `<p style="color: red;">Network Error</p>`;
    }
}

function renderHistory(alerts) {
    const list = document.getElementById('history-list');
    list.innerHTML = '';

    if (alerts.length === 0) {
        list.innerHTML = '<p>No alerts found.</p>';
        return;
    }

    alerts.forEach(alert => {
        const div = document.createElement('div');
        div.className = 'alert-item'; // Use same styling or similar
        div.style.padding = '8px';
        div.style.marginBottom = '8px';
        div.style.border = '1px solid #ddd';
        div.style.borderRadius = '4px';
        div.style.background = '#f9f9f9';

        // Simplified view for history
        let contentStr = '';
        if (alert.content.generated_text) contentStr = `<strong>${alert.content.generated_text}</strong>`;
        else contentStr = `Alert Type: ${alert.type}`;

        // Show Admin Reply
        let replyHtml = '';
        if (alert.admin_reply) {
            replyHtml = `<div style="font-size: 0.9em; color: #00796b; margin-top: 4px;">Reply: ${alert.admin_reply}</div>`;
        }

        const dateStr = new Date(alert.created_at).toLocaleString();

        div.innerHTML = `
            <div style="font-size: 0.85em; color: #555;">${dateStr} (Sender: ${alert.sender_id})</div>
            ${contentStr}
            ${replyHtml}
        `;
        list.appendChild(div);
    });
}

function clearHistory() {
    document.getElementById('history-date').value = '';
    document.getElementById('history-month').value = '';
    document.getElementById('history-airport-select').value = '';
    document.getElementById('history-list').innerHTML = '<p style="color: grey; font-size: 0.9em;">Select a date or month to view history.</p>';
}

async function promptAdminPassword() {
    const password = prompt("Please re-enter your Admin Password to view user passwords:");
    if (!password) return;

    try {
        const response = await fetch('/admin/view_passwords', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({ admin_password: password })
        });

        if (response.ok) {
            const users = await response.json();
            renderPasswordList(users);
        } else {
            alert("Incorrect Password or Error");
        }
    } catch (e) {
        console.error(e);
        alert("Network Error");
    }
}

function renderPasswordList(users) {
    const container = document.getElementById('password-list-container');
    container.style.display = 'block';

    let html = '<table border="1" style="width:100%; border-collapse: collapse;"><tr><th>Airport</th><th>Username</th><th>Password</th></tr>';
    users.forEach(u => {
        html += `<tr>
            <td style="padding: 5px;">${u.airport_code}</td>
            <td style="padding: 5px;">${u.username}</td>
            <td style="padding: 5px;">${u.password}</td>
        </tr>`;
    });
    html += '</table>';
    container.innerHTML = html;
}

function logout() {
    localStorage.removeItem('token');
    window.location.href = '/login';
}
