import time
import math

try:
    import smbus2
    HAS_SMBUS = True
except ImportError:
    HAS_SMBUS = False

MPU6050_ADDR = 0x68
REG_PWR_MGMT_1 = 0x6B
REG_GYRO_XOUT_H = 0x43
REG_ACCEL_XOUT_H = 0x3B

GYRO_SCALE = 131.0

class IMUHandler:
    def __init__(self):
        self.bus = None
        try:
            if HAS_SMBUS:
                self.bus = smbus2.SMBus(1)
                self.bus.write_byte_data(MPU6050_ADDR, REG_PWR_MGMT_1, 0)
                self.simulation = False
                print("IMU initialized successfully")
            else:
                raise Exception("smbus2 not available")
        except Exception as e:
            print(f"Error initializing IMU: {e}. Running in simulation mode.")
            self.simulation = True
            self.current_yaw = 0.0

        self.last_read_time = time.time()
        self.gyro_z_offset = 0

    def read_raw_word(self, reg):
        if self.simulation:
            return 0
        high = self.bus.read_byte_data(MPU6050_ADDR, reg)
        low = self.bus.read_byte_data(MPU6050_ADDR, reg + 1)
        val = (high << 8) + low
        return val - 65536 if val > 32767 else val

    def get_gyro_z(self):
        if self.simulation:
            return 0
        return self.read_raw_word(REG_GYRO_XOUT_H) / GYRO_SCALE

    def get_accel(self):
        if self.simulation:
            return {'x': 0, 'y': 0, 'z': 0}
        return {
            'x': self.read_raw_word(REG_ACCEL_XOUT_H),
            'y': self.read_raw_word(REG_ACCEL_XOUT_H + 2),
            'z': self.read_raw_word(REG_ACCEL_XOUT_H + 4)
        }

    def get_yaw(self):
        if self.simulation:
            return self.current_yaw
            
        current_time = time.time()
        dt = current_time - self.last_read_time
        self.last_read_time = current_time
        
        gyro_z = self.get_gyro_z()
        delta_yaw = gyro_z * dt
        self.current_yaw += delta_yaw
        
        return self.current_yaw

    def reset_yaw(self):
        self.current_yaw = 0.0
        self.last_read_time = time.time()

    def calibrate(self, samples=100):
        if self.simulation:
            print("Simulation: IMU calibrated")
            return
            
        print("Calibrating IMU...")
        sum_gyro = 0
        for _ in range(samples):
            sum_gyro += self.get_gyro_z()
            time.sleep(0.01)
        
        self.gyro_z_offset = sum_gyro / samples
        print(f"IMU Calibration complete. Gyro Z offset: {self.gyro_z_offset}")

if __name__ == "__main__":
    imu = IMUHandler()
    imu.calibrate()
    while True:
        print(f"Yaw: {imu.get_yaw():.2f} deg")
        time.sleep(0.5)
