"""Boot ordering for the appliance; never writes GPIO or serial data."""
from pathlib import Path
import socket
import time
import yaml

cfg=yaml.safe_load((Path(__file__).parent/'config/robot.yaml').read_text())
deadline=time.monotonic()+45
while time.monotonic()<deadline:
    if Path(cfg['lidar_port']).exists() and Path('/dev/i2c-1').exists():
        try:
            with socket.create_connection(('127.0.0.1',8888),timeout=.3):
                print('LiDAR, I2C and pigpiod ready',flush=True)
                break
        except OSError:pass
    time.sleep(1)
else:raise SystemExit('Hardware not ready; systemd will retry')
