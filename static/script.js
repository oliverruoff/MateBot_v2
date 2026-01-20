function sendCommand(cmd) {
    // Visuelles Feedback
    document.getElementById('status').innerText = "Status: " + cmd.toUpperCase();
    
    fetch('/control', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ command: cmd }),
    })
    .catch((error) => {
        console.error('Error:', error);
    });
}

// Stoppen wenn man mit der Maus den Button verlässt während man drückt
document.addEventListener('mouseup', function() {
    // Optional: Globaler Stop, falls mal ein Event verloren geht
    // sendCommand('stop'); 
    // ^ Kann zu viel Traffic verursachen, besser auf den Buttons lassen
});