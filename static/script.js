function sendCommand(cmd) {
    document.getElementById('status').innerText = "Status: " + cmd.toUpperCase();
    
    fetch('/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: cmd }),
    }).catch(error => console.error('Error:', error));
}

function updateSpeed() {
    const delay = document.getElementById('speedSelect').value;
    fetch('/set_speed', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ delay: delay }),
    }).then(response => response.json())
      .then(data => {
          document.getElementById('status').innerText = "Speed updated: " + delay;
      })
      .catch(error => console.error('Error:', error));
}

function toggleLogic() {
    fetch('/toggle_logic', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
    }).then(response => response.json())
      .then(data => {
          const mode = data.active_low ? "LOW (Active Low)" : "HIGH (Active High)";
          document.getElementById('status').innerText = "Enable Logic: " + mode;
      })
      .catch(error => console.error('Error:', error));
}

function updateTelemetry() {
    fetch('/telemetry')
        .then(response => response.json())
        .then(data => {
            if (data.error) return;
            
            // Update Accelerometer Bars
            updateBar('acc-x', data.accel.x, 2);
            updateBar('acc-y', data.accel.y, 2);
            updateBar('acc-z', data.accel.z, 2);
            
            // Update Gyro Text
            document.getElementById('gyro-x').innerText = `X: ${data.gyro.x.toFixed(2)} °/s`;
            document.getElementById('gyro-y').innerText = `Y: ${data.gyro.y.toFixed(2)} °/s`;
            document.getElementById('gyro-z').innerText = `Z: ${data.gyro.z.toFixed(2)} °/s`;
        })
        .catch(error => console.error('IMU Error:', error));
}

function updateBar(id, value, max) {
    const el = document.getElementById(id);
    const percentage = Math.min(Math.max((value + max) / (max * 2) * 100, 0), 100);
    el.style.width = percentage + '%';
    el.innerText = `${id.split('-')[1].toUpperCase()}: ${value.toFixed(2)}`;
}

// Poll telemetry every 100ms
setInterval(updateTelemetry, 100);
