# Recovered V2 motor history — 2026-11-17

The user's previously smooth motor control is supported by a historical V2
commit explicitly titled **MILESTONE REACHED: MOTORS WORKING**:
`fb01cce7c2d68ffdb1939f062f45a99e9f1fdd03`, dated 2026-02-01.
Its parent `81d247f` introduced continuous pigpio PWM with ramping.

This history was recovered through the original Pi checkout's reflog. It is
outside the current main history: `c2f6ec4` is a new root containing only the
hardware/spec documents. The last main commit before our November work was
`f6c059a` (2026-02-17). No commit dated approximately one week before November 17
was found in the examined branch histories or Pi reflog.

The recovered original files are preserved without modification:

- [PWM motor driver](../archive/drive-20260201/motors.py)
- [Pin configuration](../archive/drive-20260201/config.toml)

Their Git blob hashes match the historical commit. They are reference files,
not imported by the current navigation service. The recovered history and
stashes are also backed up in a private Git bundle both on the Pi and locally;
private maps, recordings and this bundle are not published to this repository.

## Differences from the recent driver

The February 1 driver uses continuous 50% pigpio PWM and a background ramp of
400 Hz every 20 ms, nominal target 8000 Hz. Its UI maps a delay to
`1 / (2 * delay)`; for example, the option labelled 2000 Hz with delay 0.0005
actually requests 1000 Hz. Forward GPIO directions are [0,1,0,1], matching our
current body-forward calibration. Enable is active-low and held on at startup.
The surviving `impl-from-spec` branch also has the 400 Hz / 20 ms ramp.

The later February 17 main driver differs: it starts a wheel, sleeps, then starts
the next while earlier wheels continue running. Its UI forward sets all four DIR
pins high, which currently produces turning rather than body-forward travel.
A whole-application rollback would therefore also alter wheel semantics.

## Physical comparison on November 17

The navigation service was stopped for each isolated probe. The original
February 1 module was executed unchanged against GPIO, with independent raw
MPU6050 gyro and LD19 scan capture, explicit STOP and an independent bounded
watchdog. Initialization required the old environment's TOML dependency; an
initial missing-dependency probe was terminated before any motion trial and
outputs were explicitly cleared before retrying.

- Original 400 Hz / 20 ms ramp to 8000 Hz: no substantial translation in either
  direction in short 0.45-second trials, despite actual 8000 Hz / 50% outputs.
- Original selectable rates: 500 Hz for 3 seconds and 1000 Hz for 2 seconds did
  not establish meaningful forward translation; 2000 Hz backward for 1 second
  produced about 11 mm backward with roughly 3 degrees unwanted yaw.
- February 17 main driver with body-forward directions: approximately 33 mm
  forward over two sequential-start batches, with about 1.3 degrees yaw.
- Separate startup experiment at 1000 Hz: starting wheels 258 ms apart did not
  establish sustained travel once all four outputs were running. Scan samples
  before and after the all-wheel phase showed little additional translation.

Scan matching has centimeter-scale residuals; millimeter estimates near zero
are not evidence of precise travel. These comparisons do not prove a hardware
fault or that the historical robot never drove properly. They do show that
restoring this recovered PWM/ramp implementation alone has not reproduced its
reported smooth movement on the current robot.

No historical driver was made active permanently. Production remains the
100 Hz crawling baseline with its original safety guards. Normal-speed motion
and autonomous arrival remain unverified. Robot stopped; navigation and camera
services restored after tests.
