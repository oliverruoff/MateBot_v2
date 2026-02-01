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
