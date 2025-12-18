// State
let currentUser = null;
let audioEnabled = false;
let audioContext = null;

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
    const meRes = await fetch('/auth/me'); // Need to implement this
    if (meRes.ok) {
        currentUser = await meRes.json();
    } else {
        currentUser = { username: payload.sub, role: payload.role, id: 0 }; // Fallback
    }

    document.getElementById('user-role-display').innerText = `Logged in as: ${currentUser.username} (${currentUser.role})`;

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
        document.getElementById('history-section').style.display = 'block';
        document.getElementById('chat-partner-select').style.display = 'block';
        document.getElementById('chat-partner-select').style.display = 'block';
        // Load list of airports for chat (Mock for now or fetch)
        loadAirportList();

        // Show Admin History Filter
        document.getElementById('admin-history-filter').style.display = 'block';
        // Populate it (re-use loadAirportList logic or separate)
        loadHistoryAirports();
    }

    // Initial Fetch
    fetchActiveAlerts();

    // Polling
    setInterval(fetchActiveAlerts, 2000); // 2s polling for faster sound response
    if (currentUser.role === 'mwo_admin') {
        // Poll for new alerts to play sound
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
            headers: { 'Content-Type': 'application/json' },
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
        const response = await fetch('/alerts/active');
        if (response.ok) {
            const alerts = await response.json();
            renderAlerts(alerts);

            // Audio Trigger for Admin
            if (currentUser.role === 'mwo_admin' && alerts.length > 0 && audioEnabled) {
                // Check if new alert? For now just play if any active.
                // Better: Track seen IDs.
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
            ${currentUser.role === 'mwo_admin' ? `<div style="margin-top: 5px;">
                <button onclick="finalizeAlert(${alert.id})">Finalize</button>
                <button onclick="replyToAlert(${alert.id})" style="background-color: #008CBA;">Reply</button>
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
            method: 'POST'
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
    currentChatPartnerId = partnerId;
    const chatBox = document.getElementById('chat-box');
    chatBox.innerHTML = '<p>Loading chat...</p>';

    try {
        const response = await fetch(`/chat/${partnerId}`);
        if (response.ok) {
            const chats = await response.json();
            renderChat(chats);
        } else {
            chatBox.innerHTML = '<p>Error loading chat.</p>';
        }
    } catch (e) {
        console.error(e);
    }
}

function renderChat(chats) {
    const chatBox = document.getElementById('chat-box');
    chatBox.innerHTML = '';
    chats.forEach(chat => {
        const div = document.createElement('div');
        const isMe = chat.sender_id === (currentUser.role === 'mwo_admin' ? 1 : currentUser.id); // Hacky ID check, better to use ID from token if available
        // Actually we don't have our own ID in token payload easily unless we put it there.
        // Let's assume we can deduce "Me" if sender_id matches my ID.
        // But I didn't put ID in token. I put username.
        // I should probably fetch /users/me to get my ID or put it in token.
        // For now, let's just use username comparison if I had it, or just style based on class.
        // Let's update the token generation to include ID or fetch user info on load.

        div.className = 'chat-message';
        div.style.textAlign = chat.sender_id === currentUser.id ? 'right' : 'left'; // We need currentUser.id
        div.style.margin = '5px';
        div.innerHTML = `<span style="background: ${chat.sender_id === currentUser.id ? '#dcf8c6' : '#fff'}; padding: 5px 10px; border-radius: 10px; display: inline-block;">${chat.message}</span>`;
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
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ receiver_id: currentChatPartnerId, message: message })
        });

        if (response.ok) {
            input.value = '';
            loadChat(currentChatPartnerId);
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


async function loadAirportList() {
    // In a real app, fetch from /users/regional
    // For prototype, we know we created 'vabb_airport' (ID 2)
    // We can re-use /admin/airports if user is admin, but for chat logic we might need IDs.
    // The previous logic used hardcoded ID 2. Let's keep it simple for now or fetch.
    const select = document.getElementById('chat-partner');
    select.innerHTML = '<option value="2">VABB (Regional)</option>';
    currentChatPartnerId = 2;
    loadChat(2);
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
        const utterance = new SpeechSynthesisUtterance(text);
        window.speechSynthesis.speak(utterance);
    }
}

const ALARM_DURATION_MS = 60000; // 1 minute
let alarmInterval = null;
let alarmTimeout = null;
let isAlarmPlaying = false;

function stopAlarm() {
    if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
    }
    if (alarmInterval) clearInterval(alarmInterval);
    if (alarmTimeout) clearTimeout(alarmTimeout);

    isAlarmPlaying = false;
    document.getElementById('stop-alarm-btn').style.display = 'none';
}

function triggerAlarm(airportName) {
    if (isAlarmPlaying) return; // Already playing

    isAlarmPlaying = true;
    document.getElementById('stop-alarm-btn').style.display = 'inline-block';

    const text = `Aerodrome alert received. Warning from ${airportName}`;

    // Play immediately
    speak(text);

    // Loop every ~4 seconds (approx duration of speech)
    // Actually, speak() queues utterances. We can queue many or use interval.
    // Let's use interval every 5 seconds to be safe.
    alarmInterval = setInterval(() => {
        speak(text);
    }, 5000);

    // Stop after 1 minute
    alarmTimeout = setTimeout(() => {
        stopAlarm();
    }, ALARM_DURATION_MS);
}

// Update fetchActiveAlerts to play sound
// We need to track last alert ID to know if new one arrived.
let lastAlertId = 0;

async function fetchActiveAlerts() {
    try {
        const response = await fetch('/alerts/active');
        if (response.ok) {
            const alerts = await response.json();
            renderAlerts(alerts);

            // Audio Trigger for Admin
            if (currentUser && currentUser.role === 'mwo_admin' && audioEnabled) {
                const newAlerts = alerts.filter(a => a.id > lastAlertId);
                if (newAlerts.length > 0) {
                    newAlerts.forEach(a => {
                        const airportName = a.content.airport || a.sender_id;
                        triggerAlarm(airportName);
                    });
                }
            }

            // Audio Trigger for User (Admin Reply)
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

// Track played replies to avoid repeating
const playedReplies = new Set();

async function replyToAlert(id) {
    const reply = prompt("Enter Reply:");
    if (!reply) return;

    try {
        const response = await fetch(`/alerts/${id}/reply?reply_text=${encodeURIComponent(reply)}`, {
            method: 'POST'
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
