#!/bin/bash
cd /home/matebot/develop/MateBot_v2
source venv/bin/activate
export PYTHONUNBUFFERED=1
nohup python main.py > app.log 2>&1 &
echo $! > server.pid
