const statusEl = document.getElementById('status');
const poiListEl = document.getElementById('poiList');
const savePoiBtn = document.getElementById('savePoiBtn');

let ws;
const mapRenderer = new MapRenderer('mapCanvas');

function connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    console.log("Connecting to", wsUrl);
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log("WS Connected");
        statusEl.innerText = 'Connected';
        statusEl.style.color = '#0f0';
        
        // Map request loop
        setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ request: 'map' }));
            }
        }, 500);
    };

    ws.onclose = () => {
        console.log("WS Closed");
        statusEl.innerText = 'Disconnected';
        statusEl.style.color = '#f00';
        setTimeout(connect, 2000);
    };

    ws.onmessage = (event) => {
        if (event.data instanceof Blob) {
            event.data.arrayBuffer().then(buffer => {
                mapRenderer.render(buffer);
            });
        }
    };
}

function sendMotion(vx, vy, omega) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        console.log("Sending Motion:", {vx, vy, omega, freq: currentFrequency});
        ws.send(JSON.stringify({ 
            joystick: { vx, vy, omega },
            frequency: currentFrequency
        }));
    }
}

// Global key state
const activeKeys = new Set();

window.addEventListener('keydown', (e) => {
    const key = e.key.toLowerCase();
    if (!activeKeys.has(key)) {
        activeKeys.add(key);
        console.log("Key Down:", key);
        processKeys();
    }
});

window.addEventListener('keyup', (e) => {
    const key = e.key.toLowerCase();
    activeKeys.delete(key);
    console.log("Key Up:", key);
    processKeys();
});

function processKeys() {
    let vx = 0, vy = 0, omega = 0;
    const speed = 0.3;
    const turn = 0.6;

    if (activeKeys.has('w') || activeKeys.has('arrowup')) vx = speed;
    if (activeKeys.has('s') || activeKeys.has('arrowdown')) vx = -speed;
    if (activeKeys.has('a') || activeKeys.has('arrowleft')) vy = speed;
    if (activeKeys.has('d') || activeKeys.has('arrowright')) vy = -speed;
    if (activeKeys.has('q')) omega = turn;
    if (activeKeys.has('e')) omega = -turn;

    sendMotion(vx, vy, omega);
}

// Joystick fallback
const joystick = new Joystick('joystickZone', (vx, vy, omega) => {
    sendMotion(vx, vy, omega);
});

// Reset map button handler
if (resetMapBtn) {
    resetMapBtn.addEventListener('click', async () => {
        if (confirm('Reset the map? This will clear all scan data.')) {
            try {
                const res = await fetch('/api/reset_map', { method: 'POST' });
                const data = await res.json();
                console.log("Map reset:", data);
                alert('Map reset successfully!');
            } catch (e) {
                console.error("Reset map error:", e);
                alert('Failed to reset map: ' + e.message);
            }
        }
    });
}

// Frequency selector handler  
if (freqSelect) {
    freqSelect.addEventListener('change', (e) => {
        currentFrequency = parseInt(e.target.value);
        if (currentFreqEl) {
            currentFreqEl.textContent = currentFrequency;
        }
        console.log("Frequency changed to:", currentFrequency);
    });
}

connect();
