# Verification — 2026-11-15

Runtime directory: `/home/matebot/develop/matebot-navigation`, host `matebot.local`.
Original software, its modified files and logs remain intact. Pre-change archives
are stored under `/home/matebot/backups/`. No credentials or floor-plan data are
included in the source repository.

## Mobile cockpit and live camera

- Actual OV5647 stream verified through the same-origin `/api/camera/frame.jpg`:
  JPEG responses 200, changing sequences 118/121/124, frame ages 30/33/8 ms.
  Images are upright with rotation 180; 640 × 360, target 12 FPS, browser 8–10 FPS.
- `matebot-camera.service` is enabled and active, listening only on 127.0.0.1:8082.
  The navigation service was restarted successfully and remains stopped/unarmed.
- Chrome responsive checks: 390 × 844, 375 × 667 and 844 × 390. Portrait controls
  fit within the viewport without horizontal overflow; landscape uses side-by-side
  radar and video. Returning to the map restores a valid canvas size.
- Touch events tested against a separate localhost fake robot, with no GPIO/ROS
  connection: joystick generates positive forward velocity, side buttons generate
  positive/negative lateral velocity with zero yaw, release sends zero. Camera
  pause stops the fake robot and disables controls. No physical driving was performed.
- 21 Python unit tests pass, including fresh/stale frame handling and HTTP proxy
  failure behavior. Three Node tests verify joystick signs/deadzone, bounded
  combined translation and front-aligned scan projection. JavaScript syntax passes.

## Physical observations with the owner present

- Pi 4 Model B Rev 1.1, 4 GB, Debian 13 64-bit, USB SanDisk system drive.
- CSI OV5647 detected; CP2102 serial bridge and MPU6050 WHO_AM_I 0x68 detected.
- LD19 capture: 757 valid packets / 9084 points with no CRC errors in the sample.
- Dimensions supplied by owner: length 41 cm, width 30 cm, wheelbase 31 cm,
  track width 21 cm; lidar centered at 14 cm height.
- A known front box produced a new cluster at scan +88..94° (median +91°),
  median range 0.507 m, about 2.79 m nearer than baseline. With yaw -pi/2 the
  measured box was approximately x=0.499 m, y=0.013 m in robot coordinates.
- Raised-wheel tests sent 960 pulses at 1200 Hz in ten finite 80 ms trains.
  Owner observed backward drive for FL/BL and forward drive for FR/BR. Software
  signs are [-1,1,-1,1]. FL and BL were retested with corrected signs and the
  owner confirmed forward drive. All individual directions are confirmed.
- Front/rear photos show mirrored roller pairs. The actual lateral drive and
  rotation behavior on the floor have not yet been verified.

## Software / stationary hardware checks

- 18 local tests pass: serial CRC/reassembly, mecanum math, bounded waves,
  one-wheel pulse isolation, API guards, raster persistence/resampling, fixed
  world coordinates, footprint checks, control leases and archive validation.
- Same suite passes inside the Pi container. Python compilation and JS syntax
  checks pass. The tests do not instantiate a physical motor controller.
- Five ROS-class safety tests pass with **fake GPIO only** in isolated domain 143:
  self returns remain NaN, expired owner stops output, unverified navigation is
  locked, no-go edits cancel control and overlay the planner map, first-floor
  commands cannot exceed the pulse budget. Late manual sequence numbers cannot
  restart movement after a newer zero command.
- Actual Nav2 planner tested in a separate domain 144 and separate container:
  synthetic wall with doorway, goal behind wall. A 100-pose path detoured to
  y≈1.955 m through the opening. Raster zones then closed the doorway; the
  planner rejected the route. **No motor controller was started in this test.**
- Live hardware scan/IMU data and map/odom/base_link/laser transforms present.
  Nominal chassis returns are filtered with a 3 cm measurement allowance;
  filtered rays remain unknown, never free space. The Nav2 footprint encloses
  the padded outline. No movement was used to tune this filter.
- Root/raw SLAM map and navigation no-go overlay are separate. The local and
  global costmaps include the static layer; raw map data is not overwritten by
  no-go annotations.
- New-map reset works, archives old test maps and starts a fresh map at the
  stationary robot. Manual save writes graph/data, exact occupancy JSON, PGM/YAML,
  session, pose, and checksums. Automatic snapshots observed on the real Pi.
- Backup downloaded through the API and restored into a temporary directory on
  the Pi. No-go cell and favorite survived and all manifest checksums matched.
- Full **Raspberry Pi reboot** tested, not only container restart. The application
  returned automatically with the same map ID, marked raster cell, favorite and
  mode. A shutdown snapshot was present. Motors remained stopped; position
  confirmation and a new control lease were required.
- systemd, Docker and pigpiod enabled; stable USB device ID used. Legacy robot
  and watchdog units remain disabled. All post-test STEP GPIOs read low, ENA high,
  wave engine idle.
- Browser checks: actual saved map renders, mode switching works, a 35-cell red
  rectangle could be painted and erased, both operations reported durable save.

## Important limits / status for the owner

No floor driving was performed while the owner was away. Translation scale,
actual lateral motion, IMU yaw sign and stopping behavior still need supervised
floor checks. The UI supports manual commissioning at low speed with bounded
initial pulses. After personally performing tests, the owner can record the four
checks in the UI; point-to-click driving remains locked until all are confirmed.

No confirmed encoders: translation odometry estimates commanded steps and does
not measure slip. No confirmed cliff sensors: physically isolate stairs. Digital
keepout cells depend on localization and do not constitute cliff protection.
There is no claim that the robot has autonomously navigated a real house.

UI, data persistence and planner behavior are tested; real manual/automatic
driving, dynamic obstacle avoidance, emergency stopping distance and localization
under slip require commissioning on this chassis. Hard power loss can discard
the last not-yet-completed snapshot and cannot guarantee filesystem/hardware health.
