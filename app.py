from flask import Flask, render_template, Response, request, jsonify
from hardware.camera import Camera
from hardware.motors import RobotMover
import time

app = Flask(__name__)

# Hardware initialisieren
motor_controller = RobotMover()
# Kamera erst beim Request initialisieren oder hier global (global ist einfacher für Stream)
# Wir instanziieren sie im Generator, um Fehler beim Start zu vermeiden

def gen(camera):
    """Video Streaming Generator"""
    while True:
        frame = camera.get_frame()
        if frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        else:
            time.sleep(0.1)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen(Camera()),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/control', methods=['POST'])
def control():
    data = request.json
    command = data.get('command')
    
    # Debug
    print(f"Command received: {command}")
    
    if command in ['forward', 'backward', 'left', 'right', 'strafe_left', 'strafe_right', 'stop']:
        if command == 'stop':
            motor_controller.set_command(None)
        else:
            motor_controller.set_command(command)
        return jsonify({'status': 'success', 'cmd': command})
    
    return jsonify({'status': 'error'}), 400

if __name__ == '__main__':
    try:
        # Host 0.0.0.0 macht es im Netzwerk verfügbar
        app.run(host='0.0.0.0', port=5000, debug=False)
    finally:
        motor_controller.cleanup()