import smbus2 as smbus
import time
import threading
import sys

# MPU6050 Registers
PWR_MGMT_1   = 0x6B
SMPLRT_DIV   = 0x19
CONFIG       = 0x1A
GYRO_CONFIG  = 0x1B
INT_ENABLE   = 0x38
ACCEL_XOUT_H = 0x3B
ACCEL_YOUT_H = 0x3D
ACCEL_ZOUT_H = 0x3F
GYRO_XOUT_H  = 0x43
GYRO_YOUT_H  = 0x45
GYRO_ZOUT_H  = 0x47

# Sensitivity scale factors
MPU_SENSOR_GYRO_CONSTANT = 131.0
MPU_SENSOR_ACCEL_CONSTANT = 16384.0

class MPU6050:
    def __init__(self, bus_num=1, address=0x68):
        self.address = address
        try:
            self.bus = smbus.SMBus(bus_num)
            self._init_mpu()
            self.available = True
            sys.stderr.write(f"MPU6050 initialized on bus {bus_num}, addr {address}\n")
        except Exception as e:
            sys.stderr.write(f"MPU6050 Init Error: {e}\n")
            self.available = False
            return

        self.accel_data = {'x': 0, 'y': 0, 'z': 0}
        self.gyro_data = {'x': 0, 'y': 0, 'z': 0}
        
        self.lock = threading.Lock()
        self.running = True
        self.thread = threading.Thread(target=self._update_loop, daemon=True)
        self.thread.start()

    def _init_mpu(self):
        self.bus.write_byte_data(self.address, SMPLRT_DIV, 7)
        self.bus.write_byte_data(self.address, PWR_MGMT_1, 1)
        self.bus.write_byte_data(self.address, CONFIG, 0)
        self.bus.write_byte_data(self.address, GYRO_CONFIG, 24)
        self.bus.write_byte_data(self.address, INT_ENABLE, 1)

    def _read_raw_data(self, addr):
        high = self.bus.read_byte_data(self.address, addr)
        low = self.bus.read_byte_data(self.address, addr + 1)
        value = (high << 8) | low
        if value > 32768:
            value -= 65536
        return value

    def _update_loop(self):
        while self.running:
            try:
                ax = self._read_raw_data(ACCEL_XOUT_H) / MPU_SENSOR_ACCEL_CONSTANT
                ay = self._read_raw_data(ACCEL_YOUT_H) / MPU_SENSOR_ACCEL_CONSTANT
                az = self._read_raw_data(ACCEL_ZOUT_H) / MPU_SENSOR_ACCEL_CONSTANT
                
                gx = self._read_raw_data(GYRO_XOUT_H) / MPU_SENSOR_GYRO_CONSTANT
                gy = self._read_raw_data(GYRO_YOUT_H) / MPU_SENSOR_GYRO_CONSTANT
                gz = self._read_raw_data(GYRO_ZOUT_H) / MPU_SENSOR_GYRO_CONSTANT

                with self.lock:
                    self.accel_data = {'x': ax, 'y': ay, 'z': az}
                    self.gyro_data = {'x': gx, 'y': gy, 'z': gz}
            except:
                pass
            time.sleep(0.05)

    def get_data(self):
        with self.lock:
            return {
                'accel': self.accel_data,
                'gyro': self.gyro_data
            }

    def cleanup(self):
        self.running = False
