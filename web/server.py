import os
import json
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
from contextlib import asynccontextmanager

import config
from src.utils.shared_mem import MapSharedMemory

# Global reference for queues
QUEUES = {"motors": None, "command": None}

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(lifespan=lifespan)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    shm_map = MapSharedMemory(create=False)
    print("WS DEBUG: Client Connected")
    try:
        while True:
            data = await websocket.receive_json()
            # print(f"WS DEBUG: Received {data}") # Too noisy if map request is frequent
            
            if "joystick" in data:
                j = data["joystick"]
                vx, vy, omega = j.get("vx", 0), j.get("vy", 0), j.get("omega", 0)
                print(f"WS DEBUG: Joystick vx={vx}, omega={omega}")
                if QUEUES["motors"]:
                    QUEUES["motors"].put((vx, vy, omega))
            
            if data.get("request") == "map":
                map_array = shm_map.get_map()
                await websocket.send_bytes(map_array.tobytes())
    except WebSocketDisconnect:
        print("WS DEBUG: Client Disconnected")
    except Exception as e:
        print(f"WS DEBUG: Error {e}")
    finally:
        shm_map.close()

# Static files
base_static_dir = os.path.join(os.path.dirname(__file__), "static")
html_dir = os.path.join(base_static_dir, "html")
app.mount("/static", StaticFiles(directory=base_static_dir, html=False), name="static")
app.mount("/", StaticFiles(directory=html_dir, html=True), name="html")

def run_server(q_motors, q_command):
    QUEUES["motors"] = q_motors
    QUEUES["command"] = q_command
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
