from flask import Flask, render_template, Response, request, jsonify
from hardware.camera import Camera
from hardware.motors import RobotMover
import time
import sys

app = Flask(__name__)

# Hardware initialisieren
print("Initializing motor controller...", file=sys.stderr)
try:
    import hardware.motors
    print(f"DEBUG: Importing motors from: {hardware.motors.__file__}", file=sys.stderr)
    motor_controller = RobotMover()
    print("Motor controller initialized successfully!", file=sys.stderr)
except Exception as e:
    print(f"ERROR initializing motor controller: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    motor_controller = None
# Kamera erst beim Request initialisieren oder hier global (global ist einfacher für Stream)
# Wir instanziieren sie im Generator, um Fehler beim Start zu vermeiden

def gen(camera):
    """Video Streaming Generator"""
    while True:
        frame = camera.get_frame()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

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
    print(f"Command received: {command}", file=sys.stderr, flush=True)
    
    if motor_controller is None:
        print("ERROR: Motor controller not initialized!", file=sys.stderr, flush=True)
        return jsonify({'status': 'error', 'message': 'Motor controller not initialized'}), 500
    
    if command in ['forward', 'backward', 'left', 'right', 'strafe_left', 'strafe_right', 'stop']:
        try:
            if command == 'stop':
                motor_controller.set_command(None)
            else:
                motor_controller.set_command(command)
            print(f"Command '{command}' sent to motor controller", file=sys.stderr, flush=True)
            return jsonify({'status': 'success', 'cmd': command})
        except Exception as e:
            print(f"ERROR executing command '{command}': {e}", file=sys.stderr, flush=True)
            return jsonify({'status': 'error', 'message': str(e)}), 500
    
    return jsonify({'status': 'error', 'message': 'Invalid command'}), 400

if __name__ == '__main__':
    try:
        # Host 0.0.0.0 macht es im Netzwerk verfügbar
        app.run(host='0.0.0.0', port=5000, debug=False)
    finally:
        if motor_controller:
            motor_controller.cleanup()