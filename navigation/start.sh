#!/bin/bash
set -e
source /opt/ros/jazzy/setup.bash
set -u
mkdir -p /data
python3 /app/configure.py
ros2 launch /app/bringup.launch.py &
launch_pid=$!
shutdown() {
  trap - TERM INT
  python3 /app/shutdown_save.py || true
  kill -TERM "$launch_pid" 2>/dev/null || true
  # Non-interactive background jobs may inherit ignored SIGINT. Bound teardown
  # after the completed snapshot instead of waiting for Docker's force-kill.
  for attempt in 1 2 3 4 5 6 7 8 9 10; do
    if ! kill -0 "$launch_pid" 2>/dev/null; then
      wait "$launch_pid" || true
      exit 0
    fi
    sleep 0.5
  done
  kill -KILL "$launch_pid" 2>/dev/null || true
  wait "$launch_pid" || true
  exit 0
}
trap shutdown TERM INT
wait "$launch_pid"
