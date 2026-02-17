from flask import Flask, render_template, jsonify, request
from src.robot import get_robot

app = Flask(__name__)
robot = get_robot()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def status():
    return jsonify(robot.get_status())

@app.route('/api/stop', methods=['POST'])
def stop():
    robot.stop()
    return jsonify({'success': True, 'message': 'Stopped'})

@app.route('/api/move', methods=['POST'])
def move():
    data = request.json
    direction = data.get('direction')
    
    if direction == 'forward':
        robot.move_forward()
    elif direction == 'backward':
        robot.move_backward()
    elif direction == 'left':
        robot.strafe_left()
    elif direction == 'right':
        robot.strafe_right()
    elif direction == 'rotate_left':
        robot.rotate_left()
    elif direction == 'rotate_right':
        robot.rotate_right()
    else:
        return jsonify({'success': False, 'error': 'Invalid direction'})
    
    return jsonify({'success': True, 'message': f'Moving {direction}'})

@app.route('/api/move_precise', methods=['POST'])
def move_precise():
    data = request.json
    distance = float(data.get('distance', 0))
    direction = data.get('direction', 'forward')
    speed = int(data.get('speed', 1000))
    
    result = robot.move_precise(distance, direction, speed)
    return jsonify(result)

@app.route('/api/turn_precise', methods=['POST'])
def turn_precise():
    data = request.json
    angle = float(data.get('angle', 0))
    direction = data.get('direction', 'left')
    speed = int(data.get('speed', 1000))
    
    result = robot.turn_precise(angle, direction, speed)
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
