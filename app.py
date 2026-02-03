from flask import Flask, render_template, Response, request, jsonify, send_file
from hardware.camera import Camera
from hardware.motors import RobotMover
from hardware.mpu import MPU6050
from hardware.ld19 import LD19
from matebot.slam.mapper import OccupancyGridMapper
from matebot.navigation.manual_mapper import ManualMapper
from matebot.localization.odometry import MecanumOdometry
import time
import os
import yaml
from datetime import datetime

app = Flask(__name__)

# Load configuration
with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Initialize hardware
motor_controller = RobotMover()
imu = MPU6050()
lidar = LD19(port="/dev/ttyUSB0")

# Initialize mapper (Dynamic Infinite Grid)
mapper = OccupancyGridMapper(chunk_size=200, resolution_cm=5.0, active_window=3)

# Initialize odometry
robot_config = config['robot']
hardware_config = config['hardware']['motors']
steps_per_rev = hardware_config['steps_per_rev'] * hardware_config['microsteps']

odometry = MecanumOdometry(
    wheel_base_m=robot_config['wheel_base'],
    wheel_radius_m=robot_config['wheel_radius'],
    steps_per_revolution=steps_per_rev,
    initial_x=0.0,  # Start at 0,0 in infinite grid
    initial_y=0.0,
    initial_heading=0.0,
    history_size=200
)

print(f"Odometry initialized at (0,0)")

# Initialize manual mapper
manual_mapper = ManualMapper(lidar, mapper, motor_controller, odometry, imu)

if lidar.available:
    lidar.start_continuous_reading()

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
    return Response(gen(Camera()), mimetype='multipart/x-mixed-replace; boundary=frame')

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

@app.route('/emergency_stop', methods=['POST'])
def emergency_stop():
    manual_mapper.stop_mapping(save_map=False)
    motor_controller.set_command(None)
    return jsonify({'status': 'success', 'message': 'Emergency stop executed'})

@app.route('/start_mapping', methods=['POST'])
def start_mapping():
    if manual_mapper.start_mapping():
        return jsonify({'status': 'success', 'mapping': True})
    return jsonify({'status': 'error', 'message': 'Failed to start mapping'}), 500

@app.route('/stop_mapping', methods=['POST'])
def stop_mapping():
    manual_mapper.stop_mapping(save_map=True)
    return jsonify({'status': 'success', 'mapping': False, 'map_saved': True})

@app.route('/mapping_status')
def mapping_status():
    return jsonify({
        'mapping': manual_mapper.is_mapping(),
        'lidar_available': lidar.available if lidar else False
    })

@app.route('/clear_map', methods=['POST'])
def clear_map():
    mapper.reset_map()
    odometry.reset_pose(0.0, 0.0, 0.0)
    manual_mapper.reset_mapping_state()
    return jsonify({'status': 'success', 'message': 'Map cleared'})

@app.route('/map')
def get_map():
    map_data = mapper.get_map_data(window_chunks=3)
    return jsonify(map_data)

@app.route('/map/stats')
def get_map_stats():
    return jsonify(mapper.get_map_stats())

@app.route('/map/export', methods=['POST'])
def export_map():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"map_export_{timestamp}.png"
    filepath = os.path.join("static", filename)
    if mapper.export_png(filepath):
        return jsonify({'status': 'success', 'url': f"/static/{filename}"})
    return jsonify({'status': 'error', 'message': 'Export failed'}), 500

@app.route('/odometry')
def get_odometry():
    x, y, heading = odometry.get_pose()
    total_dist = odometry.get_total_distance()
    return jsonify({
        'x': x, 'y': y,
        'heading': heading,
        'heading_degrees': heading * 57.2958,
        'total_distance': total_dist
    })

@app.route('/odometry/reset', methods=['POST'])
def reset_odometry():
    data = request.json
    x = data.get('x', 0.0)
    y = data.get('y', 0.0)
    heading = data.get('heading', 0.0)
    odometry.reset_pose(x, y, heading)
    manual_mapper.reset_mapping_state()
    return jsonify({'status': 'success', 'x': x, 'y': y, 'heading': heading})

@app.route('/set_speed', methods=['POST'])
def set_speed():
    data = request.json
    delay = data.get('delay')
    if motor_controller and delay:
        motor_controller.set_delay(delay)
        return jsonify({'status': 'success', 'delay': delay})
    return jsonify({'status': 'error'}), 500

@app.route('/telemetry')
def telemetry():
    if imu and imu.available:
        return jsonify(imu.get_data())
    return jsonify({'error': 'IMU not available'}), 503

@app.route('/lidar')
def lidar_data():
    if lidar and lidar.available:
        return jsonify(lidar.get_data())
    return jsonify({'error': 'LiDAR not available', 'available': False}), 503

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    finally:
        if manual_mapper:
            manual_mapper.stop_mapping(save_map=True)
        if motor_controller:
            motor_controller.cleanup()
        if lidar:
            lidar.cleanup()
