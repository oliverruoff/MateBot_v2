"""ROS-independent LD19 protocol and mecanum math, testable without hardware."""
import math
import struct


def crc8(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ (0x4D if crc & 0x80 else 0)) & 255
    return crc


class LD19:
    def __init__(self):
        self.buffer = bytearray()
        self.bad_crc = 0

    def feed(self, data):
        self.buffer.extend(data)
        packets = []
        while len(self.buffer) >= 47:
            start = self.buffer.find(b'\x54\x2c')
            if start < 0:
                self.buffer[:] = self.buffer[-1:]
                break
            del self.buffer[:start]
            if len(self.buffer) < 47:
                break
            packet = self.buffer[:47]
            if crc8(packet[:-1]) != packet[-1]:
                self.bad_crc += 1
                del self.buffer[0]
                continue
            del self.buffer[:47]
            a = struct.unpack_from('<H', packet, 4)[0] / 100
            b = struct.unpack_from('<H', packet, 42)[0] / 100
            span = (b - a) % 360
            if span > 90:
                continue
            packets.append([((a + i * span / 11) % 360,
                             struct.unpack_from('<H', packet, 6 + i * 3)[0] / 1000,
                             packet[8 + i * 3]) for i in range(12)])
        return packets


def wheels(vx, vy, wz, wheelbase, track_width):
    k = (wheelbase + track_width) / 2
    return [vx - vy - k*wz, vx + vy + k*wz,
            vx + vy - k*wz, vx - vy + k*wz]


def twist(speeds, wheelbase, track_width):
    fl, fr, bl, br = speeds
    k = (wheelbase + track_width) / 2
    return ((fl+fr+bl+br)/4, (-fl+fr+bl-br)/4, (-fl+fr-bl+br)/(4*k))


def finite_wave(frequencies, pins, duration_us=80000):
    """One finite simultaneous pulse train; expires if the controller dies."""
    edges = {0: [0, 0], duration_us: [0, sum(1 << p for p in pins)]}
    for hz, pin in zip(frequencies, pins):
        if not math.isfinite(hz) or abs(hz) > 5000:
            raise ValueError('Unsafe step frequency')
        if abs(hz) < 1:
            continue
        period = 1e6 / abs(hz)
        for i in range(int(duration_us / period)):
            on = int(i*period)
            off = min(duration_us, int(i*period + period/2))
            edges.setdefault(on, [0, 0])[0] |= 1 << pin
            edges.setdefault(off, [0, 0])[1] |= 1 << pin
    times = sorted(edges)
    return [(edges[t][0], edges[t][1], times[i+1]-t if i+1<len(times) else 1)
            for i,t in enumerate(times)]

