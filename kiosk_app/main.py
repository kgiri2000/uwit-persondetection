import asyncio
import base64
import json
import uuid
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from detection_engine import DetectionEngine

# Load environment variables
load_dotenv()

PORTAL_PASSWORD = os.getenv("PORTAL_PASSWORD", "UWIT2026")
DETECTION_WIDTH = int(os.getenv("DETECTION_WIDTH", "400"))
DETECTION_HEIGHT = int(os.getenv("DETECTION_HEIGHT", "300"))
YOLO_IMGSZ = int(os.getenv("YOLO_IMGSZ", "320"))

app = FastAPI(title="UWIT Person Detection & Intercom Kiosk")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve the frontend
@app.get("/")
async def get_index():
    return FileResponse("static/index.html")

# Serve configuration (detection resolution)
@app.get("/api/config")
async def get_config():
    return {
        "detectionWidth": DETECTION_WIDTH,
        "detectionHeight": DETECTION_HEIGHT
    }

# Password validation schema
class PasswordVerifyRequest(BaseModel):
    password: str

@app.post("/api/verify-password")
async def verify_password(req: PasswordVerifyRequest):
    is_valid = (req.password == PORTAL_PASSWORD)
    return {"valid": is_valid}

# Connection manager for WebRTC signaling
class ConnectionManager:
    def __init__(self):
        # {peer_id: {"websocket": ws, "role": role, "name": name}}
        self.active_connections = {}
        self.host_peer_ids = set()

    async def connect(self, websocket: WebSocket, peer_id: str, role: str, name: str):
        await websocket.accept()
        
        assigned_role = role
        if role == "host":
            if len(self.host_peer_ids) >= 2:
                assigned_role = "guest"
                print(f"Host limit (2) reached. Forcing peer {peer_id} to guest.")
            else:
                self.host_peer_ids.add(peer_id)
                print(f"Peer {peer_id} registered as Host. Current hosts: {self.host_peer_ids}")
        else:
            print(f"Peer {peer_id} registered as Guest ({name}).")
                
        self.active_connections[peer_id] = {
            "websocket": websocket,
            "role": assigned_role,
            "name": name
        }
        return assigned_role

    def disconnect(self, peer_id: str):
        if peer_id in self.active_connections:
            if peer_id in self.host_peer_ids:
                self.host_peer_ids.remove(peer_id)
                print(f"Host {peer_id} disconnected. Remaining hosts: {self.host_peer_ids}")
            else:
                print(f"Guest {peer_id} disconnected.")
            del self.active_connections[peer_id]

    async def send_personal_message(self, message: dict, peer_id: str):
        if peer_id in self.active_connections:
            ws = self.active_connections[peer_id]["websocket"]
            try:
                await ws.send_text(json.dumps(message))
            except Exception as e:
                print(f"Error sending message to peer {peer_id}: {e}")
                self.disconnect(peer_id)

    async def broadcast(self, message: dict, exclude_id: str = None):
        payload = json.dumps(message)
        for pid, conn in list(self.active_connections.items()):
            if exclude_id and pid == exclude_id:
                continue
            try:
                await conn["websocket"].send_text(payload)
            except Exception:
                self.disconnect(pid)

manager = ConnectionManager()
engine = None

@app.on_event("startup")
def startup_event():
    global engine
    engine = DetectionEngine(
        model_path="yolov8n.pt",
        sound_file="static/notification.wav",
        csv_file="visitor_log.csv",
        imgsz=YOLO_IMGSZ
    )

@app.websocket("/ws/signaling")
async def signaling_endpoint(
    websocket: WebSocket,
    role: str = Query("guest"),
    name: str = Query("Guest")
):
    peer_id = str(uuid.uuid4())
    assigned_role = await manager.connect(websocket, peer_id, role, name)
    
    # 1. Send initial handshake to new peer
    # Tell them their ID, assigned role, and list of existing peers
    active_peers_list = [
        {"peerId": pid, "role": conn["role"], "name": conn["name"]}
        for pid, conn in manager.active_connections.items()
        if pid != peer_id
    ]
    
    await manager.send_personal_message({
        "type": "init",
        "peerId": peer_id,
        "role": assigned_role,
        "activePeers": active_peers_list
    }, peer_id)
    
    # 2. Broadcast to other peers that a new peer joined
    await manager.broadcast({
        "type": "peer-joined",
        "peerId": peer_id,
        "role": assigned_role,
        "name": name
    }, exclude_id=peer_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            target_id = message.get("targetId")
            if not target_id:
                continue
                
            # Forward signaling data (offer, answer, ice-candidate) to target
            # Inject the senderId so target knows who sent it
            message["senderId"] = peer_id
            await manager.send_personal_message(message, target_id)
            
    except WebSocketDisconnect:
        manager.disconnect(peer_id)
        await manager.broadcast({
            "type": "peer-left",
            "peerId": peer_id
        })
    except Exception as e:
        print(f"Error in signaling socket: {e}")
        manager.disconnect(peer_id)
        await manager.broadcast({
            "type": "peer-left",
            "peerId": peer_id
        })

@app.websocket("/ws/detect")
async def detect_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Host detection socket connected.")
    try:
        while True:
            # Receive image frame as bytes
            frame_bytes = await websocket.receive_bytes()
            if not frame_bytes:
                continue
                
            if engine is None:
                continue
                
            # Process the frame
            annotated_bytes, trigger_beep, log_msg = engine.process_frame(frame_bytes)
            
            if annotated_bytes is None:
                continue
                
            # Convert annotated frame to base64
            base64_frame = base64.b64encode(annotated_bytes).decode('utf-8')
            
            # Send results back
            response = {
                "frame": base64_frame,
                "play_beep": trigger_beep,
                "log": log_msg
            }
            await websocket.send_text(json.dumps(response))
            
    except WebSocketDisconnect:
        print("Host detection socket disconnected.")
    except Exception as e:
        print(f"Error in detection socket: {e}")
