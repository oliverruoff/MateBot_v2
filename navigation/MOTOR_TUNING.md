# User-adjustable motor experiments

The mobile and desktop `/motors` page provides paired numeric/range inputs for
target frequency, acceleration, duty cycle, enable delay, startup frequency and
startup duration. It includes old-V2 ramp presets, live camera, actual selected
per-wheel PWM bins, gyro heading change and six held direction buttons.
The historical presets do not certify that the robot now moves correctly.

Draft and explicitly applied normal-driving profiles persist atomically in
`/data/motor-profiles.json`, separately from maps and annotations. Saving a draft
does not change normal driving. Applying a profile stops movement, replaces the
normal motor configuration and preserves it for restart. Existing normal body
velocity limits still apply. The duty cycle changes pulse width, not the motor
phase current configured on the physical driver.

Opening the page, selecting a preset, saving and applying never start motion.
An explicit held direction starts a test for at most the selected duration,
including startup. A valid motion lease is required at the point of starting;
a delayed request after release cannot reactivate motors. Release, STOP, page
exit, loss of refresh, duration expiry and the existing sensor/obstacle/zone
guards stop output. Refresh cannot extend a test's fixed deadline. Native enable
waiting is nonblocking, retaining STOP and watchdog handling during the wait.
Temporary tests have a separate owned PWM script/checkpoint and restore the
normal driver when stopped. They do not confirm motion calibration or arrival.

Validation: 52 Python tests, 4 JavaScript tests and 19 isolated ROS checks.
Covered cases include invalid profiles, draft/active reload isolation, stale
lease rejection after STOP, duration versus refresh, missing refresh, manual/test
exclusion, restoration, profile application without movement, custom duty and
STOP/watchdog during enable waiting.

Browser checks at 390px and 1280px cover presets, paired inputs, held/released
tests, draft isolation, applying a profile, layout overflow and JavaScript errors.
All motion and profile POSTs were intercepted with simulated responses. The live
camera was fetched successfully through the real read-only endpoint.

An attempted physical low-rate smoke test was blocked by automatic approval
review without a detailed reason. It did not execute and was not rerouted.
No physical motor-test pass is claimed for the new interface.
