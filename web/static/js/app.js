const statusEl = document.getElementById('status');
const poiListEl = document.getElementById('poiList');
const savePoiBtn = document.getElementById('savePoiBtn');

let ws;
const mapRenderer = new MapRenderer('mapCanvas');
const joystick = new Joystick('joystickZone', (vx, vy, omega) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ joystick: { vx, vy, omega } }));
    }
});

function connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    ws.onopen = () => {
        statusEl.innerText = 'Connected';
        statusEl.style.color = '#0f0';
        // Request map updates
        setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ request: 'map' }));
            }
        }, 500);
    };

    ws.onclose = () => {
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

async function loadPois() {
    const res = await fetch('/api/poi');
    const pois = await res.json();
    poiListEl.innerHTML = '';
    pois.forEach(poi => {
        const li = document.createElement('li');
        li.innerText = poi.name;
        li.onclick = () => navigateTo(poi.id);
        poiListEl.appendChild(li);
    });
}

async function navigateTo(id) {
    await fetch('/api/navigate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_id: id })
    });
}

savePoiBtn.onclick = async () => {
    const name = prompt('Enter location name:');
    if (name) {
        await fetch('/api/poi', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        loadPois();
    }
};

connect();
loadPois();
