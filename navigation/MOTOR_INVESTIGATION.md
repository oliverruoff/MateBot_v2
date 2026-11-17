# Structured motor investigation

## Latest owner-observed raised-wheel evidence

With the recovered February 1 driver, the owner confirmed all four wheels run
smoothly and quietly individually at the same 8000 Hz target / historical ramp.
Combined operation still failed. Reversing output order did not move the failure
away from BR. Synchronous and quarter-phase DMA comparisons did not repair it.

FL/FR/BL worked together with BR STEP (GPIO5) held LOW. When BR was added via an
independent finite waveform, the owner saw THREE -> ONLY BR -> THREE, despite
four simultaneous GPIO clocks. A subsequent constant-level comparison ran only
FL/FR/BL continuously: GPIO5 LOW for 2 s, HIGH for 2 s, LOW for 2 s. The owner
reported quiet/smooth -> loud/rough -> quiet/smooth, with BR not rotating.

An independent read-only CPU register sampler checked the three STEP outputs in
steady one-second windows of the same LOW/HIGH/LOW sequence. For every pin and
every stage, the median period was 125 us, median HIGH width 60 us, HIGH-width
5th/95th percentiles both 60 us; 7985 periods were counted in each window.
GPIO5 was read HIGH throughout the middle checks. This is strong digital
evidence against the proposed last-loop overwrite or changed duty on the other
three outputs. It does not measure voltage/current at a driver input.

No wiring diagnosis is established yet. Actual GPIO5 connections, common signal
returns, enables, logic supply and receiver voltages must be checked. A single
STEP edge may also wake full winding current, so the constant-level experiment
does not by itself exclude a motor-supply problem. Physical terminal tracing
and receiver/supply measurements are now required; more arbitrary frequency
changes are not supported by the evidence. No permanent drive-profile changes
were made during these owner-observed bench comparisons.

## Acceptance condition

Four wheels must visibly rotate consistently in the intended directions, first
individually and then together, with release/STOP confirmed. Only then can body
translation/yaw measurements validate full driving. Software tests, commanded
odometry and small LiDAR displacements cannot substitute for observing wheels.
The owner's latest report is that only BR rotates reliably: this condition fails.

## Evidence and uncertainties

Pi 4, GPIO assignments and software pin modes have been read from the running
system. The owner reports a 12 V / 150 W supply and the same mechanical setup as
previously working. Exact motor and driver nameplate models, terminal wiring,
input voltage/current under load and motor-rail voltage under load remain unknown.
NEMA 23 is a frame size; the TB6600 label does not uniquely identify a module.

## Primary-source research

- [Raspberry Pi GPIO electrical documentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html): BCM2711 output/drive specifications differ from older chips. Its table lists 4 mA default and 8 mA maximum drive strength. Register readback is not a measurement at the receiver. Earlier assumptions treating a pigpio setting labelled 16 mA as measured Pi 4 capability were wrong.
- [DFRobot TB6600 V1.2 manual](https://dfimg.dfrobot.com/nobody/wiki/0bcc0b661ce7750ff7d0134bfc3e88b3.pdf): optocoupled STEP/DIR/EN, 8–15 mA input drive, module-specific wiring and DIP tables. OFF/OFF/ON for the current selector means 2.8 A in this example, contradicting the repository's earlier unverified 3.5 A claim. This is a comparison module, not identification of the robot's actual driver.
- [DFRobot product specification](https://www.dfrobot.com/product-1547.html): an item sold as TB6600 may use TB67S109AFTG internally and advertises a broader input-voltage range. This reinforces the need to identify the actual module instead of applying generic chip assumptions.
- [AccelStepper implementation documentation](https://www.airspayce.com/mikem/arduino/AccelStepper/classAccelStepper.html): driver-interface STEP/DIR operation, configurable pulse width and acceleration, and explicit recognition that open-loop step counts are not actual position feedback.
- [druyang/tb6600_rpi](https://github.com/druyang/tb6600_rpi): a concrete Raspberry Pi/TB6600 project isolates individual axes with STEP/DIR signals. Its example uses Python-timed pulses; this is useful as an isolation method, not a high-rate timing implementation to copy into our robot.
- [pigpio implementation](https://github.com/joan2937/pigpio): timed GPIO PWM and waves are suitable clock mechanisms. Neither proves adequate analog drive into an unknown optocoupler circuit.

No source establishes that a magic PWM mode resolves a channel-dependent failure.
The electrical-interface concern is a hypothesis, not a diagnosed hardware fault.
No pad-strength, voltage, DIP, polarity or wiring changes were made from these
comparisons. In particular, no recommendation to buy a particular buffer or raise
supply voltage is justified without the actual module/motor specifications.

## Controlled comparisons implemented

The `/motors` page now selects All, FL, FR, BL or BR and can reverse **emission
order** without swapping wheel assignments. The order is test-only. Single-wheel
tests accept forward/backward only and leave the other three STEP rates zero.
The direct wheel-rate mask bypasses the kinematic inverse projection; otherwise
projecting a single wheel through body velocity would incorrectly activate other
wheels. Existing bounded duration, lease, STOP and sensor guards still apply.

Read-only daemon settings are shown separately for each physical pin pair.
They report configured PWM frequency/duty and pin mode; they do not certify
signal amplitude, driver input current or mechanical movement.

| Comparison | What it can establish | Current status |
|---|---|---|
| Distinct four-channel commands, normal/reverse emission order | Software channels retain independent values and pin assignments | Simulated interpreter test passes |
| Single-wheel mask, every wheel | Exactly one nonzero requested STEP output, independent of kinematic projection | Unit/isolated ROS checks |
| Read-only configured pin modes | Accidental input/alternate-function configuration | All configured STEP/DIR pins were outputs, no pulls, in the prior read-only snapshot |
| Owner observes each wheel under identical test settings | Real per-channel motor operation | Latest report: BR only; not passed |
| Same physical wheel versus last software update | Channel-dependent fault versus emission-order effect | Human-visible comparison available; no result claimed |
| Signal waveform at each driver terminal | Voltage/current/pulse integrity at the receiver | Not measured |
| 12 V at driver during motion | Supply/cable sag | Not measured |

The preceding automatic review blocked an autonomous physical smoke test without
a detailed reason. It was not rerouted. New control logic is checked with fake
GPIO and browser request interception. No physical driving pass or repaired
four-motor behavior is claimed. Exact component identification and direct
per-wheel/electrical evidence remain required to close this investigation.

## Additional read-only running-system audit

Boot configuration has I2C and built-in audio enabled; no explicit SPI or motor
GPIO remapping overlay was present. `pinctrl` reported GPIO5/6/9/10/11/13/19/22/26
as outputs with no pulls. The daemon snapshot with motors idle reported mode 1,
zero duty and zero active frequency for all four channels. This does not reveal
an alternate-function difference explaining BR-only motion. No boot overlays or
GPIO drive-strength settings were changed. Exact model numbers were requested
from the owner; none had been provided when this report was written.
