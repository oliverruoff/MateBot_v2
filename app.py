from flask import Flask, render_template, Response, request, jsonify
from hardware.camera import Camera
from hardware.motors import RobotMover
from hardware.mpu import MPU6050
import hardware.motors
import time
import sys

app = Flask(__name__)

# Hardware initialisieren
motor_controller = RobotMover()
imu = MPU6050()

def gen(camera):
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
    if motor_controller:
        if command == 'stop':
            motor_controller.set_command(None)
        else:
            motor_controller.set_command(command)
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 500

@app.route('/set_speed', methods=['POST'])
def set_speed():
    data = request.json
    delay = data.get('delay')
    if motor_controller and delay:
        motor_controller.set_delay(delay)
        return jsonify({'status': 'success', 'delay': delay})
    return jsonify({'status': 'error'}), 500

@app.route('/toggle_logic', methods=['POST'])
def toggle_logic():
    if motor_controller:
        motor_controller.active_low = not motor_controller.active_low
        motor_controller.activate()
        return jsonify({'status': 'success', 'active_low': motor_controller.active_low})
    return jsonify({'status': 'error'}), 500

@app.route('/telemetry')
def telemetry():
    if imu and imu.available:
        return jsonify(imu.get_data())
    return jsonify({'error': 'IMU not available'}), 503

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    finally:
        if motor_controller:
            motor_controller.cleanup()
