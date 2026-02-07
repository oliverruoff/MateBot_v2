import os
import json
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List

import config
from src.utils.shared_mem import MapSharedMemory

app = FastAPI()

# Queues will be injected at startup
queue_motors = None
queue_command = None

class POI(BaseModel):
    id: str = ""
    name: str
    x: float = 0.0
    y: float = 0.0
    theta: float = 0.0

@app.get("/api/poi", response_model=List[POI])
async def get_pois():
    if os.path.exists(config.LOCATIONS_FILE):
        with open(config.LOCATIONS_FILE, "r") as f:
            data = json.load(f)
            return data.get("locations", [])
    return []

@app.post("/api/poi")
async def save_poi(poi: POI):
    pois = await get_pois()
    poi.id = f"loc_{len(pois)+1:03d}"
    pois.append(poi)
    with open(config.LOCATIONS_FILE, "w") as f:
        json.dump({"locations": [p.dict() for p in pois]}, f, indent=2)
    return {"status": "ok", "id": poi.id}

@app.post("/api/navigate")
async def navigate(target: dict):
    # Send command to Process B
    if queue_command:
        queue_command.put({"action": "navigate", "target_id": target.get("target_id")})
    return {"status": "ok"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    shm_map = MapSharedMemory(create=False)
    try:
        while True:
            data = await websocket.receive_json()
            if "joystick" in data:
                # { "joystick": { "vx": 0.1, "vy": 0.0, "omega": 0.0 } }
                j = data["joystick"]
                if queue_motors:
                    queue_motors.put((j.get("vx", 0), j.get("vy", 0), j.get("omega", 0)))
            
            # Send back map data periodically (or based on request)
            # In a real app, you might want a separate loop for this
            if data.get("request") == "map":
                map_array = shm_map.get_map()
                # Sending as binary
                await websocket.send_bytes(map_array.tobytes())
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WS Error: {e}")
    finally:
        shm_map.close()

# Static files
# Serve the UI at `/` from web/static/html, and assets from `/static/...`
base_static_dir = os.path.join(os.path.dirname(__file__), "static")
html_dir = os.path.join(base_static_dir, "html")
app.mount("/static", StaticFiles(directory=base_static_dir, html=False), name="static")
app.mount("/", StaticFiles(directory=html_dir, html=True), name="html")

def run_server(q_motors, q_command):
    global queue_motors, queue_command
    queue_motors = q_motors
    queue_command = q_command
    uvicorn.run(app, host="0.0.0.0", port=8000)
