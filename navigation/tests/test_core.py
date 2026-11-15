import math
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]))
from core import LD19,crc8,wheels,twist,finite_wave


class CoreTests(unittest.TestCase):
    def packet(self):
        p=bytearray(47)
        p[:2]=b'\x54\x2c'
        struct.pack_into('<H',p,4,35900)
        struct.pack_into('<H',p,42,100)
        for i in range(12):
            struct.pack_into('<HB',p,6+3*i,1500,200)
        p[-1]=crc8(p[:-1])
        return p

    def test_serial_fragmentation_noise_and_corruption(self):
        d=LD19();p=self.packet();bad=bytearray(p);bad[12]^=1
        self.assertEqual(d.feed(b'noise'+bad+p[:16]),[])
        packets=d.feed(p[16:]+p)
        self.assertEqual(len(packets),2)
        self.assertEqual(d.bad_crc,1)
        self.assertAlmostEqual(packets[0][-1][0],1)
        self.assertEqual(packets[0][0][1],1.5)

    def test_mecanum_round_trip(self):
        for cmd in [(0.08,0,0),(0,0.06,0),(0,0,.18),(.02,-.03,.1)]:
            recovered=twist(wheels(*cmd,.5,.6),.5,.6)
            for a,b in zip(cmd,recovered):
                self.assertAlmostEqual(a,b)

    def test_wave_has_finite_duration_and_all_outputs_low(self):
        pins=[9,22,13,5]
        pulse=finite_wave([1000,2000,0,-500],pins)
        self.assertEqual(sum(p[2] for p in pulse),80001)
        levels=0
        for on,off,_ in pulse:
            levels=(levels|on)&~off
        self.assertEqual(levels,0)
        self.assertTrue(any(on&(1<<9) and on&(1<<22) for on,_,_ in pulse))
        for invalid in [math.nan,math.inf,10000]:
            with self.assertRaises(ValueError):
                finite_wave([invalid], [9])

    def test_commissioning_pulses_only_the_selected_wheel(self):
        pins=[9,22,13,5]
        for index in range(4):
            frequencies=[0,0,0,0]
            frequencies[index]=1200
            pulses=finite_wave(frequencies,pins)
            self.assertEqual(sum(bool(on&(1<<pins[index])) for on,_,_ in pulses),96)
            self.assertTrue(all(on&~(1<<pins[index])==0 for on,_,_ in pulses))



if __name__=='__main__':
    unittest.main()
