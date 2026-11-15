import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]))
from wave_driver import WaveDriver


class DMA:
    def __init__(self):self.now=0.;self.next=0;self.schedule=[];self.live=set();self.modes=[];self.stops=0
    def wave_tx_at(self):return next((w for w,s,e in self.schedule if s<=self.now<e),9999)
    def wave_tx_busy(self):return self.wave_tx_at()!=9999
    def wave_tx_stop(self):self.schedule=[(w,s,min(e,self.now)) for w,s,e in self.schedule];self.stops+=1
    def wave_delete(self,wave):
        assert not any(w==wave and e>self.now for w,s,e in self.schedule)
        self.live.discard(wave)
    def write(self,*_):pass
    def wave_add_generic(self,pulses):self.duration=sum(p[2] for p in pulses)/1e6
    def wave_create(self):self.next+=1;self.live.add(self.next);return self.next
    def wave_send_using_mode(self,wave,mode):
        self.modes.append(mode)
        start=max(self.now,max((e for w,s,e in self.schedule),default=0)) if mode==2 else self.now
        self.schedule.append((wave,start,start+self.duration))


class WaveDriverTests(unittest.TestCase):
    def make(self):
        dma=DMA();cfg=dict(direction_signs=[-1,1,-1,1],direction_pins=[11,10,19,6],step_pins=[9,22,13,5],enable_pin=26,enable_active_low=True)
        return dma,WaveDriver(dma,cfg,lambda *p:p)
    def test_successors_have_no_gaps_and_stop_after_controller_disappears(self):
        dma,driver=self.make();distance=0.
        for i in range(101):
            dma.now=i*.01;distance+=driver.take_motion(dma.now)[0];driver.pump([1000]*4,[.1,0,0],dma.now)
            self.assertLessEqual(len(driver.records),2);self.assertLessEqual(len(dma.live),2)
        self.assertAlmostEqual(distance,.1,places=5)
        for previous,next_wave in zip(dma.schedule,dma.schedule[1:]):self.assertAlmostEqual(previous[2],next_wave[1],places=8)
        self.assertEqual(driver.underruns,0);self.assertTrue(all(mode==2 for mode in dma.modes[1:]))
        self.assertLessEqual(dma.schedule[-1][2],dma.now+.161)
        dma.now+=.17;self.assertFalse(dma.wave_tx_busy())
    def test_stop_cancels_queued_wave_and_clears_allocations(self):
        dma,driver=self.make();driver.pump([1000]*4,[.1,0,0],0)
        dma.now=.04;driver.pump([1000]*4,[.1,0,0],dma.now)
        self.assertEqual(len(driver.records),2);driver.stop(dma.now)
        self.assertFalse(dma.wave_tx_busy());self.assertFalse(dma.live)
        self.assertAlmostEqual(driver.take_motion(dma.now)[0],.004)


if __name__=='__main__':unittest.main()
