// Command queue management
let lastCommandTime = 0;
let pendingCommand = null;
let commandInFlight = false;
const COMMAND_DEBOUNCE_MS = 50; 
const COMMAND_TIMEOUT_MS = 500; 

// Track active fetches
let mapFetchInFlight = false;
let statsFetchInFlight = false;
let lidarFetchInFlight = false;
let telemetryFetchInFlight = false;

let isMapping = false;
let showChunks = false;

function sendCommand(cmd) {
    const now = Date.now();
    document.getElementById('status').innerText = "Status: " + cmd.toUpperCase();
    pendingCommand = cmd;
    if (now - lastCommandTime >= COMMAND_DEBOUNCE_MS || cmd === 'stop' || !commandInFlight) {
        flushCommand();
    }
}

function flushCommand() {
    if (pendingCommand === null) return;
    const cmd = pendingCommand;
    pendingCommand = null;
    lastCommandTime = Date.now();
    commandInFlight = true;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), COMMAND_TIMEOUT_MS);
    fetch('/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: cmd }),
        signal: controller.signal
    }).then(() => {
        clearTimeout(timeoutId); commandInFlight = false;
        if (pendingCommand !== null) setTimeout(flushCommand, 10);
    }).catch(() => {
        clearTimeout(timeoutId); commandInFlight = false;
    });
}

function updateSpeed() {
    const delay = document.getElementById('speedSelect').value;
    fetch('/set_speed', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ delay: delay }) });
}

function toggleLogic() {
    fetch('/toggle_logic', { method: 'POST' }).then(r => r.json()).then(data => {
        document.getElementById('status').innerText = "Logic Mode: " + (data.active_low ? "LOW" : "HIGH");
    });
}

function updateTelemetry() {
    if (telemetryFetchInFlight) return;
    telemetryFetchInFlight = true;
    fetch('/telemetry').then(r => r.json()).then(data => {
        telemetryFetchInFlight = false;
        if (data.error) return;
        updateBar('acc-x', data.accel.x, 2); updateBar('acc-y', data.accel.y, 2); updateBar('acc-z', data.accel.z, 2);
        document.getElementById('gyro-x').innerText = `X: ${data.gyro.x.toFixed(2)} °/s`;
        document.getElementById('gyro-y').innerText = `Y: ${data.gyro.y.toFixed(2)} °/s`;
        document.getElementById('gyro-z').innerText = `Z: ${data.gyro.z.toFixed(2)} °/s`;
    }).catch(() => telemetryFetchInFlight = false);
}

function updateBar(id, value, max) {
    const el = document.getElementById(id);
    const percentage = Math.min(Math.max((value + max) / (max * 2) * 100, 0), 100);
    el.style.width = percentage + '%';
    el.innerText = `${id.split('-')[1].toUpperCase()}: ${value.toFixed(2)}`;
}

// --- LiDAR ---
const lidarCanvas = document.getElementById('lidarCanvas');
const lidarCtx = lidarCanvas.getContext('2d');

function updateLiDAR() {
    if (lidarFetchInFlight) return;
    lidarFetchInFlight = true;
    fetch('/lidar').then(r => r.json()).then(data => {
        lidarFetchInFlight = false;
        if (data.error || !data.available) {
            document.getElementById('lidar-status').style.color = '#ff4444'; return;
        }
        document.getElementById('lidar-status').style.color = '#44ff44';
        document.getElementById('lidar-strength').innerText = `Points: ${data.point_count || 0}`;
        drawLiDAR360(data.points || []);
    }).catch(() => lidarFetchInFlight = false);
}

function drawLiDAR360(points) {
    const ctx = lidarCtx; const w = lidarCanvas.width; const h = lidarCanvas.height;
    const cx = w / 2; const cy = h / 2; const maxRange = 600; 
    ctx.fillStyle = '#0a0a0a'; ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = '#222';
    for (let r = 100; r <= maxRange; r += 100) {
        const radius = (r / maxRange) * (w / 2 - 10);
        ctx.beginPath(); ctx.arc(cx, cy, radius, 0, 2 * Math.PI); ctx.stroke();
    }
    ctx.fillStyle = '#00ff00'; ctx.beginPath(); ctx.arc(cx, cy, 5, 0, 2 * Math.PI); ctx.fill();
    
    points.forEach(p => {
        if (p.distance_cm <= 0 || p.distance_cm > maxRange) return;
        // CORRECTED LiDAR Mapping: Angle 0 is Up, Angle 90 is Left
        const rad = (p.angle - 90) * Math.PI / 180;
        const r = (p.distance_cm / maxRange) * (w / 2 - 10);
        const x = cx + r * Math.cos(rad); const y = cy + r * Math.sin(rad);
        ctx.fillStyle = `rgba(0, 255, 204, 0.8)`; ctx.fillRect(x, y, 2, 2);
    });
}

// --- SLAM Exploration ---
const mapCanvas = document.getElementById('mapCanvas');
const mapCtx = mapCanvas.getContext('2d');
const gridCanvas = document.createElement('canvas');
const gridCtx = gridCanvas.getContext('2d');

function toggleChunks() { showChunks = document.getElementById('showChunksToggle').checked; }

function startMapping() {
    fetch('/start_mapping', { method: 'POST' }).then(r => r.json()).then(data => {
        if (data.status === 'success') { isMapping = true; updateMappingUI(); }
    });
}

