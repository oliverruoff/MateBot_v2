# Verification — 2026-11-15

Runtime directory: `/home/matebot/develop/matebot-navigation`, host `matebot.local`.
Original software, its modified files and logs remain intact. Pre-change archives
are stored under `/home/matebot/backups/`. No credentials or floor-plan data are
included in the source repository.

## Unified cockpit and real drive investigation (2026-11-16, follow-up)

- One responsive cockpit now contains the house map, live camera, joystick and
  strafe buttons. Root and `/drive` show the same UI. Map taps select goals by
  default; panning is an explicit toggle. Raster keepouts are edited in the same
  map, and saving, backups, favorites and settings live in the menu.
- Navigation starts after pressing Losfahren, rather than when previewing a
  target. Manual input automatically returns from navigation to mapping, without
  requiring another view or mode selection.
- A real browser-held joystick test reproduced a 470-ms IMU delay, followed by a
  misleading expired-control error. Manual driving without keepouts now tolerates
  up to 800 ms of IMU scheduling delay; navigation/keepouts retain 400 ms. LiDAR,
  command and lease watchdogs remain unchanged. Errors preserve the sensor stop
  reason. Motor acceleration is gentler (0.04 m/s², 0.15 rad/s²).
- After correction, a real three-second held joystick produced 37 finite waves,
  zero DMA underruns and no unexpected stop or expired-control message. Release
  stopped output. This validates continuous command delivery, not wheel travel.
- Physical travel remains UNVERIFIED / FAULTY: several bounded forward, rotation,
  standalone finite-wave and standalone PWM tests produced little reliable motion.
  A nominal 4-cm/s three-second forward command changed the matched scan by only
  about 4 mm, despite all four STEP outputs receiving pulses. Supply, loaded motor
  behavior and mechanical condition cannot be confirmed from GPIO telemetry.
  Do not equate integrated commanded steps with real chassis travel.
- A real map tap and 358° arrival heading started NavigateToPose from the mobile
  popup, with live camera throughout. Reported distance decreased from 0.74 m to
  approximately 0.57 m; the test was explicitly stopped. This is NOT a validated
  physical arrival. Full physical navigation remains open pending the drive fault.
- Validation: 35 Python unit tests, four Node math tests and 15 isolated ROS
  safety checks pass. The new ROS cases cover tolerated manual IMU scheduling
  delay, genuine IMU timeout reporting and unchanged navigation IMU limits.
  Mobile layout, direct goal selection, heading, start, STOP, zones and menu were
  checked against the actual robot. Private scans, camera frames and traces stay
  outside the repository.

## Point-and-click arrival pose and live mission popup (2026-11-16)

- Map tap selects a target; map drag also sets arrival yaw. The modal permits
  dragging its direction arrow and fine adjustment with a degree slider. It shows
  robot footprint, clearance, live camera, navigation startup, remaining route
  distance, arrival/failure state, and STOP. Closing cancels preparation/running
  motion. Position and yaw persist together in favorites; old favorites remain valid.
- `/api/goal-preview` is read-only and validates the entire oriented footprint,
  known map cells, current scan obstacles (only with a known pose), keepouts,
  and the 6-cm position tolerance. The UI shows the robot and clearance envelope. The goal endpoint revalidates at start.
- Arrival yaw reaches the actual NavigateToPose quaternion. Readiness requires
  active bt_navigator AND collision_monitor, not merely an advertised action server.
  An isolated test reproduced inactive action-server rejection before this check.
- Wave allocations now use two equal padded DMA slots (wave_create_and_pad(50)),
  with exclusive startup cleanup. A 60-second resource-only hardware check, with
  STEP outputs held low, completed 751 waves without allocation exhaustion. A
  short real pulse-timing check passed. Two earlier long pulse checks were aborted
  by the disabled-enable invariant; do not count them as passing timing tests.
- Latest map->odom correction is composed with current odometry; a historical
  correction stamp no longer selects historical robot odometry or creates a false
  stale-position stop. A ROS regression test checks a 10-second-old correction.
- Local Nav2 footprint uses the padded rectangle and ObstacleFootprint critic;
  angular sampling includes zero. Bridge and footprint margins are aligned. Final
  xy/yaw tolerances are 6 cm / 0.12 rad; planner tolerance is 5 cm. A directional
  obstacle block preserves the navigation lease rather than producing expired-session
  cascades, and the mission panel explains the blockage.
- Full Nav2 closed-loop test on isolated ROS domain 146, with simulated odometry,
  scans, and no GPIO: actual production stack reached (0.35,0,1.0 rad) with final
  position error 5.5 cm, yaw error 0.116 rad, action status 4 and 230 nonzero commands.
- Browser mock-robot test verifies map-drag heading, delayed arrival clearance check,
  degree adjustment (359 degrees transmitted exactly), and camera remaining in the
  mobile mission modal. No real robot movement was commanded on the resumed day.
