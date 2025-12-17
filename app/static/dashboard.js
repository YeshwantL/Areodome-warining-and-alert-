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
        // Load list of airports for chat (Mock for now or fetch)
        loadAirportList();
    }

    // Initial Fetch
    fetchActiveAlerts();

    // Polling
    setInterval(fetchActiveAlerts, 10000); // 10s
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

        div.innerHTML = `
            <strong>${alert.type} Alert</strong> <br>
            ${contentStr} <br>
            <small>Valid: ${alert.content.valid_from || alert.content.time} UTC</small>
            ${currentUser.role === 'mwo_admin' ? `<br><button onclick="finalizeAlert(${alert.id})">Finalize</button>` : ''}
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

async function loadAirportList() {
    // In a real app, fetch from /users/regional
    // For prototype, we know we created 'vabb_airport' (ID 2)
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

// Update fetchActiveAlerts to play sound
// We need to track last alert ID to know if new one arrived.
let lastAlertId = 0;

async function fetchActiveAlerts() {
    try {
        const response = await fetch('/alerts/active');
        if (response.ok) {
            const alerts = await response.json();
            renderAlerts(alerts);

            if (currentUser.role === 'mwo_admin' && audioEnabled) {
                const newAlerts = alerts.filter(a => a.id > lastAlertId);
                if (newAlerts.length > 0) {
                    newAlerts.forEach(a => {
                        speak(`New Alert from Airport ID ${a.sender_id}`); // Ideally Airport Name
                    });
                    lastAlertId = Math.max(...alerts.map(a => a.id));
                }
            } else if (alerts.length > 0) {
                lastAlertId = Math.max(...alerts.map(a => a.id));
            }
        }
    } catch (e) {
        console.error(e);
    }
}