function stopMapping() {
    fetch('/stop_mapping', { method: 'POST' }).then(r => r.json()).then(data => {
        isMapping = false; updateMappingUI();
    });
}

function resetMap() {
    if (confirm("Reset map and odometry to (0,0)?")) {
        fetch('/clear_map', { method: 'POST' }).then(() => { 
            document.getElementById('status').innerText = "Map Cleared";
            updateMapStats();
        });
    }
}

function exportMap() {
    fetch('/map/export', { method: 'POST' }).then(r => r.json()).then(data => {
        if (data.status === 'success') window.open(data.url, '_blank');
    });
}

function updateMap() {
    if (mapFetchInFlight) return;
    mapFetchInFlight = true;
    fetch('/map').then(r => r.json()).then(data => {
        mapFetchInFlight = false;
        if (data.grid) drawMapOptimized(data);
    }).catch(() => mapFetchInFlight = false);
}

function updateMapStats() {
    if (statsFetchInFlight) return;
    statsFetchInFlight = true;
    fetch('/map/stats').then(r => r.json()).then(data => {
        statsFetchInFlight = false;
        document.getElementById('chunks-loaded').innerText = `Chunks: ${data.loaded_chunks} / ${data.total_chunks}`;
        document.getElementById('coverage-area').innerText = `Area: ${data.coverage_area_m2.toFixed(1)} m²`;
        document.getElementById('memory-usage').innerText = `Memory: ${data.memory_mb.toFixed(2)} MB`;
    }).catch(() => statsFetchInFlight = false);
}

function drawMapOptimized(mapData) {
    const grid = mapData.grid; const width = mapData.width; const height = mapData.height;
    if (gridCanvas.width !== width || gridCanvas.height !== height) {
        gridCanvas.width = width; gridCanvas.height = height;
    }
    const imgData = gridCtx.createImageData(width, height); const data = imgData.data;
    for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
            const val = grid[y][x]; const idx = (y * width + x) * 4;
            if (val === 0) { data[idx] = 40; data[idx+1] = 40; data[idx+2] = 40; }
            else if (val <= 50) { const light = 255 - (val * 2); data[idx] = light; data[idx+1] = light; data[idx+2] = light; }
            else { const dark = Math.max(0, 200 - (val - 50) * 4); data[idx] = dark; data[idx+1] = 0; data[idx+2] = 0; }
            data[idx+3] = 255;
        }
    }
    gridCtx.putImageData(imgData, 0, 0);

    mapCtx.imageSmoothingEnabled = false; mapCtx.fillStyle = '#111'; mapCtx.fillRect(0, 0, mapCanvas.width, mapCanvas.height);
    const cw = mapCanvas.width; const ch = mapCanvas.height; const scale = cw / width; 
    const rx_scaled = mapData.robot_x_grid * scale; const ry_scaled = mapData.robot_y_grid * scale;
    const hRad = mapData.robot_heading * Math.PI / 180;

    mapCtx.save();
    mapCtx.translate(cw/2, ch/2);
    
    // CORRECTED Map Rendering:
    // 1. Flip X/Y if needed to match robot coordinate system (REP 103: X forward, Y left)
    // 2. hRad=0 should result in X-axis (Forward) pointing UP.
    mapCtx.scale(1, -1); // Canvas Y-down to standard Y-up
    mapCtx.rotate(-hRad - Math.PI/2); // Rotate so X-forward is UP
    mapCtx.drawImage(gridCanvas, -rx_scaled, -ry_scaled, width * scale, height * scale);
    mapCtx.restore();

    mapCtx.fillStyle = '#0f0'; mapCtx.beginPath(); mapCtx.arc(cw/2, ch/2, 8, 0, 2 * Math.PI); mapCtx.fill();
    mapCtx.strokeStyle = '#0f0'; mapCtx.lineWidth = 3; mapCtx.beginPath(); mapCtx.moveTo(cw/2, ch/2); mapCtx.lineTo(cw/2, ch/2 - 25); mapCtx.stroke();
}

function updateMappingUI() {
    const btn = document.getElementById('startMappingBtn');
    btn.innerHTML = isMapping ? '🛑 STOP UPDATING MAP' : '🚀 UPDATE MAP';
    isMapping ? btn.classList.add('mapping-active') : btn.classList.remove('mapping-active');
}

setInterval(updateTelemetry, 150); setInterval(updateLiDAR, 200); setInterval(updateMap, 1000); 
setInterval(updateMapStats, 5000);

const keyMap = { 'w': 'forward', 'a': 'left', 's': 'backward', 'd': 'right', 'ArrowUp': 'forward', 'ArrowLeft': 'left', 'ArrowDown': 'backward', 'ArrowRight': 'right', 'q': 'strafe_left', 'e': 'strafe_right' };
const keyState = {}; document.addEventListener('keydown', (e) => {
    const cmd = keyMap[e.key] || keyMap[e.key.toLowerCase()];
    if (cmd && !keyState[cmd]) { e.preventDefault(); keyState[cmd] = true; sendCommand(cmd); }
});
document.addEventListener('keyup', (e) => {
    const cmd = keyMap[e.key] || keyMap[e.key.toLowerCase()];
    if (cmd && keyState[cmd]) { keyState[cmd] = false; sendCommand('stop'); }
});
updateMappingUI();