- Last bounded physical test before the pause reached about 9 cm of its target but
  did not finish yaw because the obstacle guard blocked final motion. This is NOT
  a passing physical arrival test. On resumption automatic localization remained
  uncertain with competing map matches; physical validation is pending position
  clarification. No weak scan match was promoted to a confident position.

## Smooth motion and heading-up map (latest)

- Replaced 80-ms waves launched on a 50-ms ROS timer (inherently leaving gaps)
  with synchronized one-shot DMA successors, maximum two finite waves outstanding.
  A separate 20-ms motor thread keeps ROS callbacks out of the timing path.
- Actual GPIO timing measured with robot service stopped and motor ENABLE forced
  inactive by a wrapper: 1502 edges at 1000 Hz, minimum/maximum edge intervals
  994/1005 microseconds, zero underruns, motor power stayed disabled. This is a
  real DMA timing measurement, not a physical floor-drive validation.
- Removed always-running Nav2 stack from mapping bringup. Before change load average
  was about 9 on the four-core Pi, with many unnecessary Nav2 processes consuming
  CPU. Nav2 now starts only in calibrated navigation mode and stops on manual mode.
- Nominal manual default 6 cm/s, slider 2–12 cm/s; yaw limit 0.4 rad/s. Actual distance
  per step remains subject to the existing hardware calibration.
- Manual control without keepout cells no longer requires global SLAM localization;
  sensor/obstacle checks remain. Keepouts and autonomous navigation still require pose.
- Ownership lasts 2.5 s; movement watchdog remains separate at 500 ms. State polling
  runs independently of map download; a failed heartbeat cannot invalidate recently
  accepted drive packets. On the actual Pi with browser video running, 70 zero-speed
  packets including a deliberate 1.4-s network gap retained one owner; median/max
  HTTP latency 30/56 ms. No motion was commanded by this connection check.
- Heading-up map rotates map tiles, grid, keepouts and pose consistently; inverse
  coordinates preserve editing/panning. Four Node tests include forward-up and inverse
  transforms for multiple headings. 27 Python tests and 11 ROS fake-GPIO checks pass.

## Manual control interruption fix

- Live stationary sampling reproduced a sporadic self return at body (0.236,-0.012)
  that alternated between absent and present and blocked forward/CCW motion.
  Other nearby points were around (-0.14,0.35). The self-filter padding now covers
  this chassis return (4 cm); generated Nav2 radius encloses the padded rectangle.
- Manual obstacle rejection returns a directional warning and zero motor output,
  preserving ownership. The tick-time guard behaves the same way in mapping mode.
  Real obstacles remain blocked, while retreat works with the same token.
- Accepted manual packets refresh ownership. The UI coalesces moving requests,
  gives zero commands immediate priority, and ignores errors from superseded owners.
- Nine isolated ROS/fake-GPIO tests pass, including the observed self return,
  real-obstacle blocking, retreat without rearming, and continued ownership from
  manual packets alone followed by a real timeout when packets stop.

## Direct driving, live map and automatic localization (update)

- Manual pulse limiting is disabled in configuration. Six isolated ROS tests with
  fake GPIO pass, including continuous held input beyond 160 pulses, explicit
  stop/restart with a new gesture, owner timeout and no-go checks. No physical
  movement was commanded for this update.
- The touch UI acquires its lease on a drive gesture, without a release/presence
  dialog. A separate localhost fake robot verified forward/strafe, zero on release,
  STOP and the next gesture starting again without confirmation. Background/stale
  video and missing sensor data still stop the output; held input never restarts
  itself after a stop. The autonomous goal mode retains the existing floor checks.
- The mobile panel contains the actual map canvas, including known free area,
  walls, keepout cells, pose and scan overlay. It uses the existing `/api/map`
  version polling, not a separate front-facing radar. Full-map fit, pan and zoom
  are available; the same canvas returns to the large map editor.
- Global localization searches free map positions and all headings against a
  Gaussian wall field, rejects ray collisions/low coverage and competing poses,
  then requires three consistent scans before deserializing the saved posegraph.
  On the actual Pi after service restart: automatically localized, score 0.827,
  competing-hypothesis margin 0.332, position subsequently about (0.004,-0.003),
  yaw 0.002 rad, fresh pose, manual readiness clear, motor lease inactive.
- Synthetic localization tests cover a moved/rotated robot with a deliberately
  incorrect prior and a rotated map origin, ambiguous symmetric room rejection,
  and missing/unrelated scans. The old pose alone is never treated as localization.
- 25 Python tests pass both locally and on the Pi; three Node tests and JavaScript
  syntax checks pass. Updated responsive layout checked at 390 × 844, 375 × 667
  and 844 × 390, with a larger live-map panel and working map-editor switch.
- Before deployment a private data/config archive was saved on the Pi at
  `/home/matebot/backups/navigation-before-direct-controls.tar.gz`.

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
